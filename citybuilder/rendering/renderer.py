"""wgpu renderer for Pixel City Builder.

Pipeline (M1):
  1. Draw the 3D scene (terrain chunks, road ribbons, buildings) into a
     low-res offscreen target with a depth buffer.
  2. Nearest-neighbor upscale to the window.
  3. In-engine debug overlay (FPS, tick time, counters) in screen space.

Later passes add: depth/normal outlines, lighting/shadow, palette quantization
(post), dithering, pixel-grid camera snapping. Instancing keeps GPU calls low.
"""

from __future__ import annotations
import struct
import zlib

import numpy as np
import wgpu

from .. import config
from .debug_overlay import DebugOverlay
from ..world.chunks import build_chunk_mesh

# One uniform block: view + projection matrices (2 x mat4x4 = 32 floats).
_UNIFORM_FLOATS = 32
_UNIFORM_BYTES = _UNIFORM_FLOATS * 4

USAGE = (wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.TEXTURE_BINDING
         | wgpu.TextureUsage.COPY_SRC)

UNIFORMS_VS_BLOCK = """
struct Uniforms {
    view: mat4x4<f32>,
    proj: mat4x4<f32>,
};
@group(0) @binding(0) var<uniform> uniforms: Uniforms;
"""

VERTEX_COLOR_VS = """
struct VertexOutput {
    @builtin(position) position: vec4f,
    @location(0) color: vec4f,
};
@vertex
fn vs_main(@location(0) pos: vec3f,
           @location(1) color: vec4f) -> VertexOutput {
    var world = vec4f(pos, 1.0);
    var clip = uniforms.proj * uniforms.view * world;
    var output: VertexOutput;
    output.position = clip;
    output.color = color;
    return output;
}
"""

VERTEX_COLOR_FS = """
struct FragmentOutput {
    @location(0) color: vec4f,
};
@fragment
fn fs_main(@location(0) color: vec4f) -> FragmentOutput {
    var levels = 4.0;
    var quantized = floor(color.rgb * levels) / levels;
    var output: FragmentOutput;
    output.color = vec4f(quantized, color.a);
    return output;
}
"""

BUILDING_VS = """
struct VertexOutput {
    @builtin(position) position: vec4f,
    @location(0) color: vec4f,
    @location(1) uv: vec2f,
};
@vertex
fn vs_main(@location(0) pos: vec3f,
           @location(1) normal: vec3f,
           @location(2) uv: vec2f,
           @location(3) color: vec4f) -> VertexOutput {
    var world = vec4f(pos, 1.0);
    var clip = uniforms.proj * uniforms.view * world;
    var output: VertexOutput;
    output.position = clip;
    output.color = color;
    output.uv = uv;
    return output;
}
"""

BUILDING_FS = """
@group(1) @binding(0) var tex_sampler: sampler;
@group(1) @binding(1) var tex_array: texture_2d_array<f32>;
struct FragmentOutput {
    @location(0) color: vec4f,
};
@fragment
fn fs_main(@location(0) color: vec4f,
           @location(1) uv: vec2f) -> FragmentOutput {
    var texel = textureSample(tex_array, tex_sampler, uv, 0);
    var levels = 4.0;
    var quantized = floor(texel.rgb * levels) / levels;
    var output: FragmentOutput;
    output.color = vec4f(quantized * color.rgb, color.a * texel.a);
    return output;
}
"""


UPSCALE_VS = """
struct VertexOutput {
    @builtin(position) position: vec4f,
    @location(0) uv: vec2f,
};
@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    var xy = array<vec2f, 4>(vec2f(-1.0, -1.0), vec2f(1.0, -1.0), vec2f(-1.0, 1.0), vec2f(1.0, 1.0));
    var uv = array<vec2f, 4>(vec2f(0.0, 0.0), vec2f(1.0, 0.0), vec2f(0.0, 1.0), vec2f(1.0, 1.0));
    var output: VertexOutput;
    output.position = vec4f(xy[vertex_index], 0.0, 1.0);
    output.uv = uv[vertex_index];
    return output;
}
"""

UPSCALE_FS = """
@group(0) @binding(0) var scene_sampler: sampler;
@group(0) @binding(1) var scene_texture: texture_2d<f32>;
struct FragmentOutput {
    @location(0) color: vec4f,
};
@fragment
fn fs_main(@location(0) uv: vec2f) -> FragmentOutput {
    var color = textureSample(scene_texture, scene_sampler, uv);
    var output: FragmentOutput;
    output.color = color;
    return output;
}
"""

# ---------------------------------------------------------------------------
# Vertex buffer layouts
# ---------------------------------------------------------------------------

POS_COLOR_LAYOUT = {
    "attributes": [
        {"format": "float32x3", "offset": 0,  "shader_location": 0},  # pos
        {"format": "float32x4", "offset": 12, "shader_location": 1},  # color
    ],
    "array_stride": 28,
    "step_mode": "vertex",
}

BUILDING_VERTEX_LAYOUT = {
    "attributes": [
        {"format": "float32x3", "offset": 0,  "shader_location": 0},  # pos
        {"format": "float32x3", "offset": 12, "shader_location": 1},  # normal
        {"format": "float32x2", "offset": 24, "shader_location": 2},  # uv
        {"format": "float32x4", "offset": 32, "shader_location": 3},  # color
    ],
    "array_stride": 48,
    "step_mode": "vertex",
}




# ---------------------------------------------------------------------------
# Scene geometry helpers

def _write_png(path: str, rgba: np.ndarray) -> None:
    """Write an RGBA uint8 (H, W, 4) array as a PNG using only the stdlib."""
    h, w = rgba.shape[0], rgba.shape[1]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        c = tag + payload
        return struct.pack(">I", len(payload)) + c + struct.pack(">I", zlib.crc32(c))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    # Filter byte 0 (None) per scanline.
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))

    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------------------
# Scene geometry helpers
# ---------------------------------------------------------------------------

def _height_color(h: np.ndarray) -> np.ndarray:
    """Map height -> RGBA color (low=green, mid=tan, high=gray)."""
    h = np.clip(h, 0.0, 1.0)
    low = np.array([0.2, 0.6, 0.2, 1.0], dtype=np.float32)   # grass
    mid = np.array([0.8, 0.7, 0.4, 1.0], dtype=np.float32)   # dirt
    high = np.array([0.6, 0.6, 0.65, 1.0], dtype=np.float32) # rock
    c = np.empty(h.shape + (4,), dtype=np.float32)
    c[:] = low
    c[h > 0.33] = mid
    c[h > 0.66] = high
    return c


def _segment_ribbon(seg, steps: int = 12, width: float = 6.0):
    """Build a screen-aligned ribbon along a road segment curve."""
    pts = seg.curve.sample(steps)
    verts: list[float] = []
    idx: list[int] = []

    def add(x, y, z, r, g, b, a):
        verts.extend([x, y, z, r, g, b, a])
        return len(verts) // 7 - 1

    base = seg.lanes.width * max(seg.lanes.lane_count, 1)
    half = width if width else base * 0.5
    for i in range(len(pts) - 1):
        p0 = pts[i]
        p1 = pts[i + 1]
        dx = p1[0] - p0[0]
        dz = p1[1] - p0[1]
        n = (dx * dx + dz * dz) ** 0.5
        if n == 0:
            continue
        tx, tz = dx / n, dz / n
        nx, nz = tz, -tx  # normal
        color = (0.5, 0.5, 0.5, 1.0)  # gray road
        # quad: p0-left, p0-right, p1-right, p1-left
        v00 = add(p0[0] - nx * half, 0.0, p0[1] - nz * half, *color)
        v01 = add(p0[0] + nx * half, 0.0, p0[1] + nz * half, *color)
        v11 = add(p1[0] + nx * half, 0.0, p1[1] + nz * half, *color)
        v10 = add(p1[0] - nx * half, 0.0, p1[1] - nz * half, *color)
        idx.extend([v00, v01, v11, v00, v11, v10])
    vertices = np.array(verts, dtype=np.float32).reshape(-1, 7)
    indices = np.array(idx, dtype=np.uint32)
    return vertices, indices


def _building_color(bld) -> np.ndarray:
    """Deterministic per-building color from def key + variant."""
    h = abs(hash((bld.def_key, bld.variant))) % 1000 / 1000.0
    return np.array([0.5 + 0.4 * h, 0.5 + 0.3 * ((h * 7) % 1),
                     0.4 + 0.4 * ((h * 13) % 1), 1.0], dtype=np.float32)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, device, context):
        self.device = device
        self.context = context
        self.internal_w = config.INTERNAL_WIDTH
        self.internal_h = config.INTERNAL_HEIGHT

        self._build_internal_target()
        self._build_uniforms()
        self._load_placeholder_texture_array()
        self._build_pipelines()
        self.debug_overlay = DebugOverlay(self.device)

        self._clear_scene()

    # -- internal low-res target ---------------------------------------------
    def _build_internal_target(self):
        self.internal_texture = self.device.create_texture(
            size=(self.internal_w, self.internal_h, 1),
            format="bgra8unorm",
            usage=USAGE,
        )
        self.internal_view = self.internal_texture.create_view()
        self.depth_texture = self.device.create_texture(
            size=(self.internal_w, self.internal_h, 1),
            format="depth24plus",
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
        )
        self.depth_view = self.depth_texture.create_view()
        self.internal_sampler = self.device.create_sampler(
            mag_filter="nearest",
            min_filter="nearest",
        )

    # -- uniforms (view/proj) -------------------------------------------------
    def _build_uniforms(self):
        self.uniforms_buffer = self.device.create_buffer(
            size=_UNIFORM_BYTES,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )

    def uniforms_bind_group_for(self, pipeline):
        return self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[{"binding": 0,
                      "resource": {"buffer": self.uniforms_buffer,
                                   "offset": 0,
                                   "size": _UNIFORM_BYTES}}])

    def set_view_proj(self, view: np.ndarray, proj: np.ndarray):
        # WGSL mat4x4<f32> is column-major; numpy is row-major. Upload the
        # transpose so the shader reads view/proj as intended (identity is
        # symmetric so this bug was invisible until real camera matrices).
        data = np.ascontiguousarray(
            np.stack([view.T, proj.T]).astype(np.float32).reshape(-1))
        assert data.size == _UNIFORM_FLOATS
        self.device.queue.write_buffer(self.uniforms_buffer, 0, data.tobytes())

    # -- placeholder texture array -------------------------------------------
    def _load_placeholder_texture_array(self):
        from ..world import buildings as bmod
        names = ["asphalt", "brick", "window_grid", "roof", "checker"]
        layers = [bmod.placeholder_texture(name, size=64) for name in names]
        self.tex_names = names
        self.tex_array_size = len(layers)
        data = np.stack(layers).astype(np.uint8)  # (N, 64, 64, 4)
        self.texture_array = self.device.create_texture(
            size=(64, 64, self.tex_array_size),
            format="rgba8unorm",
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.device.queue.write_texture(
            {"texture": self.texture_array},
            data.tobytes(),
            {"bytes_per_row": 64 * 4, "rows_per_image": 64},
            {"width": 64, "height": 64, "depth_or_array_layers": self.tex_array_size},
        )
        self.tex_array_view = self.texture_array.create_view(dimension="2d-array")
        self.tex_sampler = self.device.create_sampler(
            mag_filter="nearest",
            min_filter="nearest",
        )

    # -- pipelines ------------------------------------------------------------
    def _build_pipelines(self):
        device = self.device

        vc = device.create_shader_module(
            code=UNIFORMS_VS_BLOCK + VERTEX_COLOR_VS + VERTEX_COLOR_FS)
        self.terrain_pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": vc, "entry_point": "vs_main",
                    "buffers": [POS_COLOR_LAYOUT]},
            fragment={"module": vc, "entry_point": "fs_main",
                      "targets": [{"format": "bgra8unorm"}]},
            primitive={"topology": "triangle-list"},
            depth_stencil={"format": "depth24plus",
                            "depth_write_enabled": True,
                            "depth_compare": "less"},
        )
        self.road_pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": vc, "entry_point": "vs_main",
                    "buffers": [POS_COLOR_LAYOUT]},
            fragment={"module": vc, "entry_point": "fs_main",
                      "targets": [{"format": "bgra8unorm"}]},
            primitive={"topology": "triangle-list"},
            depth_stencil={"format": "depth24plus",
                            "depth_write_enabled": True,
                            "depth_compare": "less"},
        )

        bs = device.create_shader_module(
            code=UNIFORMS_VS_BLOCK + BUILDING_VS + BUILDING_FS)
        self.building_pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": bs, "entry_point": "vs_main",
                    "buffers": [BUILDING_VERTEX_LAYOUT]},
            fragment={"module": bs, "entry_point": "fs_main",
                      "targets": [{"format": "bgra8unorm"}]},
            primitive={"topology": "triangle-list"},
            depth_stencil={"format": "depth24plus",
                            "depth_write_enabled": True,
                            "depth_compare": "less"},
        )
        # Bind group 1 (texture sampler + texture array) for building pipeline
        self._building_bg1 = self.device.create_bind_group(
            layout=self.building_pipeline.get_bind_group_layout(1),
            entries=[
                {"binding": 0, "resource": self.tex_sampler},
                {"binding": 1, "resource": self.tex_array_view},
            ])

        us = device.create_shader_module(code=UPSCALE_VS + UPSCALE_FS)
        self.upscale_pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": us, "entry_point": "vs_main"},
            fragment={"module": us, "entry_point": "fs_main",
                      "targets": [{"format": "bgra8unorm"}]},
            primitive={"topology": "triangle-strip"},
        )
        self.upscale_bind_group = device.create_bind_group(
            layout=self.upscale_pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": self.internal_sampler},
                {"binding": 1, "resource": self.internal_view},
            ])

    def _uniforms_bind_group_for(self, pipeline):
        return self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[{"binding": 0,
                      "resource": {"buffer": self.uniforms_buffer,
                                   "offset": 0,
                                   "size": _UNIFORM_BYTES}}])

    # -- buffer helpers --------------------------------------------------------
    def _vertex_buffer(self, data: np.ndarray, slot: int = 0):
        data = np.ascontiguousarray(data, dtype=np.float32)
        buf = self.device.create_buffer(
            size=data.nbytes,
            usage=wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST,
        )
        self.device.queue.write_buffer(buf, 0, data.tobytes())
        return buf

    def _index_buffer(self, data: np.ndarray):
        data = np.ascontiguousarray(data, dtype=np.uint32)
        buf = self.device.create_buffer(
            size=data.nbytes,
            usage=wgpu.BufferUsage.INDEX | wgpu.BufferUsage.COPY_DST,
        )
        self.device.queue.write_buffer(buf, 0, data.tobytes())
        return buf

    def _clear_scene(self):
        """Reset all per-scene GPU state so a stale scene can't be drawn."""
        self._gpu_buffers = {}
        self.terrain_count = 0
        self.road_count = 0
        self.building_count = 0
        self.building_index_count = 0

    # -- scene upload ----------------------------------------------------------
    def set_scene(self, chunks, segments, buildings):
        """Upload scene geometry (chunks, road segments, buildings) to GPU."""
        self._clear_scene()
        device = self.device
        gb = self._gpu_buffers

        # Terrain: upload each chunk as an independent static mesh.  Chunks
        # can then be rebuilt or culled independently as streaming evolves;
        # merging them here would make every terrain edit invalidate the whole
        # visible world.
        terrain_chunks = []
        for ch in chunks:
            pos, i = build_chunk_mesh(ch)
            col = _height_color(pos[:, 1])
            v = np.concatenate([pos, col], axis=1)
            ib = np.asarray(i, dtype=np.uint32)
            terrain_chunks.append({
                "cx": ch.cx,
                "cy": ch.cy,
                "vb": self._vertex_buffer(v, slot=0),
                "ib": self._index_buffer(ib),
                "count": int(ib.size),
            })
            self.terrain_count += int(ib.size)
        if terrain_chunks:
            gb["terrain_chunks"] = terrain_chunks

        # Roads: ribbons per segment.
        r_verts, r_idx = [], []
        r_index_offset = 0
        for seg in segments:
            v, i = _segment_ribbon(seg)
            r_verts.append(v)
            r_idx.append(i + r_index_offset)
            r_index_offset += v.shape[0]
        if r_verts:
            r_ib = np.concatenate(r_idx).astype(np.uint32)
            gb["road_vb"] = self._vertex_buffer(np.concatenate(r_verts), slot=0)
            gb["road_ib"] = self._index_buffer(r_ib)
            self.road_count = int(r_ib.size)

        # Buildings: merged into one vertex buffer; per-vertex color baked in.
        # Drawn once (instance_count=1); each building's color is constant over
        # its vertices so the per-building tint survives the merge.
        b_verts, b_idx = [], []
        b_index_offset = 0
        for bld in buildings:
            color = _building_color(bld)
            v = bld.vertices  # (N, 8): x,y,z, nx,ny,nz, u,v
            tint = np.repeat(color[np.newaxis, :], v.shape[0], axis=0)
            b_verts.append(np.concatenate([v, tint], axis=1))
            b_idx.append(bld.indices + b_index_offset)
            b_index_offset += v.shape[0]
        if b_verts:
            b_ib = np.concatenate(b_idx).astype(np.uint32)
            gb["building_vb"] = self._vertex_buffer(
                np.concatenate(b_verts), slot=0)
            gb["building_ib"] = self._index_buffer(b_ib)
            self.building_count = int(b_ib.size)
            self.building_index_count = 1

    # -- frame -----------------------------------------------------------------
    def _scene_pass(self, encoder):
        """Draw terrain, roads and buildings into the low-res internal target."""
        rpass = encoder.begin_render_pass(
            color_attachments=[{
                "view": self.internal_view,
                "clear_value": (0.1, 0.1, 0.15, 1.0),
                "load_op": "clear",
                "store_op": "store",
            }],
            depth_stencil_attachment={
                "view": self.depth_view,
                "depth_clear_value": 1.0,
                "depth_load_op": "clear",
                "depth_store_op": "store",
            })
        for chunk in self._gpu_buffers.get("terrain_chunks", []):
            rpass.set_pipeline(self.terrain_pipeline)
            rpass.set_bind_group(0, self.uniforms_bind_group_for(self.terrain_pipeline))
            rpass.set_vertex_buffer(0, chunk["vb"], 0)
            rpass.set_index_buffer(chunk["ib"],
                                   wgpu.IndexFormat.uint32)
            rpass.draw_indexed(chunk["count"], 1, 0, 0, 0)
        if self.road_count:
            rpass.set_pipeline(self.road_pipeline)
            rpass.set_bind_group(0, self.uniforms_bind_group_for(self.road_pipeline))
            rpass.set_vertex_buffer(0, self._gpu_buffers["road_vb"], 0)
            rpass.set_index_buffer(self._gpu_buffers["road_ib"],
                                   wgpu.IndexFormat.uint32)
            rpass.draw_indexed(self.road_count, 1, 0, 0, 0)
        if self.building_count:
            rpass.set_pipeline(self.building_pipeline)
            rpass.set_bind_group(0, self.uniforms_bind_group_for(self.building_pipeline))
            rpass.set_bind_group(1, self._building_bg1)
            rpass.set_vertex_buffer(0, self._gpu_buffers["building_vb"], 0)
            rpass.set_index_buffer(self._gpu_buffers["building_ib"],
                                   wgpu.IndexFormat.uint32)
            rpass.draw_indexed(self.building_count, 1, 0, 0, 0)
        rpass.end()

    def read_internal(self):
        """Copy the internal low-res target to CPU and return RGBA uint8 (H, W, 4)."""
        w, h = self.internal_w, self.internal_h
        bytes_per_row = w * 4
        staging = self.device.create_buffer(
            size=bytes_per_row * h,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        )
        encoder = self.device.create_command_encoder()
        encoder.copy_texture_to_buffer(
            {"texture": self.internal_texture},
            {"buffer": staging, "bytes_per_row": bytes_per_row, "rows_per_image": h},
            {"width": w, "height": h, "depth_or_array_layers": 1},
        )
        self.device.queue.submit([encoder.finish()])
        staging.map_sync(wgpu.MapMode.READ)
        data = np.asarray(staging.read_mapped(), dtype=np.uint8).reshape(h, w, 4)
        rgba = data[:, :, [2, 1, 0, 3]].copy()
        staging.unmap()
        return rgba

    def capture_frame(self, path: str) -> np.ndarray:
        """Render one scene frame offscreen (no window) and save it as a PNG."""
        encoder = self.device.create_command_encoder()
        self._scene_pass(encoder)
        self.device.queue.submit([encoder.finish()])
        rgba = self.read_internal()
        _write_png(path, rgba)
        return rgba

    def draw(self, view: np.ndarray, proj: np.ndarray,
             debug_lines: list[tuple[str, int, int]] | None = None) -> None:
        """Render one frame: scene -> low-res target -> upscale -> debug overlay."""
        self.set_view_proj(view, proj)
        current_texture = self.context.get_current_texture()
        present_view = current_texture.create_view()
        encoder = self.device.create_command_encoder()

        self._scene_pass(encoder)

        # Pass 2: nearest-neighbor upscale internal -> window.
        rpass = encoder.begin_render_pass(
            color_attachments=[{
                "view": present_view,
                "clear_value": (0.0, 0.0, 0.0, 1.0),
                "load_op": "clear",
                "store_op": "store",
            }])
        rpass.set_pipeline(self.upscale_pipeline)
        rpass.set_bind_group(0, self.upscale_bind_group)
        rpass.draw(4)
        rpass.end()

        # Pass 3: debug overlay in screen space over the upscaled scene.
        if debug_lines:
            self.debug_overlay.clear()
            for text, x, y in debug_lines:
                self.debug_overlay.add(text, x, y)
            self.debug_overlay.draw(encoder, present_view)

        self.device.queue.submit([encoder.finish()])

    def resize(self, width: int, height: int) -> None:
        self.context.configure(device=self.device, format="bgra8unorm")

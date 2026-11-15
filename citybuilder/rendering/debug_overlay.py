"""In-engine debug overlay: text (FPS, tick time, counters) in screen space.
Uses a code-generated 5x7 bitmap font. No external font or ImGui dep."""

from __future__ import annotations

import numpy as np
import wgpu

from .. import config

# Code-generated 5x7 bitmap font: 7 rows of 5 cells (# = pixel).
_FONT_ROWS = {
    ' ': ['.....', '.....', '.....', '.....', '.....', '.....', '.....'],
    '!': ['..#..', '..#..', '..#..', '..#..', '..#..', '.....', '..#..'],
    '#': ['..#..', '..#..', '#####', '..#..', '#####', '..#..', '..#..'],
    '%': ['#...#', '#..#.', '..#..', '.#..#', '.#..#', '.#..#', '#...#'],
    '(': ['.##..', '#...#', '.....', '.....', '.....', '#...#', '.##..'],
    ')': ['.##..', '.....', '.....', '.....', '.....', '#...#', '.##..'],
    '-': ['.....', '.....', '.....', '#####', '.....', '.....', '.....'],
    '.': ['.....', '.....', '.....', '.....', '.....', '..#..', '..#..'],
    '/': ['.....', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '.....'],
    '0': ['.##..', '#...#', '#.#.#', '#.#.#', '#.#.#', '#...#', '.##..'],
    '1': ['..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    '2': ['.###.', '#...#', '....#', '....#', '...#..', '..#.#.', '.####.'],
    '3': ['.###.', '....#', '....#', '.##..', '....#', '#...#', '.###.'],
    '4': ['.....', '#...#', '#...#', '#...#', '#####', '....#', '....#'],
    '5': ['.####', '#....', '#....', '.###.', '....#', '#...#', '.###.'],
    '6': ['.###.', '#....', '#....', '.####', '#...#', '#...#', '.###.'],
    '7': ['#####', '....#', '...#..', '..#..', '.#...', '.#...', '.#...'],
    '8': ['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.'],
    '9': ['.###.', '#...#', '#...#', '.####', '....#', '....#', '.###.'],
    ':': ['.....', '.....', '..#..', '.....', '..#..', '.....', '.....'],
    '=': ['.....', '.....', '.....', '#####', '.....', '.....', '.....'],
    'A': ['..#..', '.#.#.', '#...#', '#####', '#...#', '#...#', '#...#'],
    'B': ['####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.'],
    'C': ['.###.', '#....', '#....', '#....', '#....', '#....', '.###.'],
    'D': ['####.', '#...#', '#...#', '#...#', '#...#', '#...#', '####.'],
    'E': ['#####', '#....', '#....', '###..', '#....', '#....', '#####'],
    'F': ['#####', '#....', '#....', '###..', '#....', '#....', '#....'],
    'G': ['.###.', '#....', '#....', '#.##.', '#...#', '#...#', '.###.'],
    'H': ['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'I': ['.###.', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    'J': ['..###', '...#.', '...#.', '...#.', '#...#', '#...#', '.###.'],
    'K': ['#...#', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
    'M': ['#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '#...#'],
    'N': ['#...#', '##..#', '#.#.#', '#.#.#', '#..##', '#...#', '#...#'],
    'O': ['.##..', '#...#', '#...#', '#...#', '#...#', '#...#', '.##..'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    'R': ['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#'],
    'S': ['.###.', '#....', '#....', '.###.', '....#', '#...#', '.###.'],
    'T': ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'],
    'U': ['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'X': ['#...#', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '#...#'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
    'Z': ['#####', '....#', '...#..', '..#..', '.#...', '#....', '#####'],
    '_': ['.....', '.....', '.....', '.....', '.....', '.....', '#####'],
    'a': ['.....', '.....', '.##..', '#...#', '#####', '#...#', '#...#'],
    'e': ['.....', '.....', '.##..', '#...#', '#####', '#....', '.##..'],
    'f': ['..#..', '..#..', '.##..', '..#..', '..#..', '..#..', '.###.'],
    'n': ['.....', '.....', '#.##.', '#...#', '#...#', '#...#', '#...#'],
    'o': ['.....', '.....', '.##..', '#...#', '#...#', '#...#', '.##..'],
    'r': ['.....', '.....', '#.#..', '#.#..', '#....', '#....', '#....'],
    's': ['.....', '.....', '.###.', '#....', '.###.', '....#', '###..'],
    't': ['.....', '#....', '#....', '.##..', '#....', '#....', '#....'],
    'u': ['.....', '.....', '#...#', '#...#', '#...#', '#...#', '.###.'],
}

CELL_W = 5
CELL_H = 7
CHAR_SPACING = 1
LINE_SPACING = 1

def _glyph_columns(char: str) -> list[int]:
    rows = _FONT_ROWS.get(char, _FONT_ROWS[" "])
    cols: list[int] = []
    for cx in range(CELL_W):
        mask = 0
        for cy in range(CELL_H):
            if rows[cy][cx] == "#":
                mask |= 1 << cy
        cols.append(mask)
    return cols

    return cols


def render_text_to_bitmap(
    lines: list[tuple[str, int, int]],
    cell_w: int = CELL_W,
    cell_h: int = CELL_H,
    char_spacing: int = CHAR_SPACING,
    line_spacing: int = LINE_SPACING,
    max_width: int = 512,
    max_height: int = 128,
) -> np.ndarray:
    """Render queued text lines into a single alpha bitmap (H, W) uint8.

    Each queued line is (text, x_cell, y_cell) in cell coordinates.
    """
    if not lines:
        return np.zeros((8, 8), dtype=np.uint8)

    max_px_w = 0
    total_px_h = 0
    for text, x_cell, y_cell in lines:
        px_w = (x_cell + len(text)) * (cell_w + char_spacing)
        px_h = (y_cell + 1) * (cell_h + line_spacing)
        max_px_w = max(max_px_w, px_w)
        total_px_h = max(total_px_h, px_h)

    width = min(max_px_w, max_width)
    height = min(total_px_h, max_height)
    if width == 0:
        width = 8
    if height == 0:
        height = 8

    bitmap = np.zeros((height, width), dtype=np.uint8)
    for text, x_cell, y_cell in lines:
        ox = x_cell * (cell_w + char_spacing)
        oy = y_cell * (cell_h + line_spacing)
        for ch in text:
            cols = _glyph_columns(ch)
            for cx, mask in enumerate(cols):
                gx = ox + cx
                if gx >= width:
                    break
                for cy in range(cell_h):
                    gy = oy + cy
                    if gy >= height:
                        break
                    if mask & (1 << cy):
                        bitmap[gy, gx] = 255
            ox += cell_w + char_spacing
    return bitmap

    return bitmap


class DebugOverlay:
    """Screen-space text overlay for debug info.

    Queues lines of text, renders them to a bitmap texture, and draws one
    screen-space quad per frame. The texture is only re-uploaded when the
    queued content changes.
    """

    def __init__(self, device, width: int = 512, height: int = 128):
        self.device = device
        self.bitmap_w = width
        self.bitmap_h = height
        self.lines: list[tuple[str, int, int]] = []
        self._last_bitmap_hash: int | None = None
        self._texture = None
        self._view = None
        self._sampler = None
        self._uniforms = None
        self._pipeline = None
        self._bind_group = None
        self._content_w = 1
        self._content_h = 1
        self._build_resources()

    def _build_resources(self):
        device = self.device
        self._texture = device.create_texture(
            size=(self.bitmap_w, self.bitmap_h, 1),
            format="r8unorm",
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self._view = self._texture.create_view()
        self._sampler = device.create_sampler(
            mag_filter="nearest",
            min_filter="nearest",
        )
        self._uniforms = device.create_buffer(
            size=16,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )
        vs = """
struct VertexOutput {
    @builtin(position) position: vec4f,
    @location(0) uv: vec2f,
};
@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    var xy = array<vec2f, 4>(vec2f(0.0, 0.0), vec2f(1.0, 0.0), vec2f(0.0, 1.0), vec2f(1.0, 1.0));
    var uv = array<vec2f, 4>(vec2f(0.0, 0.0), vec2f(1.0, 0.0), vec2f(0.0, 1.0), vec2f(1.0, 1.0));
    var output: VertexOutput;
    output.position = vec4f(xy[vertex_index] * overlay.quad_size * 2.0
                            - vec2f(1.0, 1.0), 0.0, 1.0);
    output.uv = uv[vertex_index] * overlay.uv_scale;
    return output;
}

struct Overlay {
    quad_size: vec2f,
    uv_scale: vec2f,
};
@group(0) @binding(2) var<uniform> overlay: Overlay;
"""
        fs = """
@group(0) @binding(0) var text_sampler: sampler;
@group(0) @binding(1) var text_texture: texture_2d<f32>;
struct FragmentOutput {
    @location(0) color: vec4f,
};
@fragment
fn fs_main(@location(0) uv: vec2f) -> FragmentOutput {
    var alpha = textureSample(text_texture, text_sampler, uv).r;
    var color = vec4f(0.0, 1.0, 0.0, 1.0);
    color.a = alpha;
    if (alpha < 0.1) {
        discard;
    }
    var output: FragmentOutput;
    output.color = color;
    return output;
}
"""
        shader = device.create_shader_module(code=vs + "\n" + fs)
        self._pipeline = device.create_render_pipeline(
            layout="auto",
            vertex={"module": shader, "entry_point": "vs_main"},
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": "bgra8unorm"}],
            },
            primitive={"topology": "triangle-strip"},
        )
        self._bind_group = device.create_bind_group(
            layout=self._pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": self._sampler},
                {"binding": 1, "resource": self._view},
                {"binding": 2, "resource": {"buffer": self._uniforms}},
            ],
        )

    def clear(self):
        self.lines = []

    def add(self, text: str, x_cell: int = 0, y_cell: int = 0):
        self.lines.append((text, x_cell, y_cell))

    def _upload(self, bitmap: np.ndarray):
        h, w = bitmap.shape
        if w > self.bitmap_w or h > self.bitmap_h:
            self.bitmap_w = max(self.bitmap_w, w)
            self.bitmap_h = max(self.bitmap_h, h)
            self._build_resources()
        self._content_w = w
        self._content_h = h
        self.device.queue.write_texture(
            {"texture": self._texture},
            bitmap.tobytes(),
            {"bytes_per_row": w},
            {"width": w, "height": h, "depth_or_array_layers": 1},
        )
        scale = 2.0
        uniforms = np.array([
            self._content_w * scale / config.WINDOW_WIDTH,
            self._content_h * scale / config.WINDOW_HEIGHT,
            self._content_w / self.bitmap_w,
            self._content_h / self.bitmap_h,
        ], dtype=np.float32)
        self.device.queue.write_buffer(self._uniforms, 0, uniforms.tobytes())

    def _dirty(self) -> bool:
        bitmap = render_text_to_bitmap(
            self.lines, max_width=self.bitmap_w, max_height=self.bitmap_h)
        h = hash(bitmap.tobytes())
        if h == self._last_bitmap_hash:
            return False
        self._last_bitmap_hash = h
        self._upload(bitmap)
        return True

    def draw(self, command_encoder, present_view):
        if not self.lines:
            return
        self._dirty()
        rpass = command_encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": present_view,
                    "clear_value": (0.0, 0.0, 0.0, 0.0),
                    "load_op": "load",
                    "store_op": "store",
                }
            ],
        )
        rpass.set_pipeline(self._pipeline)
        rpass.set_bind_group(0, self._bind_group)
        rpass.draw(4)
        rpass.end()

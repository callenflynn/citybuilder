"""M0 render smoke test: wgpu-py + rendercanvas + low-res target + palette quant + nearest upscale."""
from rendercanvas.auto import RenderCanvas, loop
import wgpu

WIDTH, HEIGHT = 640, 360          # window size
INTERNAL_W, INTERNAL_H = 320, 180  # low-res internal buffer (pixel-art res)

canvas = RenderCanvas(size=(WIDTH, HEIGHT), title="Pixel City Builder - M0 render test")
context = canvas.get_context("wgpu")
adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
device = adapter.request_device_sync()
context.configure(device=device, format="bgra8unorm")

SCENE_VS = """
struct VertexOutput {
    @builtin(position) position: vec4f,
    @location(0) color: vec4f,
};
@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    var x = f32(i32(vertex_index) - 1);
    var y = f32(((vertex_index & 1) * 2) - 1);
    var pos = vec4f(x, y, 0.0, 1.0);
    var color = vec4f(1.0, 0.0, 0.0, 1.0);
    if (vertex_index == 1) { color = vec4f(0.0, 1.0, 0.0, 1.0); }
    if (vertex_index == 2) { color = vec4f(0.0, 0.0, 1.0, 1.0); }
    var output: VertexOutput;
    output.position = pos;
    output.color = color;
    return output;
}
"""

SCENE_FS = """
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

USAGE = wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.TEXTURE_BINDING

internal_texture = device.create_texture(
    size=(INTERNAL_W, INTERNAL_H, 1),
    format="bgra8unorm",
    usage=USAGE,
)
internal_view = internal_texture.create_view()
internal_sampler = device.create_sampler(
    mag_filter="nearest",
    min_filter="nearest",
)

scene_shader = device.create_shader_module(code=SCENE_VS + "\n" + SCENE_FS)
scene_pipeline = device.create_render_pipeline(
    layout="auto",
    vertex={"module": scene_shader, "entry_point": "vs_main"},
    fragment={
        "module": scene_shader,
        "entry_point": "fs_main",
        "targets": [{"format": "bgra8unorm"}],
    },
    primitive={"topology": "triangle-list"},
)

upscale_shader = device.create_shader_module(code=UPSCALE_VS + "\n" + UPSCALE_FS)
upscale_pipeline = device.create_render_pipeline(
    layout="auto",
    vertex={"module": upscale_shader, "entry_point": "vs_main"},
    fragment={
        "module": upscale_shader,
        "entry_point": "fs_main",
        "targets": [{"format": "bgra8unorm"}],
    },
    primitive={"topology": "triangle-strip"},
)

bind_group_layout = upscale_pipeline.get_bind_group_layout(0)
bind_group = device.create_bind_group(
    layout=bind_group_layout,
    entries=[
        {"binding": 0, "resource": internal_sampler},
        {"binding": 1, "resource": internal_view},
    ],
)

frame = 0

def draw_frame():
    global frame
    frame += 1
    current_texture = context.get_current_texture()
    command_encoder = device.create_command_encoder()
    # Pass 1: draw scene into low-res internal buffer
    rpass = command_encoder.begin_render_pass(
        color_attachments=[
            {
                "view": internal_view,
                "clear_value": (0.1, 0.1, 0.15, 1.0),
                "load_op": "clear",
                "store_op": "store",
            }
        ],
    )
    rpass.set_pipeline(scene_pipeline)
    rpass.draw(3)
    rpass.end()
    # Pass 2: nearest-neighbor upscale internal -> window
    rpass = command_encoder.begin_render_pass(
        color_attachments=[
            {
                "view": current_texture.create_view(),
                "clear_value": (0.0, 0.0, 0.0, 1.0),
                "load_op": "clear",
                "store_op": "store",
            }
        ],
    )
    rpass.set_pipeline(upscale_pipeline)
    rpass.set_bind_group(0, bind_group)
    rpass.draw(4)
    rpass.end()
    device.queue.submit([command_encoder.finish()])

canvas.request_draw(draw_frame)
loop.run()
print("render test done")

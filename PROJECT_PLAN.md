# Pixel City Builder: Project Plan

(Source of truth for design decisions. Kept alongside the code.)

## 1. Vision

Pixel-art look: a true 3D scene drawn into a small internal buffer (~480x270
or 640x360) and upscaled with nearest-neighbor filtering. Palette quantization
and outlines in shaders. Smooth rotating camera at a fixed tilt. Grid-snapped,
free-draw, and auto-curved roads. Buildings sit on roads. Scope target:
Cities: Skylines 2 depth, delivered in layers.

## 2. Locked decisions

Rendering: True 3D, low-res pixelated render, nearest-neighbor upscale
Graphics stack: wgpu-py via the `wgpu_native` backend only (Vulkan on NVIDIA;
wgpu-py has no OpenGL fallback), WGSL shaders
Languages: Python-first; Rust (via PyO3) for hot simulation systems
Roads: Grid snap, free draw, auto curves; CS2-level lane detail
Buildings: Procedural, generated in code from placeholder/generated textures
  (hand-drawn art can be dropped in later)
Placement: Zoning auto-builds; manual placement for services/special
World: Infinite/very large, streamed in chunks; full terraforming, water, rivers
Simulation: Full agent-based, deterministic
Content: Fully data-driven and moddable (JSON/TOML/YAML)
Camera: Smooth rotation and zoom, fixed tilt
Atmosphere: Day/night, weather, seasons, palette-quantized post-processing
Platform: Linux only for now
Team: Solo, heavily AI-assisted
Multiplayer: Single player; keep sim deterministic so co-op is possible later
Audio: Free sounds or silence for now
Saves: One folder per city, chunked, expandable, different map sizes
Worlds: Seeded procedural + handmade maps from a GUI map editor

## 3. Architecture

Python owns rendering, camera, input, UI, data loading, tools, map editor.
Every sim system written in Python first; ported to Rust when profiling shows
a hot spot. Python version kept as reference; tests compare Python vs Rust.
Data-oriented ECS; fixed-tick deterministic; headless mode; simulate only near
developed areas.

## 4. Rendering pipeline

1. Draw 3D scene into low-res offscreen target (depth buffer).
2. Post pass: outline from depth/normals, lighting/shadow, palette quant,
   optional dithering.
3. Upscale to window with nearest-neighbor, integer scaling where possible.
4. Snap camera to pixel grid when moving (avoid shimmering).
5. Instancing + compute shaders: few GPU calls per frame.
6. Day/night, weather, seasons via shader parameters.

Tooling (resolved at M0):
- Package manager: uv (Python + dependency management, installs Python 3.13)
- Python: pinned to 3.13 (PyO3 has no release supporting 3.14; do not rely on
  the forward-compat flag long term)
- Rust build tool: cargo (PyO3 cdylib for the sim core; Cargo.lock committed
  because this is an application, not a library)
- Test framework: pytest
- Profiler: pyinstrument (benchmarks with pytest-benchmark)

Dev UI (resolved at M0):
- Do NOT block on Dear ImGui.
- Build a minimal in-engine debug overlay first (text, FPS, tick time,
  counters) drawn in the game renderer.
- Separately, time-box ONE session on imgui-bundle or pyimgui with a custom
  wgpu renderer. Keep it only if it works cleanly; otherwise stay with the
  in-engine overlay.
- Player-facing UI is custom pixel art.

Textures (resolved at M0):
- Generate placeholder textures in code (checker, brick, window grids,
  asphalt) so nothing blocks on art.
- All texture and building definitions live in data files so custom art can
  be dropped in later.

## 5. Data, saves and tools

Content in JSON/TOML/YAML. Saves: one folder per city, manifest + versioned
migrations, chunk files hold terrain deltas/entities. World gen: seed +
settings. GUI map editor with import/export. Audio behind a small interface.

## 6. Milestones

M0 Foundations — M1 First playable — M1.5 World tools — M2 Zoning/buildings
— M3 Vehicles/traffic — M4 Citizens — M5 Utilities — M6 Economy — M7 Public
transit — Ongoing polish.

## 7. Risks and mitigations

Scope, Python performance (Python-first + profiler-driven Rust ports),
Rust skill gap (reference Python + comparison tests), infinite world + agents
(simulate near developed areas only), lane-level roads (designed into graph
from M1), determinism (no wall-clock, stable iteration order).

## 7.5 Non-negotiable engineering rules

1. Python-first. Every simulation system is written in Python first, with
   tests. Port to Rust only when a benchmark shows it is too slow, and only
   then. Keep the Python version as the reference oracle, and add tests that
   compare Python and Rust outputs.
2. Deterministic sim: seeded RNG only (sim/rng.py), no wall-clock time, no
   unordered iteration, fixed tick. Add a replay test: same seed plus same
   input log gives an identical state hash after N ticks.
3. The sim runs headless and is fully testable without a GPU.
4. Data-driven content: buildings, zones, roads, policies, resources defined
   in JSON/TOML/YAML, loaded by data/loader.py. No hardcoded content in
   systems.
5. Rendering: scene into the low-res target with depth, then a post pass
   (depth/normal outlines, lighting, palette quantization), then nearest
   neighbor integer upscale. Snap the camera to the texel grid to prevent
   shimmer. Use instancing so Python makes few GPU calls per frame.
6. Lane data is first-class on every road segment from M1 (lane count,
   direction, width, allowed vehicle types), because lane-level editing is
   needed in M3.
7. Keep the Rust crate small. Expose state to Python as NumPy arrays.
8. Do not expand scope. Do not start the next milestone before approval.
9. Never fake a result. If something does not work, say so plainly.

Working loop for each milestone:
1. Write a short design note in docs/<milestone>.md (data structures,
   interfaces, risks).
2. Implement in small commits, tests first where practical.
3. Run the full test suite, cargo check, and a headless benchmark for any new
   system.
4. Provide a runnable demo (a script or flag) so it can be seen and felt.
5. Update PROJECT_PLAN.md, README.md and PROGRESS.md (what is done, what is
   not, known bugs, benchmark numbers, decisions made).
6. Commit, then STOP and report: what works, what does not, how to run the
   demo, benchmark numbers, open questions. Wait for "continue".

## 8. Open items (resolved)

- Project name / repository: citybuilder (done)
- Exact internal resolution: 640x360 default, player-adjustable
  (480x270 / 640x360 / 960x540) in settings (done)
- Tooling choices at M0: uv, Python 3.13, cargo, pytest, pyinstrument (done)
- First art: generated placeholder textures in code (done)

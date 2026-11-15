# Pixel City Builder

A Linux-first city builder in Python with a Rust simulation core. True 3D
rendered at low resolution so it looks like pixel art, with a smooth rotating
camera. Long-term feature target: Cities: Skylines 2 depth.

See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for the full project plan, locked
decisions, architecture, milestones, risks, and open items.

## Status: M1 First Playable (in progress)

- Project layout, Python package, Rust PyO3 crate skeleton
- wgpu-py window + low-res render target + nearest-neighbor upscale
- Palette-quantization test shader
- Headless, fixed-tick, deterministic simulation loop (ECS over flat numpy arrays)
- Data loader (JSON/TOML/YAML content definitions)
- Tests (pytest) + profiling setup

The repository is currently being audited against the M1 specification. The
headless renderer and screenshot path work, but the 12-angle rotation sweep
still exposes a combined terrain/building regression at yaw 180° and 210°.
Do not treat M1 as complete until that failure is fixed and the full checker
passes.

## Requirements

- Linux only (for now)
- Python 3.10+ (tested on 3.14)
- Rust toolchain (for the simulation core)
- NVIDIA Vulkan (wgpu-py `wgpu_native` backend) — GL fallback not bundled in wgpu-py 0.33

## Quick start

```bash
# create + activate the venv (one time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run the M0 app (window opens; arrows rotate/zoom, R resets, Esc quits)
python -m citybuilder

# run the test suite
pip install -e ".[dev]"
pytest

# run the standalone render smoke test
python test_render.py

# run the standard verification command (tests, screenshots, rotation sweep)
./scripts/check_all.sh
```

## Repository layout

```
citybuilder/         # Python package (renderer, camera, sim, data, save, ui, ...)
rust/                # Rust simulation core (PyO3)
tests/               # top-level / cross-cutting tests
assets/textures      # wall/window/roof/road textures (drawn by hand)
assets/sounds        # placeholder/free audio
scripts/             # build/release helpers
```

## Open items (from the project plan)

- Internal resolution: 480x270 vs 640x360, player-changeable?
- ImGui integration for dev tools (not bundled with wgpu-py)
- First art: wall/window/roof/road textures

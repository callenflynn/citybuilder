# Progress

## Done

- Repository audit completed against the development specification on 2026-11-14.
- Fixed editable installation: setuptools now discovers only `citybuilder*` packages, so `pip install -e '.[dev]'` succeeds instead of treating `rust/` as a Python package.
- Added `scripts/check_all.sh` as the standard verification entry point. It runs pytest, the headless screenshot smoke test, and the 12-angle rotation sweep.
- Headless rendering is implemented and screenshot tests cover non-flat scene output and camera-angle differences.
- Depth attachment and depth testing are present in the renderer.
- Fixed the rear-angle regression: the demo's first tower was placed almost on top of the camera at yaw 180°. Towers are now restricted to the central city area; the complete 12-angle sweep passes.
- Implemented independent per-chunk static terrain GPU meshes. Each visible chunk has its own vertex/index buffers and draw call, so future streaming edits need not invalidate the entire terrain scene.
- Expanded the deterministic demo to an 84-segment 7x7 road grid with 216 varied procedural buildings across the blocks.
- Current automated result: 46 tests passed, screenshots rendered at 0°, 45°, and 90°, and the 12-angle rotation sweep passed. `scripts/check_all.sh` passes.

## Broken

- The dense demo is a static showcase; zoning-driven growth and citizen simulation are not yet connected to the visible buildings.
- GUI window mapping remains compositor-dependent; headless rendering is the reliable verification path in this environment.
- M1.5 features are not implemented: terraforming, water/rivers, world-generation settings, per-city saves, and the map editor.
- Building placement mode is currently a keyboard toggle only; it does not yet place a building from a mouse ghost preview.

## Next

1. Add the M1 visual pass: outlines, banded lighting, palette lookup, and texel snapping.
2. Add a GPU-synchronized benchmark at 100, 1,000, and 5,000 buildings.
3. Continue with terrain picking and validated two-click road placement.
4. Implement a building ghost preview and pinned manual placement.

## Verification commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
./scripts/check_all.sh
```

The commands must be run with `MANGOHUD` and `PYTHONPATH` removed; the checker handles this automatically.

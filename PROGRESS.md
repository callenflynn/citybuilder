# Progress

## Done

- Repository audit completed against the development specification on 2026-11-14.
- Fixed editable installation: setuptools now discovers only `citybuilder*` packages, so `pip install -e '.[dev]'` succeeds instead of treating `rust/` as a Python package.
- Added `scripts/check_all.sh` as the standard verification entry point. It runs pytest, the headless screenshot smoke test, and the 12-angle rotation sweep.
- Headless rendering is implemented and the screenshot tests cover non-flat scene output and camera-angle differences.
- Depth attachment and depth testing are present in the renderer.
- The project currently has 45 passing tests when the known rotation regression is excluded; `compileall` and editable installation complete successfully.

## Broken

- `citybuilder/tests/test_rotation_sweep.py` fails at yaw 180° and 210° with distance 60 and the fixed 35° tilt. Terrain-only rendering succeeds at those angles, but the combined terrain/building scene collapses to a nearly flat frame. This is the first unfinished M1 rendering task and is not being marked fixed without a verified cause.
- Full `scripts/check_all.sh` is therefore expected to fail at the rotation sweep until the combined-scene regression is fixed.
- GUI window mapping remains compositor-dependent; headless rendering is the reliable verification path in this environment.
- M1.5 features are not implemented: terraforming, water/rivers, world-generation settings, per-city saves, and the map editor.

## Next

1. Diagnose and fix the combined-scene dark-frame regression at the rear yaw angles.
2. Re-run the full 12-angle rotation sweep and capture updated PNG evidence.
3. Only after that, continue with the next M1 item: per-chunk static meshes.

## Verification commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
./scripts/check_all.sh
```

The commands must be run with `MANGOHUD` and `PYTHONPATH` removed; the checker handles this automatically.

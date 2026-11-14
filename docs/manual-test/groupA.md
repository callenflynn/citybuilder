# Manual test: Phase A (M1 finish)

Run from `/home/cal/Projects/citybuilder`. Always use the project venv with
the two env vars cleared, or imports break:

```
cd /home/cal/Projects/citybuilder
export PYTHONPATH=        # unset it; Hermes's PYTHONPATH shadows the venv
env -u MANGOHUD -u PYTHONPATH .venv/bin/python ...
```

## A0/A1: app runs, tests green

```
env -u MANGOHUD -u PYTHONPATH .venv/bin/python -m pytest citybuilder/tests tests -q
```
Expect: **45 passed** (43 original + 2 screenshot tests).

```
env -u MANGOHUD -u PYTHONPATH .venv/bin/python -m citybuilder
```
Expect: window opens, stays open, no crash. (Note: on this Hyprland setup
the window may not map visibly due to a libdecor/GTK fallback warning; the
process runs and renders frames. Check `ps` for the process and stderr for
"Traceback"/"Validation Error"/"Draw error" — none should appear.)

## A2: headless screenshots

```
env -u MANGOHUD -u PYTHONPATH .venv/bin/python -m citybuilder --screenshot docs/verification
```
Expect: stdout prints one line per angle with `std=9X.X` and `distinct=5..6`,
and writes `docs/verification/city_yaw0.png`, `city_yaw45.png`, `city_yaw90.png`.
PASS = each line has `distinct >= 5` and `std > 90`. FAIL = `distinct=1` or
`std < 5` (flat/clear color = the view/proj uniform bug regressed).

Then verify a PNG is not flat:
```
env -u MANGOHUD -u PYTHONPATH .venv/bin/python /home/cal/.hermes/cache/scratch/pngread.py docs/verification/city_yaw0.png
```
(pngread.py is a scratch decoder; any PNG reader works.) PASS = distinct >= 3,
std > 5, and the 3x3 region means differ (sky dark on top, green/brown below).

## What a failure looks like

- `distinct=1` and all pixels ~(25,25,38): the view/proj matrices are being
  read as their transpose (the A2 bug). Re-check `set_view_proj` uploads
  `view.T` / `proj.T` (WGSL mat4 is column-major).
- `Validation Error ... COPY_SRC`: the internal texture lost its COPY_SRC flag.
- `ModuleNotFoundError: numpy._core._multiarray_umath`: you forgot
  `env -u PYTHONPATH` (Hermes's 3.14 venv is shadowing the project venv).

## Known open items (not failures)

- yaw=180 at pitch=35 renders mostly sky (grazing angle on flat terrain).
  Steeper pitch (50-70) shows terrain. Not a renderer bug; camera placement.
- The GUI window does not map on this compositor (libdecor-gtk fails,
  falls back). Headless --screenshot is the verification path.

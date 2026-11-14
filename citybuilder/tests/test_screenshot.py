"""Headless screenshot tests: the demo city renders to a non-flat PNG.

These run without a display: they build the headless App (no window) and
call the same capture path the --screenshot CLI uses. A regression that
breaks the view/proj uniform upload (e.g. row-major vs column-major)
makes the frame collapse to the clear color, which these tests catch.
"""

from __future__ import annotations

import os

import numpy as np

from citybuilder.main import _build_headless_app, render_screenshots


def _assert_real_image(rgba: np.ndarray) -> None:
    assert rgba.dtype == np.uint8
    assert rgba.ndim == 3 and rgba.shape[2] == 4
    # not the flat clear color (0.1, 0.1, 0.15) -> (25, 25, 38)
    std = float(rgba.std())
    assert std > 5.0, f"image is nearly flat (std={std:.2f})"
    quant = (rgba[:, :, :3] // 64).reshape(-1, 3)
    distinct = len(np.unique(quant, axis=0))
    assert distinct >= 3, f"fewer than 3 dominant colors ({distinct})"


def test_headless_app_builds_and_renders_nonflat(tmp_path):
    app = _build_headless_app()
    assert app.renderer.terrain_count == 0  # set_scene not called yet
    import math
    app.camera.yaw = 0.0
    app.camera.distance = 60.0
    app.camera.tilt = math.radians(35.0)
    app.camera.update(0.0)
    cam_x, _, cam_z = app.camera.position()
    chunks = app.chunk_mgr.update(cam_x, cam_z, radius_chunks=3)
    app.renderer.set_scene(chunks, app.road_graph.segment_list(),
                           list(app.buildings.values()))
    assert app.renderer.terrain_count > 0
    assert app.renderer.road_count > 0
    assert app.renderer.building_count > 0
    app.renderer.set_view_proj(app.camera.view_matrix(),
                               app.camera.projection_matrix())
    rgba = app.renderer.capture_frame(str(tmp_path / "t.png"))
    assert os.path.getsize(str(tmp_path / "t.png")) > 0
    _assert_real_image(rgba)


def test_screenshot_cli_renders_three_angles(tmp_path):
    out = str(tmp_path / "shots")
    paths = render_screenshots(out, [0, 45, 90], distance=60.0, pitch=35.0)
    assert len(paths) == 3
    for p in paths:
        assert os.path.getsize(p) > 0
    # each angle must actually differ (camera rotated)
    from citybuilder.rendering.renderer import _write_png  # noqa: F401
    imgs = []
    for p in paths:
        # decode via capture return is gone; re-read is slow, so compare bytes
        imgs.append(open(p, "rb").read())
    assert imgs[0] != imgs[1] != imgs[2]

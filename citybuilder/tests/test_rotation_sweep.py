"""Rotation sweep: every 30 deg of yaw at the fixed 35 deg tilt must show terrain.

Catches back-face culling regressions (yaw 180 saw only sky when the terrain
winding was culled) and any uniform-transpose regression.
"""
from __future__ import annotations

import math

import numpy as np

from citybuilder.main import _build_headless_app


def _frame_stats(rgba: np.ndarray) -> dict:
    rgb = rgba[:, :, :3]
    green = int(((rgb[:, :, 1].astype(int) > rgb[:, :, 0] + 8)
                 & (rgb[:, :, 1].astype(int) > rgb[:, :, 2] + 8)).sum())
    # quantized-to-black sky/clear is (0,0,0); terrain green band is (0,127,0)
    black = int((np.abs(rgb.astype(int) - np.array([0, 0, 0])).max(axis=2) <= 6).sum())
    return {"green": green, "black": black, "std": float(rgba.std())}


def test_rotation_sweep_every_30_degrees_shows_terrain():
    app = _build_headless_app()
    failing = []
    for yaw in range(0, 360, 30):
        app.camera.yaw = math.radians(yaw)
        app.camera.distance = 60.0
        app.camera.tilt = math.radians(35.0)  # fixed by design
        app.camera.update(0.0)
        cam_x, _, cam_z = app.camera.position()
        chunks = app.chunk_mgr.update(cam_x, cam_z, radius_chunks=3)
        app.renderer.set_scene(chunks, app.road_graph.segment_list(),
                               list(app.buildings.values()))
        app.renderer.set_view_proj(app.camera.view_matrix(),
                                   app.camera.projection_matrix())
        rgba = app.renderer.capture_frame("/tmp/sweep_%d.png" % yaw)
        s = _frame_stats(rgba)
        ok = s["green"] > 2000 and s["std"] > 20
        print("yaw=%3d green=%6d black=%6d std=%.1f %s"
              % (yaw, s["green"], s["black"], s["std"], "OK" if ok else "FAIL"))
        if not ok:
            failing.append((yaw, s))
    assert not failing, f"yaw angles with no terrain content: {failing}"

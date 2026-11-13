"""Tests for camera-based road picking (mouse -> world ray -> road node).

The scene is rendered to an internal 640x360 buffer and upscaled 2x to the
1280x720 window. `_snap_mouse_to_road` must convert window pixels to NDC in
the internal viewport, unproject through the camera, and return the road node
under the click -- or None when clicking empty space. Pure math, no GPU.
"""

import math

import pytest

from citybuilder.camera import Camera
from citybuilder.world.roadgraph import RoadGraph
from citybuilder import picking
from citybuilder.main import App


def make_app():
    """Build an App without running the GPU __init__ (no display needed)."""
    app = App.__new__(App)
    app.road_graph = RoadGraph()
    app.camera = Camera()
    return app


def make_graph():
    g = RoadGraph()
    n0 = g.add_node(0.0, 0.0)
    n1 = g.add_node(8.0, 0.0)
    n2 = g.add_node(16.0, 0.0)
    n3 = g.add_node(0.0, 8.0)
    g.add_segment(n0, n1)
    g.add_segment(n1, n2)
    g.add_segment(n0, n3)
    return g, {"n0": n0, "n1": n1, "n2": n2, "n3": n3}


# --- pure math -------------------------------------------------------------
def test_window_to_ndc_center():
    assert picking.window_to_ndc(640.0, 360.0) == pytest.approx((0.0, 0.0))


def test_window_to_ndc_corners():
    # top-left of window -> NDC (-1, +1); bottom-right -> (+1, -1)
    assert picking.window_to_ndc(0.0, 0.0) == pytest.approx((-1.0, 1.0))
    assert picking.window_to_ndc(1280.0, 720.0) == pytest.approx((1.0, -1.0))


def test_project_unproject_round_trip():
    """A world point projects to a pixel that unprojects back to the ray."""
    cam = Camera()
    view = cam.view_matrix()
    proj = cam.projection_matrix()
    sp = picking.project_to_window((16.0, 0.0, 0.0), view, proj)
    assert sp is not None
    ndc = picking.window_to_ndc(sp[0], sp[1])
    origin, direction = picking.unproject_ray(ndc[0], ndc[1], view, proj)
    # The ray must pass (near) the world point: direction from origin toward it.
    w = (16.0, 0.0, 0.0)
    d = picking.point_ray_distance(w, origin, direction)
    assert d < 1.0  # within a world unit


# --- picking via App._snap_mouse_to_road -----------------------------------
def test_snap_returns_node_at_projected_position():
    """Clicking directly on a node's screen position returns that node."""
    app = make_app()
    nodes = make_graph()[1]
    app.road_graph = make_graph()[0]
    view = app.camera.view_matrix()
    proj = app.camera.projection_matrix()
    # project node n2 to window px, then click there
    sp = picking.project_to_window((16.0, 0.0, 0.0), view, proj)
    assert sp is not None
    got = app._snap_mouse_to_road(int(round(sp[0])), int(round(sp[1])))
    assert got == nodes["n2"]


def test_snap_returns_node_within_radius():
    """Clicking slightly off a node still snaps to it (screen-space radius)."""
    app = make_app()
    g, nodes = make_graph()
    app.road_graph = g
    view = app.camera.view_matrix()
    proj = app.camera.projection_matrix()
    sp = picking.project_to_window((8.0, 0.0, 0.0), view, proj)
    assert sp is not None
    # nudge 5px away -- inside the 10px radius
    got = app._snap_mouse_to_road(int(round(sp[0])) + 5, int(round(sp[1])) + 3)
    assert got == nodes["n1"]


def test_snap_returns_nearest_endpoint_on_segment():
    """Clicking mid-segment returns one of the segment's endpoints."""
    app = make_app()
    g, nodes = make_graph()
    app.road_graph = g
    view = app.camera.view_matrix()
    proj = app.camera.projection_matrix()
    sp = picking.project_to_window((12.0, 0.0, 0.0), view, proj)
    assert sp is not None
    got = app._snap_mouse_to_road(int(round(sp[0])), int(round(sp[1])))
    assert got in (nodes["n1"], nodes["n2"])


def test_snap_returns_none_when_far_from_any_road():
    """Clicking empty sky/corner returns None."""
    app = make_app()
    g, _ = make_graph()
    app.road_graph = g
    # top-right corner of the window -- no road geometry projects there
    assert app._snap_mouse_to_road(1270.0, 5.0) is None


def test_snap_none_on_empty_graph():
    app = make_app()
    got = app._snap_mouse_to_road(640.0, 360.0)
    assert got is None
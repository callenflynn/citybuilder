"""Tests for the road graph (grid snap, dedup, lane data, determinism)."""

from citybuilder.world.roadgraph import RoadGraph, LaneData, snap


def test_grid_snap():
    assert snap(0.0) == 0.0
    assert snap(3.0) == 0.0      # nearest multiple of 8 (3 is closer to 0)
    assert snap(4.0) == 8.0      # half rounds up
    assert snap(-4.0) == 0.0     # .5 boundary rounds toward zero
    assert snap(12.0) == 16.0
    assert snap(100.0) == 104.0


def test_add_node_snaps_and_dedups():
    g = RoadGraph()
    a = g.add_node(1.0, 2.0)     # snaps to (0, 0)
    b = g.add_node(7.0, 9.0)     # snaps to (8, 8)
    c = g.add_node(0.0, 0.0)     # same snapped pos as a
    assert a == c                # dedup returns same id
    assert a != b
    assert g.num_nodes() == 2


def test_add_segment_requires_nodes():
    g = RoadGraph()
    assert g.add_segment(0, 1) is None
    a = g.add_node(0.0, 0.0)
    b = g.add_node(16.0, 0.0)
    assert g.add_segment(a, b) is not None


def test_segment_undirected_dedup():
    g = RoadGraph()
    a = g.add_node(0.0, 0.0)
    b = g.add_node(16.0, 0.0)
    s1 = g.add_segment(a, b)
    s2 = g.add_segment(b, a)     # same undirected pair
    assert s1 == s2
    assert g.num_segments() == 1


def test_lane_data_first_class():
    g = RoadGraph()
    a = g.add_node(0.0, 0.0)
    b = g.add_node(16.0, 0.0)
    sid = g.add_segment(a, b, LaneData(lane_count=4, direction="forward",
                                       width=3.5))
    seg = g.get_segment(sid)
    assert seg.lanes.lane_count == 4
    assert seg.lanes.direction == "forward"
    assert seg.lanes.width == 3.5


def test_bezier_straight():
    from citybuilder.world.roadgraph import Bezier
    b = Bezier.straight((0.0, 0.0), (16.0, 0.0))
    assert b.point(0.0) == (0.0, 0.0)
    assert b.point(1.0) == (16.0, 0.0)
    # midpoint of straight line
    assert b.point(0.5) == (8.0, 0.0)


def test_state_hash_deterministic():
    g1 = RoadGraph()
    a = g1.add_node(0.0, 0.0)
    b = g1.add_node(16.0, 0.0)
    g1.add_segment(a, b)

    g2 = RoadGraph()
    a2 = g2.add_node(0.0, 0.0)
    b2 = g2.add_node(16.0, 0.0)
    g2.add_segment(a2, b2)

    assert g1.state_hash_input() == g2.state_hash_input()

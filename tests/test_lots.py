"""Tests for lot generation along road segments."""

from citybuilder.world.lots import LotGenerator, LOT_WIDTH, LOT_DEPTH
from citybuilder.world.roadgraph import RoadGraph, LaneData


def _make_graph():
    g = RoadGraph()
    a = g.add_node(0.0, 0.0)
    b = g.add_node(100.0, 0.0)
    g.add_segment(a, b)
    return g, a, b


def test_lots_generated_along_segment():
    g, _, _ = _make_graph()
    gen = LotGenerator(g)
    lots = gen.generate()
    assert len(lots) > 0
    # lots should span much of the 100-unit segment
    offsets = sorted(l.along_offset for l in lots.values())
    assert offsets[0] >= 0
    assert offsets[-1] > 50


def test_lots_do_not_overlap():
    g, _, _ = _make_graph()
    gen = LotGenerator(g)
    lots = gen.generate()
    footprints = [l.footprint for l in lots.values()]
    from citybuilder.world.lots import _polygon_overlaps
    for i in range(len(footprints)):
        for j in range(i + 1, len(footprints)):
            assert not _polygon_overlaps(footprints[i], footprints[j])


def test_lots_deterministic():
    g1, _, _ = _make_graph()
    g2, _, _ = _make_graph()
    gen1 = LotGenerator(g1)
    gen2 = LotGenerator(g2)
    l1 = gen1.generate()
    l2 = gen2.generate()
    assert len(l1) == len(l2)
    for (k1, v1), (k2, v2) in zip(sorted(l1.items()), sorted(l2.items())):
        assert v1.footprint == v2.footprint
        assert v1.along_offset == v2.along_offset


def test_lots_touch_road_frontage():
    # every lot's footprint should include a point on the road (z=0 line within segment)
    g, _, _ = _make_graph()
    gen = LotGenerator(g)
    lots = gen.generate()
    for lot in lots.values():
        # footprint z range should straddle z=0 (the road) at its near edge
        zs = [c[1] for c in lot.footprint]
        assert min(zs) <= 0.0 <= max(zs)

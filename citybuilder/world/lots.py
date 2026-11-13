"""Lot generation along road segments.

Lots are generated along road segments so that buildings sit on road frontage.
Each lot has a footprint polygon and is buildable if it does not overlap
another lot. M1: simple rectangular lots on the right side of each segment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .roadgraph import RoadGraph, Segment, Bezier

LOT_WIDTH = 14.0      # width of a lot along the road
LOT_DEPTH = 30.0      # depth of a lot back from the road
LOT_SPACING = 2.0     # gap between lots along the road


@dataclass
class Lot:
    id: int
    footprint: list[tuple[float, float]]  # [(x, z), ...] closed polygon
    segment_id: int
    along_offset: float  # distance along segment where lot starts
    building: int | None = None  # building id, assigned later


def _segment_points(seg: Segment, steps: int = 24) -> list[tuple[float, float]]:
    return seg.curve.sample(steps)


def _length(seg: Segment, steps: int = 24) -> float:
    pts = _segment_points(seg, steps)
    total = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dz = pts[i][1] - pts[i - 1][1]
        total += math.hypot(dx, dz)
    return total


def _tangent_at(seg: Segment, t: float) -> tuple[float, float]:
    """Approximate tangent direction at parameter t in [0, 1]."""
    eps = 0.001
    t0 = max(0.0, t - eps)
    t1 = min(1.0, t + eps)
    p0 = seg.curve.point(t0)
    p1 = seg.curve.point(t1)
    dx = p1[0] - p0[0]
    dz = p1[1] - p0[1]
    n = math.hypot(dx, dz)
    if n == 0:
        return (1.0, 0.0)
    return (dx / n, dz / n)


def _right_normal(tangent: tuple[float, float]) -> tuple[float, float]:
    # right of travel = (dz, -dx)
    return (tangent[1], -tangent[0])


def _point_on_curve(seg: Segment, along: float, steps: int = 24) -> tuple[float, float]:
    """Map a distance along the segment to a curve point (linear approx)."""
    pts = _segment_points(seg, steps)
    if len(pts) < 2:
        return pts[0] if pts else (0.0, 0.0)
    # cumulative lengths
    cum = [0.0]
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dz = pts[i][1] - pts[i - 1][1]
        cum.append(cum[-1] + math.hypot(dx, dz))
    total = cum[-1]
    if total == 0:
        return pts[0]
    # clamp
    along = max(0.0, min(along, total))
    # find segment
    for i in range(1, len(pts)):
        if cum[i] >= along:
            t = (along - cum[i - 1]) / (cum[i] - cum[i - 1]) if cum[i] > cum[i - 1] else 0.0
            p0, p1 = pts[i - 1], pts[i]
            return (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))
    return pts[-1]


def _polygon_overlaps(a: list[tuple[float, float]],
                      b: list[tuple[float, float]]) -> bool:
    """Simple convex-polygon overlap via separating axis theorem (2D)."""
    def axes(poly):
        axs = []
        m = len(poly)
        for i in range(m):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % m]
            ex, ez = x2 - x1, z2 - z1
            axs.append((ez, -ex))  # normal
        return axs

    def project(poly, axis):
        dots = [px * axis[0] + pz * axis[1] for px, pz in poly]
        return min(dots), max(dots)

    all_axes = axes(a) + axes(b)
    for axis in all_axes:
        ax, az = axis
        n = math.hypot(ax, az)
        if n == 0:
            continue
        axis = (ax / n, az / n)
        mina, maxa = project(a, axis)
        minb, maxb = project(b, axis)
        if maxa < minb or maxb < mina:
            return False  # separating axis found -> no overlap
    return True


class LotGenerator:
    def __init__(self, road_graph: RoadGraph):
        self.graph = road_graph
        self.lots: dict[int, Lot] = {}
        self._next_id = 0

    def generate(self) -> dict[int, Lot]:
        """Generate lots along all segments. Rebuilds from scratch (deterministic)."""
        self.lots = {}
        self._next_id = 0
        for seg in self.graph.segment_list():
            self._generate_on_segment(seg)
        return self.lots

    def _generate_on_segment(self, seg: Segment):
        total = _length(seg)
        if total <= 0:
            return
        offset = 0.0
        while offset + LOT_WIDTH <= total:
            p = _point_on_curve(seg, offset)
            tan = _tangent_at(seg, offset / total if total else 0.0)
            rn = _right_normal(tan)
            # footprint: rectangle centered on the road at `offset`, extending
            # lot_width along the road and lot_depth along the right normal.
            hw = LOT_WIDTH / 2.0
            # corners in order (counter-clockwise viewed from above)
            footprint = [
                (p[0] - tan[0] * hw - rn[0] * LOT_DEPTH,
                 p[1] - tan[1] * hw - rn[1] * LOT_DEPTH),
                (p[0] - tan[0] * hw,
                 p[1] - tan[1] * hw),
                (p[0] + tan[0] * hw,
                 p[1] + tan[1] * hw),
                (p[0] + tan[0] * hw + rn[0] * LOT_DEPTH,
                 p[1] + tan[1] * hw + rn[1] * LOT_DEPTH),
            ]
            # overlap check with existing lots
            if not any(_polygon_overlaps(footprint, ex.footprint)
                       for ex in self.lots.values()):
                lid = self._next_id
                self._next_id += 1
                self.lots[lid] = Lot(lid, footprint, seg.id, offset)
            offset += LOT_WIDTH + LOT_SPACING

    def buildable_lots(self) -> list[Lot]:
        return [lot for lot in self.lots.values() if lot.building is None]

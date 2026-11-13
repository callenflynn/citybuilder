"""Road graph: nodes + segments with Bezier curves and first-class lane data.

Design notes (see docs/M1.md):
- Nodes are snapped to the road grid at placement time.
- A segment stores one Bezier curve (start/end = node positions). Grid,
  free-draw and auto-curve all share this single representation; M1 uses
  straight segments (controls equal to endpoints) and defaults free-draw /
  auto-curve to later milestones.
- Lane data is first-class on every segment from M1 (lane count, direction,
  width, allowed vehicle types) because M3 lane-level editing/consumption
  depends on it.
- IDs are stable insertion order; iteration order is deterministic (by id)
  so replays are reproducible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config
from ..sim.rng import RNG


@dataclass
class LaneData:
    """First-class lane information on a road segment."""
    lane_count: int = 2
    direction: str = "both"          # "forward" | "backward" | "both"
    width: float = 3.0               # per-lane width in world units
    allowed_vehicle_types: frozenset = field(
        default_factory=lambda: frozenset({"car", "pedestrian"})
    )


@dataclass
class Bezier:
    p0: tuple[float, float]  # start (from node)
    p1: tuple[float, float]  # control 1
    p2: tuple[float, float]  # control 2
    p3: tuple[float, float]  # end (to node)

    @classmethod
    def straight(cls, a: tuple[float, float], b: tuple[float, float]) -> "Bezier":
        return cls(a, a, b, b)

    def point(self, t: float) -> tuple[float, float]:
        """Cubic Bezier point at t in [0, 1]. Deterministic, no RNG."""
        p0, p1, p2, p3 = self.p0, self.p1, self.p2, self.p3
        u = 1.0 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        z = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return (x, z)

    def sample(self, steps: int = 16) -> list[tuple[float, float]]:
        return [self.point(i / max(steps - 1, 1)) for i in range(steps)]


@dataclass
class Node:
    id: int
    pos: tuple[float, float]  # snapped (x, z)


@dataclass
class Segment:
    id: int
    from_node: int
    to_node: int
    curve: Bezier
    lanes: LaneData


def snap(value: float) -> float:
    """Snap a world coordinate to the road grid (round half up)."""
    return math.floor(value / config.ROAD_GRID_SIZE + 0.5) * config.ROAD_GRID_SIZE


class RoadGraph:
    """Deterministic node/segment road graph."""

    def __init__(self):
        self.nodes: dict[int, Node] = {}
        self.segments: dict[int, Segment] = {}
        self._next_node_id = 0
        self._next_segment_id = 0
        # snapped pos -> node id, for dedup
        self._pos_to_node: dict[tuple[float, float], int] = {}

    # -- nodes ----------------------------------------------------------------
    def add_node(self, x: float, z: float) -> int:
        sx, sz = snap(x), snap(z)
        key = (sx, sz)
        if key in self._pos_to_node:
            return self._pos_to_node[key]
        nid = self._next_node_id
        self._next_node_id += 1
        node = Node(nid, (sx, sz))
        self.nodes[nid] = node
        self._pos_to_node[key] = nid
        return nid

    def get_node(self, nid: int) -> Node | None:
        return self.nodes.get(nid)

    def node_positions(self) -> list[tuple[int, tuple[float, float]]]:
        return [(n.id, n.pos) for n in sorted(self.nodes.values(), key=lambda n: n.id)]

    # -- segments -------------------------------------------------------------
    def add_segment(self, from_id: int, to_id: int,
                    lanes: LaneData | None = None) -> int | None:
        """Add a straight segment between two existing nodes.

        Returns the new segment id, or None if either node is missing or the
        segment already exists (undirected dedup).
        """
        if from_id not in self.nodes or to_id not in self.nodes:
            return None
        if from_id == to_id:
            return None
        # Undirected dedup: a segment between the same pair already exists?
        for seg in self.segments.values():
            if {seg.from_node, seg.to_node} == {from_id, to_id}:
                return seg.id
        sid = self._next_segment_id
        self._next_segment_id += 1
        a = self.nodes[from_id].pos
        b = self.nodes[to_id].pos
        curve = Bezier.straight(a, b)
        seg = Segment(sid, from_id, to_id, curve,
                      lanes or LaneData())
        self.segments[sid] = seg
        return sid

    def get_segment(self, sid: int) -> Segment | None:
        return self.segments.get(sid)

    def segment_list(self) -> list[Segment]:
        return [self.segments[sid] for sid in sorted(self.segments)]

    def num_nodes(self) -> int:
        return len(self.nodes)

    def num_segments(self) -> int:
        return len(self.segments)

    # -- determinism helper ---------------------------------------------------
    def state_hash_input(self) -> tuple:
        """A deterministic snapshot for replay/comparison testing."""
        nodes = tuple(sorted((n.id, n.pos) for n in self.nodes.values()))
        segs = tuple(sorted(
            (s.id, s.from_node, s.to_node,
             s.curve.p0, s.curve.p1, s.curve.p2, s.curve.p3,
             s.lanes.lane_count, s.lanes.direction, s.lanes.width,
             tuple(sorted(s.lanes.allowed_vehicle_types)))
            for s in self.segments.values()))
        return (nodes, segs)

"""Procedural buildings and code-generated placeholder textures.

Per the resolved decision: placeholder textures are generated in code (checker,
brick, window grid, asphalt) so nothing blocks on art. All texture and building
definitions live in data files so custom art can be dropped in later.

A building is extruded from a lot footprint: walls tiled with a wall texture,
roof tiled with a roof texture. Geometry is generated deterministically from a
seeded variant pick.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def _rng(seed: int):
    return np.random.default_rng(seed)


def texture_checker(size: int = 64) -> np.ndarray:
    rng = _rng(0x1)
    a = np.full((size, size, 4), [120, 120, 130, 255], dtype=np.uint8)
    b = np.full((size, size, 4), [90, 90, 100, 255], dtype=np.uint8)
    tile = 8
    for y in range(size):
        for x in range(size):
            if ((x // tile) + (y // tile)) % 2 == 0:
                a[y, x] = b[y, x]
    noise = (rng.integers(0, 12, (size, size, 1))).astype(np.uint8)
    a = np.clip(a.astype(int) + noise, 0, 255).astype(np.uint8)
    return a


def texture_asphalt(size: int = 64) -> np.ndarray:
    rng = _rng(0x2)
    base = np.full((size, size, 4), [60, 60, 66, 255], dtype=np.uint8)
    noise = rng.integers(0, 14, (size, size, 1)).astype(np.uint8)
    base = np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)
    specks = rng.integers(0, size * size, size * size // 4)
    yy = (specks // size).astype(np.uintp)
    xx = (specks % size).astype(np.uintp)
    base[yy, xx] = [40, 40, 44, 255]
    return base


def texture_brick(size: int = 64) -> np.ndarray:
    rng = _rng(0x3)
    brick = np.full((size, size, 4), [160, 70, 60, 255], dtype=np.uint8)
    mortar = np.full((size, size, 4), [90, 80, 75, 255], dtype=np.uint8)
    for y in range(size):
        row = y // 10
        offset = 5 if row % 2 else 0
        for x in range(size):
            if (x + offset) % 10 < 2 or y % 10 < 2:
                brick[y, x] = mortar[y, x]
    noise = rng.integers(0, 10, (size, size, 1)).astype(np.uint8)
    brick = np.clip(brick.astype(int) + noise, 0, 255).astype(np.uint8)
    return brick


def texture_window_grid(size: int = 64) -> np.ndarray:
    rng = _rng(0x4)
    glass = np.full((size, size, 4), [20, 40, 90, 235], dtype=np.uint8)
    frame = np.full((size, size, 4), [10, 15, 30, 255], dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            if x % 8 < 1 or y % 8 < 1:
                glass[y, x] = frame[y, x]
    noise = rng.integers(0, 6, (size, size, 1)).astype(np.uint8)
    glass = np.clip(glass.astype(int) + noise, 0, 255).astype(np.uint8)
    return glass


def texture_roof(size: int = 64) -> np.ndarray:
    rng = _rng(0x5)
    base = np.full((size, size, 4), [50, 50, 55, 255], dtype=np.uint8)
    noise = rng.integers(0, 10, (size, size, 1)).astype(np.uint8)
    base = np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)
    return base


PLACEHOLDER_TEXTURES = {
    "checker": texture_checker,
    "asphalt": texture_asphalt,
    "brick": texture_brick,
    "window_grid": texture_window_grid,
    "roof": texture_roof,
}


def placeholder_texture(name: str, size: int = 64) -> np.ndarray:
    """Return an RGBA uint8 placeholder texture (size x size x 4), generated in code."""
    if name not in PLACEHOLDER_TEXTURES:
        raise KeyError(f"unknown placeholder texture: {name}")
    return PLACEHOLDER_TEXTURES[name](size=size)


# ---------------------------------------------------------------------------
# Building definition + instance
# ---------------------------------------------------------------------------

@dataclass
class BuildingDef:
    key: str
    floor_count: int = 3
    floor_height: float = 4.0
    roof_type: str = "flat"   # "flat" | "gabled" | "sloped"
    wall_texture: str = "brick"
    window_texture: str = "window_grid"
    roof_texture: str = "roof"


@dataclass
class Building:
    id: int
    def_key: str
    variant: int  # seeded pick, deterministic
    footprint: list[tuple[float, float]]
    position: tuple[float, float]
    height: float
    # GPU-ready mesh: (vertices, indices); vertices = (x,y,z, nx,ny,nz, u,v)
    vertices: np.ndarray = field(repr=False)
    indices: np.ndarray = field(repr=False)


def building_mesh(footprint: list[tuple[float, float]],
                  height: float,
                  tile_size: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """Extrude a footprint into a box building mesh.

    Vertices: float32 (x, y, z, nx, ny, nz, u, v).
    Indices: uint32 triangles.
    Deterministic given footprint + height.
    """
    verts: list[float] = []
    idx: list[int] = []

    def add(x, y, z, nx, ny, nz, u, v):
        verts.extend([x, y, z, nx, ny, nz, u, v])
        return len(verts) // 8 - 1

    n = len(footprint)
    # Walls: one quad per footprint edge, extruded 0 -> height.
    for i in range(n):
        x0, z0 = footprint[i]
        x1, z1 = footprint[(i + 1) % n]
        ex, ez = x1 - x0, z1 - z0
        length = math.hypot(ex, ez)
        if length == 0:
            continue
        tx, tz = ex / length, ez / length
        nx, nz = tz, -tx  # outward normal
        u0 = 0.0
        u1 = length / tile_size
        v0, v1 = 0.0, height / tile_size
        v_bl = add(x0, 0.0, z0, nx, 0.0, nz, u0, v0)
        v_br = add(x1, 0.0, z1, nx, 0.0, nz, u1, v0)
        v_tr = add(x1, height, z1, nx, 0.0, nz, u1, v1)
        v_tl = add(x0, height, z0, nx, 0.0, nz, u0, v1)
        idx.extend([v_bl, v_br, v_tr, v_bl, v_tr, v_tl])

    # Roof: flat roof at height (triangle fan from centroid).
    if n >= 3:
        cx = sum(c[0] for c in footprint) / n
        cz = sum(c[1] for c in footprint) / n
        center = add(cx, height, cz, 0.0, 1.0, 0.0, 0.5, 0.5)
        roof_verts = []
        for i in range(n):
            x, z = footprint[i]
            u = 0.5 + (x - cx) / tile_size * 0.5
            v = 0.5 + (z - cz) / tile_size * 0.5
            roof_verts.append(add(x, height, z, 0.0, 1.0, 0.0, u, v))
        for i in range(n):
            idx.extend([center, roof_verts[i], roof_verts[(i + 1) % n]])

    vertices = np.array(verts, dtype=np.float32).reshape(-1, 8)
    indices = np.array(idx, dtype=np.uint32)
    return vertices, indices


def make_building(bid: int, def_key: str, footprint: list[tuple[float, float]],
                  rng_seed: int,
                  defs: dict[str, BuildingDef] | None = None) -> Building:
    """Create a deterministic building instance from a footprint + seeded RNG."""
    rng = np.random.default_rng(int(rng_seed))
    if defs is None:
        defs = {}
    if def_key not in defs:
        def_key = "generic"
    bdef = defs.get(def_key, BuildingDef(key=def_key))
    variant = int(rng.integers(0, 10000))
    height = bdef.floor_count * bdef.floor_height
    vertices, indices = building_mesh(footprint, height)
    cx = sum(c[0] for c in footprint) / len(footprint)
    cz = sum(c[1] for c in footprint) / len(footprint)
    return Building(bid, def_key, variant, footprint, (cx, cz), height,
                    vertices, indices)

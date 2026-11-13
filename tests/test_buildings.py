"""Tests for procedural buildings and placeholder textures."""

import numpy as np
from citybuilder.world.buildings import (
    placeholder_texture, building_mesh, make_building, BuildingDef,
    PLACEHOLDER_TEXTURES,
)


def test_placeholder_textures():
    for name in PLACEHOLDER_TEXTURES:
        t = placeholder_texture(name)
        assert t.shape == (64, 64, 4)
        assert t.dtype == np.uint8
        assert not np.all(t == t[0, 0])  # not uniform (has detail)


def test_placeholder_texture_deterministic():
    a = placeholder_texture("brick")
    b = placeholder_texture("brick")
    assert np.array_equal(a, b)


def test_building_mesh_shapes():
    verts, idx = building_mesh([(0, 0), (8, 0), (8, 8), (0, 8)], 12.0)
    assert verts.shape[1] == 8  # x,y,z,nx,ny,nz,u,v
    assert verts.dtype == np.float32
    assert idx.dtype == np.uint32


def test_building_deterministic():
    fp = [(0, 0), (10, 0), (10, 10), (0, 10)]
    defs = {"generic": BuildingDef("generic", floor_count=5)}
    b1 = make_building(1, "generic", fp, 42, defs)
    b2 = make_building(1, "generic", fp, 42, defs)
    assert b1.variant == b2.variant
    assert b1.height == b2.height
    assert np.array_equal(b1.vertices, b2.vertices)

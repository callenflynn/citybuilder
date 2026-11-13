"""Tests for chunked terrain streaming."""

import numpy as np

from citybuilder.world.chunks import ChunkManager, build_chunk_mesh


def test_chunk_deterministic_and_cached():
    m = ChunkManager(seed=42, chunk_size=16, max_chunks=10)
    c1 = m.ensure(0, 0)
    c2 = m.get(0, 0)
    assert c1 is c2
    assert c1.heightmap.shape == (16, 16)


def test_chunk_different_seed_different_heightmap():
    m1 = ChunkManager(seed=1, chunk_size=16)
    m2 = ChunkManager(seed=2, chunk_size=16)
    assert not np.array_equal(m1.ensure(0, 0).heightmap,
                              m2.ensure(0, 0).heightmap)


def test_update_loads_around_camera():
    import numpy as np
    m = ChunkManager(seed=7, chunk_size=16, max_chunks=100)
    loaded = m.update(world_x=0.0, world_z=0.0, radius_chunks=1)
    keys = {(c.cx, c.cy) for c in loaded}
    assert (0, 0) in keys
    assert (-1, 0) in keys
    assert (0, -1) in keys
    assert m.chunk_count() == 9  # (2*1+1)^2


def test_update_evicts_beyond_max():
    m = ChunkManager(seed=1, chunk_size=16, max_chunks=4)
    m.update(world_x=0.0, world_z=0.0, radius_chunks=2)  # 25 chunks wanted
    assert m.chunk_count() <= 4


def test_build_chunk_mesh():
    m = ChunkManager(seed=1, chunk_size=8)
    chunk = m.ensure(0, 0)
    verts, idx = build_chunk_mesh(chunk)
    n = chunk.heightmap.shape[0]
    assert verts.shape == (n * n, 3)
    assert verts.dtype == np.float32
    assert idx.dtype == np.uint32
    # expected triangles: 2 per cell, 3 indices each
    assert idx.shape[0] == 2 * (n - 1) * (n - 1) * 3


def test_chunk_mesh_world_offset():
    m = ChunkManager(seed=1, chunk_size=8)
    chunk = m.ensure(1, 2)  # world offset (8, 16)
    verts, _ = build_chunk_mesh(chunk)
    # first vertex = lower-left corner of the chunk
    assert verts[0, 0] == 8.0   # x = cx*size
    assert verts[0, 2] == 16.0  # z = cy*size


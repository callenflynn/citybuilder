"""Chunked terrain streaming.

Terrain is a chunked heightmap. Chunks are generated deterministically from
(cx, cy, seed) via worldgen.generate_chunk; edits (terraforming/water) are
M1.5. The ChunkManager keeps an LRU cache of chunks around the camera and
reports which chunks are in range each frame so the renderer can draw them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .. import config
from .. import worldgen


@dataclass
class Chunk:
    cx: int
    cy: int
    heightmap: np.ndarray  # (chunk_size, chunk_size) float32
    last_used: int = 0


class ChunkManager:
    """Deterministic chunked terrain streaming around a camera position."""

    def __init__(self, seed: int = config.DEFAULT_SEED,
                 chunk_size: int = config.CHUNK_SIZE,
                 max_chunks: int = 64):
        self.seed = int(seed)
        self.chunk_size = int(chunk_size)
        self.max_chunks = int(max_chunks)
        self._chunks: dict[tuple[int, int], Chunk] = {}
        self._order: list[tuple[int, int]] = []  # LRU order (least first)
        self._frame = 0

    def _chunk_key(self, cx: int, cy: int) -> tuple[int, int]:
        return (int(cx), int(cy))

    def get(self, cx: int, cy: int) -> Chunk | None:
        return self._chunks.get(self._chunk_key(cx, cy))

    def ensure(self, cx: int, cy: int) -> Chunk:
        key = self._chunk_key(cx, cy)
        chunk = self._chunks.get(key)
        if chunk is None:
            hmap = worldgen.generate_chunk(cx, cy, self.seed, self.chunk_size)
            chunk = Chunk(cx, cy, hmap, last_used=self._frame)
            self._chunks[key] = chunk
            self._order.append(key)
            self._evict()
        else:
            chunk.last_used = self._frame
            self._order.remove(key)
            self._order.append(key)
        return chunk

    def _evict(self):
        while len(self._chunks) > self.max_chunks and self._order:
            key = self._order.pop(0)
            self._chunks.pop(key, None)

    def update(self, world_x: float, world_z: float,
               radius_chunks: int = 4) -> list[Chunk]:
        """Ensure chunks within radius_chunks of the world position are loaded.

        Returns the list of currently-cached chunks (to draw this frame).
        Unloads chunks far outside the radius.
        """
        self._frame += 1
        cx = int(math.floor(world_x / self.chunk_size))
        cy = int(math.floor(world_z / self.chunk_size))
        for dx in range(-radius_chunks, radius_chunks + 1):
            for dy in range(-radius_chunks, radius_chunks + 1):
                self.ensure(cx + dx, cy + dy)
        # Unload chunks outside an unload radius (slightly larger than load radius)
        unload_r = radius_chunks + 2
        to_remove = []
        for key, chunk in self._chunks.items():
            if (abs(chunk.cx - cx) > unload_r or
                    abs(chunk.cy - cy) > unload_r):
                to_remove.append(key)
        for key in to_remove:
            self._chunks.pop(key, None)
            if key in self._order:
                self._order.remove(key)
        return list(self._chunks.values())

    def chunk_count(self) -> int:
        return len(self._chunks)


def build_chunk_mesh(chunk: Chunk) -> tuple[np.ndarray, np.ndarray]:
    """Build a triangle mesh from a chunk heightmap.

    Returns (vertices, indices) where vertices are float32 (x, y, z) in world
    space and indices are uint32 triangle indices.
    """
    size = chunk.heightmap.shape[0]
    hmap = chunk.heightmap
    n = size
    # world offset of the chunk's lower-left corner
    ox = chunk.cx * size
    oz = chunk.cy * size
    # Include the full chunk interval so adjacent chunks share the boundary
    # at ox + size / oz + size rather than leaving a one-unit crack.
    xs = np.linspace(0, size, n, dtype=np.float32) + ox
    zs = np.linspace(0, size, n, dtype=np.float32) + oz
    X, Z = np.meshgrid(xs, zs)
    Y = hmap.astype(np.float32)
    vertices = np.stack([X, Y, Z], axis=-1).reshape(-1, 3).astype(np.float32)

    idx = []
    for i in range(n - 1):
        for j in range(n - 1):
            v00 = i * n + j
            v10 = (i + 1) * n + j
            v01 = i * n + (j + 1)
            v11 = (i + 1) * n + (j + 1)
            idx.append([v00, v01, v10])
            idx.append([v10, v01, v11])
    indices = np.array(idx, dtype=np.uint32).reshape(-1)
    return vertices, indices

"""Seeded procedural world generation (terrain heightmap, rivers, mountains).

Stub for M0/M1.5. Produces a heightmap chunk given (cx, cy, seed).
"""

from __future__ import annotations

import numpy as np


def generate_chunk(cx: int, cy: int, seed: int, chunk_size: int = 64) -> np.ndarray:
    """Return a (chunk_size, chunk_size) float32 heightmap for chunk (cx, cy).

    Deterministic in (cx, cy, seed). Placeholder noise until real terrain
    generation is implemented at M1.5.
    """
    import hashlib

    h = int(hashlib.sha256(f"{seed}:{cx}:{cy}".encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(h % (2**32))
    # Smooth-ish placeholder terrain: a few sine waves + noise.
    xs = np.linspace(0, 4, chunk_size, dtype=np.float32)
    ys = np.linspace(0, 4, chunk_size, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)
    hmap = (np.sin(X + h * 0.01) + np.cos(Y * 1.3 + h * 0.01)) * 0.5 + 0.5
    hmap += 0.2 * rng.normal(size=(chunk_size, chunk_size)).astype(np.float32)
    return hmap.astype(np.float32)

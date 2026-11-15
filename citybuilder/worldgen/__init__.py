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
    # Keep the first playable city on a stable ground plane.  The earlier
    # placeholder varied from below zero to almost two world units, while
    # roads and building foundations were flat; that caused roads to dive in
    # and out of the terrain and read as diagonal geometry corruption.  Leave
    # only a gentle variation for a little visual breakup until roads can
    # conform to a fully featured heightmap.
    # Use world coordinates rather than chunk-local coordinates.  Independent
    # per-chunk phases create visible cracks/z-fighting at every chunk edge.
    world_scale = max(float(chunk_size), 1.0)
    xs = (np.linspace(0, chunk_size, chunk_size, dtype=np.float32)
          + cx * chunk_size) / world_scale
    ys = (np.linspace(0, chunk_size, chunk_size, dtype=np.float32)
          + cy * chunk_size) / world_scale
    X, Y = np.meshgrid(xs, ys)
    seed_phase = float(seed % 997) * 0.01
    waves = (np.sin(X + seed_phase) + np.cos(Y * 1.3 + seed_phase)) * 0.5
    hmap = 0.08 + 0.025 * waves
    return hmap.astype(np.float32)

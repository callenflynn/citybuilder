"""World-space picking: mouse -> world ray -> road node. Pure math, no GPU.

The scene is rendered to an internal pixel buffer (INTERNAL_WIDTH x
INTERNAL_HEIGHT) and nearest-neighbour upscaled to the window. Mouse events
arrive in *window* pixels, so the first step maps them to NDC in the internal
viewport. We then unproject the click into a world-space ray and pick the road
node whose projected screen position is nearest the click (screen-space
radius), falling back to the road segment nearest to the ray.
"""

from __future__ import annotations

import math

import numpy as np

from . import config


def window_to_ndc(
    mx: float,
    my: float,
    win_w: int = config.WINDOW_WIDTH,
    win_h: int = config.WINDOW_HEIGHT,
    internal_w: int = config.INTERNAL_WIDTH,
    internal_h: int = config.INTERNAL_HEIGHT,
) -> tuple[float, float]:
    """Map a window pixel to NDC in the internal (pixel-art) viewport.

    The window is an integer nearest-neighbour upscale of the internal buffer,
    so we divide by the per-axis scale factor to reach internal pixels, then
    convert to NDC (y up).
    """
    scale_x = win_w / internal_w
    scale_y = win_h / internal_h
    px = mx / scale_x
    py = my / scale_y
    ndc_x = (px / internal_w) * 2.0 - 1.0
    ndc_y = 1.0 - (py / internal_h) * 2.0  # screen y down -> NDC y up
    return ndc_x, ndc_y


def unproject_ray(
    ndc_x: float,
    ndc_y: float,
    view: np.ndarray,
    proj: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Unproject an NDC point into a world-space (origin, direction) ray.

    Two NDC depths (near/far clip planes) are unprojected through the inverse
    of (proj @ view); the ray origin is the near point and the direction is
    the vector from near to far.
    """
    inv = np.linalg.inv((proj @ view).astype(np.float64))
    p_near = inv @ np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float64)
    p_far = inv @ np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float64)
    near = p_near[:3] / p_near[3]
    far = p_far[:3] / p_far[3]
    return near, (far - near)


def project_to_window(
    world_pos: tuple[float, float, float],
    view: np.ndarray,
    proj: np.ndarray,
    win_w: int = config.WINDOW_WIDTH,
    win_h: int = config.WINDOW_HEIGHT,
) -> tuple[float, float] | None:
    """Project a world-space point to window pixels, or None if behind camera."""
    v = np.array(
        [world_pos[0], world_pos[1], world_pos[2], 1.0], dtype=np.float64
    )
    clip = (proj @ view).astype(np.float64) @ v
    if abs(clip[3]) < 1e-9:
        return None
    ndc = clip[:3] / clip[3]
    if ndc[2] < -1.0 or ndc[2] > 1.0:
        return None
    sx = (ndc[0] + 1.0) * 0.5 * win_w
    sy = (1.0 - ndc[1]) * 0.5 * win_h
    return sx, sy


def point_ray_distance(
    point: tuple[float, float, float],
    origin: np.ndarray,
    direction: np.ndarray,
) -> float:
    """Perpendicular distance from a 3D point to a ray (clamped to origin)."""
    p = np.asarray(point, dtype=np.float64)
    o = np.asarray(origin, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64)
    n = float(np.linalg.norm(d))
    if n < 1e-12:
        return float(np.linalg.norm(p - o))
    d = d / n
    v = p - o
    t = max(0.0, float(np.dot(v, d)))
    closest = o + t * d
    return float(np.linalg.norm(p - closest))


def ray_segment_closest_point(
    origin: np.ndarray,
    direction: np.ndarray,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, tuple[float, float, float]]:
    """Closest point on segment [a, b] to the ray (origin, direction).

    Uses the classic infinite-line closest-point solution (Real-Time Collision
    Detection), then clamps the ray parameter to >= 0 and the segment parameter
    to [0, 1]. Returns (u, point) where u is the segment parameter.
    """
    o = np.asarray(origin, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64)
    pa = np.asarray(a, dtype=np.float64)
    pb = np.asarray(b, dtype=np.float64)
    seg = pb - pa
    w0 = o - pa

    d_dot_d = float(d @ d)
    seg_dot_seg = float(seg @ seg)
    d_dot_seg = float(d @ seg)
    d_dot_w0 = float(d @ w0)
    seg_dot_w0 = float(seg @ w0)

    if d_dot_d < 1e-12:
        # Degenerate ray: just project onto the segment.
        t = 0.0
        if seg_dot_seg > 1e-12:
            t = min(1.0, max(0.0, seg_dot_w0 / seg_dot_seg))
        point = pa + t * seg
        return t, (float(point[0]), float(point[1]), float(point[2]))
    if seg_dot_seg < 1e-12:
        # Degenerate segment: point a, distance to ray.
        point = pa
        return 0.0, (float(point[0]), float(point[1]), float(point[2]))

    denom = d_dot_d * seg_dot_seg - d_dot_seg * d_dot_seg
    if abs(denom) < 1e-12:
        u = 0.0
    else:
        u = (d_dot_d * seg_dot_w0 - d_dot_seg * d_dot_w0) / denom
    u = min(1.0, max(0.0, u))
    point = pa + u * seg
    return u, (float(point[0]), float(point[1]), float(point[2]))


def pick_road_node(
    road_graph,
    camera,
    mx: float,
    my: float,
    radius_px: float = 10.0,
    max_world_dist: float = 20.0,
) -> int | None:
    """Return the id of the road node under the mouse, else None.

    Strategy:
      1. Unproject the window pixel to a world ray.
      2. Any node whose projected screen position is within `radius_px` of the
         click is a candidate; the closest wins.
      3. Otherwise, the road segment nearest to the ray wins, returning its
         nearest endpoint node -- but only if the ray passes within
         `max_world_dist` world units of it. Isolated nodes (no segments) are
         also considered against the ray.
    """
    if not road_graph.nodes:
        return None

    view = camera.view_matrix()
    proj = camera.projection_matrix()
    ndc_x, ndc_y = window_to_ndc(mx, my)
    origin, direction = unproject_ray(ndc_x, ndc_y, view, proj)

    # 1) Screen-space node hit (closest within radius).
    best_screen = radius_px
    screen_hit: int | None = None
    for nid, node in road_graph.nodes.items():
        sp = project_to_window((node.pos[0], 0.0, node.pos[1]), view, proj)
        if sp is None:
            continue
        dist = math.hypot(sp[0] - mx, sp[1] - my)
        if dist < best_screen:
            best_screen = dist
            screen_hit = nid
    if screen_hit is not None:
        return screen_hit

    # 2) Nearest road geometry to the ray, within a world-space threshold.
    best_dist = math.inf
    best_id: int | None = None

    for nid, node in road_graph.nodes.items():
        rd = point_ray_distance((node.pos[0], 0.0, node.pos[1]), origin, direction)
        if rd < best_dist:
            best_dist = rd
            best_id = nid

    for seg in road_graph.segments.values():
        a = road_graph.nodes[seg.from_node].pos
        b = road_graph.nodes[seg.to_node].pos
        _, point = ray_segment_closest_point(
            origin, direction, (a[0], 0.0, a[1]), (b[0], 0.0, b[1])
        )
        rd = point_ray_distance(point, origin, direction)
        # Nearest endpoint of this segment.
        da = point_ray_distance((a[0], 0.0, a[1]), origin, direction)
        db = point_ray_distance((b[0], 0.0, b[1]), origin, direction)
        endpoint = seg.from_node if da <= db else seg.to_node
        if rd < best_dist:
            best_dist = rd
            best_id = endpoint

    if best_id is not None and best_dist <= max_world_dist:
        return best_id
    return None

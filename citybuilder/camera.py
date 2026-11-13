"""Camera: smooth rotation and zoom around a fixed tilt angle.

The camera orbits a target point. Yaw (horizontal rotation) and distance
(zoom) are interpolated smoothly each frame so the pixel look stays
consistent when the camera moves. Tilt (pitch) is fixed.

The position is recomputed from (yaw, distance, target) each frame and can be
snapped to the pixel grid (see rendering) to avoid shimmering.
"""

from __future__ import annotations

import math

from . import config


class Camera:
    def __init__(self):
        self.target = [0.0, 0.0, 0.0]  # orbit center (world)
        self.yaw = 0.0                  # radians, 0 = looking along +X
        self.distance = 40.0            # zoom
        self.tilt = math.radians(35.0)  # fixed tilt above horizon

        # Smoothing: target values that the camera interpolates toward.
        self._target_yaw = self.yaw
        self._target_distance = self.distance
        self._target_target = list(self.target)

        # How fast the camera catches up (1.0 = instant, 0 = frozen).
        self.smoothing = 0.15

    # -- input-driven requests -----------------------------------------------
    def rotate(self, delta_yaw: float) -> None:
        self._target_yaw += delta_yaw

    def zoom(self, factor: float) -> None:
        """Multiply distance by factor (>1 zooms in, <1 zooms out)."""
        self._target_distance *= factor

    def pan(self, dx: float, dy: float) -> None:
        """Move the orbit target in screen-space right/up directions."""
        right = [math.cos(self.yaw), 0.0, math.sin(self.yaw)]
        # screen "up" in world = up-projected, orthogonal to right and view
        up = [-math.sin(self.yaw) * math.sin(self.tilt),
              math.cos(self.tilt),
              -math.cos(self.yaw) * math.sin(self.tilt)]
        self._target_target[0] += right[0] * dx + up[0] * dy
        self._target_target[1] += right[1] * dx + up[1] * dy
        self._target_target[2] += right[2] * dx + up[2] * dy

    # -- per-frame update -------------------------------------------------------
    def update(self, dt: float = 1.0 / 60.0) -> None:
        # Exponential smoothing toward targets (frame-rate independent-ish).
        k = 1.0 - math.exp(-self.smoothing * 60.0 * dt)
        self.yaw += (self._target_yaw - self.yaw) * k
        self.distance += (self._target_distance - self.distance) * k
        for i in range(3):
            self.target[i] += (self._target_target[i] - self.target[i]) * k
        # clamp zoom
        self.distance = max(5.0, min(self.distance, 200.0))

    # -- derived view data ------------------------------------------------------
    def position(self) -> tuple[float, float, float]:
        """World-space camera position."""
        cx = math.cos(self.yaw) * math.cos(self.tilt)
        cy = math.sin(self.tilt)
        cz = math.sin(self.yaw) * math.cos(self.tilt)
        return (
            self.target[0] + self.distance * cx,
            self.target[1] + self.distance * cy,
            self.target[2] + self.distance * cz,
        )

    def view_matrix(self):
        """Return a (4,4) float32 look-at view matrix (numpy)."""
        import numpy as np

        eye = np.array(self.position(), dtype=np.float32)
        center = np.array(self.target, dtype=np.float32)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        f = center - eye
        f = f / np.linalg.norm(f)
        r = np.cross(f, up)
        r = r / np.linalg.norm(r)
        u = np.cross(r, f)
        m = np.eye(4, dtype=np.float32)
        m[0, 0:3] = r
        m[1, 0:3] = u
        m[2, 0:3] = -f
        m[0, 3] = -np.dot(r, eye)
        m[1, 3] = -np.dot(u, eye)
        m[2, 3] = np.dot(f, eye)
        return m

    def projection_matrix(self) -> "np.ndarray":
        """Perspective projection matched to the internal aspect ratio."""
        import numpy as np

        aspect = config.INTERNAL_WIDTH / config.INTERNAL_HEIGHT
        fov_y = math.radians(45.0)
        near, far = 0.1, 1000.0
        f = 1.0 / math.tan(fov_y / 2.0)
        m = np.zeros((4, 4), dtype=np.float32)
        m[0, 0] = f / aspect
        m[1, 1] = f
        m[2, 2] = (far + near) / (near - far)
        m[2, 3] = (2 * far * near) / (near - far)
        m[3, 2] = -1.0
        return m

"""Rendering layer (wgpu-py).

Draws the 3D scene into a low-res offscreen target, applies post-processing
(outline from depth/normals, lighting, palette quantization), then nearest-
neighbor upscales to the window.
"""

from .renderer import Renderer

__all__ = ["Renderer"]

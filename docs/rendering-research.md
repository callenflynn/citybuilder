# Rendering references used for the visual correction

The current renderer was compared against these open-source projects on 2026-11-14:

- [3d.city README](https://github.com/lo-th/3d.city) describes a 3D city builder using Three.js/WebGL2/WebGPU, custom shaders, textures, and 3D models. It separates the simulation engine from rendering through a worker boundary.
- [OpenTTD `viewport.cpp`](https://raw.githubusercontent.com/OpenTTD/OpenTTD/master/src/viewport.cpp) shows a deliberate viewport transform and row/column traversal for landscape tiles. It computes visible map coordinates, draws the ground in deterministic order, then handles buildings and sortable sprites separately.
- [OpenTTD `viewport_func.h`](https://raw.githubusercontent.com/OpenTTD/OpenTTD/master/src/viewport_func.h) exposes explicit viewport zoom, screen-to-tile translation, and sortable 3D sprite submission APIs.
- [Unknown Horizons README](https://github.com/unknown-horizons/unknown-horizons) describes a 2D city-building/RTS architecture using a dedicated engine and data-driven content; it is useful as a separation-of-simulation-and-presentation reference, but not as a direct 3D renderer model.

The relevant implementation lessons are: keep the ground representation stable and ordered, keep buildings as distinct depth-tested objects, make camera/viewport transforms explicit, and avoid high-frequency textures as a substitute for a readable pixel-art material. The user-provided screenshot showed long diagonal geometry/texture strips, so the first code correction targets the building material rather than adding more post-processing.

"""Pixel City Builder - M0/M1 entry point.

Run: python -m citybuilder (from project root with .venv active)
Controls:
  Arrows: rotate camera
  Up/Down: zoom
  R: reset camera
  B: toggle building placement mode
  Mouse click-drag: place grid-snapped roads (2-click with preview)
  Esc: quit
"""

from __future__ import annotations

import sys
import time
import math
import os
import argparse

from rendercanvas.auto import RenderCanvas, loop

import wgpu

from . import config
from .camera import Camera
from .rendering import Renderer
from .sim.loop import SimLoop, SimConfig
from .world.chunks import ChunkManager
from .world.lots import LotGenerator
from .world.roadgraph import RoadGraph
from .world.buildings import make_building, BuildingDef
from . import picking


class App:
    def __init__(self):
        self.canvas = RenderCanvas(
            size=(config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            title="citybuilder (M1)",
            update_mode="continuous",
            max_fps=config.RENDER_FPS,
        )
        self.context = self.canvas.get_context("wgpu")
        self.adapter = wgpu.gpu.request_adapter_sync(
            power_preference="high-performance")
        self.device = self.adapter.request_device_sync()
        self.context.configure(device=self.device, format="bgra8unorm")

        self.renderer = Renderer(self.device, self.context)
        self.camera = Camera()
        self.sim = SimLoop(SimConfig(tick_rate=config.SIM_TICK_RATE,
                                     seed=config.DEFAULT_SEED))
        self.chunk_mgr = ChunkManager(seed=config.DEFAULT_SEED)
        self.road_graph = RoadGraph()
        self.lot_gen = LotGenerator(self.road_graph)
        self.buildings: dict = {}
        self._last_chunk_keys: frozenset | None = None

        # interactive state
        self._road_mode = False
        self._road_start_px = None
        self._road_preview_node = None
        self._building_mode = False

        self._accum = 0.0
        self._dt = 1.0 / config.RENDER_FPS

        self._frame_count = 0
        self._fps_t = 0.0
        self._fps = 0.0
        self._tick_ms = 0.0

        self._build_demo_city()

        # register pointer events
        self.canvas.add_event_handler(self._handle_pointer,
                                      "key_down",
                                      "pointer_down", "pointer_move", "pointer_up")

    def _handle_pointer(self, event):
        """Dispatch a rendercanvas event dict.

        rendercanvas events are plain dicts: {"event_type": ..., ...}.
        """
        etype = event["event_type"]
        if etype == "key_down":
            self._on_key(event["key"])
        elif etype == "pointer_down":
            self._on_pointer_down(event)
        elif etype == "pointer_move":
            self._on_pointer_move(event)
        elif etype == "pointer_up":
            self._on_pointer_up(event)

    # --- keyboard -------------------------------------------------------
    def _on_key(self, key: str):
        if key == "Escape":
            loop.stop()
        elif key == "ArrowLeft":
            self.camera.rotate(-0.05)
        elif key == "ArrowRight":
            self.camera.rotate(0.05)
        elif key == "ArrowUp":
            self.camera.zoom(1.1)
        elif key == "ArrowDown":
            self.camera.zoom(0.9)
        elif key == "r":
            self.camera = Camera()
        elif key == "b":
            self._building_mode = not self._building_mode
            print(f"Building mode: {'ON' if self._building_mode else 'OFF'}")

    # --- pointer --------------------------------------------------------
    def _on_pointer_down(self, event):
        x, y = event["x"], event["y"]
        self._road_mode = True
        self._road_start_px = (x, y)
        self._road_preview_node = self._snap_mouse_to_road(x, y)

    def _on_pointer_move(self, event):
        if not self._road_mode:
            return
        x, y = event["x"], event["y"]
        self._road_preview_node = self._snap_mouse_to_road(x, y)

    def _on_pointer_up(self, event):
        self._road_mode = False
        self._place_road_from_preview()
        self._road_start_px = None
        self._road_preview_node = None

    # --- picking --------------------------------------------------------
    # Real camera-based pick: unproject the mouse into a world ray and find
    # the road node (or nearest segment endpoint) under the click.
    def _snap_mouse_to_road(self, mx: int, my: int) -> int | None:
        return picking.pick_road_node(self.road_graph, self.camera, mx, my)

    # --- road placement ------------------------------------------------
    def _place_road_from_preview(self):
        if self._road_start_px is None or self._road_preview_node is None:
            self._road_mode = False
            return
        end_node = self._road_preview_node
        # pick the start node nearest to the original click (the pointer-down
        # position), so a click-drag places a segment from where the user
        # pressed to where they released.
        start_node = picking.pick_road_node(
            self.road_graph, self.camera, *self._road_start_px)
        if start_node is None or end_node != start_node:
            new_seg = self.road_graph.add_segment(start_node, end_node)
            if new_seg is not None:
                self.lot_gen.generate()
                import numpy as np
                from citybuilder.world.buildings import BuildingDef
                bdefs = {'generic': BuildingDef('generic', floor_count=4)}
                bid = 0
                for lot in self.lot_gen.generate().values():
                    self.buildings[bid] = make_building(
                        bid, 'generic', lot.footprint, 42 + bid, bdefs)
                    bid += 1
        self._road_mode = False

    # --- building mode -------------------------------------------------
    def _toggle_building_mode(self):
        self._building_mode = not self._building_mode
        print(f"Building mode: {'ON' if self._building_mode else 'OFF'}")

    # --- demo city -------------------------------------------------------
    def _build_demo_city(self):
        g = self.road_graph
        # A deterministic 7x7 road grid gives the first playable scene enough
        # frontage to exercise chunk streaming, road ribbons, and procedural
        # growth without introducing a second world-generation system.
        grid = list(range(-96, 97, 32))
        for z in grid:
            for x0, x1 in zip(grid, grid[1:]):
                g.add_segment(g.add_node(x0, z), g.add_node(x1, z))
        for x in grid:
            for z0, z1 in zip(grid, grid[1:]):
                g.add_segment(g.add_node(x, z0), g.add_node(x, z1))
        self.lot_gen.generate()
        from citybuilder.world.buildings import BuildingDef
        bdefs = {
            "generic": BuildingDef("generic", floor_count=4),
            "low": BuildingDef("low", floor_count=2, floor_height=3.5),
            "mid": BuildingDef("mid", floor_count=6, floor_height=3.5),
            "tower": BuildingDef("tower", floor_count=10, floor_height=3.5),
        }
        bid = 0
        # Fill the 6x6 blocks between roads.  Six small footprints per block
        # gives 216 buildings while keeping every footprint close to a road
        # frontage and leaving enough gaps for the terrain to show through.
        for block_z in range(-96, 96, 32):
            for block_x in range(-96, 96, 32):
                block_center_x = block_x + 16
                block_center_z = block_z + 16
                for dx, dz in ((-8, -8), (0, -8), (8, -8),
                               (-8, 8), (0, 8), (8, 8)):
                    center_x = block_center_x + dx
                    center_z = block_center_z + dz
                    half = 3.0
                    footprint = [
                        (center_x - half, center_z - half),
                        (center_x + half, center_z - half),
                        (center_x + half, center_z + half),
                        (center_x - half, center_z + half),
                    ]
                    # Keep the tallest demo buildings away from the outer
                    # road ends so rear-angle checks retain terrain visibility.
                    central = abs(center_x) < 20.0 and abs(center_z) < 20.0
                    if central and bid % 11 == 0:
                        key = "tower"
                    elif bid % 3 == 0:
                        key = "low"
                    elif bid % 3 == 1:
                        key = "mid"
                    else:
                        key = "generic"
                    self.buildings[bid] = make_building(
                        bid, key, footprint, 42 + bid, bdefs)
                    bid += 1

    # --- frame -----------------------------------------------------------
    def on_draw(self, dt: float = 0.0):
        t0 = time.perf_counter()
        self._accum += dt
        steps = 0
        while self._accum >= self._dt and steps < config.MAX_SUBSTEPS:
            self.sim.tick_once()
            self._accum -= self._dt
            steps += 1
        self._tick_ms = (time.perf_counter() - t0) * 1000.0
        self.camera.update(dt)
        cam_x, _, cam_z = self.camera.position()

        chunks = self.chunk_mgr.update(cam_x, cam_z, radius_chunks=3)
        chunk_keys = frozenset((c.cx, c.cy) for c in chunks)
        scene_dirty = (chunk_keys != self._last_chunk_keys)
        if scene_dirty or not self._gpu_scene_uploaded():
            self.renderer.set_scene(
                chunks,
                self.road_graph.segment_list(),
                list(self.buildings.values()),
            )
            self._last_chunk_keys = chunk_keys

        view = self.camera.view_matrix()
        proj = self.camera.projection_matrix()

        self._frame_count += 1
        self._fps_t += dt
        if self._fps_t >= 0.5:
            self._fps = self._frame_count / self._fps_t
            self._frame_count = 0
            self._fps_t = 0.0

        debug_lines = [
            (f"fps={self._fps:5.1f}", 1, 0),
            (f"tick_ms={self._tick_ms:5.2f}", 1, 1),
            (f"sim_tick={self.sim.tick}", 1, 2),
            (f"chunks={len(chunks)}", 1, 3),
            (f"roads={self.road_graph.num_segments()}", 1, 4),
            (f"buildings={len(self.buildings)}", 1, 5),
        ]
        self.renderer.draw(view, proj, debug_lines)

    def _gpu_scene_uploaded(self):
        return bool(self.renderer._gpu_buffers)

    def run(self):
        self.canvas.request_draw(self.on_draw)
        loop.run()


def _build_headless_app():
    """Build an App-like object with a GPU device but no window/canvas.

    Reuses App._build_demo_city for the scene. capture_frame() does not touch
    self.canvas or self.context, so a minimal object is enough.
    """
    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    device = adapter.request_device_sync()

    app = App.__new__(App)
    app.device = device
    app.camera = Camera()
    app.sim = SimLoop(SimConfig(tick_rate=config.SIM_TICK_RATE,
                                seed=config.DEFAULT_SEED))
    app.chunk_mgr = ChunkManager(seed=config.DEFAULT_SEED)
    app.road_graph = RoadGraph()
    app.lot_gen = LotGenerator(app.road_graph)
    app.buildings = {}
    app.renderer = Renderer(device, context=None)
    app._build_demo_city()
    return app


def render_screenshots(outdir, angles, distance, pitch):
    """Render the demo city headless at each camera angle; return PNG paths."""
    import numpy as np
    os.makedirs(outdir, exist_ok=True)
    app = _build_headless_app()
    paths = []
    for yaw_deg in angles:
        app.camera.yaw = math.radians(yaw_deg)
        app.camera.distance = distance
        app.camera.tilt = math.radians(pitch)
        app.camera.update(0.0)
        cam_x, _, cam_z = app.camera.position()
        chunks = app.chunk_mgr.update(cam_x, cam_z, radius_chunks=3)
        app.renderer.set_scene(chunks, app.road_graph.segment_list(),
                               list(app.buildings.values()))
        app.renderer.set_view_proj(app.camera.view_matrix(),
                                   app.camera.projection_matrix())
        path = os.path.join(outdir, "city_yaw%d.png" % int(yaw_deg))
        rgba = app.renderer.capture_frame(path)
        assert rgba.dtype == np.uint8, rgba.dtype
        assert rgba.ndim == 3 and rgba.shape[2] == 4, rgba.shape
        std = float(rgba.std())
        quant = (rgba[:, :, :3] // 64).reshape(-1, 3)
        distinct = len(np.unique(quant, axis=0))
        h, w = rgba.shape[:2]
        top = rgba[:h // 3, :, :3].mean(axis=(0, 1)).round(1)
        mid = rgba[h // 3:2 * h // 3, :, :3].mean(axis=(0, 1)).round(1)
        bot = rgba[2 * h // 3:, :, :3].mean(axis=(0, 1)).round(1)
        print("%s: shape=%s std=%.2f distinct=%d top=%s mid=%s bot=%s"
              % (os.path.basename(path), rgba.shape, std, distinct, top, mid, bot))
        assert std > 0, "flat image"
        assert distinct >= 3, "fewer than 3 dominant colors"
        paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser(prog="citybuilder")
    ap.add_argument("--screenshot", metavar="OUTDIR", default=None,
                    help="render the demo city headless and write PNGs to OUTDIR")
    ap.add_argument("--angles", default="0,45,90",
                    help="comma-separated camera yaw degrees (default 0,45,90)")
    ap.add_argument("--distance", type=float, default=150.0,
                    help="camera distance (zoom)")
    ap.add_argument("--pitch", type=float, default=35.0,
                    help="camera tilt in degrees")
    args = ap.parse_args()

    if args.screenshot is not None:
        angles = [float(a) for a in args.angles.split(",") if a.strip()]
        render_screenshots(args.screenshot, angles, args.distance, args.pitch)
        return 0

    try:
        app = App()
        app.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

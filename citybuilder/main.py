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


class App:
    def __init__(self):
        self.canvas = RenderCanvas(
            size=(config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            title="Pixel City Builder (M1)",
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
                                      "pointer_down", "pointer_move", "pointer_up")

    # ------------------------------------------------------------------
    # Event dispatch
    # ---------------------------------------------------------------
    def _handle_pointer(self, event):
        etype = event.type
        key = event.key
        if etype == "key_down":
            self._on_key(key)
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
        elif key == "KeyR":
            self.camera = Camera()
        elif key == "KeyB":
            self._building_mode = not self._building_mode
            print(f"Building mode: {'ON' if self._building_mode else 'OFF'}")

    # --- pointer --------------------------------------------------------
    def _on_pointer_down(self, event):
        x, y = event.x, event.y
        self._road_mode = True
        self._road_start_px = (x, y)
        self._road_preview_node = self._snap_mouse_to_road(x, y)

    def _on_pointer_move(self, event):
        if not self._road_mode:
            return
        x, y = event.x, event.y
        self._road_preview_node = self._snap_mouse_to_road(x, y)

    def _on_pointer_up(self, event):
        self._road_mode = False
        self._place_road_from_preview()
        self._road_start_px = None
        self._road_preview_node = None

    # --- picking --------------------------------------------------------
    # world -> rough screen conversion: we approximate by comparing world dist
    # to a hardcoded snap radius and accepting the first node that falls within.
    def _snap_mouse_to_road(self, mx: int, my: int) -> int | None:
        if not self.road_graph.nodes:
            return None
        for nid, npos in self.road_graph.nodes.items():
            # rough world-distance check; 20 world units roughly maps to
            # the click radius in the demo viewport.
            if (npos[0] * npos[0] + npos[1] * npos[1]) < 400:
                return nid
        return None

    # --- road placement ------------------------------------------------
    def _place_road_from_preview(self):
        if self._road_start_px is None or self._road_preview_node is None:
            self._road_mode = False
            return
        end_node = self._road_preview_node
        # pick start node nearest to the original click area (approximate)
        start_node = min(self.road_graph.nodes.keys(),
                         key=lambda n: math.hypot(
                             self.road_graph.nodes[n].pos[0],
                             self.road_graph.nodes[n].pos[1]))
        if end_node != start_node:
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
        a = g.add_node(-40.0, 0.0)
        b = g.add_node(40.0, 0.0)
        g.add_segment(a, b)
        c = g.add_node(0.0, -40.0)
        d = g.add_node(0.0, 40.0)
        g.add_segment(c, d)
        self.lot_gen.generate()
        import numpy as np
        from citybuilder.world.buildings import BuildingDef
        bdefs = {
            "generic": BuildingDef("generic", floor_count=4),
            "tower": BuildingDef("tower", floor_count=10, floor_height=3.5),
        }
        bid = 0
        for lot in self.lot_gen.generate().values():
            key = "tower" if (bid % 7 == 0) else "generic"
            self.buildings[bid] = make_building(
                bid, key, lot.footprint, 42 + bid, bdefs)
            bid += 1

    # --- frame -----------------------------------------------------------
    def on_draw(self, dt: float):
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


def main():
    try:
        app = App()
        app.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

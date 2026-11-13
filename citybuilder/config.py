"""Project-wide configuration for Pixel City Builder.

Open item (from project plan): the exact internal resolution (480x270 or 640x360)
and whether the player can change it. Defaults here are changeable at runtime
and stored per-city in the save manifest once save/load exists (M1.5).
"""

# --- Rendering ---
# Internal (pixel-art) render buffer size. The scene is drawn here then
# nearest-neighbor upscaled to the window.
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360

# Window size. Should be an integer multiple of the internal size where
# possible for crisp nearest-neighbor scaling.
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# Target frames per second for the render loop.
RENDER_FPS = 60

# --- Simulation (fixed-tick, deterministic) ---
# Fixed simulation tick rate (Hz). The sim advances in integer tick steps,
# never by wall-clock delta, so replays are deterministic.
SIM_TICK_RATE = 60
SIM_DT = 1.0 / SIM_TICK_RATE  # seconds per tick (fixed)

# Default world seed (used when none is provided).
DEFAULT_SEED = 0xC071_B73D

# Maximum number of sim ticks to run per frame when catching up.
# Prevents a spiral of death if the sim temporarily lags.
MAX_SUBSTEPS = 5

# --- World / chunks ---
# Chunk size in world units. Terrain heightmap and edits are stored per chunk.
CHUNK_SIZE = 64

# --- Roads ---
# Grid snap size for grid-snapped road placement.
ROAD_GRID_SIZE = 8.0

# --- Data / content ---
# Directory (relative to project root) holding JSON/TOML city content definitions.
CONTENT_DIR = "citybuilder/data/citydefs"

# --- Platform ---
PLATFORM = "linux"


def window_scale() -> int:
    """Integer nearest-neighbor scale factor (window / internal)."""
    sx = WINDOW_WIDTH // INTERNAL_WIDTH
    sy = WINDOW_HEIGHT // INTERNAL_HEIGHT
    return min(sx, sy)

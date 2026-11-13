"""Fixed-tick, deterministic simulation loop.

Headless-capable: the loop advances the simulation by a fixed number of
ticks per frame and never depends on wall-clock time. This makes replays
deterministic given (seed, input log).

The sim only does detailed work near developed areas; that chunk-aware
culling is stubbed here and filled in at M1/M1.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rng import RNG
from .ecs import World


@dataclass
class SimConfig:
    tick_rate: int = 60
    seed: int = 0xC071_B73D
    max_substeps: int = 5


@dataclass
class SimState:
    tick: int = 0
    rng: RNG = field(default_factory=lambda: RNG(0xC071_B73D))
    # Inputs applied this tick (from the input log / player). Kept ordered
    # and deterministic.
    inputs: list = field(default_factory=list)


class SimLoop:
    """Runs systems in a fixed order every tick.

    Systems are registered callables ``system(world, state, tick) -> None``.
    They run in registration order for stable iteration.
    """

    def __init__(self, config: SimConfig | None = None):
        self.config = config or SimConfig()
        self.state = SimState(tick=0, rng=RNG(self.config.seed))
        self.world = World()
        self._systems: list = []

    @property
    def tick(self) -> int:
        return self.state.tick

    def register_system(self, system) -> None:
        self._systems.append(system)

    def tick_once(self) -> None:
        """Advance exactly one simulation tick."""
        state = self.state
        world = self.world
        tick = state.tick
        for system in self._systems:
            system(world, state, tick)
        state.tick = tick + 1

    def run(self, num_ticks: int) -> None:
        """Advance ``num_ticks`` ticks (headless / no rendering)."""
        for _ in range(num_ticks):
            self.tick_once()

    def snapshot(self) -> dict:
        """Deterministic snapshot for replay/comparison testing."""
        return {
            "tick": self.state.tick,
            "rng_state": self.state.rng.state,
            "num_entities": self.world.num_entities(),
        }

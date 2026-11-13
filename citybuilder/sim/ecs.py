"""Entity-Component System with flat numpy arrays.

Components are stored as contiguous flat arrays per component type; systems
process them in bulk. Entities are slot indices plus a generation counter so
that handles stay valid across deletions.

This is the Python reference. The Rust port exposes identical state as
NumPy arrays so Python debug tools can inspect it, and comparison tests can
check Python vs Rust outputs tick-by-tick.
"""

from __future__ import annotations

import numpy as np

from .rng import RNG


class Entity:
    """Opaque handle to an entity. Compare with ==; do not fabricate."""

    __slots__ = ("_slot", "_generation")

    def __init__(self, slot: int, generation: int):
        self._slot = int(slot)
        self._generation = int(generation)

    @property
    def slot(self) -> int:
        return self._slot

    @property
    def generation(self) -> int:
        return self._generation

    def __eq__(self, other) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self._slot == other._slot and self._generation == other._generation

    def __hash__(self) -> int:
        return hash((self._slot, self._generation))

    def __repr__(self) -> str:
        return f"Entity(slot={self._slot}, gen={self._generation})"


class ComponentRegistry:
    """Maps component names to their flat array storage."""

    def __init__(self):
        self._names: list[str] = []
        self._dtypes: dict[str, np.dtype] = {}
        self._data: dict[str, np.ndarray] = {}
        self._capacity = 0

    def register(self, name: str, dtype, shape=()):
        if name in self._dtypes:
            raise KeyError(f"component {name!r} already registered")
        self._names.append(name)
        self._dtypes[name] = np.dtype(dtype)
        # Placeholder data at the current capacity so _ensure_capacity can
        # resize every registered component (including this new one).
        base = () if not shape else shape
        self._data[name] = np.zeros((self._capacity,) + base, dtype=self._dtypes[name])
        self._ensure_capacity(max(self._capacity, 1))

    def _ensure_capacity(self, capacity: int):
        if capacity <= self._capacity:
            return
        new_cap = max(capacity, self._capacity * 2 if self._capacity else 8)
        for name in self._names:
            arr = self._data[name]
            if arr.ndim == 1:
                new_arr = np.zeros(new_cap, dtype=arr.dtype)
            else:
                new_arr = np.zeros((new_cap,) + arr.shape[1:], dtype=arr.dtype)
            new_arr[: self._capacity] = arr
            self._data[name] = new_arr
        self._capacity = new_cap

    def __len__(self) -> int:
        return self._capacity


class World:
    """ECS world. Components are flat numpy arrays indexed by entity slot."""

    def __init__(self):
        self._registry = ComponentRegistry()
        self._alive = np.zeros(0, dtype=bool)
        self._generation = np.zeros(0, dtype=np.uint32)
        self._free_slots: list[int] = []
        self._next_slot = 0

    # -- component registration -------------------------------------------------
    def register_component(self, name: str, dtype, shape=()) -> None:
        self._registry.register(name, dtype, shape)
        self._grow_entities(self._registry._capacity)

    def _grow_entities(self, capacity: int):
        if capacity <= self._alive.shape[0]:
            return
        new_alive = np.zeros(capacity, dtype=bool)
        new_alive[: self._alive.shape[0]] = self._alive
        self._alive = new_alive
        new_gen = np.zeros(capacity, dtype=np.uint32)
        new_gen[: self._generation.shape[0]] = self._generation
        self._generation = new_gen

    # -- entities ----------------------------------------------------------------
    def create_entity(self) -> Entity:
        if self._free_slots:
            slot = self._free_slots.pop()
        else:
            slot = self._next_slot
            self._next_slot += 1
            self._grow_entities(slot + 1)
        self._alive[slot] = True
        self._generation[slot] += 1
        return Entity(slot, int(self._generation[slot]))

    def destroy_entity(self, entity: Entity) -> None:
        if not self.is_alive(entity):
            return
        self._alive[entity.slot] = False
        self._free_slots.append(entity.slot)

    def is_alive(self, entity: Entity) -> bool:
        if entity.slot >= self._alive.shape[0]:
            return False
        return bool(self._alive[entity.slot]) and self._generation[entity.slot] == entity.generation

    def num_entities(self) -> int:
        return int(self._alive.sum())

    # -- components --------------------------------------------------------------
    def add_component(self, entity: Entity, name: str, value) -> None:
        if not self.is_alive(entity):
            raise ValueError(f"entity {entity} is not alive")
        if name not in self._registry._data:
            raise KeyError(f"component {name!r} not registered")
        self._registry._data[name][entity.slot] = value

    def get_component(self, entity: Entity, name: str):
        if not self.is_alive(entity):
            raise ValueError(f"entity {entity} is not alive")
        return self._registry._data[name][entity.slot]

    def has_component(self, entity: Entity, name: str) -> bool:
        if not self.is_alive(entity):
            return False
        return name in self._registry._data

    def component_array(self, name: str) -> np.ndarray:
        return self._registry._data[name]

    def component_names(self) -> list[str]:
        return list(self._registry._names)

    # -- iteration helpers -------------------------------------------------------
    def alive_slots(self) -> np.ndarray:
        """Indices of currently-alive entities (stable ascending order)."""
        return np.flatnonzero(self._alive)

    def entities_with(self, *names: str) -> np.ndarray:
        """Alive slots (component presence bitmask can be added later)."""
        return self.alive_slots()


class Query:
    """Bulk read of one or more component arrays over alive slots."""

    def __init__(self, world: World, names: tuple[str, ...]):
        self.world = world
        self.names = names
        self.arrays = [world.component_array(n) for n in names]

    def slots(self) -> np.ndarray:
        return self.world.alive_slots()

    def __iter__(self):
        slots = self.slots()
        for slot in slots:
            yield int(slot), tuple(arr[slot] for arr in self.arrays)

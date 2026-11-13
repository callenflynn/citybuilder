"""Tests for the ECS (flat numpy arrays)."""

import numpy as np
from citybuilder.sim.ecs import World, Entity


def test_create_and_destroy_entity():
    world = World()
    world.register_component("position", np.float32, shape=(3,))
    e1 = world.create_entity()
    e2 = world.create_entity()
    assert world.num_entities() == 2
    assert world.is_alive(e1) and world.is_alive(e2)
    world.destroy_entity(e1)
    assert not world.is_alive(e1)
    assert world.is_alive(e2)
    assert world.num_entities() == 1


def test_component_roundtrip():
    world = World()
    world.register_component("position", np.float32, shape=(3,))
    e = world.create_entity()
    world.add_component(e, "position", np.array([1.0, 2.0, 3.0], dtype=np.float32))
    got = world.get_component(e, "position")
    np.testing.assert_array_equal(got, np.array([1.0, 2.0, 3.0], dtype=np.float32))


def test_query_bulk_read():
    world = World()
    world.register_component("value", np.float32)
    ents = [world.create_entity() for _ in range(5)]
    for i, e in enumerate(ents):
        world.add_component(e, "value", np.float32(i * 10))
    q = __import__("citybuilder.sim.ecs", fromlist=["Query"]).Query(world, ("value",))
    values = [v for _, (v,) in q]
    assert values == [np.float32(i * 10) for i in range(5)]


def test_generation_increments_on_recreate():
    world = World()
    e1 = world.create_entity()
    gen1 = e1.generation
    world.destroy_entity(e1)
    e2 = world.create_entity()
    # Same slot may be reused, but generation must differ.
    assert e2.generation > gen1

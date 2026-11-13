"""Determinism + fixed-tick tests for the reference simulation loop."""

from citybuilder.sim.loop import SimLoop, SimConfig


def test_sim_advances_ticks():
    sim = SimLoop(SimConfig(tick_rate=60, seed=1234))
    sim.run(100)
    assert sim.tick == 100


def test_sim_deterministic_same_seed():
    a = SimLoop(SimConfig(tick_rate=60, seed=42))
    b = SimLoop(SimConfig(tick_rate=60, seed=42))
    a.run(50)
    b.run(50)
    assert a.snapshot() == b.snapshot()


def test_sim_different_seed_diverges():
    a = SimLoop(SimConfig(tick_rate=60, seed=42))
    b = SimLoop(SimConfig(tick_rate=60, seed=43))
    a.run(50)
    b.run(50)
    # RNG state should differ after the same number of ticks with different seeds.
    assert a.snapshot()["rng_state"] != b.snapshot()["rng_state"]

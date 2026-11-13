"""Tests for the deterministic RNG."""

from citybuilder.sim.rng import RNG


def test_rng_deterministic():
    a = RNG(42)
    b = RNG(42)
    assert [a.next_u32() for _ in range(10)] == [b.next_u32() for _ in range(10)]


def test_rng_different_seed_diverges():
    a = RNG(42)
    b = RNG(43)
    assert any(a.next_u32() != b.next_u32() for _ in range(20))


def test_random_range():
    rng = RNG(1)
    for _ in range(1000):
        assert 0.0 <= rng.random() < 1.0


def test_randint_range():
    rng = RNG(1)
    for _ in range(1000):
        v = rng.randint(5, 15)
        assert 5 <= v < 15


def test_copy_independent():
    a = RNG(7)
    _ = [a.next_u32() for _ in range(5)]
    b = a.copy()
    assert a.next_u32() == b.next_u32()

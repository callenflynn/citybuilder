"""Deterministic seeded RNG.

Uses xorshift64* so it is trivial to port to Rust bit-for-bit and keep
Python/Rust replays in sync. No dependence on wall-clock or global RNG.
"""

MASK64 = (1 << 64) - 1
MULT = 0x2545F4914F6CDD1D


class RNG:
    def __init__(self, seed: int = 0):
        self.state = int(seed) & MASK64
        if self.state == 0:
            self.state = 0x9E3779B97F4A7C15  # avoid degenerate zero state

    def next_u32(self) -> int:
        state = self.state
        state ^= (state >> 12) & MASK64
        state ^= (state << 25) & MASK64
        state ^= (state >> 27) & MASK64
        self.state = state & MASK64
        return ((state * MULT) >> 32) & MASK64 & 0xFFFFFFFF

    def random(self) -> float:
        """Uniform float in [0, 1)."""
        return self.next_u32() / 2**32

    def randint(self, low: int, high: int) -> int:
        """Integer in [low, high)."""
        if high <= low:
            return low
        return low + (self.next_u32() % (high - low))

    def choice(self, seq):
        if not seq:
            raise IndexError("cannot choose from empty sequence")
        return seq[self.randint(0, len(seq))]

    def copy(self) -> "RNG":
        rng = RNG(0)
        rng.state = self.state
        return rng

"""The one seeded random source. Same seed + same inputs = same game."""

from __future__ import annotations

import random
from typing import Sequence, TypeVar

T = TypeVar("T")


class GameRng:
    """Seeded RNG. Each loop gets its own stream so loops replay identically."""

    def __init__(self, seed: int, stream: str = "") -> None:
        self.seed = seed
        self.stream = stream
        self._random = random.Random(f"{seed}/{stream}")

    def chance(self, probability: float) -> bool:
        """True with the given probability."""
        return self._random.random() < probability

    def choice(self, items: Sequence[T]) -> T:
        """Pick one item."""
        return items[self._random.randrange(len(items))]

    def for_loop(self, loop: int) -> "GameRng":
        """A fresh, independent stream for one loop."""
        return GameRng(self.seed, f"loop{loop}")

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any


class StreamRNG:
    """Deterministic RNG bound to a derived integer seed. Process hash() is not used."""

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)

    def uniform(self, low: float, high: float) -> float:
        return float(low) + (float(high) - float(low)) * self._rng.random()

    def randint(self, low: int, high: int) -> int:
        return self._rng.randint(int(low), int(high))

    def choice(self, seq: Sequence[Any]) -> Any:
        items = list(seq)
        return items[self._rng.randrange(len(items))]

    def sample(self, seq: Sequence[Any], k: int) -> list[Any]:
        return self._rng.sample(list(seq), k)

    def shuffle(self, seq: Sequence[Any]) -> list[Any]:
        items = list(seq)
        self._rng.shuffle(items)
        return items


def sample_distribution(rng: StreamRNG, spec: dict[str, Any]) -> float | int:
    kind = spec.get("distribution")
    if kind == "uniform":
        return rng.uniform(spec["low"], spec["high"])
    if kind == "uniform_int":
        return rng.randint(spec["low"], spec["high"])
    if kind == "fixed":
        return spec["value"]
    raise ValueError(f"unsupported distribution {kind}")

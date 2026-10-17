"""Explicit evaluation backend selector.

Legacy batched continuation is the default. The engineering harness opts into
the compiled candidate. Nothing in the import of this module selects it.
"""

from __future__ import annotations

LEGACY = "legacy"
CANDIDATE = "candidate"
_BACKEND = LEGACY


def evaluation_backend() -> str:
    return _BACKEND


def select_evaluation_backend(name: str) -> str:
    """Return the previous backend. ``legacy`` restores the production default."""
    global _BACKEND
    if name not in {LEGACY, CANDIDATE}:
        raise ValueError(f"unknown evaluation backend {name!r}")
    previous = _BACKEND
    _BACKEND = name
    return previous

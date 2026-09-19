"""Import and access boundaries for Gate C auditability."""

from __future__ import annotations

import importlib
import sys
from typing import Any

# Modules that must never be imported by the action generator or proxy compiler.
FORBIDDEN_COMPILER_IMPORTS = frozenset(
    {
        "f1q.simulator.engine",
        "f1q.formulation.evaluator",
        "f1q.formulation.qubo",
    }
)

FORBIDDEN_OBSERVATION_KEYS = frozenset(
    {
        "private",
        "fuel_actual",
        "actual_fuel_kg",
        "RaceEngine",
        "engine_state",
        "regime_end_race_s",
        "sampled_future_regime_duration_s",
        "future_regime_duration_s",
        "rival_eventual_pit_lap",
        "evaluator_only_rng",
        "continue_to_finish",
    }
)


class ForbiddenAccessError(AssertionError):
    pass


class SpyMapping(dict):
    """Adversarial observation wrapper: forbidden keys fail conspicuously."""

    def __getitem__(self, key):  # type: ignore[override]
        if key in FORBIDDEN_OBSERVATION_KEYS:
            raise ForbiddenAccessError(f"forbidden observation key {key!r}")
        return super().__getitem__(key)

    def get(self, key, default=None):  # type: ignore[override]
        if key in FORBIDDEN_OBSERVATION_KEYS:
            raise ForbiddenAccessError(f"forbidden observation key {key!r}")
        return super().get(key, default)

    def __contains__(self, key):  # type: ignore[override]
        if key in FORBIDDEN_OBSERVATION_KEYS:
            raise ForbiddenAccessError(f"forbidden observation key {key!r}")
        return super().__contains__(key)


def assert_no_forbidden_imports(module_name: str) -> None:
    mod = sys.modules.get(module_name)
    if mod is None:
        mod = importlib.import_module(module_name)
    imported = set(getattr(mod, "__forbidden_checked_imports__", ()) )
    # Inspect module globals for imported modules by name.
    for value in vars(mod).values():
        other = getattr(value, "__module__", None)
        if other in FORBIDDEN_COMPILER_IMPORTS and module_name.startswith("f1q.formulation."):
            if module_name in {"f1q.formulation.actions", "f1q.formulation.compiler"}:
                raise ForbiddenAccessError(f"{module_name} imported forbidden {other}")
    del imported


def reject_private_payload(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_OBSERVATION_KEYS:
                raise ForbiddenAccessError(f"private/future field {key!r} at {path}")
            reject_private_payload(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            reject_private_payload(value, path=f"{path}[{i}]")

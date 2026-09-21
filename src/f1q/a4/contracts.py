"""Versioned A4 schemas, structural errors, and scientific exclusion codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from f1q.errors import F1QError
from f1q.hashing import sha256_json

DONOR_BANK_SCHEMA_V2 = "f1q.a4.donor_bank.v2"
FAMILY_DEPTH_KEYS = ("C0_p1", "C0_p2", "C1_p1", "C1_p2")
ALLOCATOR_OPTIONS = ("stop_fallback", "classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2")
NOMINAL_BUDGETS_S = (5, 10, 30, 60, 120)
PRIMARY_BUDGET_S = 30
PORTFOLIO_K = 4
EVALUATOR_POLICY_VERSION = "a4.evaluator.v2"
CONTINUATION_POLICY_VERSION = "a4.continuation.v2"


class StructuralError(F1QError):
    """Schema, code, missing-artifact, integrity, leakage, or invariant failure.

    The coordinator must cancel pending work and stop on the first occurrence.
    A raw Python exception is never converted into a scientific exclusion.
    """

    exit_code = 4

    def __init__(self, code: str, message: str, *, path: str | None = None, value: Any = None):
        self.code = code
        self.path = path
        self.value = value
        detail = message if path is None else f"{message} (path={path!r} value={value!r})"
        super().__init__(detail)


class ScientificExclusionCode(str, Enum):
    CLOSED_DECISION_WINDOW = "CLOSED_DECISION_WINDOW"
    NO_LEGAL_NONFALLBACK_ACTION = "NO_LEGAL_NONFALLBACK_ACTION"


FROZEN_EXCLUSION_CODES = frozenset(c.value for c in ScientificExclusionCode)


def require_mapping(obj: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise StructuralError("SCHEMA", "expected mapping", path=path, value=type(obj).__name__)
    return obj


def require_nonempty_list(obj: Any, *, path: str) -> list[Any]:
    if not isinstance(obj, list):
        raise StructuralError("SCHEMA", "expected list", path=path, value=type(obj).__name__)
    if not obj:
        raise StructuralError("SCHEMA", "empty list", path=path, value=obj)
    return obj


def require_finite(value: Any, *, path: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise StructuralError("SCHEMA", "non-numeric", path=path, value=value) from exc
    if v != v or v in {float("inf"), float("-inf")}:
        raise StructuralError("SCHEMA", "nonfinite", path=path, value=value)
    return v


@dataclass(frozen=True)
class Candidate:
    plan: dict[str, Any]
    plan_hash: str
    proxy_cost: float | None
    found_by: tuple[str, ...]
    generator: str
    donor_id: str | None
    family_depth: str | None
    policy_seed: int | None
    validation_ok: bool
    portfolio_role: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "plan_hash": self.plan_hash,
            "proxy_cost": self.proxy_cost,
            "found_by": list(self.found_by),
            "generator": self.generator,
            "donor_id": self.donor_id,
            "family_depth": self.family_depth,
            "policy_seed": self.policy_seed,
            "validation_ok": self.validation_ok,
            "portfolio_role": self.portfolio_role,
            "quantum_generated": "quantum" in self.found_by,
            "classical_generated": "classical" in self.found_by,
        }


@dataclass
class CountLedger:
    attempted_parents: int = 0
    successful_parents: int = 0
    failed_parents: int = 0
    excluded_parents: int = 0
    attempted_cases: int = 0
    successful_cases: int = 0
    failed_cases: int = 0
    excluded_cases: int = 0
    failed_rows: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempted_parents": self.attempted_parents,
            "successful_parents": self.successful_parents,
            "failed_parents": self.failed_parents,
            "excluded_parents": self.excluded_parents,
            "attempted_cases": self.attempted_cases,
            "successful_cases": self.successful_cases,
            "failed_cases": self.failed_cases,
            "excluded_cases": self.excluded_cases,
            "n_failed_row_records": len(self.failed_rows),
        }


def provenance_flags(
    *,
    plan_hash: str,
    hybrid_hashes: set[str],
    classical_hashes: set[str],
    found_by: set[str] | tuple[str, ...] | list[str],
) -> dict[str, bool]:
    fb = set(found_by)
    incremental = plan_hash in hybrid_hashes and plan_hash not in classical_hashes
    return {
        "quantum_generated": "quantum" in fb,
        "classical_generated": "classical" in fb,
        "quantum_incremental_at_k": incremental,
    }


def hash_record(obj: Any) -> str:
    return sha256_json(obj)

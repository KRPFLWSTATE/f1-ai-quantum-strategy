"""Conditioned initial-fuel generation for the no-refueling domain.

Declared modelling assumption. Not empirical fuel calibration and not an
unconditioned physical population. Amendment: development_spec.fuel.v1.1
(clarifies v1; generation rule unchanged).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from f1q.errors import RejectionError

AMENDMENT_ID = "development_spec.fuel.v1.1"
AMENDMENT_SUPERSEDES = "development_spec.fuel.v1"


@dataclass(frozen=True)
class FuelRealization:
    estimate_kg: float
    uncertainty_kg: float
    offset_kg: float
    need_kg: float
    provisional_actual_kg: float
    actual_kg: float
    error_kg: float
    floor_applied: bool
    need_source: str = "remaining_laps_at_init * kg_per_lap"
    conditioned_on_no_refueling_domain: bool = True
    unbiased_uniform_error: bool = False

    def as_public_audit(self) -> dict[str, Any]:
        """Public estimate and modelled quantities. Private actual belongs in private evidence."""
        return {
            "estimate_kg": self.estimate_kg,
            "uncertainty_kg": self.uncertainty_kg,
            "need_kg": self.need_kg,
            "need_source": self.need_source,
            "floor_applied": self.floor_applied,
            "unbiased_uniform_error": False,
            "conditioned_on_no_refueling_domain": True,
        }

    def as_private_audit(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unbiased_uniform_error"] = False
        return payload


def horizon_need_kg(remaining_laps_at_init: float, kg_per_lap: float) -> float:
    """Horizon need from information available at initialization.

    This is a declared conservative bound (remaining laps at init times the
    on-track consumption rate). It does not use private realized future
    consumption draws.
    """
    return float(remaining_laps_at_init) * float(kg_per_lap)


def realize_initial_fuel(
    *,
    estimate_kg: float,
    uncertainty_kg: float,
    offset_kg: float,
    need_kg: float,
    car_id: str = "car",
) -> FuelRealization:
    """Joint generation of public estimate, private actual, and observation error.

    Let u = uncertainty_kg >= 0. Offset is a keyed Uniform(-u, u) draw, independent
    across cars given the evaluation stream. Provisional actual is estimate+offset.

    Support / conditioning:
    - If provisional actual >= need: actual = provisional (interior of the band).
    - If provisional actual < need and estimate + u >= need: actual = need
      (atom at the minimum sufficient fuel; floor_applied true).
    - If estimate + u < need: reject IMPOSSIBLE_INITIAL_FUEL. No silent clamp.

    Implications: error = actual - estimate is **not** Uniform(-u, u) and is **not**
    unbiased whenever the floor can fire. Probability mass at the threshold equals
    the Uniform(-u, u) measure of offsets that would undershoot need, provided
    estimate + u covers need. This is an intentionally conditioned fictional
    corpus on the supported no-refueling domain.
    """
    est = float(estimate_kg)
    u = float(uncertainty_kg)
    off = float(offset_kg)
    need = float(need_kg)
    if est < 0:
        raise RejectionError("IMPOSSIBLE_INITIAL_FUEL", f"{car_id} has negative estimated fuel")
    if u < 0:
        raise RejectionError("IMPOSSIBLE_INITIAL_FUEL", f"{car_id} has negative fuel uncertainty")
    provisional = est + off
    floor_applied = False
    if provisional < need - 1e-12:
        if est + u + 1e-12 >= need:
            actual = need
            floor_applied = True
        else:
            raise RejectionError(
                "IMPOSSIBLE_INITIAL_FUEL",
                f"{car_id} cannot cover {need} kg within the uncertainty band",
            )
    else:
        actual = provisional
    return FuelRealization(
        estimate_kg=est,
        uncertainty_kg=u,
        offset_kg=off,
        need_kg=need,
        provisional_actual_kg=provisional,
        actual_kg=actual,
        error_kg=actual - est,
        floor_applied=floor_applied,
    )

"""Declared public formulation configuration (solver-visible + published constants)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from f1q.errors import SchemaError
from f1q.formulation.versions import COEFFICIENT_UNITS, FORMULATION_VERSION, RISK_WEIGHT
from f1q.schemas import StrictModel, reject_non_finite


class PublicPhysicsConfig(StrictModel):
    """Public tyre/fuel/pit constants. Must not include private fuel or future regime end."""

    green_lap_s: float = Field(gt=0)
    green_pit_loss_s: float = Field(gt=0)
    tyre_form: str
    tyre_wear_per_lap: float = Field(ge=0)
    tyre_curvature: float | None = None
    time_scale_s: float = Field(gt=0)
    curve_scale_s: float = Field(ge=0)
    compound_offset_s: dict[str, float]
    kg_per_lap: float = Field(gt=0)
    time_per_kg_s: float = Field(ge=0)
    service_stationary_s: float = Field(gt=0)
    pit_entry_frac: float = Field(gt=0, lt=1)
    sc_pace_factor: float = Field(gt=1)
    vsc_pace_factor: float = Field(gt=1)
    distinct_compounds_required: int = Field(ge=1, le=3)
    units: str = COEFFICIENT_UNITS
    risk_weight: float = RISK_WEIGHT
    formulation_version: str = FORMULATION_VERSION

    def regime_pace_factor(self, regime: str | None) -> float:
        if regime == "SC":
            return float(self.sc_pace_factor)
        if regime == "VSC":
            return float(self.vsc_pace_factor)
        return 1.0

    def effective_pit_loss_s(self, regime: str | None) -> float:
        """Regime-adjusted pit loss: absolute track loss shrinks when pace stretches."""
        return float(self.green_pit_loss_s) / self.regime_pace_factor(regime)


def public_physics_from_sources(
    *,
    simulator_cfg: dict[str, Any],
    block_parameters: dict[str, Any],
    compound_obligation: dict[str, Any] | None = None,
) -> PublicPhysicsConfig:
    tyres = simulator_cfg["tyres"]
    fuel = simulator_cfg["fuel"]
    pit = simulator_cfg["pit"]
    regime = simulator_cfg["regime"]
    required = 2
    if compound_obligation:
        required = int(compound_obligation.get("distinct_compounds_required") or 2)
    payload = {
        "green_lap_s": float(block_parameters["green_lap_s"]),
        "green_pit_loss_s": float(block_parameters["green_pit_loss_s"]),
        "tyre_form": str(block_parameters["tyre_form"]),
        "tyre_wear_per_lap": float(block_parameters["tyre_wear_per_lap"]),
        "tyre_curvature": block_parameters.get("tyre_curvature"),
        "time_scale_s": float(tyres["time_scale_s"]),
        "curve_scale_s": float(tyres["curve_scale_s"]),
        "compound_offset_s": {k: float(v) for k, v in tyres["compound_offset_s"].items()},
        "kg_per_lap": float(fuel["kg_per_lap"]),
        "time_per_kg_s": float(fuel["time_per_kg_s"]),
        "service_stationary_s": float(pit["service_stationary_s"]),
        "pit_entry_frac": float(simulator_cfg["track"]["pit_entry_frac"]),
        "sc_pace_factor": float(regime["sc_pace_factor"]),
        "vsc_pace_factor": float(regime["vsc_pace_factor"]),
        "distinct_compounds_required": required,
    }
    reject_non_finite(payload)
    return PublicPhysicsConfig.model_validate(payload)


def parse_public_physics(data: dict[str, Any]) -> PublicPhysicsConfig:
    try:
        return PublicPhysicsConfig.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc

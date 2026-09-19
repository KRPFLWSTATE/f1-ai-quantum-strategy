from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from f1q import CAUSAL_SCHEMA_VERSION
from f1q.errors import SchemaError
from f1q.schemas import StrictModel, reject_forbidden_keys, reject_non_finite

QuantityStatus = Literal["known", "inferred", "assumed", "unknown", "forecast"]
Regime = Literal["SC", "VSC"]
Partition = Literal["training", "tuning", "calibration", "test", "shift", "development", "setup_fixture"]
ValidationStatus = Literal["awaiting_simulator", "schema_rejected", "validated_by_simulator"]

PRIVATE_SOLVER_EXCLUSIONS = frozenset(
    {
        "future_outcome",
        "future_sc_duration",
        "future_regime_duration_s",
        "realized_sc_duration_s",
        "realized_vsc_duration_s",
        "sampled_future_regime_duration_s",
        "rival_eventual_pit_lap",
        "rival_eventual_pit_laps",
        "current_lap_final_time",
        "final_evaluation_score",
        "evaluator_only_rng",
        "evaluator_bank_key",
        "evaluator_only_fields",
        "calibrated_threshold",
        "model_artifact",
        "simulation_distribution",
        "frozen_protocol_hash",
        "completed_gate",
        "verified_qpu_job_id",
        "episode_stream_seed",
        "block_stream_seed",
        "simulation_seed",
        "private_rng_state",
        "private",
        "fuel_actual",
        "actual_fuel_kg",
        "engine_state",
        "regime_end_race_s",
        "fuel_floor_applied",
    }
)


class Quantity(StrictModel):
    value: Any = None
    unit: str
    source: str
    availability_time: str
    status: QuantityStatus
    unknown_reason: str | None = None
    forecast_issuance_time: str | None = None
    forecast_uncertainty: dict[str, Any] | None = None

    @field_validator("value")
    @classmethod
    def _finite(cls, value: Any) -> Any:
        return reject_non_finite(value)

    @model_validator(mode="after")
    def _status_rules(self) -> Quantity:
        if self.status == "unknown":
            if self.value is not None:
                raise SchemaError("unknown quantity must not carry a silent numeric default")
            if not self.unknown_reason:
                raise SchemaError("unknown quantity requires unknown_reason")
        if self.status == "forecast":
            if self.forecast_issuance_time is None:
                raise SchemaError("forecast requires forecast_issuance_time")
        if self.status in {"known", "inferred", "assumed"} and self.value is None:
            raise SchemaError(f"{self.status} quantity requires a value")
        return self


class ClockContract(StrictModel):
    race_clock_unit: Literal["s"] = "s"
    race_clock_origin: Literal["race_start"] = "race_start"
    monotonic_client_clock: Literal["separate_from_race_clock"] = "separate_from_race_clock"
    communication_margin_s: float = Field(ge=0)


class CheckpointRequest(StrictModel):
    rule: Literal["completed_laps_equals"]
    completed_laps: int = Field(ge=1)
    remaining_laps: int = Field(ge=0)
    requested_regime: Regime
    race_time_s: Quantity
    note: str = "Stage 3 must advance from initialization to this condition, then reveal the regime."


class TyreSet(StrictModel):
    set_id: str
    compound: Literal["soft", "medium", "hard"]
    used: bool
    age_laps: float = Field(ge=0)


class CarInit(StrictModel):
    car_id: str
    team_id: str
    classified_position: int = Field(ge=1, le=20)
    gap_ahead_s: float = Field(ge=0)
    lap_deficit: int = Field(ge=0)
    compound: Literal["soft", "medium", "hard"]
    tyre_age_laps: float = Field(ge=0)
    mounted_set_id: str
    inventory: list[TyreSet]
    fuel_kg: float = Field(ge=0)
    fuel_uncertainty_kg: float = Field(ge=0)
    pit_entry_commitment_cutoff_remaining_s: float
    in_pit_lane: bool = False
    service_state: str = "on_track"


class ScenarioSpec(StrictModel):
    schema_version: str = CAUSAL_SCHEMA_VERSION
    kind: Literal["scenario_spec"] = "scenario_spec"
    spec_id: str
    block_id: str
    episode_id: str
    family_id: str
    partition: Partition
    namespace: str
    generator_version: str
    evidence_kind: Literal["development"] | Literal["planned_unmaterialized"] = "development"
    awaiting_simulator_validation: Literal[True] = True
    not_a_validated_race_checkpoint: Literal[True] = True
    not_a_scientific_split_member: bool = True
    factors: dict[str, str]
    block_parameters: dict[str, Any]
    race_horizon_laps: int = Field(ge=1)
    initialization: dict[str, Any]
    checkpoint_request: CheckpointRequest
    selected_team_id: str
    selected_car_ids: list[str]
    field: list[CarInit]
    weather: Literal["dry"] = "dry"
    compound_obligation: dict[str, Any]
    pit_lane: dict[str, Any]
    team_service: dict[str, Any]
    rival_policy_ref: dict[str, Any]
    clock: ClockContract
    deadline_interface: dict[str, Any]
    stream_key_ids: dict[str, str]
    assumptions: list[dict[str, str]]
    exclusions: list[str]
    provenance: dict[str, Any]
    substantive_fingerprint: str | None = None

    @model_validator(mode="after")
    def _basic(self) -> ScenarioSpec:
        if len(self.selected_car_ids) != 2:
            raise SchemaError("selected team must have two cars")
        if self.partition == "development" and not self.not_a_scientific_split_member:
            raise SchemaError("development specs must not be scientific split members")
        if self.partition in {"training", "tuning", "calibration", "test", "shift"}:
            raise SchemaError("Stage 2 must not materialize reserved scientific partitions")
        ids = [c.car_id for c in self.field]
        if len(ids) != len(set(ids)):
            raise SchemaError("duplicate car_id")
        positions = [c.classified_position for c in self.field]
        if len(positions) != len(set(positions)):
            raise SchemaError("duplicate classified_position")
        return self


class PrivateSimState(StrictModel):
    not_solver_visible: Literal[True] = True
    block_stream_seed: int
    episode_stream_seed: int
    sampled_future_regime_duration_s: float | None = None
    rival_eventual_pit_laps: dict[str, int] | None = None
    evaluator_bank_key: str | None = None
    actual_fuel_kg: dict[str, float] | None = None
    regime_end_race_s: float | None = None
    engine_state: dict[str, Any] | None = None
    fuel_floor_applied: dict[str, bool] | None = None
    amendment_ids: list[str] | None = None


class SimulatorState(StrictModel):
    schema_version: str = CAUSAL_SCHEMA_VERSION
    kind: Literal["simulator_state"] = "simulator_state"
    not_solver_visible: Literal[True] = True
    episode_id: str
    spec_id: str
    public: dict[str, Any]
    private: PrivateSimState
    stream_key_ids: dict[str, str]


class ExpiredAction(StrictModel):
    car_id: str
    action: Literal["pit_now"]
    state: Literal["expired"]
    reason_code: Literal["PIT_WINDOW_CLOSED"]
    cutoff_race_s: float
    decision_time_race_s: float
    not_relabeled_as: Literal["pit_next_lap"] = "pit_next_lap"


class DecisionObservation(StrictModel):
    schema_version: str = CAUSAL_SCHEMA_VERSION
    kind: Literal["decision_observation"] = "decision_observation"
    fixture_kind: str | None = None
    checkpoint_id: str
    scenario_id: str
    block_id: str
    episode_id: str
    family_id: str
    partition: Partition
    decision_time: Quantity
    clock: ClockContract
    field_size: Quantity
    completed_laps: Quantity
    remaining_laps: Quantity
    race_horizon_laps: Quantity
    safety_regime: Quantity | None = None
    safety_regime_duration: Quantity
    selected_team_id: str
    cars: list[dict[str, Any]]
    inventories: dict[str, Any]
    pit_lane: dict[str, Any]
    team_service: dict[str, Any]
    compound_obligations: dict[str, Any]
    cutoffs: dict[str, Quantity]
    nominal_budget_s: Quantity
    effective_deadline_s: Quantity
    expired_actions: list[ExpiredAction] = Field(default_factory=list)
    forecasts: list[Quantity] = Field(default_factory=list)
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def _no_private(self) -> DecisionObservation:
        payload = self.model_dump(mode="python")
        _reject_private(payload)
        reject_non_finite(payload)
        return self


class EnvelopeAccess(StrictModel):
    solver_may_read: list[str]
    evaluator_may_read: list[str]


class CheckpointEnvelope(StrictModel):
    schema_version: str = CAUSAL_SCHEMA_VERSION
    kind: Literal["checkpoint_envelope"] = "checkpoint_envelope"
    envelope_id: str
    spec_id: str
    checkpoint_id: str
    episode_id: str
    block_id: str
    partition: Partition
    validation_status: ValidationStatus
    not_a_validated_race_checkpoint: bool
    solver_observation_ref: str | None = None
    evaluator_state_ref: str | None = None
    access: EnvelopeAccess
    timing: dict[str, Any]
    provenance: dict[str, Any]


def _reject_private(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in PRIVATE_SOLVER_EXCLUSIONS:
                raise SchemaError(f"private or future-only field {key!r} is not permitted at {path}")
            _reject_private(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _reject_private(value, path=f"{path}[{index}]")


def parse_scenario_spec(data: dict[str, Any]) -> ScenarioSpec:
    reject_forbidden_keys(data)
    try:
        return ScenarioSpec.model_validate(data)
    except SchemaError:
        raise
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_decision_observation(data: dict[str, Any]) -> DecisionObservation:
    _reject_private(data)
    try:
        return DecisionObservation.model_validate(data)
    except SchemaError:
        raise
    except Exception as exc:
        raise SchemaError(str(exc)) from exc

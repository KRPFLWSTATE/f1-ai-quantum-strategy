from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from f1q import SCHEMA_VERSION
from f1q.errors import SchemaError

EvidenceKind = Literal[
    "setup_fixture",
    "training",
    "tuning",
    "calibration",
    "test",
    "shift",
    "development",
]
ObservationStatus = Literal["known", "inferred", "assumed"]
Split = Literal["training", "tuning", "calibration", "test", "shift", "setup_fixture"]
RunStatus = Literal["pending", "running", "completed", "failed", "interrupted"]
AttemptStatus = Literal["running", "completed", "failed", "interrupted"]

FORBIDDEN_DECISION_INPUT_KEYS = frozenset(
    {
        "future_outcome",
        "future_sc_duration",
        "rival_eventual_pit_lap",
        "current_lap_final_time",
        "final_evaluation_score",
        "evaluator_only_rng",
        "calibrated_threshold",
        "model_artifact",
        "simulation_distribution",
        "frozen_protocol_hash",
        "completed_gate",
        "verified_qpu_job_id",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def reject_non_finite(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise SchemaError("NaN and infinite scientific values are forbidden")
    if isinstance(value, dict):
        for item in value.values():
            reject_non_finite(item)
    if isinstance(value, list):
        for item in value:
            reject_non_finite(item)
    return value


def reject_forbidden_keys(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_DECISION_INPUT_KEYS:
                raise SchemaError(
                    f"Future-only or evaluator-only field {key!r} is not permitted in decision input at {path}"
                )
            reject_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            reject_forbidden_keys(value, path=f"{path}[{index}]")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(StrictModel):
    value: Any
    unit: str
    source: str
    availability_time: str
    status: ObservationStatus

    @field_validator("value")
    @classmethod
    def _finite(cls, value: Any) -> Any:
        return reject_non_finite(value)


class UnresolvedField(StrictModel):
    field: str
    value: None = None
    reason: str


class DossierRef(StrictModel):
    version: str
    dated: str
    relative_path: str
    sha256: str = Field(min_length=64, max_length=64)
    page_count: int = Field(ge=1)

    @field_validator("relative_path")
    @classmethod
    def _no_escape(cls, value: str) -> str:
        if value.startswith("/") or ".." in Pathish(value):
            raise SchemaError(f"Unsafe dossier path: {value}")
        return value


def Pathish(value: str) -> list[str]:
    return value.replace("\\", "/").split("/")


class QPUDraft(StrictModel):
    provider: Literal["ibm"] = "ibm"
    reported_balance_seconds: int = Field(ge=0)
    reported_balance_status: Literal["unverified"] = "unverified"
    verified_available_seconds: int | None = None
    verified_available_seconds_reason: str
    protected_reserve_seconds: int = Field(ge=0)
    campaign_ceiling_seconds: int | None = None
    campaign_ceiling_seconds_reason: str
    submission_path_implemented: Literal[False] = False

    @model_validator(mode="after")
    def _unverified_nulls(self) -> QPUDraft:
        if self.verified_available_seconds is not None:
            raise SchemaError(
                "verified_available_seconds must remain null until a later authorised account check"
            )
        if self.campaign_ceiling_seconds is not None:
            raise SchemaError(
                "campaign_ceiling_seconds must remain null until verified_available_seconds exists"
            )
        if self.submission_path_implemented is not False:
            raise SchemaError("Stage 1 must not implement a provider submission path")
        return self


class WorkerDefaults(StrictModel):
    max_workers: int = Field(ge=1, le=2)
    reason: str


class PathConfig(StrictModel):
    evidence_dir: str
    ledger_relpath: str

    @field_validator("evidence_dir", "ledger_relpath")
    @classmethod
    def _relative_safe(cls, value: str) -> str:
        parts = Pathish(value)
        if value.startswith("/") or ".." in parts or parts[0] == "":
            raise SchemaError(f"Unsafe path: {value}")
        return value


class PythonConfig(StrictModel):
    requires: str
    selected: str


class AuthorizationConfig(StrictModel):
    scope: str
    allowed_plans: list[str]
    github_push_authorized: Literal[False] = False


class ProjectConfig(StrictModel):
    schema_version: str = SCHEMA_VERSION
    project_name: Literal["f1-ai-quantum-strategy"] = "f1-ai-quantum-strategy"
    active_stage: Literal[1, 2, 3, 4] = 4
    scientific_protocol_status: Literal["DRAFT"] = "DRAFT"
    protocol_frozen: Literal[False] = False
    hardware_execution_enabled: Literal[False] = False
    mode: Literal["local"] = "local"
    zero_additional_spending: Literal[True] = True
    dossier: DossierRef
    qpu: QPUDraft
    workers: WorkerDefaults
    paths: PathConfig
    python: PythonConfig
    unresolved: list[UnresolvedField]
    authorization: AuthorizationConfig

    @field_validator("mode")
    @classmethod
    def _local_only(cls, value: str) -> str:
        if value != "local":
            raise SchemaError(f"Unsupported mode: {value}")
        return value


class AuthorizedWorkUnit(StrictModel):
    schema_version: str = SCHEMA_VERSION
    unit_id: str
    stage: int = Field(ge=1, le=10)
    plan_id: str
    evidence_kind: EvidenceKind
    authorization_scope: str
    description: str
    seed: int | None = None


class BootstrapPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["bootstrap"] = "bootstrap"
    stage: Literal[1] = 1
    evidence_kind: Literal["setup_fixture"] = "setup_fixture"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage1_units(self) -> BootstrapPlan:
        if not self.units:
            raise SchemaError("bootstrap plan must contain at least one unit")
        for unit in self.units:
            if unit.plan_id != "bootstrap" or unit.stage != 1:
                raise SchemaError(f"bootstrap unit {unit.unit_id} is not a Stage 1 bootstrap unit")
            if unit.evidence_kind != "setup_fixture":
                raise SchemaError("bootstrap units must be setup_fixture evidence")
        return self


class DevelopmentPreviewPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["development_preview"] = "development_preview"
    stage: Literal[2] = 2
    evidence_kind: Literal["development"] = "development"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage2_units(self) -> DevelopmentPreviewPlan:
        if len(self.units) != 8:
            raise SchemaError("development preview plan must contain eight family units")
        for unit in self.units:
            if unit.plan_id != "development_preview" or unit.stage != 2:
                raise SchemaError(f"unit {unit.unit_id} is not a Stage 2 development preview unit")
            if unit.evidence_kind != "development":
                raise SchemaError("development preview units must be development evidence")
        return self


class SimulatorCheckPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["simulator_check"] = "simulator_check"
    stage: Literal[3] = 3
    evidence_kind: Literal["development"] = "development"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage3_units(self) -> SimulatorCheckPlan:
        if not self.units:
            raise SchemaError("simulator_check plan must contain units")
        for unit in self.units:
            if unit.plan_id != "simulator_check" or unit.stage != 3:
                raise SchemaError(f"unit {unit.unit_id} is not a Stage 3 simulator_check unit")
            if unit.evidence_kind != "development":
                raise SchemaError("simulator_check units remain development evidence")
        return self


class SimulatorFollowupPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["simulator_followup"] = "simulator_followup"
    stage: Literal[3] = 3
    evidence_kind: Literal["development"] = "development"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage31_units(self) -> SimulatorFollowupPlan:
        if not self.units:
            raise SchemaError("simulator_followup plan must contain units")
        for unit in self.units:
            if unit.plan_id != "simulator_followup" or unit.stage != 3:
                raise SchemaError(f"unit {unit.unit_id} is not a Stage 3 simulator_followup unit")
            if unit.evidence_kind != "development":
                raise SchemaError("simulator_followup units remain development evidence")
        return self


class SimulatorRepairPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["simulator_repair"] = "simulator_repair"
    stage: Literal[3] = 3
    evidence_kind: Literal["development"] = "development"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage32_units(self) -> SimulatorRepairPlan:
        if not self.units:
            raise SchemaError("simulator_repair plan must contain units")
        for unit in self.units:
            if unit.plan_id != "simulator_repair" or unit.stage != 3:
                raise SchemaError(f"unit {unit.unit_id} is not a Stage 3 simulator_repair unit")
            if unit.evidence_kind != "development":
                raise SchemaError("simulator_repair units remain development evidence")
        return self


class FormulationCheckPlan(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: Literal["formulation_check"] = "formulation_check"
    stage: Literal[4] = 4
    evidence_kind: Literal["development"] = "development"
    authorization_scope: str
    description: str
    units: list[AuthorizedWorkUnit]
    seed_specification: dict[str, Any]

    @model_validator(mode="after")
    def _stage4_units(self) -> FormulationCheckPlan:
        if not self.units:
            raise SchemaError("formulation_check plan must contain units")
        for unit in self.units:
            if unit.plan_id != "formulation_check" or unit.stage != 4:
                raise SchemaError(f"unit {unit.unit_id} is not a Stage 4 formulation_check unit")
            if unit.evidence_kind != "development":
                raise SchemaError("formulation_check units remain development evidence")
        return self


class ArtifactRecord(StrictModel):
    schema_version: str = SCHEMA_VERSION
    artifact_id: str
    run_id: str
    unit_id: str | None = None
    relative_path: str
    sha256: str = Field(min_length=64, max_length=64)
    kind: str
    created_at_utc: str

    @field_validator("relative_path")
    @classmethod
    def _safe(cls, value: str) -> str:
        if value.startswith("/") or ".." in Pathish(value):
            raise SchemaError(f"Unsafe artifact path: {value}")
        return value


class UnitAttempt(StrictModel):
    schema_version: str = SCHEMA_VERSION
    attempt_id: str
    run_id: str
    unit_id: str
    status: AttemptStatus
    started_at_utc: str
    ended_at_utc: str | None = None
    duration_monotonic_s: float | None = None
    error: str | None = None
    injected_failure: bool = False


class RunManifest(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    stage: int
    plan_id: str
    evidence_kind: EvidenceKind
    source_snapshot_hash: str
    git_commit: str | None
    git_dirty: bool
    dossier_sha256: str
    configuration_hash: str
    configuration_hash_kind: Literal["draft"] = "draft"
    dependency_lock_hash: str | None
    planned_unit_ids: list[str]
    seed_specification: dict[str, Any]
    authorization_scope: str
    started_at_utc: str
    ended_at_utc: str | None = None
    duration_monotonic_s: float | None = None
    status: RunStatus
    artifact_index: list[ArtifactRecord] = Field(default_factory=list)
    provider_job_id: None = None
    provider_job_id_reason: str = (
        "Not applicable: Stage 1 has no provider submission path and hardware is disabled."
    )
    qpu_usage_seconds: Literal[0] = 0


class Receipt(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    plan_id: str
    stage: int
    evidence_kind: EvidenceKind
    status: RunStatus
    configuration_hash: str
    configuration_hash_kind: Literal["draft"] = "draft"
    source_snapshot_hash: str
    dossier_sha256: str
    git_commit: str | None
    git_dirty: bool
    planned_unit_ids: list[str]
    completed_unit_ids: list[str]
    failed_unit_ids: list[str]
    interrupted_unit_ids: list[str]
    attempt_count: int
    injected_failure_count: int
    artifact_count: int
    event_count: int
    qpu_usage_seconds: Literal[0] = 0
    new_physical_qpu_jobs_submitted: Literal[0] = 0
    hardware_execution_enabled: Literal[False] = False
    scientific_protocol: Literal["DRAFT"] = "DRAFT"
    started_at_utc: str
    ended_at_utc: str | None
    duration_monotonic_s: float | None
    next_permitted_work: str
    notes: list[str] = Field(default_factory=list)


class CarDecisionState(StrictModel):
    car_id: str
    position: Observation
    gap_ahead_s: Observation
    compound: Observation
    tyre_age_laps: Observation
    fuel_kg: Observation
    pit_entry_commitment_cutoff: Observation
    service_state: Observation


class CausalCheckpoint(StrictModel):
    schema_version: str = SCHEMA_VERSION
    fixture_kind: Literal["fictional_setup_fixture"]
    not_a_scientific_observation: Literal[True] = True
    checkpoint_id: str
    scenario_id: str
    decision_checkpoint_id: str
    policy_repetition_id: str | None = None
    circuit_sample_pool_id: str | None = None
    provider_job_id: None = None
    provider_job_id_reason: str = "Not applicable in Stage 1 setup fixture."
    work_unit_id: str | None = None
    attempt_id: str | None = None
    block_id: str | None = None
    family: str | None = None
    split: Split
    field_size: Observation
    race_time_s: Observation
    lap: Observation
    regime: Observation
    team_service_state: Observation
    cars: list[CarDecisionState]
    inventories: dict[str, Observation]
    action_commitment_cutoffs: dict[str, Observation]
    provenance: dict[str, str]

    @model_validator(mode="after")
    def _fixture_and_cars(self) -> CausalCheckpoint:
        payload = self.model_dump(mode="python")
        reject_forbidden_keys(payload)
        reject_non_finite(payload)
        if self.split != "setup_fixture":
            raise SchemaError("Stage 1 checkpoint fixture must use split=setup_fixture")
        if len(self.cars) != 2:
            raise SchemaError("Two-car decision state is required")
        if self.provider_job_id is not None:
            raise SchemaError("provider_job_id must be null in Stage 1")
        return self


def parse_project_config(data: dict[str, Any]) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_checkpoint(data: dict[str, Any]) -> CausalCheckpoint:
    reject_forbidden_keys(data)
    try:
        return CausalCheckpoint.model_validate(data)
    except SchemaError:
        raise
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_bootstrap_plan(data: dict[str, Any]) -> BootstrapPlan:
    try:
        return BootstrapPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_development_preview_plan(data: dict[str, Any]) -> DevelopmentPreviewPlan:
    try:
        return DevelopmentPreviewPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_simulator_check_plan(data: dict[str, Any]) -> SimulatorCheckPlan:
    try:
        return SimulatorCheckPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_simulator_followup_plan(data: dict[str, Any]) -> SimulatorFollowupPlan:
    try:
        return SimulatorFollowupPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_simulator_repair_plan(data: dict[str, Any]) -> SimulatorRepairPlan:
    try:
        return SimulatorRepairPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def parse_formulation_check_plan(data: dict[str, Any]) -> FormulationCheckPlan:
    try:
        return FormulationCheckPlan.model_validate(data)
    except Exception as exc:
        raise SchemaError(str(exc)) from exc


def write_json_schemas(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {
        "project_config.schema.json": ProjectConfig,
        "authorized_work_unit.schema.json": AuthorizedWorkUnit,
        "bootstrap_plan.schema.json": BootstrapPlan,
        "development_preview_plan.schema.json": DevelopmentPreviewPlan,
        "simulator_check_plan.schema.json": SimulatorCheckPlan,
        "simulator_followup_plan.schema.json": SimulatorFollowupPlan,
        "simulator_repair_plan.schema.json": SimulatorRepairPlan,
        "formulation_check_plan.schema.json": FormulationCheckPlan,
        "run_manifest.schema.json": RunManifest,
        "unit_attempt.schema.json": UnitAttempt,
        "artifact_record.schema.json": ArtifactRecord,
        "receipt.schema.json": Receipt,
        "causal_checkpoint.schema.json": CausalCheckpoint,
    }
    from f1q.causal import CheckpointEnvelope, DecisionObservation, ScenarioSpec, SimulatorState

    mapping.update(
        {
            "scenario_spec.schema.json": ScenarioSpec,
            "simulator_state.schema.json": SimulatorState,
            "decision_observation.schema.json": DecisionObservation,
            "checkpoint_envelope.schema.json": CheckpointEnvelope,
        }
    )
    from f1q.hashing import atomic_write_text, canonical_json

    for name, model in mapping.items():
        atomic_write_text(directory / name, canonical_json(model.model_json_schema()).decode("utf-8") + "\n")


def export_json_schemas(directory) -> None:
    from pathlib import Path
    import json

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    models = {
        "project_config": ProjectConfig,
        "authorized_work_unit": AuthorizedWorkUnit,
        "bootstrap_plan": BootstrapPlan,
        "run_manifest": RunManifest,
        "unit_attempt": UnitAttempt,
        "artifact_record": ArtifactRecord,
        "receipt": Receipt,
        "causal_checkpoint": CausalCheckpoint,
    }
    for name, model in models.items():
        path = directory / f"{name}.v1.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

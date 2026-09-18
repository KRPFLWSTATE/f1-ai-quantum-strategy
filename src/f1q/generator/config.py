from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.authorization import load_yaml
from f1q.errors import SchemaError
from f1q.hashing import sha256_file
from f1q.paths import resolve_within
from f1q.schemas import StrictModel

PIT_LEVELS = ("low", "high")
TYRE_LEVELS = ("near_linear", "nonlinear")
TRAFFIC_LEVELS = ("sparse", "dense")
STREAM_DOMAINS = ("block_params", "episode", "fitting", "online_scoring", "evaluation")
SCIENTIFIC_PARTITIONS = ("training", "tuning", "calibration", "test", "shift")


class FamilyRecord(StrictModel):
    id: str
    green_pit_loss: str
    tyre_degradation: str
    traffic: str


class GeneratorConfigFile(StrictModel):
    schema_version: str
    generator_version: str
    kind: str
    not_calibrated_f1_parameters: bool
    scientific_protocol_status: str
    dossier: dict[str, Any]
    identity: dict[str, Any]
    pit_loss_definition: dict[str, Any]
    clock: dict[str, Any]
    nominal_decision_budgets_s: list[int]
    primary_nominal_budget_s: int
    domain: dict[str, Any]
    factors: dict[str, Any]
    families: list[FamilyRecord]
    provisional_quantities: list[dict[str, Any]]
    pending_stage3_interfaces: list[str]
    fictional_teams: list[dict[str, str]]
    rival_policy_ref: dict[str, Any]
    splits: dict[str, Any]
    development_preview: dict[str, Any]
    retry_policy: dict[str, Any]
    stream_domains: list[str]
    private_state_retention: dict[str, Any]
    observation_exclusions: list[str]


def family_id_for(pit: str, tyre: str, traffic: str) -> str:
    return f"fam.green_pit_{pit}.tyre_{tyre}.traffic_{traffic}"


def cartesian_family_ids() -> list[str]:
    ids = [
        family_id_for(pit, tyre, traffic)
        for pit in PIT_LEVELS
        for tyre in TYRE_LEVELS
        for traffic in TRAFFIC_LEVELS
    ]
    return sorted(ids)


def load_generator_config(root: Path) -> tuple[GeneratorConfigFile, str, dict[str, Any]]:
    path = resolve_within(root, "configs/generator.v1.yaml", must_exist=True)
    data = load_yaml(path)
    config = validate_generator_config(data)
    return config, sha256_file(path), data


def validate_generator_config(data: dict[str, Any]) -> GeneratorConfigFile:
    try:
        config = GeneratorConfigFile.model_validate(data)
    except Exception as exc:
        raise SchemaError(f"generator config invalid: {exc}") from exc
    expected = cartesian_family_ids()
    got = sorted(f.id for f in config.families)
    if got != expected:
        raise SchemaError(f"families must be the Cartesian product {expected}, got {got}")
    for fam in config.families:
        rebuilt = family_id_for(fam.green_pit_loss, fam.tyre_degradation, fam.traffic)
        if fam.id != rebuilt:
            raise SchemaError(f"family id {fam.id} does not match factors {rebuilt}")
        if fam.green_pit_loss not in PIT_LEVELS:
            raise SchemaError(f"unknown pit level {fam.green_pit_loss}")
        if fam.tyre_degradation not in TYRE_LEVELS:
            raise SchemaError(f"unknown tyre level {fam.tyre_degradation}")
        if fam.traffic not in TRAFFIC_LEVELS:
            raise SchemaError(f"unknown traffic level {fam.traffic}")
    if config.stream_domains != list(STREAM_DOMAINS):
        raise SchemaError(f"stream_domains must equal {list(STREAM_DOMAINS)}")
    if config.identity.get("uses_python_builtin_hash"):
        raise SchemaError("Python hash() is forbidden for persistent identities")
    if config.scientific_protocol_status != "DRAFT":
        raise SchemaError("generator config must remain DRAFT in Stage 2")
    if not config.pit_loss_definition.get("includes_stationary_service_time"):
        raise SchemaError("pit-loss definition must state that service time is included")
    preview = config.development_preview
    if preview.get("blocks") != 8 or preview.get("episodes_per_block") != 8:
        raise SchemaError("authorized development preview is eight blocks of eight episodes")
    if preview.get("scientific_split"):
        raise SchemaError("development preview must not be a scientific split")
    splits = config.splits
    if splits["training"]["blocks"] != 120 or splits["tuning"]["blocks"] != 16:
        raise SchemaError("main split planned block counts do not match the dossier floor")
    if splits["calibration"]["blocks"] != 24 or splits["test"]["floor_blocks"] != 80:
        raise SchemaError("main split planned block counts do not match the dossier floor")
    if splits["shift"]["blocks"] != 40:
        raise SchemaError("shift panel planned blocks must be 40")
    if splits["test"]["maximum_blocks"] != 160:
        raise SchemaError("test maximum planned blocks must be 160")
    return config


def sorted_families(config: GeneratorConfigFile) -> list[FamilyRecord]:
    return sorted(config.families, key=lambda item: item.id)

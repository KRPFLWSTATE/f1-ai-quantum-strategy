from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.errors import AuthorizationError, UnsupportedModeError
from f1q.hashing import sha256_file, sha256_json
from f1q.paths import resolve_within
from f1q.schemas import (
    ProjectConfig,
    parse_bootstrap_plan,
    parse_development_preview_plan,
    parse_formulation_check_plan,
    parse_formulation_repair_check_plan,
    parse_project_config,
    parse_simulator_check_plan,
    parse_simulator_followup_plan,
    parse_simulator_repair_plan,
)


HARDWARE_TOKENS = frozenset(
    {
        "ibm",
        "qpu",
        "hardware",
        "braket",
        "azure",
        "backend",
        "submit",
        "job",
    }
)

RESERVED_MATERIALIZE_PLANS = frozenset(
    {
        "training",
        "tuning",
        "calibration",
        "test",
        "shift",
        "campaign",
        "materialize-training",
        "materialize_training",
        "materialize-test",
        "materialize_test",
        "materialize-shift",
        "materialize_shift",
    }
)


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise AuthorizationError(f"YAML at {path} is not a mapping")
    return data


def load_project_config(root: Path) -> tuple[ProjectConfig, str, dict[str, Any]]:
    path = resolve_within(root, "configs/project.draft.yaml", must_exist=True)
    data = load_yaml(path)
    config = parse_project_config(data)
    return config, sha256_file(path), data


def load_bootstrap_plan(root: Path):
    path = resolve_within(root, "configs/plans/bootstrap.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_bootstrap_plan(data)
    return plan, sha256_file(path), data


def load_development_preview_plan(root: Path):
    path = resolve_within(root, "configs/plans/development_preview.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_development_preview_plan(data)
    return plan, sha256_file(path), data


def load_simulator_check_plan(root: Path):
    path = resolve_within(root, "configs/plans/simulator_check.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_simulator_check_plan(data)
    return plan, sha256_file(path), data


def load_simulator_followup_plan(root: Path):
    path = resolve_within(root, "configs/plans/simulator_followup.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_simulator_followup_plan(data)
    return plan, sha256_file(path), data


def load_simulator_repair_plan(root: Path):
    path = resolve_within(root, "configs/plans/simulator_repair.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_simulator_repair_plan(data)
    return plan, sha256_file(path), data


def load_formulation_check_plan(root: Path):
    path = resolve_within(root, "configs/plans/formulation_check.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_formulation_check_plan(data)
    return plan, sha256_file(path), data


def load_formulation_repair_check_plan(root: Path):
    path = resolve_within(root, "configs/plans/formulation_repair_check.yaml", must_exist=True)
    data = load_yaml(path)
    plan = parse_formulation_repair_check_plan(data)
    return plan, sha256_file(path), data


def lock_hash(root: Path) -> str | None:
    lock = root / "requirements.lock"
    if not lock.is_file():
        return None
    return sha256_file(lock)


def reject_unsupported_mode(args_ns) -> None:
    requested = []
    for name in ("plan", "mode", "provider", "backend"):
        value = getattr(args_ns, name, None)
        if value:
            requested.append(str(value).lower())
    if getattr(args_ns, "hardware", False):
        requested.append("hardware")
    for token in requested:
        if token in HARDWARE_TOKENS and token not in {"bootstrap"}:
            raise UnsupportedModeError(
                f"Unsupported mode {token!r}: Stage 1 has no provider submission path, "
                "hardware execution is disabled, and IBM is not contacted."
            )
        if token not in {"bootstrap", "local", "none", ""} and token in HARDWARE_TOKENS:
            raise UnsupportedModeError(f"Unsupported mode {token!r}")


def authorize_plan(config: ProjectConfig, plan_id: str) -> None:
    if config.hardware_execution_enabled:
        raise AuthorizationError("hardware_execution_enabled must remain false")
    if config.authorization.github_push_authorized:
        raise AuthorizationError("github push is not authorised in the local config")
    if plan_id in RESERVED_MATERIALIZE_PLANS or plan_id.startswith("materialize"):
        raise AuthorizationError(
            f"plan {plan_id!r} would materialize a reserved scientific partition or campaign; "
            "that is not authorised in Stage 2"
        )
    if plan_id not in config.authorization.allowed_plans:
        raise AuthorizationError(
            f"plan {plan_id!r} is not in authorization.allowed_plans={config.authorization.allowed_plans}"
        )
    if plan_id == "bootstrap":
        pass
    elif plan_id == "development_preview":
        if config.active_stage < 2:
            raise AuthorizationError("development_preview requires active_stage >= 2")
    elif plan_id == "simulator_check":
        if config.active_stage < 3:
            raise AuthorizationError("simulator_check requires active_stage >= 3")
    elif plan_id == "simulator_followup":
        if config.active_stage < 3:
            raise AuthorizationError("simulator_followup requires active_stage >= 3")
    elif plan_id == "simulator_repair":
        if config.active_stage < 3:
            raise AuthorizationError("simulator_repair requires active_stage >= 3")
    elif plan_id == "formulation_check":
        if config.active_stage < 4:
            raise AuthorizationError("formulation_check requires active_stage >= 4")
    elif plan_id == "formulation_repair_check":
        if config.active_stage < 4:
            raise AuthorizationError("formulation_repair_check requires active_stage >= 4")
    else:
        raise AuthorizationError(f"plan {plan_id!r} is not implemented")
    if config.mode != "local":
        raise AuthorizationError(f"unsupported mode {config.mode}")


def fingerprints_match(
    *,
    expected_config_hash: str,
    actual_config_hash: str,
    expected_source_hash: str,
    actual_source_hash: str,
    expected_plan_hash: str | None = None,
    actual_plan_hash: str | None = None,
) -> None:
    if expected_config_hash != actual_config_hash:
        raise AuthorizationError("configuration fingerprint changed; dispatch blocked")
    if expected_source_hash != actual_source_hash:
        raise AuthorizationError(
            "source snapshot fingerprint changed; dispatch blocked. Git HEAD alone does not identify a dirty tree."
        )
    if expected_plan_hash and expected_plan_hash != actual_plan_hash:
        raise AuthorizationError("plan fingerprint changed; dispatch blocked")


def dossier_hash(root: Path, config: ProjectConfig) -> str:
    path = resolve_within(root, config.dossier.relative_path, must_exist=True)
    digest = sha256_file(path)
    if digest != config.dossier.sha256:
        raise AuthorizationError(
            f"dossier SHA-256 mismatch: file={digest} config={config.dossier.sha256}"
        )
    return digest

"""Frozen Phase 6 pilot configuration (ceilings, not fabrication grounds)."""

from __future__ import annotations

from typing import Any

from f1q.hashing import sha256_json
from f1q.schemas import StrictModel
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID, PHASE5_FINAL_ACCEPTANCE_COMMIT, STAGE6_VERSION


class Phase6Config(StrictModel):
    schema_version: str = "stage6.config.v1"
    stage6_version: str = STAGE6_VERSION
    phase5_final_acceptance_commit: str = PHASE5_FINAL_ACCEPTANCE_COMMIT
    phase5_corrected_run_id: str = PHASE5_CORRECTED_RUN_ID
    selected_architecture: str = "A2_multi_epoch_scenario_contingent_strategy_policy"
    qpu_execution_authorised: bool = False
    hardware_execution_enabled: bool = False
    n_families: int = 8
    calibration_blocks_per_family: int = 3
    calibration_blocks_total: int = 24
    cases_per_block: int = 2  # SC + VSC restricted-menu
    family_depths: list[str] = ["C0_p1", "C0_p2", "C1_p1", "C1_p2"]
    policies: list[str] = ["learned", "fixed", "nn", "random"]
    pool_shots: int = 1024
    pool_seeds: int = 10
    max_pilot_compute_s: float = 1800.0
    max_verify_s: float = 600.0
    max_subprocess_s: float = 300.0
    max_ram_fraction: float = 0.60
    max_workers: int = 2
    progress_interval_s: float = 30.0
    circuit_unit_n_scenarios: int = 2
    circuit_unit_n_epochs: int = 2
    circuit_unit_n_actions: int = 2
    deadline_s: float = 5.0
    split_source_salt: str = "phase6.calibration.v1"
    improvement_tol: float = 1e-8
    tie_tol: float = 1e-8
    noisy_max_qubits: int = 10
    noisy_shots: int = 1024
    noisy_seeds: int = 3
    # Predeclared BEFORE calibration outcomes (development timing only)
    noisy_depth_choice: str = "p1"
    noisy_noise_model: str = "depolarizing_1q_1e-3_2q_1e-2"
    noisy_panel_enabled: bool = True
    superiority_delta: float = 0.02
    precision_halfwidth: float = 0.01
    test_block_floor: int = 80
    test_block_max: int = 160
    mc_world_candidates: list[int] = [2048, 8192, 32768]
    dossier_cpu_hour_ceiling: float = 24.0
    ridge_lambda: float = 1.0
    one_hot_amp_tol: float = 1e-8
    causal_model_scope: str = "restricted_synthetic_revealed_at_epoch_1"


def default_phase6_config() -> Phase6Config:
    return Phase6Config()


def config_to_frozen_dict(cfg: Phase6Config) -> dict[str, Any]:
    data = cfg.model_dump(mode="python")
    data["config_sha256"] = sha256_json(data)
    return data

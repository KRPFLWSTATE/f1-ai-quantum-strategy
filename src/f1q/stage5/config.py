"""Frozen Phase 5 configuration schema and defaults."""

from __future__ import annotations

from typing import Any

from f1q.hashing import sha256_json
from f1q.schemas import StrictModel


class Phase5Config(StrictModel):
    schema_version: str = "stage5.config.v1"
    stage5_version: str = "0.5.0"
    selected_architecture: str = "A2_multi_epoch_scenario_contingent_strategy_policy"
    novelty_status: str = "PROPOSED_NOT_LITERATURE_VERIFIED"
    qpu_execution_authorised: bool = False
    hardware_execution_enabled: bool = False
    n_families: int = 8
    anchors_per_family: int = 3
    training_extra_per_family: int = 15
    tuning_per_family: int = 10
    family_depths: list[str] = ["C0_p1", "C0_p2", "C1_p1", "C1_p2"]
    starts_per_anchor: int = 3
    max_evals_per_start: int = 80
    max_total_expectation_evals: int = 23040
    max_donors_per_family_depth: int = 8
    noninferiority_margin: float = 0.02
    circuit_unit_max_qubits: int = 12
    tiny_expected_vars_min: int = 24
    tiny_expected_vars_max: int = 40
    optimiser_seed_salt: str = "phase5.bank.v1"
    split_source_salt: str = "phase5.splits.v1"
    transpiler_seed: int = 17
    transpile_opt_level: int = 1
    ridge_lambda: float = 1.0
    pool_size: int = 32
    one_hot_amp_tol: float = 1e-8
    deadline_s_circuit_unit: float = 5.0
    run_timeout_s: float = 1200.0
    progress_interval_s: float = 30.0
    variational_ref_starts: int = 1
    variational_ref_max_evals: int = 40
    corrected_phase5: bool = True
    feature_schema: list[str] = [
        "n_logical_vars",
        "n_info_sets",
        "n_scenarios",
        "n_epochs",
        "n_blocks",
        "mean_block_size",
        "qubo_n_terms",
        "qubo_density",
        "coeff_abs_mean",
        "coeff_abs_max",
        "penalty_M",
        "crew_overlap_cost",
        "family_is_c1",
        "depth_p",
        "nnz_Q",
    ]


def default_phase5_config() -> Phase5Config:
    return Phase5Config()


def config_to_frozen_dict(cfg: Phase5Config) -> dict[str, Any]:
    data = cfg.model_dump(mode="python")
    data["config_sha256"] = sha256_json(data)
    return data

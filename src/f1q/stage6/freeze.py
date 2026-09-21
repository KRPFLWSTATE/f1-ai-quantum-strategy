"""Pre-calibration freeze record — frozen BEFORE inspecting calibration outcomes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_file, sha256_json
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID, PHASE5_FINAL_ACCEPTANCE_COMMIT
from f1q.stage6.config import Phase6Config, config_to_frozen_dict


def _file_hash(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        return {"path": rel, "present": False, "sha256": None}
    return {"path": rel, "present": True, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def build_freeze_record(
    root: Path,
    cfg: Phase6Config,
    *,
    source_commit: str,
    dirty_tree_patch_hash: str | None,
    machine: dict[str, Any],
    development_unit_timing: dict[str, Any],
    proposed_workload: dict[str, Any],
) -> dict[str, Any]:
    """Assemble immutable freeze payload. Callers must write this before pilot outcomes."""
    corrected = root / f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}"
    fa = root / "evidence/stage5/final_acceptance_repair"
    artifacts = {
        "phase5_corrected_frozen_config": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/frozen_config.json"
        ),
        "selector_model_artifacts": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/selector_model_artifacts.json"
        ),
        "donor_inventory": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/donor_inventory.json"
        ),
        "parameter_bank_receipt": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/parameter_bank_receipt.json"
        ),
        "selector_tuning_results": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/selector_tuning_results.json"
        ),
        "selector_train_usage": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/selector_train_usage.json"
        ),
        "split_block_ids": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/split_block_ids.json"
        ),
        "headroom_results": _file_hash(
            root, f"evidence/stage5/{PHASE5_CORRECTED_RUN_ID}/headroom_results.json"
        ),
        "final_acceptance_manifest": _file_hash(
            root, "docs/evidence/stage5_final_acceptance/STAGE_5_FINAL_ACCEPTANCE_MANIFEST.json"
        ),
        "final_acceptance_verify": _file_hash(
            root, "docs/evidence/stage5_final_acceptance/STAGE_5_FINAL_ACCEPTANCE_FINAL_VERIFY.json"
        ),
        "repaired_c1_resources": _file_hash(
            root, "evidence/stage5/final_acceptance_repair/actual_circuit_resources.json"
        ),
        "c1_repaired_definition": _file_hash(
            root, "evidence/stage5/final_acceptance_repair/c1_repaired_circuit_definition.json"
        ),
    }

    # Tuning-selected fixed donors (from corrected Phase 5 — not superseded 6ad68021)
    tuning = json.loads((corrected / "selector_tuning_results.json").read_text(encoding="utf-8"))
    donors = json.loads((corrected / "donor_inventory.json").read_text(encoding="utf-8"))
    fixed_by_fd: dict[str, Any] = {}
    for fd, row in tuning.get("per_family_depth", {}).items():
        target_hash = row.get("fixed_donor_params_hash")
        selected = donors.get(fd, {}).get("selected", [])
        match = next((d for d in selected if d.get("params_hash") == target_hash), None)
        fixed_by_fd[fd] = {
            "params_hash": target_hash,
            "selection_rule": row.get("fixed_donor_selection"),
            "donor_present_in_bank": match is not None,
            "family": None if match is None else match.get("family"),
            "p": None if match is None else match.get("p"),
        }

    # Bank fits vs fresh variational reference disclosure
    bank_receipt = json.loads((corrected / "parameter_bank_receipt.json").read_text(encoding="utf-8"))
    bank_vs_ref = {
        "bank_fits_retained": bank_receipt.get("fits_retained"),
        "bank_fit_identities": bank_receipt.get("n_fit_identities"),
        "disclosure": (
            "Parameter-bank fit records prove bank training fits retained parameter vectors. "
            "They do NOT prove that separate per-instance variational-reference fits from Phase 5 "
            "retained full parameter vectors in published evidence beyond summarised regrets. "
            "Phase 6 does not campaign-rerun historical variational references solely to fill gaps; "
            "new fits (if any) save params + eval histories."
        ),
        "historical_variational_param_vectors_in_corrected_evidence": "summarised_regrets_only_not_full_vectors",
        "phase6_fresh_variational_fits_planned": False,
        "reason_no_fresh_var_campaign": "30-minute pilot ceiling; reuse bank donors; document gap",
    }

    freeze = {
        "schema_version": "stage6.freeze.v1",
        "frozen_before_calibration_outcomes": True,
        "source_commit": source_commit,
        "phase5_final_acceptance_commit": PHASE5_FINAL_ACCEPTANCE_COMMIT,
        "phase5_corrected_run_id": PHASE5_CORRECTED_RUN_ID,
        "dirty_tree_patch_hash": dirty_tree_patch_hash,
        "pilot_config": config_to_frozen_dict(cfg),
        "artifacts": artifacts,
        "frozen_policies": {
            "learned": "RidgeDonorSelector from selector_model_artifacts.json (corrected run)",
            "fixed": "tuning-selected argmin_mean_training_normalised_regret donor per family-depth",
            "nn": "nearest training-block donor by feature L2 using train_usage best_donor_params_hash",
            "random": "seeded_random_donor over frozen bank selected donors",
        },
        "fixed_donors_by_family_depth": fixed_by_fd,
        "circuits": {
            "families": ["C0", "C1"],
            "depths": [1, 2],
            "c1_source": "repaired final_acceptance_repair executable prep",
            "c2": "NOT_ADMITTED_BY_PROTOCOL",
        },
        "classical_comparators": {
            "exact_legal_enumeration": True,
            "uniform_legal_sampling": True,
            "greedy_safe_fallback": True,
            "milp_when_inside_deadline": True,
            "strongest_timely": "exact_enumeration_when_inside_deadline_else_best_timely_heuristic",
        },
        "objective": {
            "units": "synthetic_expected_team_loss_A2",
            "normalisation": "dossier_normalised_regret_(f-f*)/(f_max-f*)",
            "legality": "one_hot_vs_complete_semantic_legal_separated",
            "tie_tolerance": cfg.tie_tol,
            "improvement_tolerance": cfg.improvement_tol,
            "ties_are_not_improvements": True,
        },
        "endpoints_and_exclusions": {
            "primary_mechanism": [
                "exact_ideal_probabilities",
                "one_hot_vs_legal_yield",
                "normalised_regret_best_of_pool",
                "strict_improvement_vs_exact_and_weak",
            ],
            "operational_race_outcome": "NOT_ELIGIBLE_without_causal_simulator_integration",
            "exclusions": [
                "final_test_blocks",
                "QPU",
                "C2",
                "paid_resources",
                "retraining_selector",
            ],
            "analysis_rules": [
                "independent_units_are_blocks",
                "preserve_SC_VSC_pairing_and_policy_seeds",
                "equal_family_weight_stratified_block_bootstrap",
                "do_not_expand_n_after_viewing_effects",
                "calibration_is_not_independent_final_test_evidence",
            ],
        },
        "noisy_panel_predeclared": {
            "enabled": cfg.noisy_panel_enabled,
            "depth_choice": cfg.noisy_depth_choice,
            "noise_model": cfg.noisy_noise_model,
            "max_qubits": cfg.noisy_max_qubits,
            "one_case_per_family": True,
            "policies": ["learned", "fixed"],
            "families": ["C0", "C1"],
            "zero_noise_consistency_control": True,
            "synthetic_noise_is_not_ibm_measurement": True,
            "freeze_basis": "development_timing_only_before_calibration_outcomes",
        },
        "bank_vs_variational_reference_audit": bank_vs_ref,
        "machine_at_freeze": machine,
        "development_unit_timing": development_unit_timing,
        "proposed_workload": proposed_workload,
        "final_acceptance_dir_present": fa.is_dir(),
        "corrected_dir_present": corrected.is_dir(),
    }
    freeze["freeze_sha256"] = sha256_json({k: v for k, v in freeze.items() if k != "freeze_sha256"})
    return freeze

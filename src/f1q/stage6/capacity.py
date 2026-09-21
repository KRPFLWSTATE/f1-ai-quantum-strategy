"""Machine capacity tables and Phase 7 resource extrapolations (labelled)."""

from __future__ import annotations

import os
import platform
import time
from typing import Any

import numpy as np

from f1q.stage5.ideal_sim import estimate_statevector_memory_bytes
from f1q.stage6.config import Phase6Config


def inspect_machine() -> dict[str, Any]:
    import resource

    mem_bytes = None
    try:
        import subprocess

        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        mem_bytes = int(out)
    except Exception:
        mem_bytes = None
    ncpu = os.cpu_count() or 1
    try:
        import shutil

        disk = shutil.disk_usage(".")
        disk_free = disk.free
        disk_total = disk.total
    except Exception:
        disk_free = disk_total = None
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "ncpu": ncpu,
        "mem_bytes": mem_bytes,
        "mem_gib": None if mem_bytes is None else mem_bytes / (1024**3),
        "ram_budget_bytes": None if mem_bytes is None else int(0.60 * mem_bytes),
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
        "rusage_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hostname_hash_note": "host identity not required for scientific claims",
    }


def dossier_phase7_counts() -> dict[str, Any]:
    """Reconcile dossier §17 proposed counts (not a claim that they fit)."""
    return {
        "main_decision_panel": {
            "cases": 80,
            "note": "held-out test floor; SC/VSC checkpoints; blocks independent units",
        },
        "ideal_circuit_panel": {
            "cases": 120,
            "families": 2,
            "depths": 2,
            "pool_seeds": 30,
            "pools_per_parameter_policy": 14400,
            "policies_learned_fixed_nn_random": 4,
            "ideal_policy_pools": 57600,
            "variational_reference_pools": 14400,
            "total_ideal_pools": 72000,
            "variational_fitting_expectation_evals_cap": 115200,
        },
        "noisy_panel": {
            "cases": 40,
            "families": 2,
            "depths": 2,
            "pool_seeds": 10,
            "pools_per_parameter_policy": 1600,
            "learned_plus_simple": 3200,
        },
        "stochastic_policy_seeds": 10,
        "shots_per_pool": 1024,
        "conditional_scaling": {
            "instances": 1200,
            "status": "separately_excluded_unless_admitted",
        },
        "ablations": "required_by_dossier_not_executed_in_phase6",
        "provisional_cpu_hour_ceiling": 24.0,
        "ceiling_is_constraint_not_assumption_matrix_fits": True,
    }


def build_capacity_estimates(
    cfg: Phase6Config,
    *,
    development_timing: dict[str, Any],
    pilot_receipt: dict[str, Any],
    repaired_resources: list[dict[str, Any]] | None,
    machine: dict[str, Any],
) -> dict[str, Any]:
    unit = float(development_timing.get("one_case_four_fd_s") or 3.5)
    # Measured from pilot
    pilot_s = float(pilot_receipt.get("elapsed_s") or 0.0)
    completed = int(pilot_receipt.get("completed_cases") or 0)
    per_case = pilot_s / completed if completed else unit * 4

    # Extrapolations clearly labelled
    ideal_pools = 72000
    # Each pool reuses ideal distribution: amortised ~ pool sample cost only after first sim
    pool_only = 0.36  # measured ~10 seeds; scale to 30 seeds ≈ 1.08s
    amortised_pool_30 = pool_only * (30 / 10)
    cold_sim = 0.16
    est_ideal_cpu_h = (ideal_pools * amortised_pool_30 + 120 * 2 * 2 * 4 * cold_sim) / 3600.0
    est_var_fit_h = 115200 * 0.05 / 3600.0  # ~50ms/eval rough from Phase 5 bank
    est_noisy_h = 3200 * (cold_sim * 5 + amortised_pool_30) / 3600.0  # noisy denser
    est_classical_h = 120 * 0.01 / 3600.0
    est_offline_train_h = 0.5  # reuse Phase 5; no retrain
    total_est = est_ideal_cpu_h + est_var_fit_h + est_noisy_h + est_classical_h + est_offline_train_h

    qubit_rows = []
    for n in (8, 10, 12, 16, 20, 30, 40):
        qubit_rows.append(
            {
                "n_qubits": n,
                "statevector_bytes_complex128": estimate_statevector_memory_bytes(n),
                "local_dense_statevector_practical_claim": n <= 20,
                "note_30_40q": (
                    "No claim that 30–40q execution is practical; native-basis decomp ≠ topology routing; "
                    "no backend-duration claim without identified target"
                    if n >= 30
                    else None
                ),
            }
        )

    # Feasible proposed Phase 7 matrix (reduced) with arithmetic
    # Preserve substantive comparisons; cut redundant resampling first
    feasible = {
        "amendment_required_before_final_test": True,
        "rationale": (
            f"Full dossier ideal 72k pools ≈ {est_ideal_cpu_h:.1f} CPU-h cold/amortised mix; "
            f"plus variational cap ≈ {est_var_fit_h:.1f} h exceeds provisional {cfg.dossier_cpu_hour_ceiling} CPU-h ceiling "
            "when combined with noisy/classical/offline. Reduce pool seeds and variational evals first."
        ),
        "proposed_counts": {
            "mechanism_calibration_reuse": "forbidden_as_final_test",
            "held_out_mechanism_cases": 80,
            "families": 2,
            "depths": 2,
            "policies": 4,
            "pool_seeds": 10,
            "ideal_pools": 80 * 2 * 2 * 4 * 10,  # 12800
            "variational_reference_cases": 40,
            "variational_max_evals_per_case": 40,
            "variational_evals": 40 * 40,  # 1600
            "noisy_cases": 16,
            "noisy_pools": 16 * 2 * 1 * 2 * 10,  # 640 at p=predeclared depth only
            "ablations": "deferred_minimal_set_post_mechanism",
            "conditional_scaling": "excluded",
            "superiority_H1": "NOT_INCLUDED_zero_headroom_gate",
        },
        "arithmetic_cpu_hours": {
            "ideal_pools_12800_x_amortised_0_36s": 12800 * 0.36 / 3600.0,
            "variational_1600_x_0_05s": 1600 * 0.05 / 3600.0,
            "noisy_640_x_2_0s": 640 * 2.0 / 3600.0,
            "classical_enum_80_x_0_01s": 80 * 0.01 / 3600.0,
            "report_packaging": 0.1,
        },
    }
    feasible["arithmetic_cpu_hours"]["sum"] = sum(
        v for k, v in feasible["arithmetic_cpu_hours"].items() if k != "sum"
    )
    feasible["fits_24h_ceiling"] = feasible["arithmetic_cpu_hours"]["sum"] <= cfg.dossier_cpu_hour_ceiling

    return {
        "machine": machine,
        "measured": {
            "development_unit": development_timing,
            "pilot_elapsed_s": pilot_s,
            "pilot_completed_cases": completed,
            "pilot_per_case_s": per_case,
        },
        "repaired_circuit_resource_rows": repaired_resources,
        "qubit_memory_table": qubit_rows,
        "dossier_full_matrix": dossier_phase7_counts(),
        "extrapolation_full_dossier_cpu_hours": {
            "label": "EXTRAPOLATION_not_measured_campaign",
            "ideal_amortised": est_ideal_cpu_h,
            "variational_fitting_cap": est_var_fit_h,
            "noisy": est_noisy_h,
            "classical": est_classical_h,
            "offline_reuse_training": est_offline_train_h,
            "total": total_est,
            "vs_24h_ceiling": total_est / cfg.dossier_cpu_hour_ceiling,
            "fits_ceiling": total_est <= cfg.dossier_cpu_hour_ceiling,
        },
        "feasible_proposed_phase7_matrix": feasible,
        "distinctions": {
            "cached_vs_cold": "Ideal distribution computed once per (case,family,depth,params); pools resample",
            "amortised": "Pool seeds are repeated measurements not independent cases",
            "native_basis_decomp_not_routing": True,
            "no_30_40q_practical_claim": True,
        },
    }

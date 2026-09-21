"""Machine capacity tables and Phase 7 resource extrapolations from measured timings."""

from __future__ import annotations

import os
import platform
import time
from typing import Any

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
            "independent_blocks": 80,
            "cases_note": (
                "Dossier often says '80 cases' for the held-out floor; Phase 6/7 protocol "
                "treats the independent statistical unit as the parent block. SC/VSC are "
                "paired checkpoints within a block, not independent blocks. "
                "Do not equate 80 blocks with 80 cases without stating pairing."
            ),
            "sc_vsc_checkpoints_per_block": 2,
            "implied_case_rows_if_both_regimes": 160,
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


def measure_component_timings(cfg: Phase6Config) -> dict[str, Any]:
    """Foreground measured costs for resource arithmetic (not hard-coded constants)."""
    import numpy as np

    from f1q.stage5.circuits_c0 import simulate_c0
    from f1q.stage5.circuits_c1 import simulate_c1
    from f1q.stage5.enumerate_policies import enumerate_legal_policies
    from f1q.stage5.model import build_a2_instance
    from f1q.stage5.qubo import build_a2_qubo
    from f1q.stage5.selector import compute_features
    from f1q.stage6.metrics_pilot import exact_distribution_metrics, pool_sample_metrics

    inst = build_a2_instance(
        instance_id="phase6.capacity.measure",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        seed=777001,
        deadline_s=cfg.deadline_s,
        n_scenarios=cfg.circuit_unit_n_scenarios,
        n_epochs=cfg.circuit_unit_n_epochs,
        n_actions=cfg.circuit_unit_n_actions,
        microcase="standard",
    )
    t0 = time.perf_counter()
    qubo = build_a2_qubo(inst)
    qubo_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    en = enumerate_legal_policies(inst)
    enum_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    feats = compute_features(inst, qubo, "C0", 1)
    feat_s = time.perf_counter() - t0

    gammas, betas = [0.3], [0.2]
    t0 = time.perf_counter()
    sim0 = simulate_c0(qubo, gammas, betas, scaled=True)
    c0_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    sim1 = simulate_c1(inst, qubo, gammas, betas, scaled=True)
    c1_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = exact_distribution_metrics(
        inst,
        sim0["probs"],
        exact_cost=en.get("f_star"),
        f_max=en.get("f_max"),
        weak_incumbent_cost=None,
        improvement_tol=cfg.improvement_tol,
    )
    exact_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    pool = pool_sample_metrics(
        inst,
        sim0["probs"],
        exact_cost=en.get("f_star"),
        f_max=en.get("f_max"),
        pool_size=1024,
        seed=42,
    )
    pool_1024_s = time.perf_counter() - t0

    # Optional gate-noise cost on ≤8q
    noisy_s = None
    try:
        from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit
        from f1q.stage6.noisy import simulate_circuit_with_depolarizing

        if qubo["n"] <= 8:
            built = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)
            t0 = time.perf_counter()
            _ = simulate_circuit_with_depolarizing(built["circuit"], p1=1e-3, p2=1e-2)
            noisy_s = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001 — measurement best-effort
        noisy_s = None
        noisy_err = str(exc)
    else:
        noisy_err = None

    return {
        "n_qubits": qubo["n"],
        "n_legal": en.get("n_legal"),
        "measured_s": {
            "instance_qubo_construction": qubo_s,
            "exact_legal_reference_enum": enum_s,
            "features": feat_s,
            "circuit_c0_p1_evolution": c0_s,
            "circuit_c1_p1_evolution": c1_s,
            "exact_distribution_scan": exact_s,
            "one_pool_1024_draws": pool_1024_s,
            "gate_depolarizing_density_matrix": noisy_s,
        },
        "pool_shot_conservation_ok": pool.get("shot_conservation_ok"),
        "actual_draws": pool.get("actual_draws"),
        "features_keys": sorted(feats.keys()),
        "noisy_measure_error": noisy_err,
        "label": "MEASURED_local_representative_not_full_campaign",
    }


def build_capacity_estimates(
    cfg: Phase6Config,
    *,
    development_timing: dict[str, Any],
    pilot_receipt: dict[str, Any],
    repaired_resources: list[dict[str, Any]] | None,
    machine: dict[str, Any],
    measured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    measured = measured or measure_component_timings(cfg)
    m = measured["measured_s"]

    pilot_s = float(pilot_receipt.get("elapsed_s") or 0.0)
    completed = int(pilot_receipt.get("completed_cases") or 0)
    per_case = pilot_s / completed if completed else None

    # Unique distributions per case: 4 family-depths × 4 policies (params may collide; upper bound)
    cold_sim = float(np_mean([m["circuit_c0_p1_evolution"], m["circuit_c1_p1_evolution"]]))
    pool_s = float(m["one_pool_1024_draws"])
    enum_s = float(m["exact_legal_reference_enum"])
    qubo_s = float(m["instance_qubo_construction"])
    exact_scan_s = float(m["exact_distribution_scan"])
    feat_s = float(m["features"])
    noisy_s = m.get("gate_depolarizing_density_matrix")

    dossier = dossier_phase7_counts()
    ideal_pools = int(dossier["ideal_circuit_panel"]["total_ideal_pools"])
    # Amortised model: unique (case, family, depth, policy) cold sims + incremental pools
    # 120 cases × 2 fam × 2 depth × 4 policies = 1920 unique distributions (upper)
    n_unique_dist = 120 * 2 * 2 * 4
    n_pool_seeds = 30
    # Do NOT multiply seed counts twice: pools already = unique × seeds in dossier total
    # Use dossier total pools for incremental pool cost; unique for cold sim.
    est_ideal_cpu_s = (
        n_unique_dist * (qubo_s / 4 + cold_sim + exact_scan_s)  # qubo shared ~4 ways
        + ideal_pools * pool_s
        + 120 * enum_s
        + n_unique_dist * feat_s
    )
    est_var_fit_s = 115200 * cold_sim  # eval ≈ one circuit evolution (measured)
    est_noisy_s = (
        40 * 2 * 2 * 2 * (float(noisy_s) if noisy_s is not None else cold_sim * 20)
        + 3200 * pool_s
    )
    est_classical_s = 120 * enum_s
    est_offline_s = 0.5 * 3600  # reuse Phase 5 training; labelled prior cost
    total_est_s = est_ideal_cpu_s + est_var_fit_s + est_noisy_s + est_classical_s + est_offline_s
    total_est_h = total_est_s / 3600.0

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

    # Feasible proposed Phase 7 matrix — preserve comparisons; do not cut cases solely for bad estimate
    # Independent statistical unit = block. Held-out mechanism: 80 blocks (not 80 cases).
    held_out_blocks = 80
    cases_per_block = 2  # SC+VSC paired
    held_out_cases = held_out_blocks * cases_per_block
    families = 2
    depths = 2
    policies = 4
    pool_seeds = 10
    ideal_pools_reduced = held_out_cases * families * depths * policies * pool_seeds
    var_cases = 40
    var_evals_per = 40
    var_evals = var_cases * var_evals_per
    noisy_cases = 16
    noisy_pools = noisy_cases * 2 * 1 * 2 * pool_seeds

    arith_s = {
        "unique_dist_approx": held_out_cases * families * depths * policies,
        "cold_sim_plus_exact_scan_s": held_out_cases
        * families
        * depths
        * policies
        * (cold_sim + exact_scan_s),
        "ideal_pools_incremental_s": ideal_pools_reduced * pool_s,
        "enum_s": held_out_cases * enum_s,
        "features_s": held_out_cases * families * depths * policies * feat_s,
        "variational_evals_s": var_evals * cold_sim,
        "noisy_exact_s": noisy_cases * 2 * 1 * 2 * (float(noisy_s) if noisy_s else cold_sim * 20),
        "noisy_pools_s": noisy_pools * pool_s,
        "report_packaging_s": 360.0,
    }
    arith_s["sum_s"] = sum(v for k, v in arith_s.items() if k.endswith("_s") or k == "report_packaging_s")
    # Fix sum: only timing values
    arith_s["sum_s"] = (
        arith_s["cold_sim_plus_exact_scan_s"]
        + arith_s["ideal_pools_incremental_s"]
        + arith_s["enum_s"]
        + arith_s["features_s"]
        + arith_s["variational_evals_s"]
        + arith_s["noisy_exact_s"]
        + arith_s["noisy_pools_s"]
        + arith_s["report_packaging_s"]
    )
    arith_h = {k: (v / 3600.0 if isinstance(v, (int, float)) and k != "unique_dist_approx" else v) for k, v in arith_s.items()}
    arith_h["sum_cpu_hours"] = arith_s["sum_s"] / 3600.0
    # Conservative range: ×1.0–×2.0 for cold-cache variance / larger qubits
    arith_h["conservative_range_cpu_hours"] = [
        arith_h["sum_cpu_hours"],
        arith_h["sum_cpu_hours"] * 2.0,
    ]

    feasible = {
        "amendment_required_before_final_test": True,
        "rationale": (
            f"Full dossier ideal pools amortised from measured component timings ≈ {total_est_h:.2f} CPU-h "
            f"(prior hard-coded 25.46h withdrawn). Reduced matrix uses 80 independent blocks "
            f"({held_out_cases} SC+VSC case rows), pool_seeds={pool_seeds}, measured pool_1024={pool_s:.4f}s. "
            "Seeds are not double-counted. Variational reference retained at reduced but nonzero budget."
        ),
        "blocks_vs_cases_resolution": {
            "independent_statistical_unit": "block",
            "held_out_mechanism_blocks": held_out_blocks,
            "checkpoints_per_block": cases_per_block,
            "case_rows": held_out_cases,
            "do_not_collapse_80_blocks_to_80_cases": True,
        },
        "proposed_counts": {
            "mechanism_calibration_reuse": "forbidden_as_final_test",
            "held_out_mechanism_blocks": held_out_blocks,
            "held_out_mechanism_case_rows_sc_vsc": held_out_cases,
            "families": families,
            "depths": depths,
            "policies": policies,
            "pool_seeds": pool_seeds,
            "ideal_pools": ideal_pools_reduced,
            "variational_reference_cases": var_cases,
            "variational_max_evals_per_case": var_evals_per,
            "variational_evals": var_evals,
            "noisy_cases": noisy_cases,
            "noisy_pools": noisy_pools,
            "ablations": "minimal_set_required_disclosed_if_deferred",
            "conditional_scaling": "excluded",
            "superiority_H1": "NOT_INCLUDED_zero_headroom_gate",
        },
        "arithmetic_cpu_hours_measured": arith_h,
        "parallelism_assumption": "serial CPU-hours; wall-hours = CPU-hours / min(workers, ncpu) with workers<=2",
        "fits_24h_ceiling": arith_h["conservative_range_cpu_hours"][1] <= cfg.dossier_cpu_hour_ceiling
        or arith_h["sum_cpu_hours"] <= cfg.dossier_cpu_hour_ceiling,
    }

    return {
        "machine": machine,
        "measured_components": measured,
        "measured_pilot": {
            "development_unit": development_timing,
            "pilot_elapsed_s": pilot_s,
            "pilot_completed_cases": completed,
            "pilot_per_case_s": per_case,
            "pilot_cpu_note": "wall ≈ CPU under max_workers=1 default; track separately when parallel",
        },
        "repaired_circuit_resource_rows": repaired_resources,
        "qubit_memory_table": qubit_rows,
        "dossier_full_matrix": dossier,
        "extrapolation_full_dossier_cpu_hours": {
            "label": "EXTRAPOLATION_from_measured_components_not_full_campaign",
            "hard_coded_constants_withdrawn": True,
            "prior_unsupported_25_46h_note": "superseded; was based on hard-coded 0.36s/pool and double-count risk",
            "ideal_amortised": est_ideal_cpu_s / 3600.0,
            "variational_fitting_cap": est_var_fit_s / 3600.0,
            "noisy": est_noisy_s / 3600.0,
            "classical": est_classical_s / 3600.0,
            "offline_reuse_training": est_offline_s / 3600.0,
            "total": total_est_h,
            "vs_24h_ceiling": total_est_h / cfg.dossier_cpu_hour_ceiling,
            "fits_ceiling": total_est_h <= cfg.dossier_cpu_hour_ceiling,
            "uncertainty": "factor_2_conservative_band_recommended",
        },
        "feasible_proposed_phase7_matrix": feasible,
        "distinctions": {
            "cached_vs_cold": "Ideal distribution computed once per (case,family,depth,params); pools resample",
            "amortised": "Pool seeds are repeated measurements not independent cases — not multiplied twice",
            "cpu_vs_wall": "Estimates are CPU-seconds; wall depends on <=2 workers",
            "native_basis_decomp_not_routing": True,
            "no_30_40q_practical_claim": True,
        },
    }


def np_mean(xs: list[float]) -> float:
    return float(sum(xs) / max(len(xs), 1))

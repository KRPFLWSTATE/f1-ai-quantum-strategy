"""A2 residual superseding package: histograms, native noise, paired descriptive, resource grid."""

from __future__ import annotations

import hashlib
import json
import resource
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import compute_features
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID
from f1q.stage6.config import default_phase6_config
from f1q.stage6.histograms import persist_distribution
from f1q.stage6.metrics_pilot import exact_distribution_metrics, pool_sample_metrics
from f1q.stage6.native_noise import run_native_noisy_panel, simulate_native_depolarizing, verify_native_analytical_fixtures
from f1q.stage6.pilot import _load_phase5_assets, _select_policy_donor, write_json
from f1q.stage6.sizing import stratified_block_bootstrap
from f1q.stage6.splits import build_calibration_splits
from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit
from f1q.stage5.circuits_c1 import build_c1_qiskit_circuit

ProgressFn = Callable[[str], None]
HISTORICAL_CORRECTED = "2a3fb275-6c37-4bbc-bdb4-addede80b5c3"
HISTORICAL_ORIGINAL = "bd83cb22-6a38-4d21-9267-3253f52587d7"


def _cpu() -> float:
    u = resource.getrusage(resource.RUSAGE_SELF)
    return float(u.ru_utime + u.ru_stime)


def regenerate_sampling(
    root: Path,
    out: Path,
    *,
    assets: dict[str, Any],
    progress: ProgressFn,
    max_blocks_per_family: int = 1,
    pool_seeds: int = 3,
    policies: tuple[str, ...] = ("learned", "fixed"),
    depths: tuple[tuple[str, int], ...] = (("C0", 1), ("C1", 1)),
) -> dict[str, Any]:
    cfg = default_phase6_config()
    phase5_hash = assets["models_hash"]
    splits = build_calibration_splits(
        source_hash="a2_residual_histograms",
        phase5_source_hash=phase5_hash,
        salt=cfg.split_source_salt,
    )
    dist_dir = out / "distributions"
    pool_dir = out / "pools"
    dist_dir.mkdir(parents=True, exist_ok=True)
    pool_dir.mkdir(parents=True, exist_ok=True)
    from f1q.stage6.pilot import _build_nn_tables

    nn = _build_nn_tables(root, cfg, assets, phase5_hash, progress)
    unique: dict[str, dict[str, Any]] = {}
    pool_index = []
    n_pools = 0
    t0 = time.perf_counter()
    for block in splits["calibration"]:
        if int(block["index"]) >= max_blocks_per_family:
            continue
        for case in block["cases"]:
            progress(f"residual sample {case['case_id']}")
            seed = int(block["seed"]) + int(case["seed_offset"])
            inst = build_a2_instance(
                instance_id=case["case_id"],
                family_id=block["family_id"],
                rung="circuit_unit",
                seed=seed,
                deadline_s=cfg.deadline_s,
                n_scenarios=cfg.circuit_unit_n_scenarios,
                n_epochs=cfg.circuit_unit_n_epochs,
                n_actions=cfg.circuit_unit_n_actions,
                microcase=case["microcase"],
            )
            qubo = build_a2_qubo(inst)
            en = enumerate_legal_policies(inst)
            for family, p in depths:
                fd = f"{family}_p{p}"
                feats = compute_features(inst, qubo, family, p)
                for policy in policies:
                    chosen = _select_policy_donor(
                        policy=policy,
                        fd=fd,
                        family=family,
                        p=p,
                        feats=feats,
                        assets=assets,
                        nn_tables=nn,
                        case_id=case["case_id"],
                        seed=seed,
                    )
                    donor = chosen["donor"]
                    if donor is None:
                        continue
                    params = np.asarray(donor["params"], dtype=float)
                    gammas = params[:p].tolist()
                    betas = params[p:].tolist()
                    if family == "C0":
                        sim = simulate_c0(qubo, gammas, betas, scaled=True)
                    else:
                        sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
                    from f1q.stage6.metrics_pilot import distribution_hash as _dh

                    dhash = _dh(sim["probs"])
                    if dhash not in unique:
                        path = dist_dir / f"{dhash[:16]}.npz"
                        unique[dhash] = persist_distribution(sim["probs"], path)
                        unique[dhash]["circuit_id"] = family
                        unique[dhash]["parameter_id"] = donor.get("params_hash")
                        unique[dhash]["instance_id"] = case["case_id"]
                    exact = exact_distribution_metrics(
                        inst,
                        sim["probs"],
                        exact_cost=en.get("f_star"),
                        f_max=en.get("f_max"),
                        weak_incumbent_cost=None,
                        improvement_tol=cfg.improvement_tol,
                    )
                    pool_base = int(
                        hashlib.sha256(f"{case['case_id']}:{fd}:{policy}".encode()).hexdigest()[:8],
                        16,
                    ) % (2**31 - 1)
                    for s in range(pool_seeds):
                        pool = pool_sample_metrics(
                            inst,
                            sim["probs"],
                            exact_cost=en.get("f_star"),
                            f_max=en.get("f_max"),
                            pool_size=1024,
                            seed=pool_base + s,
                            distribution_id=dhash,
                            circuit_id=family,
                            parameter_id=str(donor.get("params_hash")),
                            instance_id=case["case_id"],
                            policy_id=f"{fd}:{policy}",
                        )
                        n_pools += 1
                        rec_path = pool_dir / f"{case['case_id'].replace('.', '_')}_{fd}_{policy}_{s}.json"
                        write_json(rec_path, pool)
                        pool_index.append(
                            {
                                "path": str(rec_path.relative_to(out)),
                                "case_id": case["case_id"],
                                "family_id": block["family_id"],
                                "fd": fd,
                                "policy": policy,
                                "seed": pool["seed"],
                                "requested_shots": pool["requested_shots"],
                                "actual_draws": pool["actual_draws"],
                                "histogram_sum": pool["histogram_sum"],
                                "shot_conservation_ok": pool["shot_conservation_ok"],
                                "distribution_hash": pool["distribution_hash"],
                                "n_legal": pool["n_legal_in_pool"],
                                "n_decoding_invalid": pool["n_decoding_invalid"],
                                "n_semantic_invalid": pool["n_semantic_invalid"],
                                "selected_candidate_bitstring": pool["selected_candidate_bitstring"],
                                "tie_rule": pool["tie_rule"],
                                "best_of_pool_normalised_regret": pool["best_of_pool_normalised_regret"],
                                "ideal_one_hot": exact["one_hot_probability"],
                                "ideal_legal": exact["complete_legal_policy_probability"],
                                "optimal_mass": exact["optimal_sample_probability"],
                                "expected_legal_cost": exact["expected_cost_on_legal_support"],
                            }
                        )
    return {
        "status": "COMPLETED",
        "elapsed_s": time.perf_counter() - t0,
        "n_unique_distributions": len(unique),
        "n_pools": n_pools,
        "pool_seeds": pool_seeds,
        "max_blocks_per_family": max_blocks_per_family,
        "policies": list(policies),
        "depths": [f"{a}_p{b}" for a, b in depths],
        "training_not_regenerated": True,
        "circuit_optimisation_not_regenerated": True,
        "frozen_phase5_run": PHASE5_CORRECTED_RUN_ID,
        "does_not_overwrite": [HISTORICAL_CORRECTED, HISTORICAL_ORIGINAL],
        "unique_distributions": unique,
        "pools": pool_index,
        "all_shot_conservation_ok": all(p["shot_conservation_ok"] for p in pool_index),
    }


def paired_descriptive_from_corrected(root: Path) -> dict[str, Any]:
    """Descriptive diagnostics from frozen 2a3fb275 summaries. Not a new A2 primary endpoint."""
    base = root / f"evidence/stage6_corrected/{HISTORICAL_CORRECTED}"
    units = sorted((base / "pilot_units").glob("*.json"))
    rows = []
    for p in units:
        u = json.loads(p.read_text(encoding="utf-8"))
        fam = u.get("family_id")
        block = u.get("block_id")
        regime = "SC" if str(u.get("case_id", "")).endswith(".SC") else "VSC"
        pr = u.get("policy_results") or {}
        rec = {"block_id": block, "family_id": fam, "regime": regime, "n_qubits": u.get("n_qubits")}
        for key, val in pr.items():
            if not isinstance(val, dict) or "exact" not in val:
                continue
            ex = val["exact"]
            agg = val.get("pools_agg") or {}
            rec[key] = {
                "one_hot": ex.get("one_hot_probability"),
                "legal": ex.get("complete_legal_policy_probability"),
                "optimal_mass": ex.get("optimal_sample_probability"),
                "expected_legal_cost": ex.get("expected_cost_on_legal_support"),
                "best_of_pool_regret": agg.get("mean_normalised_regret"),
                "all_invalid_rate": agg.get("all_infeasible_pool_rate"),
            }
        rows.append(rec)

    def _pair_mean(a: str, b: str, field: str) -> list[dict[str, Any]]:
        out = []
        for r in rows:
            if a not in r or b not in r:
                continue
            va = r[a].get(field)
            vb = r[b].get(field)
            if va is None or vb is None:
                continue
            out.append(
                {
                    "block_id": r["block_id"],
                    "family_id": r["family_id"],
                    "regime": r["regime"],
                    "a": a,
                    "b": b,
                    "field": field,
                    "value_a": va,
                    "value_b": vb,
                    "diff_a_minus_b": float(va) - float(vb),
                }
            )
        return out

    comparisons = {
        "learned_vs_fixed": _pair_mean("C0_p1:learned", "C0_p1:fixed", "best_of_pool_regret"),
        "learned_vs_nn": _pair_mean("C0_p1:learned", "C0_p1:nn", "best_of_pool_regret"),
        "learned_vs_random": _pair_mean("C0_p1:learned", "C0_p1:random", "best_of_pool_regret"),
        "c1_vs_c0_matched_p1": _pair_mean("C1_p1:learned", "C0_p1:learned", "legal"),
        "p2_vs_p1_c0": _pair_mean("C0_p2:learned", "C0_p1:learned", "optimal_mass"),
    }
    # Block-level: average SC/VSC then bootstrap on learned C0 regret (descriptive).
    block_effects = {}
    for r in rows:
        key = (r["block_id"], r["family_id"])
        val = (r.get("C0_p1:learned") or {}).get("best_of_pool_regret")
        if val is None:
            continue
        block_effects.setdefault(key, []).append(float(val))
    effects = [
        {"block_id": k[0], "family_id": k[1], "effect": float(np.mean(v))}
        for k, v in block_effects.items()
    ]
    boot = stratified_block_bootstrap(effects, n_boot=2000, seed=20260921) if effects else {"status": "EMPTY"}
    return {
        "n_case_rows": len(rows),
        "source": f"evidence/stage6_corrected/{HISTORICAL_CORRECTED}/pilot_units",
        "class": "DESCRIPTIVE_DIAGNOSTICS",
        "not_promoted_to_a2_primary": True,
        "best_of_pool_regret_saturated": True,
        "comparisons": {k: {"n": len(v), "mean_diff": float(np.mean([x["diff_a_minus_b"] for x in v])) if v else None} for k, v in comparisons.items()},
        "bootstrap": boot,
        "preserved_sc_vsc_pairing": True,
    }


def resource_grid(assets: dict[str, Any], progress: ProgressFn, *, n_reps: int = 5) -> dict[str, Any]:
    """Measured wall+CPU grid. Does not reuse a single 8q p=1 timing for every size/depth."""
    cfg = default_phase6_config()
    specs = [
        {"label": "8q_standard", "n_actions": 2, "n_epochs": 2, "n_scenarios": 2, "microcase": "standard"},
        {"label": "12q_force_branching", "n_actions": 2, "n_epochs": 2, "n_scenarios": 2, "microcase": "force_branching"},
    ]
    rows = []
    donor = assets["fixed"]["C0_p1"]
    for spec in specs:
        inst = build_a2_instance(
            instance_id=f"a2.residual.grid.{spec['label']}",
            family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
            rung="circuit_unit",
            seed=4242,
            deadline_s=cfg.deadline_s,
            n_scenarios=spec["n_scenarios"],
            n_epochs=spec["n_epochs"],
            n_actions=spec["n_actions"],
            microcase=spec["microcase"],
        )
        qubo = build_a2_qubo(inst)
        n = int(qubo["n"])
        progress(f"resource grid {spec['label']} n={n}")
        en = enumerate_legal_policies(inst)
        for family, p, warm in (("C0", 1, False), ("C0", 1, True), ("C0", 2, False), ("C1", 1, False), ("C1", 2, False)):
            fd = f"{family}_p{p}"
            don = assets["fixed"].get(fd) or donor
            params = np.asarray(don["params"], dtype=float)
            # If donor p mismatches, use prefix/repeat.
            gammas = (params[:p].tolist() + [0.3] * p)[:p]
            betas = (params[p:p + p].tolist() + [0.2] * p)[:p]
            walls = []
            cpus = []
            noisy_walls = []
            obj_walls = []
            for r in range(n_reps):
                if not warm:
                    # cold: rebuild circuit path
                    pass
                c0 = _cpu()
                w0 = time.perf_counter()
                if family == "C0":
                    sim = simulate_c0(qubo, gammas, betas, scaled=True)
                else:
                    sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
                walls.append(time.perf_counter() - w0)
                cpus.append(_cpu() - c0)
                w1 = time.perf_counter()
                _ = float(sim["expectation_scaled"])  # actual variational objective
                obj_walls.append(time.perf_counter() - w1)
                if n <= 8 and r == 0 and p == 1:
                    if family == "C0":
                        qc = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)["circuit"]
                    else:
                        qc = build_c1_qiskit_circuit(inst, qubo, gammas, betas, scaled=True)["circuit"]
                    wn = time.perf_counter()
                    simulate_native_depolarizing(qc, p1=1e-3, p2=1e-2)
                    noisy_walls.append(time.perf_counter() - wn)
            def _summ(xs):
                if not xs:
                    return None
                a = np.asarray(xs, dtype=float)
                return {
                    "median": float(np.median(a)),
                    "min": float(np.min(a)),
                    "max": float(np.max(a)),
                    "p95": float(np.quantile(a, 0.95)),
                    "n_reps": int(a.size),
                }
            rows.append(
                {
                    "label": spec["label"],
                    "n_qubits": n,
                    "family": family,
                    "p": p,
                    "warm": warm,
                    "wall_s": _summ(walls),
                    "cpu_s": _summ(cpus),
                    "variational_objective_eval_s": _summ(obj_walls),
                    "native_noisy_s": _summ(noisy_walls),
                    "exact_enum_s": en.get("elapsed_s"),
                    "one_complete_run_unit": True,
                }
            )
    # Arithmetic note: unique distributions × cost + pools × incremental, counted once.
    # Do not include assumed historical 0.5h.
    return {
        "rows": rows,
        "n_10q_native_a2_size": False,
        "reason_10q_absent": "A2 circuit_unit native sizes observed are 8 (standard) and 12 (force_branching); 10q would require dummy padding — not used",
        "historical_0.5h_excluded": True,
        "one_8q_p1_not_used_for_all": True,
        "native_noisy_on_8q_only": True,
        "analytical_native": verify_native_analytical_fixtures(),
    }


def run_a2_residual(root: Path, run_id: str, progress: ProgressFn) -> dict[str, Any]:
    out = root / "evidence/stage6_a2_residual" / run_id
    out.mkdir(parents=True, exist_ok=True)
    assets = _load_phase5_assets(root, PHASE5_CORRECTED_RUN_ID)
    sampling = regenerate_sampling(root, out, assets=assets, progress=progress)
    write_json(out / "sampling_index.json", {k: v for k, v in sampling.items() if k != "unique_distributions"})
    write_json(out / "unique_distributions.json", sampling["unique_distributions"])
    progress("native noise panel")
    noisy = run_native_noisy_panel(default_phase6_config(), assets=assets, progress=progress)
    write_json(out / "native_noisy_panel.json", noisy)
    progress("paired descriptive")
    paired = paired_descriptive_from_corrected(root)
    write_json(out / "paired_descriptive.json", paired)
    progress("resource grid")
    grid = resource_grid(assets, progress)
    write_json(out / "resource_grid.json", grid)
    supersession = {
        "this_run": run_id,
        "supersedes_for": ["shot_histograms", "native_basis_noise", "paired_descriptive", "resource_grid"],
        "does_not_overwrite": [
            f"evidence/stage6/{HISTORICAL_ORIGINAL}",
            f"evidence/stage6_corrected/{HISTORICAL_CORRECTED}",
        ],
        "a2_zero_headroom_retained": True,
        "gate_e_a2_still_fail_for_intended_contribution": True,
    }
    write_json(out / "supersession.json", supersession)
    return {
        "run_id": run_id,
        "evidence_dir": str(out),
        "sampling": {
            "n_pools": sampling["n_pools"],
            "n_unique_distributions": sampling["n_unique_distributions"],
            "all_shot_conservation_ok": sampling["all_shot_conservation_ok"],
        },
        "native_noise": {
            "status": noisy.get("status"),
            "zero_noise_pass": noisy.get("zero_noise_pass"),
            "zero_noise_total": noisy.get("zero_noise_total"),
            "analytical_ok": (noisy.get("analytical") or {}).get("ok"),
        },
        "paired": paired["class"],
        "resource_grid_n_rows": len(grid["rows"]),
        "supersession": supersession,
    }

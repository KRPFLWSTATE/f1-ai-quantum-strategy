"""Bounded local mechanism pilot — resumable units, progress ≥30s, atomic writes."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.heuristic import greedy_safe_fallback
from f1q.stage5.milp import solve_a2_milp
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import (
    RidgeDonorSelector,
    compute_features,
    nn_transfer_donor,
    seeded_random_donor,
)
from f1q.stage5.splits import build_phase5_splits
from f1q.stage6.config import Phase6Config
from f1q.stage6.metrics_pilot import aggregate_pools, exact_distribution_metrics, pool_sample_metrics


ProgressFn = Callable[[str], None]


def write_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str)
    atomic_write_text(path, text + "\n")
    return sha256_file(path)


def measure_development_unit(cfg: Phase6Config) -> dict[str, Any]:
    """Representative development timing before freezing workload."""
    inst = build_a2_instance(
        instance_id="phase6.dev.timing",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        seed=424242,
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
    rows = {}
    for family, p in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        gammas = [0.3] * p
        betas = [0.2] * p
        t0 = time.perf_counter()
        if family == "C0":
            sim = simulate_c0(qubo, gammas, betas, scaled=True)
        else:
            sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
        sim_s = time.perf_counter() - t0
        exact = exact_distribution_metrics(
            inst,
            sim["probs"],
            exact_cost=en.get("f_star"),
            f_max=en.get("f_max"),
            weak_incumbent_cost=None,
            improvement_tol=cfg.improvement_tol,
        )
        pools = [
            pool_sample_metrics(
                inst,
                sim["probs"],
                exact_cost=en.get("f_star"),
                f_max=en.get("f_max"),
                pool_size=cfg.pool_shots,
                seed=s,
            )
            for s in range(cfg.pool_seeds)
        ]
        rows[f"{family}_p{p}"] = {
            "sim_s": sim_s,
            "exact_s": exact["exact_scan_s"],
            "pools_s": sum(p["pool_s"] for p in pools),
            "n": qubo["n"],
        }
    unit_s = sum(v["sim_s"] + v["exact_s"] + v["pools_s"] for v in rows.values())
    return {
        "n_qubits": qubo["n"],
        "n_legal": en.get("n_legal"),
        "qubo_s": qubo_s,
        "enum_s": enum_s,
        "per_family_depth": rows,
        "one_case_four_fd_s": unit_s,
        "est_48_cases_one_policy_s": unit_s * 48,
        "est_48_cases_four_policies_s": unit_s * 48 * 4,
    }


def _load_phase5_assets(root: Path, run_id: str) -> dict[str, Any]:
    base = root / f"evidence/stage5/{run_id}"
    models = json.loads((base / "selector_model_artifacts.json").read_text(encoding="utf-8"))
    donors = json.loads((base / "donor_inventory.json").read_text(encoding="utf-8"))
    tuning = json.loads((base / "selector_tuning_results.json").read_text(encoding="utf-8"))
    train_usage = json.loads((base / "selector_train_usage.json").read_text(encoding="utf-8"))
    frozen_cfg = json.loads((base / "frozen_config.json").read_text(encoding="utf-8"))
    selectors = {fd: RidgeDonorSelector.from_artifact(art) for fd, art in models.items()}
    fixed: dict[str, Any] = {}
    for fd, row in tuning.get("per_family_depth", {}).items():
        ph = row.get("fixed_donor_params_hash")
        match = next((d for d in donors[fd]["selected"] if d.get("params_hash") == ph), None)
        if match is None and donors[fd]["selected"]:
            match = donors[fd]["selected"][0]
        fixed[fd] = match
    return {
        "selectors": selectors,
        "donors": donors,
        "fixed": fixed,
        "train_usage": train_usage,
        "frozen_cfg": frozen_cfg,
        "models_hash": sha256_file(base / "selector_model_artifacts.json"),
        "donors_hash": sha256_file(base / "donor_inventory.json"),
    }


def _build_nn_tables(
    root: Path,
    cfg: Phase6Config,
    assets: dict[str, Any],
    phase5_source_hash: str,
    progress: ProgressFn,
) -> dict[str, Any]:
    """Rebuild training features cheaply; map best donor hashes from train_usage."""
    splits = build_phase5_splits(source_hash=phase5_source_hash)
    train_blocks = splits["anchors"] + splits["training_extra"]
    tables: dict[str, Any] = {}
    for family, p in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        fd = f"{family}_p{p}"
        progress(f"nn table {fd}")
        usage = {u["block_id"]: u for u in assets["train_usage"][fd]}
        donor_by_hash = {d["params_hash"]: d for d in assets["donors"][fd]["selected"]}
        feats_list: list[dict[str, float]] = []
        donors_list: list[dict[str, Any]] = []
        for block in train_blocks:
            inst = build_a2_instance(
                instance_id=block["block_id"],
                family_id=block["family_id"],
                rung="circuit_unit",
                seed=int(block["seed"]),
                deadline_s=cfg.deadline_s,
                n_scenarios=cfg.circuit_unit_n_scenarios,
                n_epochs=cfg.circuit_unit_n_epochs,
                n_actions=cfg.circuit_unit_n_actions,
            )
            qubo = build_a2_qubo(inst)
            feats = compute_features(inst, qubo, family, p)
            feats_list.append(feats)
            uh = usage.get(block["block_id"], {})
            ph = uh.get("best_donor_params_hash")
            donors_list.append(donor_by_hash.get(ph) or assets["fixed"][fd])
        tables[fd] = {"train_feats": feats_list, "fitted_donors": donors_list}
    return tables


def _select_policy_donor(
    *,
    policy: str,
    fd: str,
    family: str,
    p: int,
    feats: dict[str, float],
    assets: dict[str, Any],
    nn_tables: dict[str, Any],
    case_id: str,
    seed: int,
) -> dict[str, Any]:
    donors = assets["donors"][fd]["selected"]
    if policy == "learned":
        sel = assets["selectors"][fd].select(feats, donors)
        return {"donor": sel["selected_donor"], "detail": {"rule": sel["rule"], "index": sel["selected_index"]}}
    if policy == "fixed":
        return {"donor": assets["fixed"][fd], "detail": {"rule": "tuning_selected_fixed"}}
    if policy == "nn":
        tab = nn_tables[fd]
        info = nn_transfer_donor(feats, tab["train_feats"], tab["fitted_donors"])
        return {
            "donor": info["donor"] or assets["fixed"][fd],
            "detail": {
                "rule": "nn_feature_l2",
                "nearest_train_index": info.get("nearest_train_index"),
                "distance": info.get("distance"),
            },
        }
    rnd = seeded_random_donor(donors, case_id, seed)
    return {"donor": rnd["donor"], "detail": {"rule": "seeded_random", "index": rnd["index"]}}


def _evaluate_donor_distribution(
    inst,
    qubo,
    donor: dict[str, Any],
    *,
    exact_cost: float | None,
    f_max: float | None,
    weak_cost: float | None,
    cfg: Phase6Config,
    pool_base_seed: int,
) -> dict[str, Any]:
    family = donor["family"]
    p = int(donor["p"])
    params = np.asarray(donor["params"], dtype=float)
    gammas = params[:p].tolist()
    betas = params[p:].tolist()
    t0 = time.perf_counter()
    if family == "C0":
        sim = simulate_c0(qubo, gammas, betas, scaled=True)
    else:
        sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
    sim_s = time.perf_counter() - t0
    exact = exact_distribution_metrics(
        inst,
        sim["probs"],
        exact_cost=exact_cost,
        f_max=f_max,
        weak_incumbent_cost=weak_cost,
        improvement_tol=cfg.improvement_tol,
    )
    pools = [
        pool_sample_metrics(
            inst,
            sim["probs"],
            exact_cost=exact_cost,
            f_max=f_max,
            pool_size=cfg.pool_shots,
            seed=pool_base_seed + s,
        )
        for s in range(cfg.pool_seeds)
    ]
    # Do not retain full probability vectors in evidence (storage).
    return {
        "family": family,
        "p": p,
        "params_hash": donor.get("params_hash"),
        "sim_s": sim_s,
        "norm": float(sim["norm"]),
        "expectation_scaled": float(sim["expectation_scaled"]),
        "amp_outside_one_hot": float(sim.get("amp_outside_one_hot", 0.0)),
        "exact": exact,
        "pools": pools,
        "pools_agg": aggregate_pools(pools),
        "strict_improvement_vs_exact": float(exact["strictly_improving_vs_exact_probability"]),
        "zero_headroom_declared": exact_cost is not None
        and float(exact["strictly_improving_vs_exact_probability"]) <= cfg.improvement_tol,
    }


def uniform_legal_sample(
    inst,
    *,
    exact_cost: float | None,
    f_max: float | None,
    pool_size: int,
    seed: int,
) -> dict[str, Any]:
    """Uniform over legal one-hot policies (classical comparator), equal shot budget."""
    from f1q.stage5.encode import binary_to_policy
    from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
    from f1q.stage5.metrics import normalised_regret

    n = inst.n_logical_vars()
    legal_costs: list[float] = []
    for b in range(1 << n):
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(inst, x)
        if pol is None:
            continue
        if not check_policy_legal(inst, pol)["legal"]:
            continue
        legal_costs.append(float(evaluate_policy_cost(inst, pol)["expected_cost"]))
    if not legal_costs:
        return {
            "success": False,
            "n_legal": 0,
            "mean_normalised_regret": 1.0,
            "best_of_pool_normalised_regret": 1.0,
        }
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(legal_costs), size=pool_size)
    best = min(legal_costs[int(i)] for i in picks)
    return {
        "success": True,
        "n_legal": len(legal_costs),
        "pool_size": int(pool_size),
        "best_of_pool_cost": float(best),
        "best_of_pool_normalised_regret": normalised_regret(best, exact_cost, f_max, feasible=True),
        "mean_legal_cost": float(np.mean(legal_costs)),
        "method": "uniform_over_legal_one_hot_policies",
    }


def run_mechanism_pilot(
    root: Path,
    cfg: Phase6Config,
    calibration: list[dict[str, Any]],
    *,
    evidence_dir: Path,
    progress: ProgressFn,
    phase5_source_hash: str,
) -> dict[str, Any]:
    assets = _load_phase5_assets(root, cfg.phase5_corrected_run_id)
    nn_tables = _build_nn_tables(root, cfg, assets, phase5_source_hash, progress)
    write_json(
        evidence_dir / "nn_table_receipt.json",
        {
            "family_depths": list(nn_tables.keys()),
            "n_train_per_fd": {k: len(v["train_feats"]) for k, v in nn_tables.items()},
            "models_hash": assets["models_hash"],
            "donors_hash": assets["donors_hash"],
        },
    )

    units_dir = evidence_dir / "pilot_units"
    units_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    completed = 0
    planned = len(calibration) * cfg.cases_per_block
    t_start = time.perf_counter()
    last_progress = t_start

    for block in calibration:
        for case in block["cases"]:
            elapsed = time.perf_counter() - t_start
            if elapsed > cfg.max_pilot_compute_s:
                failed.append(
                    {
                        "case_id": case["case_id"],
                        "reason": "aggregate_pilot_compute_ceiling",
                        "elapsed_s": elapsed,
                    }
                )
                continue
            unit_path = units_dir / f"{case['case_id'].replace('.', '_')}.json"
            if unit_path.is_file():
                # Resume: reuse valid completed unit
                try:
                    prev = json.loads(unit_path.read_text(encoding="utf-8"))
                    if prev.get("status") == "completed":
                        summary_rows.append(prev.get("summary") or {"case_id": case["case_id"], "resumed": True})
                        completed += 1
                        progress(f"resume skip {case['case_id']} ({completed}/{planned})")
                        continue
                except (OSError, json.JSONDecodeError):
                    pass

            unit_t0 = time.perf_counter()
            try:
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
                t_enc = time.perf_counter()
                qubo = build_a2_qubo(inst)
                encode_s = time.perf_counter() - t_enc
                en = enumerate_legal_policies(inst)
                exact_cost = en.get("f_star")
                f_max = en.get("f_max")
                fb = greedy_safe_fallback(inst)
                weak_cost = float(fb["cost"]) if fb.get("feasible") else None
                milp = solve_a2_milp(inst, time_limit_s=min(5.0, cfg.deadline_s))
                exact_inside = bool(en.get("status") == "OK" and float(en.get("elapsed_s") or 0) <= cfg.deadline_s)
                strongest = {
                    "method": "exact_enumeration" if exact_inside else "greedy_safe_fallback",
                    "cost": exact_cost if exact_inside else weak_cost,
                    "exact_inside_deadline": exact_inside,
                    "enum_s": en.get("elapsed_s"),
                    "milp_success": milp.get("success"),
                    "milp_s": milp.get("solve_s"),
                    "milp_cost": milp.get("objective"),
                    "objective_headroom_vs_exact": 0.0 if exact_inside else None,
                    "note": (
                        "Exact incumbent ⇒ strictly positive proxy improvement probability is zero "
                        "within tolerance; ties are not improvements."
                    ),
                }
                uniform = uniform_legal_sample(
                    inst,
                    exact_cost=exact_cost,
                    f_max=f_max,
                    pool_size=cfg.pool_shots,
                    seed=seed + 99,
                )

                policy_results: dict[str, Any] = {}
                for family, p in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
                    fd = f"{family}_p{p}"
                    t_feat = time.perf_counter()
                    feats = compute_features(inst, qubo, family, p)
                    feat_s = time.perf_counter() - t_feat
                    for policy in cfg.policies:
                        chosen = _select_policy_donor(
                            policy=policy,
                            fd=fd,
                            family=family,
                            p=p,
                            feats=feats,
                            assets=assets,
                            nn_tables=nn_tables,
                            case_id=case["case_id"],
                            seed=seed,
                        )
                        donor = chosen["donor"]
                        if donor is None:
                            policy_results[f"{fd}:{policy}"] = {"status": "failed", "reason": "no_donor"}
                            continue
                        import hashlib

                        pool_base = int(
                            hashlib.sha256(f"{case['case_id']}:{fd}:{policy}".encode()).hexdigest()[:8],
                            16,
                        ) % (2**31 - 1)
                        ev = _evaluate_donor_distribution(
                            inst,
                            qubo,
                            donor,
                            exact_cost=exact_cost,
                            f_max=f_max,
                            weak_cost=weak_cost,
                            cfg=cfg,
                            pool_base_seed=pool_base,
                        )
                        ev["policy"] = policy
                        ev["feature_compute_s"] = feat_s
                        ev["selection_detail"] = chosen["detail"]
                        ev["encode_s"] = encode_s
                        policy_results[f"{fd}:{policy}"] = ev

                unit = {
                    "status": "completed",
                    "case_id": case["case_id"],
                    "block_id": block["block_id"],
                    "family_id": block["family_id"],
                    "regime": case["regime"],
                    "microcase": case["microcase"],
                    "n_qubits": qubo["n"],
                    "n_legal": en.get("n_legal"),
                    "exact_cost": exact_cost,
                    "f_max": f_max,
                    "strongest_classical": strongest,
                    "uniform_legal": uniform,
                    "weak_fallback_cost": weak_cost,
                    "policy_results": policy_results,
                    "timings": {"unit_s": time.perf_counter() - unit_t0, "encode_s": encode_s},
                }
                # Compact summary without full pool arrays for rollup
                summary = {
                    "case_id": case["case_id"],
                    "block_id": block["block_id"],
                    "family_id": block["family_id"],
                    "regime": case["regime"],
                    "n_qubits": qubo["n"],
                    "n_legal": en.get("n_legal"),
                    "exact_inside_deadline": exact_inside,
                    "objective_headroom": 0.0 if exact_inside else None,
                    "mean_regret_by_arm": {
                        k: v.get("pools_agg", {}).get("mean_normalised_regret")
                        for k, v in policy_results.items()
                        if isinstance(v, dict) and "pools_agg" in v
                    },
                    "strict_improve_vs_exact_by_arm": {
                        k: v.get("strict_improvement_vs_exact")
                        for k, v in policy_results.items()
                        if isinstance(v, dict)
                    },
                    "unit_s": unit["timings"]["unit_s"],
                }
                unit["summary"] = summary
                write_json(unit_path, unit)
                summary_rows.append(summary)
                completed += 1
            except Exception as exc:  # noqa: BLE001 — retain failure, continue
                failed.append(
                    {
                        "case_id": case["case_id"],
                        "reason": f"{type(exc).__name__}: {exc}",
                        "elapsed_s": time.perf_counter() - unit_t0,
                    }
                )
                write_json(
                    unit_path.with_suffix(".failed.json"),
                    {"status": "failed", "case_id": case["case_id"], "error": str(exc)},
                )

            now = time.perf_counter()
            if now - last_progress >= cfg.progress_interval_s or completed % 4 == 0:
                progress(
                    f"pilot {completed}/{planned} failed={len(failed)} "
                    f"elapsed={now - t_start:.1f}s case={case['case_id']}"
                )
                last_progress = now

    # Aggregate headroom / improvement
    n_zero_headroom = sum(1 for s in summary_rows if s.get("exact_inside_deadline"))
    improve_vals = []
    for s in summary_rows:
        for v in (s.get("strict_improve_vs_exact_by_arm") or {}).values():
            if v is not None:
                improve_vals.append(float(v))
    receipt = {
        "planned_cases": planned,
        "completed_cases": completed,
        "failed_cases": len(failed),
        "failures": failed,
        "n_zero_headroom_cases": n_zero_headroom,
        "mean_strict_improve_vs_exact": float(np.mean(improve_vals)) if improve_vals else None,
        "max_strict_improve_vs_exact": float(np.max(improve_vals)) if improve_vals else None,
        "development_headroom": "ZERO" if n_zero_headroom == completed and completed > 0 else "MIXED_OR_PARTIAL",
        "superiority_path_available": False,
        "superiority_path_reason": (
            "Exact classical enumeration finishes inside deadline on completed calibration cases; "
            "strictly positive proxy improvement vs exact is impossible within tolerance."
            if n_zero_headroom == completed and completed > 0
            else "See per-case strongest_classical; superiority disabled while exact incumbent dominates."
        ),
        "elapsed_s": time.perf_counter() - t_start,
        "summaries": summary_rows,
    }
    write_json(evidence_dir / "pilot_receipt.json", receipt)
    return receipt

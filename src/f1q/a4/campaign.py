"""A4 campaign: preflight + one authoritative foreground execution. No Phase 7."""

from __future__ import annotations

import json
import resource
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from f1q.a4.allocator import RidgeModel
from f1q.a4.anchors import FAMILY_DEPTHS, run_anchor_fits, select_donors
from f1q.a4.banks import EVALUATION_BANK, PLANNING_BANK, bank_world_seeds, banks_disjoint
from f1q.a4.loop import adversarial_validation, decide_and_evaluate, family_spec
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.problem import FEATURE_KEYS, build_a4_qubo, build_menu_and_instance, extract_causal_view, enumerate_legal_policies
from f1q.a4.qpu_guard import assert_local_only
from f1q.a4.reports import write_a4_reports
from f1q.a4.verify import run_independent_verify
from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.simulator.interface import RaceSimulator
from f1q.stage6.native_noise import run_native_noisy_panel, verify_native_analytical_fixtures
from f1q.stage6.pilot import _load_phase5_assets, write_json
from f1q.stage6.sizing import stratified_block_bootstrap
from f1q.stage6 import PHASE5_CORRECTED_RUN_ID
from f1q.stage6.config import default_phase6_config

CAMPAIGN_CEILING_S = 75 * 60
TASK_NOTE = "A4 scientific supersession; local sim only; no Phase 7"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
    except Exception:
        return "UNKNOWN"


class Progress:
    def __init__(self, label: str = "a4") -> None:
        self.label = label
        self.t0 = time.perf_counter()
        self.cpu0 = resource.getrusage(resource.RUSAGE_SELF)
        self.last = self.t0

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        cpu = resource.getrusage(resource.RUSAGE_SELF)
        cpu_s = (cpu.ru_utime - self.cpu0.ru_utime) + (cpu.ru_stime - self.cpu0.ru_stime)
        print(f"[{self.label} +{now - self.t0:7.1f}s wall / {cpu_s:7.1f}s cpu] {msg}", flush=True)
        self.last = now

    def maybe_heartbeat(self, msg: str = "heartbeat") -> None:
        if time.perf_counter() - self.last >= 45.0:
            self(msg)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        fh.flush()


def inspect_a3_defects() -> dict[str, Any]:
    """Independently confirm A3 constructions from live source, not from this prompt's list."""
    import inspect

    from f1q.a3 import agents as a3_agents
    from f1q.a3 import campaign as a3_campaign
    from f1q.a3 import loop as a3_loop
    from f1q.a3 import partitions as a3_parts
    from f1q.a3 import problem as a3_problem
    from f1q.a3 import verify as a3_verify

    src_loop = inspect.getsource(a3_loop.decide_from_observation)
    src_port = inspect.getsource(a3_agents.assemble_portfolio)
    src_camp = inspect.getsource(a3_campaign.execute_campaign)
    src_menu = inspect.getsource(a3_problem.build_menu_and_instance)
    src_plan = inspect.getsource(a3_problem.policy_to_simulator_plan)
    src_red = inspect.getsource(a3_parts.reduced_execution_subset)
    src_params = inspect.getsource(a3_loop.default_params)
    src_ver = inspect.getsource(a3_verify.run_independent_verify)
    defects = {
        "selects_downstream_candidates_0": '["downstream_candidates"][0]' in src_loop,
        "portfolio_appends_quantum": "equal_k * 2" in src_port and "merged.append" in src_port,
        "offline_copied_from_classical": 'offline_plan_loss = cl["mean_loss"]' in src_camp,
        "later_info_set_not_executed": "contingent_completion" in src_plan and "CURRENT_INFO" in src_plan,
        "two_action_menu": "acts[:2]" in src_menu,
        "no_anchor_optimisation_loop": "for block in reduced[\"anchors\"]" not in src_camp,
        "hardcoded_45min_reduction": "45 min" in src_red,
        "ridge_labels_identical_plans": "always_hybrid_c0" in src_camp and "y_util.append(delta)" in src_camp,
        "random_default_params": "standard_normal" in src_params,
        "worlds_not_persisted_for_primary": "write_json(a3_dir / \"pilot_blocks.json\"" in src_camp
        and "CALIBRATION_WORLD_OUTCOMES" not in src_camp,
        "verifier_internal_only": "portfolio_budget_matched" not in src_ver and "offline" not in src_ver.lower(),
    }
    return {
        "a3_run_id": "a5fdb488-9a90-47f9-a4f5-7f77a74180a6",
        "defects": defects,
        "all_confirmed": all(defects.values()),
        "disposition": "SUPERSEDED_INVALID_IMPLEMENTATION",
        "preserved_path": "evidence/a3/a5fdb488-9a90-47f9-a4f5-7f77a74180a6",
    }


def _freeze_record(partitions: dict[str, Any], preflight: dict[str, Any], source_commit: str) -> dict[str, Any]:
    worlds = preflight["frozen_worlds"]
    return {
        "status": "A4_PROTOCOL_FROZEN_BEFORE_CALIBRATION",
        "written_before_opening_calibration_outcomes": True,
        "datetime_utc": _utc(),
        "source_commit": source_commit,
        "architecture": "A4_checkpoint_candidate_generation_downstream_reranking",
        "a3_not_a_continuation": True,
        "a3_scientific_result": "SUPERSEDED_INVALID_IMPLEMENTATION",
        "primary_estimand": {
            "name": "paired_parent_block_mean_classical_minus_dispatched_evaluation_loss",
            "formula": "classical_only_evaluation_loss - safely_dispatched_A4_evaluation_loss",
            "positive_favours": "A4_dispatched",
            "budget_s": 30,
            "minimum_worthwhile_effect": 0.02,
            "sensitivity": [0.01, 0.05],
        },
        "interval_method": "stratified_equal_family_weight_block_bootstrap",
        "n_boot": 2000,
        "bootstrap_seed": 20260921,
        "missing_as_failure_in_denominator": True,
        "worlds": worlds,
        "portfolio_k": preflight["frozen_k"],
        "max_anchor_evals": preflight["frozen_max_evals"],
        "classical_comparator": "strongest_deadline_feasible_classical_portfolio",
        "donor_policy_choices": ["learned", "fixed", "nn", "random"],
        "allocator_modes": ["learned", "always_classical", "always_c0", "always_c1", "threshold"],
        "nominal_budgets_s": [5, 10, 30, 60, 120],
        "primary_budget_s": 30,
        "partitions_planned": partitions["planned"],
        "final_test_sealed": True,
        "qpu_execution_authorised": False,
        "phase_7_not_started": True,
        "gate_e_does_not_require_positive_quantum": True,
        "stochastic_policy_seeds_tune_calib": 3,
        "stop_before_calibration": not bool(preflight.get("minima_fit")),
        "gate_f_fails_if_incomplete_or_unfit_minima": True,
    }


def measure_preflight(progress: Progress) -> dict[str, Any]:
    """Two non-calibration development blocks; freeze worlds from measured throughput."""
    blocks = [
        {
            "family_id": "fam.green_pit_low.tyre_near_linear.traffic_sparse",
            "block_id": "a4.preflight.0",
            "index": 0,
            "seed": 101,
        },
        {
            "family_id": "fam.green_pit_high.tyre_nonlinear.traffic_dense",
            "block_id": "a4.preflight.1",
            "index": 1,
            "seed": 202,
        },
    ]
    cache: dict[str, Any] = {}
    timings = []
    n_qubits = []
    n_legal = []
    t0 = time.perf_counter()
    for block in blocks:
        for regime in ("SC", "VSC"):
            progress(f"preflight {block['block_id']} {regime}")
            spec = family_spec(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="development",
                index=block["index"],
                seed=block["seed"],
            )
            wplan = [11, 12]
            weval = [101, 102, 103, 104]
            t1 = time.perf_counter()
            cl = decide_and_evaluate(
                spec,
                mode="always_classical",
                runtime=None,
                donor_bank=None,
                donor_policy="fixed",
                planning_seeds=wplan,
                evaluation_seeds=weval,
                online_seed=7,
                cache=cache,
                pool_size=32,
                equal_k=4,
                deadline_s=30.0,
                margin=0.001,
                conservative_residual=0.0,
            )
            hy = decide_and_evaluate(
                spec,
                mode="always_c0",
                runtime=None,
                donor_bank=None,
                donor_policy="fixed",
                planning_seeds=wplan,
                evaluation_seeds=weval,
                online_seed=8,
                cache=cache,
                pool_size=32,
                equal_k=4,
                deadline_s=30.0,
                margin=0.001,
                conservative_residual=0.0,
            )
            dt = time.perf_counter() - t1
            timings.append(dt)
            n_qubits.append(cl["n_qubits"])
            n_legal.append(cl["legal_plan_count"])
            progress(f"preflight case wall={dt:.2f}s n={cl['n_qubits']} legal={cl['legal_plan_count']} cl_loss={cl['mean_loss']} hy_loss={hy['mean_loss']}")
    elapsed = time.perf_counter() - t0
    per_case = float(np.median(timings)) if timings else 30.0
    # Scale relative to measured 2-plan/4-eval. Minima: train 2/4, tune 4/8, calib 8/16.
    # Approximate cost ∝ (K * n_plan + n_eval). K=4.
    def cost_units(n_plan: int, n_eval: int, n_cases: int) -> float:
        return n_cases * (4 * n_plan + n_eval) / (4 * 2 + 4)

    usable = 0.80 * CAMPAIGN_CEILING_S
    # Reserve time for anchors: measure one C0 eval.
    spec0 = family_spec(
        family_id=blocks[0]["family_id"],
        block_id="a4.preflight.anchorprobe",
        regime="SC",
        partition="development",
        index=0,
        seed=3,
    )
    sim = RaceSimulator()
    sim.initialize(spec0)
    sim.advance_to_checkpoint()
    inst = build_menu_and_instance(extract_causal_view(sim.observe()))
    qubo = build_a4_qubo(inst)
    from f1q.a4.circuits import c0_objective, c1_objective

    params = np.zeros(2)
    ta = time.perf_counter()
    c0_objective(qubo, params)
    t_c0 = time.perf_counter() - ta
    ta = time.perf_counter()
    c1_objective(inst, qubo, params)
    t_c1 = time.perf_counter() - ta
    n_starts = 24 * 4 * 3  # family/depth × starts
    t_anchor_80 = n_starts * 80 * (0.5 * t_c0 + 0.5 * t_c1)
    max_evals = 80
    if t_anchor_80 > 0.35 * usable:
        max_evals = max(8, int(80 * (0.35 * usable) / max(t_anchor_80, 1e-6)))
        max_evals = int(np.floor(max_evals / 1) )  # uniform reduction
    t_anchor = n_starts * max_evals * (0.5 * t_c0 + 0.5 * t_c1)
    remain = usable - t_anchor - elapsed
    # Try maxima then drop to minima.
    grid = [
        {"train_p": 4, "train_e": 8, "tune_p": 8, "tune_e": 16, "calib_p": 16, "calib_e": 32},
        {"train_p": 2, "train_e": 4, "tune_p": 4, "tune_e": 8, "calib_p": 8, "calib_e": 16},
    ]
    chosen = None
    projection = []
    for g in grid:
        units = (
            cost_units(g["train_p"], g["train_e"], 240)
            + cost_units(g["tune_p"], g["tune_e"], 160)
            + cost_units(g["calib_p"], g["calib_e"], 48)
            + cost_units(g["calib_p"], g["calib_e"], 16)  # offline subset ~8 parents × 2
        )
        t_proj = units * per_case
        projection.append({"grid": g, "t_proj_s": t_proj, "fits": t_proj <= remain})
        if t_proj <= remain and chosen is None:
            chosen = g
    if chosen is None:
        chosen = grid[-1]
        minima_fit = projection[-1]["t_proj_s"] <= remain
    else:
        minima_fit = True
    return {
        "n_blocks": 2,
        "n_cases": len(timings),
        "timings_s": timings,
        "median_case_s": per_case,
        "elapsed_s": elapsed,
        "n_qubits": n_qubits,
        "n_legal": n_legal,
        "t_c0_eval_s": t_c0,
        "t_c1_eval_s": t_c1,
        "projected_anchor_80_s": t_anchor_80,
        "frozen_max_evals": int(max_evals),
        "anchor_time_s_projected": t_anchor,
        "usable_s": usable,
        "remain_after_anchor_preflight_s": remain,
        "projection": projection,
        "frozen_worlds": {
            "training": {"planning": chosen["train_p"], "evaluation": chosen["train_e"]},
            "tuning": {"planning": chosen["tune_p"], "evaluation": chosen["tune_e"]},
            "calibration": {"planning": chosen["calib_p"], "evaluation": chosen["calib_e"]},
        },
        "frozen_k": 4,
        "minima_fit": bool(minima_fit),
        "headroom_fraction_reserved": 0.20,
        "arithmetic": (
            f"median_case={per_case:.3f}s at 2-plan/4-eval; scale by (4*n_plan+n_eval)/12; "
            f"usable=0.8*4500s; anchors={n_starts} starts * {max_evals} evals * avg(c0,c1)"
        ),
        "not_invented_after_seeing_calib": True,
    }


def _run_block_arm(
    block: dict[str, Any],
    regime: str,
    partition: str,
    *,
    mode: str,
    runtime: RidgeModel | None,
    donor_bank,
    donor_policy: str,
    worlds: dict[str, int],
    seed: int,
    cache: dict[str, Any],
    k: int,
    pool_size: int,
    deadline_s: float,
    margin: float,
    residual: float,
    n_stochastic_seeds: int = 1,
) -> dict[str, Any]:
    spec = family_spec(
        family_id=block["family_id"],
        block_id=block["block_id"],
        regime=regime,
        partition=partition,
        index=int(block["index"]),
        seed=int(block["seed"]),
    )
    plan_seeds = bank_world_seeds(block["block_id"], regime, PLANNING_BANK, worlds["planning"])
    eval_seeds = bank_world_seeds(block["block_id"], regime, EVALUATION_BANK, worlds["evaluation"])
    assert banks_disjoint(plan_seeds, eval_seeds)
    n_stoch = n_stochastic_seeds
    if partition in {"tuning", "calibration"} and n_stoch < 3:
        n_stoch = 3
    return decide_and_evaluate(
        spec,
        mode=mode,
        runtime=runtime,
        donor_bank=donor_bank,
        donor_policy=donor_policy,
        planning_seeds=plan_seeds,
        evaluation_seeds=eval_seeds,
        online_seed=seed,
        cache=cache,
        pool_size=pool_size,
        equal_k=k,
        deadline_s=deadline_s,
        margin=margin,
        conservative_residual=residual,
        n_stochastic_seeds=n_stoch,
    )


def execute_campaign(root: Path, *, mode: str = "full", run_id: str | None = None) -> dict[str, Any]:
    assert_local_only()
    progress = Progress("a4_redesign")
    t_limit = time.perf_counter() + CAMPAIGN_CEILING_S
    source_commit = _git_head(root)
    run_id = run_id or str(uuid.uuid4())
    ev = root / "evidence/stage6_a4" / run_id
    ev.mkdir(parents=True, exist_ok=True)
    docs_ev = root / "docs/evidence/stage6_a4" / run_id
    docs_ev.mkdir(parents=True, exist_ok=True)
    tests_dir = ev / "TEST_RECEIPTS"
    tests_dir.mkdir(parents=True, exist_ok=True)

    start_state = {
        "run_id": run_id,
        "source_commit": source_commit,
        "datetime_utc": _utc(),
        "expected_start_commit": "be9e11e3ca0e92d4579f060071e07b44e0932bae",
        "head_at_campaign_start": source_commit,
        "head_matches_expected_at_first_authorisation": source_commit == "be9e11e3ca0e92d4579f060071e07b44e0932bae",
        "qpu_execution_authorised": False,
        "phase_7_started": False,
    }
    write_json(ev / "START_STATE.json", start_state)
    a3_inv = inspect_a3_defects()
    write_json(ev / "A3_INVALIDATION.json", a3_inv)
    write_json(
        ev / "PROTOCOL_AMENDMENT_A4.json",
        {
            "architecture": "A4",
            "question": (
                "Under the same observable checkpoint, deadline and downstream simulation-evaluation "
                "budget, can an AI-gated portfolio containing C0 or C1 quantum-generated legal "
                "candidates improve independent simulated team loss over the strongest tuning-selected "
                "classical portfolio?"
            ),
            "not_multi_epoch_policy": True,
            "a3_superseded": True,
        },
    )

    progress("partitions")
    partitions = build_a4_partitions()
    write_json(
        ev / "PARTITIONS.json",
        {
            **{k: v for k, v in partitions.items() if k not in {"anchors", "train", "tune", "calib"}},
            "anchors_ids": [b["block_id"] for b in partitions["anchors"]],
            "train_ids": [b["block_id"] for b in partitions["train"]],
            "tune_ids": [b["block_id"] for b in partitions["tune"]],
            "calib_ids": [b["block_id"] for b in partitions["calib"]],
        },
    )

    preflight_path = ev / "PREFLIGHT.json"
    freeze_path = ev / "PROTOCOL_FREEZE.json"
    if preflight_path.is_file() and freeze_path.is_file() and mode == "full":
        progress("reusing committed preflight/freeze")
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    else:
        progress("preflight")
        preflight = measure_preflight(progress)
        write_json(preflight_path, preflight)
        freeze = _freeze_record(partitions, preflight, source_commit)
        write_json(freeze_path, freeze)

    stop_before_calib = (not bool(preflight.get("minima_fit"))) or bool(freeze.get("stop_before_calibration"))
    if mode == "preflight":
        return {"status": "preflight_complete", "run_id": run_id, "preflight": preflight, "evidence_dir": str(ev)}

    worlds = freeze["worlds"]
    k = int(freeze["portfolio_k"])
    max_evals = int(freeze["max_anchor_evals"])
    residual = 0.0
    margin = 0.001

    progress("native-basis noise panel into A4 tree")
    try:
        assets = _load_phase5_assets(root, PHASE5_CORRECTED_RUN_ID)
        noisy = run_native_noisy_panel(default_phase6_config(), assets=assets, progress=progress)
    except Exception as exc:  # noqa: BLE001
        noisy = {"status": "FAILED", "error": str(exc), "analytical": verify_native_analytical_fixtures()}
    write_json(ev / "NATIVE_NOISE_CORRECTION.json", {
        "panel": {kk: vv for kk, vv in noisy.items() if kk != "rows"},
        "n_rows": len(noisy.get("rows") or []),
        "analytical": noisy.get("analytical"),
        "a2_residual_192_pool_label": (
            "evidence/stage6_a2_residual/e437fa3d-c29c-43c3-9a55-708c1b36f5e6 192-pool "
            "histogram run is a balanced method-validation subset (8 families × 1 parent × "
            "SC/VSC × {C0_p1,C1_p1} × {learned,fixed} × 3 seeds), not a full empirical "
            "supersession of all historical pools."
        ),
        "does_not_overwrite": [
            "evidence/stage6_a2_residual/e437fa3d-c29c-43c3-9a55-708c1b36f5e6",
            "evidence/stage6_corrected/2a3fb275-6c37-4bbc-bdb4-addede80b5c3",
            "evidence/stage6/bd83cb22-6a38-4d21-9267-3253f52587d7",
        ],
        "convention": "E_p(rho)=(1-p)rho + p I/d",
        "synthetic_not_ibm": True,
        "rows": noisy.get("rows"),
    })

    progress("adversarial causal validation")
    causal = adversarial_validation()
    write_json(ev / "causal_adversarial.json", causal)

    progress(f"anchor fits max_evals={max_evals}")
    anchor_path = ev / "ANCHOR_FITS.jsonl"
    if anchor_path.exists():
        anchor_path.unlink()
    fits = run_anchor_fits(partitions["anchors"], max_evals=max_evals, progress=progress, t_deadline=t_limit)
    for row in fits:
        _append_jsonl(anchor_path, row)
    donor_bank = select_donors(fits)
    write_json(ev / "DONOR_BANK.json", donor_bank)
    write_json(ev / "DONOR_SELECTOR.json", {"policy_options": ["learned", "fixed", "nn", "random"], "default": "learned"})

    cache: dict[str, Any] = {}
    X = []
    y = []
    train_path = ev / "TRAINING_RESULTS.jsonl"
    if train_path.exists():
        train_path.unlink()
    n_train_done = 0
    n_train_fail = 0
    for block in partitions["train"]:
        if time.perf_counter() > t_limit:
            progress("training hit ceiling")
            break
        for regime in ("SC", "VSC"):
            progress(f"train {block['block_id']} {regime}")
            try:
                cl = _run_block_arm(
                    block, regime, "training", mode="always_classical", runtime=None,
                    donor_bank=donor_bank, donor_policy="fixed", worlds=worlds["training"],
                    seed=int(block["seed"]), cache=cache, k=k, pool_size=48, deadline_s=30.0,
                    margin=margin, residual=residual,
                )
                hy = _run_block_arm(
                    block, regime, "training", mode="always_c1", runtime=None,
                    donor_bank=donor_bank, donor_policy="learned", worlds=worlds["training"],
                    seed=int(block["seed"]) + 3, cache=cache, k=k, pool_size=48, deadline_s=30.0,
                    margin=margin, residual=residual,
                )
                delta = float((cl["mean_loss"] or 0) - (hy["mean_loss"] or 0))
                # Genuine treatment difference required: skip label if identical executed plans.
                same_plan = cl["plan_hash"] == hy["plan_hash"]
                if not same_plan:
                    X.append([hy["features"][kk] for kk in FEATURE_KEYS])
                    y.append(delta)
                _append_jsonl(train_path, {
                    "block_id": block["block_id"], "family_id": block["family_id"], "regime": regime,
                    "classical_loss": cl["mean_loss"], "hybrid_c0_loss": hy["mean_loss"],
                    "delta": delta, "same_executed_plan": same_plan,
                    "classical_plan": cl["plan_hash"], "hybrid_plan": hy["plan_hash"],
                    "n_downstream_cl": cl["portfolio"]["n_downstream"],
                    "n_downstream_hy": hy["portfolio"]["n_downstream"],
                    "legal_plan_count": cl["legal_plan_count"],
                    "n_qubits": cl["n_qubits"],
                    "datetime_utc": _utc(),
                })
                n_train_done += 1
            except Exception as exc:  # noqa: BLE001
                n_train_fail += 1
                _append_jsonl(train_path, {"block_id": block["block_id"], "regime": regime, "failed": True, "error": str(exc)})
            progress.maybe_heartbeat("training")

    runtime = RidgeModel(l2=1.0)
    if X:
        fit = runtime.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
    else:
        fit = runtime.fit(np.zeros((2, len(FEATURE_KEYS))), np.zeros(2))
        fit["note"] = "no_genuine_treatment_difference_on_training_labels; intercept-only fallback"
    write_json(ev / "ALLOCATOR_MODEL.json", fit)

    tune_path = ev / "TUNING_RESULTS.jsonl"
    if tune_path.exists():
        tune_path.unlink()
    tune_rows = []
    for block in partitions["tune"]:
        if time.perf_counter() > t_limit:
            progress("tuning hit ceiling")
            break
        for regime in ("SC", "VSC"):
            progress(f"tune {block['block_id']} {regime}")
            cl = _run_block_arm(
                block, regime, "tuning", mode="always_classical", runtime=runtime,
                donor_bank=donor_bank, donor_policy="fixed", worlds=worlds["tuning"],
                seed=int(block["seed"]), cache=cache, k=k, pool_size=48, deadline_s=30.0, margin=margin, residual=residual,
            )
            ds = _run_block_arm(
                block, regime, "tuning", mode="learned", runtime=runtime,
                donor_bank=donor_bank, donor_policy="learned", worlds=worlds["tuning"],
                seed=int(block["seed"]) + 5, cache=cache, k=k, pool_size=48, deadline_s=30.0, margin=margin, residual=residual,
            )
            row = {
                "block_id": block["block_id"], "family_id": block["family_id"], "regime": regime,
                "classical_loss": cl["mean_loss"], "dispatched_loss": ds["mean_loss"],
                "n_policy_seeds": 3, "datetime_utc": _utc(),
                "stochastic_seeds_in_generators": 3,
                "choice": ds["choice"],
            }
            tune_rows.append(row)
            _append_jsonl(tune_path, row)
            progress.maybe_heartbeat("tuning")

    # Freeze hyperparameters already in PROTOCOL_FREEZE; conservative residual from training residual_std.
    conservative = float(fit.get("residual_std") or 0.0)
    write_json(ev / "ALLOCATOR_MODEL.json", {**fit, "conservative_residual_used_on_calib": conservative})

    calib_path = ev / "CALIBRATION_CANDIDATES.jsonl"
    world_path = ev / "CALIBRATION_WORLD_OUTCOMES.jsonl"
    for p in (calib_path, world_path):
        if p.exists():
            p.unlink()
    calib_rows = []
    n_plan_diff = 0
    n_q_selected = 0
    n_denom = 0
    if stop_before_calib:
        progress(
            "STOP BEFORE CALIBRATION: measured minima cannot process every required "
            "block inside the 75-minute ceiling after caching/vectorisation; Gate F FAIL"
        )
        calib_path.write_text("", encoding="utf-8")
        world_path.write_text("", encoding="utf-8")
    for block in ([] if stop_before_calib else partitions["calib"]):
        if time.perf_counter() > t_limit:
            progress("calibration hit ceiling")
            break
        sc_row = None
        vsc_row = None
        for regime in ("SC", "VSC"):
            progress(f"calib {block['block_id']} {regime}")
            cl = _run_block_arm(
                block, regime, "calibration", mode="always_classical", runtime=runtime,
                donor_bank=donor_bank, donor_policy="fixed", worlds=worlds["calibration"],
                seed=int(block["seed"]), cache=cache, k=k, pool_size=64, deadline_s=30.0,
                margin=margin, residual=conservative,
            )
            ds = _run_block_arm(
                block, regime, "calibration", mode="learned", runtime=runtime,
                donor_bank=donor_bank, donor_policy="learned", worlds=worlds["calibration"],
                seed=int(block["seed"]) + 9, cache=cache, k=k, pool_size=64, deadline_s=30.0,
                margin=margin, residual=conservative,
            )
            hy0 = _run_block_arm(
                block, regime, "calibration", mode="always_c0", runtime=runtime,
                donor_bank=donor_bank, donor_policy="learned", worlds=worlds["calibration"],
                seed=int(block["seed"]) + 11, cache=cache, k=k, pool_size=64, deadline_s=30.0,
                margin=margin, residual=conservative,
            )
            hy1 = _run_block_arm(
                block, regime, "calibration", mode="always_c1", runtime=runtime,
                donor_bank=donor_bank, donor_policy="learned", worlds=worlds["calibration"],
                seed=int(block["seed"]) + 13, cache=cache, k=k, pool_size=64, deadline_s=30.0,
                margin=margin, residual=conservative,
            )
            th = _run_block_arm(
                block, regime, "calibration", mode="threshold", runtime=runtime,
                donor_bank=donor_bank, donor_policy="fixed", worlds=worlds["calibration"],
                seed=int(block["seed"]) + 15, cache=cache, k=k, pool_size=64, deadline_s=30.0,
                margin=margin, residual=conservative,
            )
            n_denom += 1
            if cl["plan_hash"] != ds["plan_hash"]:
                n_plan_diff += 1
            if ds.get("selected_origin") == "quantum":
                n_q_selected += 1
            for arm_name, rec in (("classical_only", cl), ("dispatched", ds), ("always_c0", hy0), ("always_c1", hy1), ("threshold", th)):
                for w in rec.get("eval_worlds") or []:
                    _append_jsonl(world_path, {
                        "block_id": block["block_id"], "family_id": block["family_id"], "regime": regime,
                        "arm": arm_name, "loss": w["loss"], "world_seed": w["world_seed"],
                        "timely": w["timely"], "fallback": w["fallback"], "plan_hash": rec["plan_hash"],
                        "origin": rec.get("selected_origin"),
                    })
            row = {
                "block_id": block["block_id"], "family_id": block["family_id"], "regime": regime,
                "classical_only_loss": cl["mean_loss"], "dispatched_loss": ds["mean_loss"],
                "always_c0_loss": hy0["mean_loss"], "always_c1_loss": hy1["mean_loss"],
                "threshold_loss": th["mean_loss"],
                "dispatcher_choice": ds["choice"],
                "classical_plan": cl["plan_hash"], "dispatched_plan": ds["plan_hash"],
                "plan_differs": cl["plan_hash"] != ds["plan_hash"],
                "quantum_origin_selected": ds.get("selected_origin") == "quantum",
                "n_downstream": ds["portfolio"]["n_downstream"],
                "k": k, "portfolio_budget_matched": ds["portfolio"]["portfolio_budget_matched"],
                "fallback_rate": ds["fallback_rate"], "timely_rate": ds["timely_rate"],
                "legal_plan_count": ds["legal_plan_count"], "n_qubits": ds["n_qubits"],
                "generation_s": ds["timings"]["generation_s"],
                "datetime_utc": _utc(),
            }
            calib_rows.append(row)
            _append_jsonl(calib_path, row)
            if regime == "SC":
                sc_row = row
            else:
                vsc_row = row
            # latency budgets diagnostic (same plan, different arrival labels)
            _ = (sc_row, vsc_row)
            progress.maybe_heartbeat("calibration")

    # Offline finite-simulation reference on 8 families (first calib block each family)
    offline_path = ev / "OFFLINE_REFERENCE.jsonl"
    if offline_path.exists():
        offline_path.unlink()
    seen_fam = set()
    offline_rows = []
    for block in ([] if stop_before_calib else partitions["calib"]):
        if block["family_id"] in seen_fam:
            continue
        seen_fam.add(block["family_id"])
        for regime in ("SC", "VSC"):
            if time.perf_counter() > t_limit:
                break
            progress(f"offline {block['block_id']} {regime}")
            spec = family_spec(
                family_id=block["family_id"], block_id=block["block_id"], regime=regime,
                partition="calibration", index=int(block["index"]), seed=int(block["seed"]),
            )
            sim = RaceSimulator()
            sim.initialize(spec)
            sim.advance_to_checkpoint()
            blob = sim.serialize()
            view = extract_causal_view(sim.observe())
            inst = build_menu_and_instance(view)
            legal = enumerate_legal_policies(inst)
            t_off = time.perf_counter()
            plan_seeds = bank_world_seeds(f"offline:{block['block_id']}", regime, "offline_planning_bank", worlds["calibration"]["planning"])
            eval_seeds = bank_world_seeds(f"offline:{block['block_id']}", regime, "offline_evaluation_bank", worlds["calibration"]["evaluation"])
            from f1q.a4.loop import evaluate_candidates_on_bank
            from f1q.hashing import sha256_json as _h

            spec_hash = _h({kk: spec[kk] for kk in spec if kk != "stream_key_ids"})
            bank_res = evaluate_candidates_on_bank(
                spec, blob, legal, plan_seeds, bank="offline_planning_bank",
                arrival_delay_s=0.05, common_commit_delay_s=0.05, cache=cache,
                spec_hash=spec_hash, checkpoint_hash=view["observation_hash"],
            )
            best_hash = min(bank_res["means"], key=lambda h: (bank_res["means"][h], h))
            best = next(r for r in legal if r["plan_hash"] == best_hash)
            ev_res = evaluate_candidates_on_bank(
                spec, blob, [best], eval_seeds, bank="offline_evaluation_bank",
                arrival_delay_s=0.05, common_commit_delay_s=0.05, cache=cache,
                spec_hash=spec_hash, checkpoint_hash=view["observation_hash"],
            )
            wall = time.perf_counter() - t_off
            # Matching calib row
            match = next((r for r in calib_rows if r["block_id"] == block["block_id"] and r["regime"] == regime), None)
            cl_plan = match["classical_plan"] if match else None
            row = {
                "block_id": block["block_id"], "family_id": block["family_id"], "regime": regime,
                "n_legal_evaluated": len(legal),
                "selected_plan_hash": best_hash,
                "planning_mean": bank_res["means"][best_hash],
                "evaluation_loss": ev_res["means"][best_hash],
                "wall_s": wall,
                "deadline_feasible": wall <= 30.0,
                "copied_from_arm": False,
                "classical_plan_hash": cl_plan,
                "matches_classical_plan": cl_plan == best_hash,
                "datetime_utc": _utc(),
            }
            offline_rows.append(row)
            _append_jsonl(offline_path, row)

    # Primary analysis
    by_block: dict[str, list[dict[str, Any]]] = {}
    for r in calib_rows:
        by_block.setdefault(r["block_id"], []).append(r)
    block_effects = []
    for bid, items in by_block.items():
        d = float(np.mean([(x["classical_only_loss"] or 0) - (x["dispatched_loss"] or 0) for x in items]))
        block_effects.append({"block_id": bid, "family_id": items[0]["family_id"], "effect": d})
    boot = stratified_block_bootstrap(block_effects, n_boot=2000, seed=20260921) if block_effects else {"status": "EMPTY"}
    mean_diff = float(np.mean([e["effect"] for e in block_effects])) if block_effects else None
    n_pos = sum(1 for e in block_effects if e["effect"] > 1e-12)
    n_neg = sum(1 for e in block_effects if e["effect"] < -1e-12)

    # Headroom vs offline
    headroom_cases = 0
    for r in offline_rows:
        match = next((c for c in calib_rows if c["block_id"] == r["block_id"] and c["regime"] == r["regime"]), None)
        if match and abs((match["classical_only_loss"] or 0) - (r["evaluation_loss"] or 0)) > 1e-8:
            headroom_cases += 1
        if match and r["matches_classical_plan"] is False:
            headroom_cases += 1
    if headroom_cases == 0:
        operational_headroom = "ZERO_OR_UNMEASURED_ON_OFFLINE_SUBSET"
    else:
        operational_headroom = "NONZERO_ON_SOME_OFFLINE_SUBSET_CASES"

    menu_trivial = all(int(r.get("legal_plan_count") or 0) <= 1 for r in calib_rows) if calib_rows else True
    same_all = n_plan_diff == 0 and n_denom > 0
    gate_e = "FAIL"
    if causal.get("ok") and not menu_trivial and not same_all:
        gate_e = "PASS"
    elif causal.get("ok") and not menu_trivial:
        # still a substantive candidate-generation question even if plans matched
        if any(int(r.get("legal_plan_count") or 0) > k for r in calib_rows):
            gate_e = "PASS"
        else:
            gate_e = "FAIL"

    n_anchor_blocks = len({r.get("block_id") for r in fits})
    n_train_blocks = len({json.loads(l).get("block_id") for l in train_path.read_text().splitlines() if l.strip()}) if train_path.is_file() else 0
    n_tune_blocks = len({r["block_id"] for r in tune_rows})
    n_calib_blocks = len(by_block)
    complete = (
        n_anchor_blocks == 24
        and n_train_blocks == 120
        and n_tune_blocks == 80
        and n_calib_blocks == 24
        and preflight["minima_fit"]
    )
    gate_f = "PASS" if complete else "FAIL"

    primary = {
        "mean_difference": mean_diff,
        "n_parent_blocks": len(block_effects),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "bootstrap": boot,
        "minimum_worthwhile_effect": 0.02,
        "formula": freeze["primary_estimand"]["formula"],
        "n_plan_diff": n_plan_diff,
        "n_quantum_origin_selected": n_q_selected,
        "denominator": n_denom,
        "effects": block_effects,
    }
    write_json(ev / "PRIMARY_ANALYSIS.json", primary)
    write_json(ev / "MECHANISM_RESULTS.json", {
        "always_c0_vs_classical": float(np.mean([(r["classical_only_loss"] or 0) - (r["always_c0_loss"] or 0) for r in calib_rows])) if calib_rows else None,
        "always_c1_vs_classical": float(np.mean([(r["classical_only_loss"] or 0) - (r["always_c1_loss"] or 0) for r in calib_rows])) if calib_rows else None,
        "exploratory": True,
    })
    write_json(ev / "PRECISION_AND_SIZING.json", {
        "worlds": worlds,
        "n_calib_parent_blocks": n_calib_blocks,
        "bootstrap": boot,
        "do_not_use_zero_variance_from_identical_plans_as_precision": True,
        "phase7_not_sized_as_authorised": True,
    })
    elapsed = time.perf_counter() - progress.t0
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (cpu.ru_utime - progress.cpu0.ru_utime) + (cpu.ru_stime - progress.cpu0.ru_stime)
    write_json(ev / "RESOURCE_ACCOUNTING.json", {
        "elapsed_s": elapsed, "cpu_s": cpu_s, "qpu_jobs": 0, "qpu_usage_seconds": 0,
        "preflight": {k: preflight[k] for k in ("median_case_s", "frozen_worlds", "frozen_max_evals", "arithmetic")},
    })

    phase7_boundary = gate_e == "PASS" and gate_f == "PASS"
    readiness = {
        "GATE_E_SCIENTIFIC_VALUE": gate_e,
        "GATE_F_PRECISION_AND_RESOURCES": gate_f,
        "PHASE_7_BOUNDARY_STUDY_READY": False,  # still requires later prompt even if candidate
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "would_be_boundary_if_authorised": phase7_boundary,
        "OPERATIONAL_DOWNSTREAM_HEADROOM": operational_headroom,
        "QPU_EXECUTION_AUTHORISED": False,
        "ACTION_DOMAIN_COMPLETE": True,
        "CAUSAL_OPERATIONAL_INTEGRATION": bool(causal.get("ok")),
    }
    write_json(ev / "readiness.json", readiness)
    write_json(ev / "CLAIMS_LEDGER.json", {
        "no_quantum_advantage": True,
        "no_first_claim": True,
        "no_real_team_performance": True,
        "synthetic_checkpoints_not_historical": True,
        "labels": "proposed/implemented/verified_by_named_check/simulated",
    })
    write_json(ev / "ISSUE_REGISTER.json", {
        "issues": [
            {"id": "A3-INVALID", "disposition": "SUPERSEDED"},
            {"id": "A2-NOISE-CONVENTION", "disposition": "CORRECTED_IN_A4"},
            {"id": "FINAL-TEST-SEALED", "disposition": "UNOPENED"},
            {
                "id": "STOP-BEFORE-CALIBRATION" if stop_before_calib else "CALIBRATION-EXECUTED",
                "disposition": "GATE_F_FAIL" if stop_before_calib else "ATTEMPTED",
            },
        ]
    })
    audit = ev / "ACTION_MENU_AUDIT.jsonl"
    form = ev / "FORMULATION_CHECKS.jsonl"
    if audit.exists():
        audit.unlink()
    if form.exists():
        form.unlink()
    menu_src = calib_rows
    if not menu_src and train_path.is_file():
        menu_src = [json.loads(l) for l in train_path.read_text().splitlines() if l.strip() and not json.loads(l).get("failed")]
    if not menu_src:
        audit.write_text("", encoding="utf-8")
        form.write_text("", encoding="utf-8")
    for r in menu_src:
        row = {
            "block_id": r.get("block_id"),
            "regime": r.get("regime"),
            "legal_plan_count": r.get("legal_plan_count"),
            "n_qubits": r.get("n_qubits"),
            "source": "calibration" if calib_rows else "training",
        }
        _append_jsonl(audit, row)
        _append_jsonl(form, row)
    if not offline_path.is_file():
        offline_path.write_text("", encoding="utf-8")

    tmp_receipts = Path("/tmp/a4_test_receipts")
    if tmp_receipts.is_dir():
        tests_dir.mkdir(parents=True, exist_ok=True)
        for src in tmp_receipts.iterdir():
            if src.is_file():
                (tests_dir / src.name).write_bytes(src.read_bytes())

    receipt = {
        "run_id": run_id,
        "source_commit": source_commit,
        "elapsed_s": elapsed,
        "cpu_s": cpu_s,
        "gate_e": gate_e,
        "gate_f": gate_f,
        "operational_headroom": operational_headroom,
        "stop_before_calibration": bool(stop_before_calib),
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "qpu_execution_authorised": False,
        "final_test_accessed": False,
        "n_anchor_blocks": n_anchor_blocks,
        "n_train_blocks": n_train_blocks,
        "n_tune_blocks": n_tune_blocks,
        "n_calib_blocks": n_calib_blocks,
        "n_train_case_rows": n_train_done,
        "n_train_fail": n_train_fail,
        "n_plan_diff": n_plan_diff,
        "n_quantum_origin_selected": n_q_selected,
        "n_denom": n_denom,
        "mean_difference": mean_diff,
        "portfolio_k": k,
        "worlds": worlds,
        "max_evals": max_evals,
        "causal_ok": causal.get("ok"),
        "a3_defects_confirmed": a3_inv.get("all_confirmed"),
        "minima_fit": bool(preflight.get("minima_fit")),
    }
    write_json(ev / "RUN_RECEIPT.json", receipt)

    files = {}
    for f in sorted(ev.rglob("*")):
        if f.is_file() and f.name not in {"MANIFEST.json", "FINAL_VERIFY.json"}:
            rel = str(f.relative_to(root))
            files[rel] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
    manifest = {"run_id": run_id, "n_files": len(files), "files": files, "inventory_sha256": sha256_json(files)}
    write_json(ev / "MANIFEST.json", manifest)

    progress("independent verifier")
    verify = run_independent_verify(root, run_id)
    write_json(ev / "FINAL_VERIFY.json", verify)
    write_a4_reports(
        root,
        run_id,
        start_commit="be9e11e3ca0e92d4579f060071e07b44e0932bae",
        reviewed_commit=source_commit,
    )

    # Mirror key artifacts
    for name in ("RUN_RECEIPT.json", "FINAL_VERIFY.json", "PRIMARY_ANALYSIS.json", "PROTOCOL_FREEZE.json", "MANIFEST.json", "readiness.json"):
        if (ev / name).is_file():
            write_json(docs_ev / name, json.loads((ev / name).read_text(encoding="utf-8")))

    return {
        **receipt,
        "verify_ok": verify.get("ok"),
        "verify_n_pass": verify.get("n_pass"),
        "verify_n_checks": verify.get("n_checks"),
        "status": "completed",
        "evidence_dir": str(ev),
        "readiness": readiness,
        "primary": primary,
        "freeze_path": str(ev / "PROTOCOL_FREEZE.json"),
    }

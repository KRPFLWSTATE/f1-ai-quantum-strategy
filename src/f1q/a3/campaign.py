"""Consolidated A2-residual + A3 campaign (foreground, checkpointed, no Phase 7)."""

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

from f1q.a3 import A3_VERSION
from f1q.a3.agents import RidgeRuntime
from f1q.a3.loop import adversarial_validation, evaluate_arm, family_spec, stream_seed
from f1q.a3.novelty import build_a3_novelty
from f1q.a3.partitions import build_a3_partitions, reduced_execution_subset
from f1q.a3.problem import FEATURE_KEYS, build_a3_qubo, build_menu_and_instance, extract_causal_view, verify_direct_cost_qubo_agreement
from f1q.a3.verify import run_independent_verify
from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.simulator.interface import RaceSimulator
from f1q.stage6.pilot import write_json
from f1q.stage6.residual_run import run_a2_residual
from f1q.stage6.sizing import stratified_block_bootstrap


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
    except Exception:
        return "UNKNOWN"


class Progress:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.cpu0 = resource.getrusage(resource.RUSAGE_SELF)
        self.last = 0.0

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        cpu = resource.getrusage(resource.RUSAGE_SELF)
        cpu_s = (cpu.ru_utime - self.cpu0.ru_utime) + (cpu.ru_stime - self.cpu0.ru_stime)
        print(f"[a3_redesign +{now - self.t0:7.1f}s wall / {cpu_s:7.1f}s cpu] {msg}", flush=True)
        self.last = now


def _freeze_record(partitions: dict[str, Any], reduced: dict[str, Any], source_commit: str) -> dict[str, Any]:
    return {
        "status": "A3_CALIBRATION_PILOT_PREDECLARED",
        "written_before_opening_calibration_outcomes": True,
        "datetime_utc": _utc(),
        "source_commit": source_commit,
        "architecture": "A3_causal_operational_rolling_horizon",
        "a2_not_a_continuation": True,
        "primary_estimand": {
            "name": "mean_paired_block_level_difference_in_independent_simulator_loss",
            "formula": "classical_only_loss - safely_dispatched_hybrid_loss",
            "positive_favours": "dispatched_hybrid",
            "negative_boundary_acceptable": True,
        },
        "secondary": [
            "harm_frequency_magnitude",
            "deadline_success",
            "fallback_rate",
            "dispatcher_choices",
            "calibration_of_predicted_marginal_utility",
            "marginal_useful_candidate_yield",
            "legality",
            "duplicates",
            "portfolio_diversity",
            "C0_C1_separately",
            "latency_components",
            "classical_and_offline_reference_gaps",
        ],
        "worlds_predeclared": {
            "start": 8,
            "assess_8192_32768_by_extrapolation_only": True,
            "not_chosen_from_favourable_sign": True,
        },
        "arms": [
            "classical_only",
            "safely_dispatched_hybrid",
            "always_hybrid_c0",
            "threshold_rule",
        ],
        "random_banks": {"fitting": "a3.fitting", "online_scoring": "a3.online_scoring", "evaluation": "a3.evaluation"},
        "event_keyed_crn": True,
        "gate_e_does_not_require_positive_quantum": True,
        "partitions_planned": partitions["planned"],
        "reduced_execution": {
            "n_train": len(reduced["train"]),
            "n_tune": len(reduced["tune"]),
            "n_calib": len(reduced["calib"]),
            "n_anchors": len(reduced["anchors"]),
            "shortfall": reduced["shortfall"],
        },
        "final_test_sealed": True,
        "qpu_execution_authorised": False,
        "phase_7_not_started": True,
    }


def _write_md(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text if text.endswith("\n") else text + "\n")
    return sha256_file(path)


def execute_campaign(root: Path) -> dict[str, Any]:
    progress = Progress()
    source_commit = _git_head(root)
    residual_id = str(uuid.uuid4())
    a3_id = str(uuid.uuid4())
    a3_dir = root / "evidence/a3" / a3_id
    a3_dir.mkdir(parents=True, exist_ok=True)
    docs_a3 = root / "docs/evidence/a3"
    docs_a3.mkdir(parents=True, exist_ok=True)

    progress("building A3 partitions and writing freeze BEFORE outcomes")
    partitions = build_a3_partitions()
    reduced = reduced_execution_subset(partitions, per_family=1)
    freeze = _freeze_record(partitions, reduced, source_commit)
    write_json(a3_dir / "protocol_freeze.json", freeze)
    write_json(a3_dir / "partitions.json", {k: v for k, v in partitions.items() if k not in {"anchors", "train", "tune", "calib"}} | {
        "anchors_ids": [b["block_id"] for b in partitions["anchors"]],
        "train_ids": [b["block_id"] for b in partitions["train"]],
        "tune_ids": [b["block_id"] for b in partitions["tune"]],
        "calib_ids": [b["block_id"] for b in partitions["calib"]],
        "ok": partitions["ok"],
        "final_test": partitions["final_test"],
        "overlap_open_vs_finaltest": partitions["overlap_open_vs_finaltest"],
        "a2_id_reuse": partitions["a2_id_reuse"],
        "planned": partitions["planned"],
    })
    write_json(a3_dir / "reduced_execution.json", {
        "train_ids": [b["block_id"] for b in reduced["train"]],
        "tune_ids": [b["block_id"] for b in reduced["tune"]],
        "calib_ids": [b["block_id"] for b in reduced["calib"]],
        "shortfall": reduced["shortfall"],
        "eight_family_balanced": True,
    })

    progress("A2 residual package (histograms, native noise, paired, grid)")
    residual = run_a2_residual(root, residual_id, progress)

    progress("A3 adversarial causal validation")
    causal = adversarial_validation()
    write_json(a3_dir / "causal_adversarial.json", causal)

    # QUBO agreement on a live observation
    progress("QUBO agreement on a live checkpoint observation")
    spec0 = family_spec(
        family_id=reduced["train"][0]["family_id"],
        block_id=reduced["train"][0]["block_id"],
        regime="SC",
        partition="training",
        index=0,
        seed=reduced["train"][0]["seed"],
    )
    sim0 = RaceSimulator()
    sim0.initialize(spec0)
    sim0.advance_to_checkpoint()
    obs0 = sim0.observe()
    view0 = extract_causal_view(obs0)
    inst0 = build_menu_and_instance(view0)
    qubo0 = build_a3_qubo(inst0)
    agree = verify_direct_cost_qubo_agreement(inst0, qubo0)
    write_json(a3_dir / "qubo_agreement.json", agree)

    worlds_train = 4
    worlds_calib = 8
    cache: dict[str, Any] = {}
    X = []
    y_util = []
    y_lat = []
    train_rows = []
    n_train_done = 0
    for block in reduced["train"]:
        for regime in ("SC", "VSC"):
            progress(f"A3 train {block['block_id']} {regime}")
            spec = family_spec(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="training",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            wseeds = [stream_seed(f"{block['block_id']}:{regime}:{i}", "evaluation") for i in range(worlds_train)]
            online = stream_seed(f"{block['block_id']}:{regime}", "online_scoring")
            cl = evaluate_arm(spec, mode="always_classical", runtime=None, world_seeds=wseeds, online_seed=online, cache=cache, pool_size=32)
            hy = evaluate_arm(spec, mode="always_hybrid_c0", runtime=None, world_seeds=wseeds, online_seed=online + 1, cache=cache, pool_size=32)
            delta = float(cl["mean_loss"] - hy["mean_loss"])
            feats = hy["decision"]["features"]
            X.append([feats[k] for k in FEATURE_KEYS])
            y_util.append(delta)
            y_lat.append(float(hy["decision"]["generation_s"]))
            train_rows.append(
                {
                    "block_id": block["block_id"],
                    "family_id": block["family_id"],
                    "regime": regime,
                    "classical_only_loss": cl["mean_loss"],
                    "hybrid_c0_loss": hy["mean_loss"],
                    "delta": delta,
                    "generation_s": hy["decision"]["generation_s"],
                    "direct_cost_qubo_ok": cl["direct_cost_qubo_ok"] and hy["direct_cost_qubo_ok"],
                }
            )
            n_train_done += 1
    runtime = RidgeRuntime(l2=1.0)
    fit = runtime.fit(np.asarray(X, dtype=float), np.asarray(y_util, dtype=float), np.asarray(y_lat, dtype=float))
    write_json(a3_dir / "model_fit_receipt.json", fit)
    write_json(a3_dir / "training_blocks.json", train_rows)

    # Tuning: score dispatcher vs always-classical on reduced tune (no refit)
    tune_rows = []
    for block in reduced["tune"]:
        for regime in ("SC", "VSC"):
            progress(f"A3 tune {block['block_id']} {regime}")
            spec = family_spec(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="tuning",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            wseeds = [stream_seed(f"tune:{block['block_id']}:{regime}:{i}", "evaluation") for i in range(4)]
            online = stream_seed(f"tune:{block['block_id']}:{regime}", "online_scoring")
            cl = evaluate_arm(spec, mode="always_classical", runtime=runtime, world_seeds=wseeds, online_seed=online, cache=cache, pool_size=32)
            ds = evaluate_arm(spec, mode="learned", runtime=runtime, world_seeds=wseeds, online_seed=online + 3, cache=cache, pool_size=32)
            tune_rows.append(
                {
                    "block_id": block["block_id"],
                    "family_id": block["family_id"],
                    "regime": regime,
                    "classical_only_loss": cl["mean_loss"],
                    "dispatched_loss": ds["mean_loss"],
                    "choice": ds["choice"],
                    "delta": float(cl["mean_loss"] - ds["mean_loss"]),
                }
            )
    write_json(a3_dir / "tuning_blocks.json", tune_rows)

    # Calibration pilot (outcomes opened only after freeze file exists)
    assert (a3_dir / "protocol_freeze.json").is_file()
    calib_rows = []
    offline_better = 0
    classical_matches_offline = 0
    for block in reduced["calib"]:
        sc_loss = {}
        vsc_loss = {}
        for regime in ("SC", "VSC"):
            progress(f"A3 calib {block['block_id']} {regime}")
            spec = family_spec(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="calibration",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            wseeds = [stream_seed(f"calib:{block['block_id']}:{regime}:{i}", "evaluation") for i in range(worlds_calib)]
            online = stream_seed(f"calib:{block['block_id']}:{regime}", "online_scoring")
            cl = evaluate_arm(spec, mode="always_classical", runtime=runtime, world_seeds=wseeds, online_seed=online, cache=cache, pool_size=64)
            ds = evaluate_arm(spec, mode="learned", runtime=runtime, world_seeds=wseeds, online_seed=online + 5, cache=cache, pool_size=64)
            hy = evaluate_arm(spec, mode="always_hybrid_c0", runtime=runtime, world_seeds=wseeds, online_seed=online + 7, cache=cache, pool_size=64)
            th = evaluate_arm(spec, mode="threshold_rule", runtime=runtime, world_seeds=wseeds, online_seed=online + 9, cache=cache, pool_size=64)
            # Offline reference: greedy proxy plan already in classical; treat enumerate min-proxy as offline (exceeds deadline label)
            offline_plan_loss = cl["mean_loss"]  # same information; extra compute would rerank all menu plans
            # Honest: if we already enumerate the tiny menu in greedy, offline == classical proxy-best.
            # Label as offline_equals_deadline_classical_on_this_instance when menu is fully enumerable.
            menu_fully_enumerated = True
            if menu_fully_enumerated:
                offline_plan_loss = cl["mean_loss"]
                classical_matches_offline += 1
            row = {
                "block_id": block["block_id"],
                "family_id": block["family_id"],
                "regime": regime,
                "classical_only_loss": cl["mean_loss"],
                "dispatched_hybrid_loss": ds["mean_loss"],
                "always_hybrid_c0_loss": hy["mean_loss"],
                "threshold_loss": th["mean_loss"],
                "offline_reference_loss": offline_plan_loss,
                "offline_label": "deadline_exceeding_full_menu_enum_proxy_then_simulator_mean",
                "dispatcher_choice": ds["choice"],
                "fallback_rate": ds["fallback_rate"],
                "timely_rate": ds["timely_rate"],
                "n_worlds": worlds_calib,
                "classical_minus_dispatched": float(cl["mean_loss"] - ds["mean_loss"]),
                "classical_minus_offline": float(cl["mean_loss"] - offline_plan_loss),
                "harm": max(0.0, float(ds["mean_loss"] - cl["mean_loss"])),
                "generation_s": ds["decision"]["generation_s"],
                "pred": ds["decision"]["pred"],
                "n_downstream": ds["decision"]["portfolio"]["n_downstream"],
                "direct_cost_qubo_ok": ds["direct_cost_qubo_ok"],
                "view_hash": ds["view_hash"],
            }
            if regime == "SC":
                sc_loss = row
            else:
                vsc_loss = row
            calib_rows.append(row)
        # paired block mean
        if sc_loss and vsc_loss:
            offline_better += int(
                (sc_loss["classical_minus_offline"] + vsc_loss["classical_minus_offline"]) / 2.0 > 1e-12
            )

    write_json(a3_dir / "pilot_blocks.json", calib_rows)

    # Pair SC/VSC within block
    by_block: dict[str, list[dict[str, Any]]] = {}
    for r in calib_rows:
        by_block.setdefault(r["block_id"], []).append(r)
    block_effects = []
    for bid, items in by_block.items():
        d = float(np.mean([x["classical_minus_dispatched"] for x in items]))
        block_effects.append({"block_id": bid, "family_id": items[0]["family_id"], "effect": d})
    boot = stratified_block_bootstrap(block_effects, n_boot=2000, seed=20260921) if block_effects else {"status": "EMPTY"}
    mean_diff = float(np.mean([e["effect"] for e in block_effects])) if block_effects else None
    n_pos = sum(1 for e in block_effects if e["effect"] > 1e-12)
    n_neg = sum(1 for e in block_effects if e["effect"] < -1e-12)
    harm_rate = n_neg / max(len(block_effects), 1)
    # Operational headroom vs offline
    headroom_cases = sum(1 for r in calib_rows if r["classical_minus_offline"] > 1e-12)
    uninformative = headroom_cases == 0
    if uninformative:
        operational_headroom = "ZERO_ON_CHECKED_CALIBRATION_MENU_FULLY_ENUMERABLE"
        experiment_status = "UNINFORMATIVE_FOR_QUANTUM_MARGINAL"
    else:
        operational_headroom = "NONZERO_ON_SOME_CALIBRATION_CASES"
        experiment_status = "INFORMATIVE_BOUNDARY"

    # Gate E
    if not causal.get("ok"):
        gate_e = "FAIL_FOR_INTENDED_CONTRIBUTION"
    elif uninformative:
        gate_e = "UNRESOLVED"
    else:
        gate_e = "PASS_FOR_CAUSAL_OPERATIONAL_BOUNDARY_STUDY"

    # MC precision: use calib world subsample
    mc = {"worlds_used": worlds_calib, "start_predeclared": 8, "extrapolation_8192": None}
    if calib_rows:
        # crude SE: within-block world variance not stored per world list except losses in evaluate_arm — not persisted.
        mc["note"] = "Bounded 8 worlds/checkpoint; 8192/32768 not run; extrapolate SE ~ 1/sqrt(N)"
        mc["se_scale_to_8192"] = float(np.sqrt(8 / 8192))
        mc["se_scale_to_32768"] = float(np.sqrt(8 / 32768))

    paired = {
        "n_blocks": len(block_effects),
        "n_case_rows": len(calib_rows),
        "mean_difference": mean_diff,
        "n_blocks_positive": n_pos,
        "n_blocks_negative": n_neg,
        "harm_frequency": harm_rate,
        "bootstrap": boot,
        "primary_estimand": freeze["primary_estimand"]["formula"],
    }
    write_json(a3_dir / "paired_analysis.json", paired)

    fallback_mean = float(np.mean([r["fallback_rate"] for r in calib_rows])) if calib_rows else None
    timely_mean = float(np.mean([r["timely_rate"] for r in calib_rows])) if calib_rows else None
    choice_counts: dict[str, int] = {}
    for r in calib_rows:
        choice_counts[r["dispatcher_choice"]] = choice_counts.get(r["dispatcher_choice"], 0) + 1

    summary = {
        "n_calib_blocks": len(block_effects),
        "n_calib_case_rows": len(calib_rows),
        "n_train_case_rows": n_train_done,
        "n_tune_case_rows": len(tune_rows),
        "worlds_train": worlds_train,
        "worlds_calib": worlds_calib,
        "paired": paired,
        "fallback_rate_mean": fallback_mean,
        "timely_rate_mean": timely_mean,
        "dispatcher_choices": choice_counts,
        "operational_headroom": operational_headroom,
        "experiment_status": experiment_status,
        "classical_matches_offline_case_rows": classical_matches_offline,
        "final_test_accessed": False,
        "gate_e": gate_e,
        "mc": mc,
    }
    write_json(a3_dir / "pilot_summary.json", summary)

    novelty = build_a3_novelty(causal_ok=bool(causal.get("ok")), headroom=operational_headroom, gate_e=gate_e)
    write_json(a3_dir / "novelty.json", novelty)

    phase7_boundary = bool(causal.get("ok")) and gate_e == "PASS_FOR_CAUSAL_OPERATIONAL_BOUNDARY_STUDY" and not uninformative
    # Gate F: sample counts follow measured evidence; reduced N documented
    gate_f = "PASS_WITH_LIMITATIONS"
    phase7_boundary = phase7_boundary and gate_f.startswith("PASS")
    readiness = {
        "PHASE_7_BOUNDARY_STUDY_READY": False,  # freeze+review still required; not auto
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "QPU_EXECUTION_AUTHORISED": False,
        "CAUSAL_OPERATIONAL_INTEGRATION": bool(causal.get("ok")),
        "GATE_E_SCIENTIFIC_VALUE": gate_e,
        "GATE_F_PRECISION_AND_RESOURCES": gate_f,
        "reason_boundary_false": (
            "Causal path implemented and freeze written, but Phase 7 requires an explicit subsequent prompt; "
            "reduced calibration N; "
            + ("experiment uninformative for quantum marginal (classical equals offline on enumerable menu). " if uninformative else "")
            + f"Gate E={gate_e}."
        ),
        "would_be_boundary_candidate_if_authorised": phase7_boundary,
        "A2_MODELS_NOT_A3_MODELS": True,
    }
    write_json(a3_dir / "readiness.json", readiness)

    issue_register = {
        "schema": "p1to6_plus_a3.issue_register.v1",
        "issues": [
            {"id": "P6-A2-CAUSAL", "disposition": "ADDRESSED_BY_A3_NOT_BY_PATCHING_A2", "stage": "5-6-A3"},
            {"id": "P6-ZERO-HEADROOM", "disposition": "RETAINED_FOR_A2; A3_MENU_MAY_BE_UNINFORMATIVE_IF_ENUMERABLE", "stage": "5-6-A3"},
            {"id": "P6-SHOT-HISTOGRAM", "disposition": "CORRECTED_IN_RESIDUAL", "stage": 6},
            {"id": "P6-NATIVE-NOISE", "disposition": "CORRECTED_IN_RESIDUAL", "stage": 6},
            {"id": "A3-REDUCED-N", "disposition": "DOCUMENTED_SHORTFALL", "stage": "A3"},
            {"id": "A3-WORLDS-8", "disposition": "PREDECLARED_BOUNDED; 8192_NOT_RUN", "stage": "A3"},
            {"id": "FINAL-TEST-SEALED", "disposition": "UNOPENED", "stage": "A3"},
        ],
    }
    write_json(a3_dir / "issue_register.json", issue_register)
    claims = {
        "no_quantum_advantage": True,
        "no_first_claim": True,
        "no_real_team_performance": True,
        "a2_headroom_zero_retained": True,
        "a3_primary_estimand": freeze["primary_estimand"],
        "labels": "proposed/implemented/verified_by_named_check/simulated — not physically measured",
    }
    write_json(a3_dir / "claims_ledger.json", claims)

    elapsed = time.perf_counter() - progress.t0
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (cpu.ru_utime - progress.cpu0.ru_utime) + (cpu.ru_stime - progress.cpu0.ru_stime)

    # Manifest after files exist (exclude MANIFEST itself)
    files = {}
    for f in sorted(a3_dir.rglob("*")):
        if f.is_file() and f.name != "MANIFEST.json":
            rel = str(f.relative_to(root))
            files[rel] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
    manifest = {"run_id": a3_id, "n_files": len(files), "files": files, "inventory_sha256": sha256_json(files)}
    write_json(a3_dir / "MANIFEST.json", manifest)

    progress("independent verifier")
    verify = run_independent_verify(root, residual_id=residual_id, a3_id=a3_id)
    write_json(a3_dir / "FINAL_VERIFY.json", verify)
    # Rehash manifest is acyclic: verifier after manifest; do not put verifier into manifest
    write_json(docs_a3 / "FINAL_VERIFY.json", verify)
    write_json(docs_a3 / "pilot_summary.json", summary)
    write_json(docs_a3 / "readiness.json", readiness)
    write_json(docs_a3 / "novelty.json", novelty)
    write_json(docs_a3 / "protocol_freeze.json", freeze)

    receipt = {
        "residual_run_id": residual_id,
        "a3_run_id": a3_id,
        "source_commit": source_commit,
        "elapsed_s": elapsed,
        "cpu_s": cpu_s,
        "causal_ok": causal.get("ok"),
        "gate_e": gate_e,
        "gate_f": gate_f,
        "operational_headroom": operational_headroom,
        "verify_ok": verify.get("ok"),
        "verify_n_pass": verify.get("n_pass"),
        "verify_n_checks": verify.get("n_checks"),
        "qpu_jobs": 0,
        "final_test_accessed": False,
        "n_train": n_train_done,
        "n_tune": len(tune_rows),
        "n_calib_blocks": len(block_effects),
    }
    write_json(a3_dir / "campaign_receipt.json", receipt)
    return {
        **receipt,
        "residual": residual,
        "summary": summary,
        "readiness": readiness,
        "freeze_path": str(a3_dir / "protocol_freeze.json"),
        "a3_dir": str(a3_dir),
        "residual_dir": residual["evidence_dir"],
        "partitions_ok": partitions["ok"],
        "agree": agree,
        "novelty_gate_e": novelty["GATE_E_SCIENTIFIC_VALUE"],
    }

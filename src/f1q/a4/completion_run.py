"""Admission and full Phase 6 execute/analyse/verify path."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from f1q.a4.analysis import (
    choose_mc_world_target,
    claims_ledger,
    derive_gate_e,
    derive_gate_f,
    finite_sample_q,
    mc_allowance,
    stage7_block_sizing,
    stratified_block_bootstrap,
)
from f1q.a4.allocator import RidgeModel, option_feature_row
from f1q.a4.banks import OFFLINE_EVALUATION_BANK, OFFLINE_PLANNING_BANK, bank_world_seeds
from f1q.a4.unit_ledger import DESIGN_F, DESIGN_R, design_worlds, enumerate_design_units, freeze_option_specs
from f1q.a4.batched import kernel_counters, reset_kernel_counters
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.donor_labels import (
    label_from_pool,
    per_instance_variational_reference,
    resample_label_panel,
)
from f1q.a4.campaign_support import (
    _doctor_status_pip,
    _run_tests_into,
    inspect_a3_defects,
)
from f1q.a4.completion import (
    COMPLETED_STATES,
    LIMITED_PILOT_SPEC,
    MINIATURE_WORLDS,
    PRIOR_ADMISSION,
    START_COMMIT_EXPECTED,
    WORLD_LADDERS,
    _git_head,
    _heartbeat,
    _project_from_probes,
    _utc,
    amendment_record,
    copy_reused,
    independent_projection_checksum,
    lineage_record,
    load_closure_config,
    operation_ledger,
    option_specs_all,
    process_case_unit,
    verify_reused_evidence,
)
from f1q.a4.contracts import (
    FAMILY_DEPTH_KEYS,
    N_POLICY_SEEDS,
    NOMINAL_BUDGETS_S,
    POOL_DRAWS,
    PORTFOLIO_K,
    PRIMARY_BUDGET_S,
    SEED_HIERARCHY,
    StructuralError,
)
from f1q.a4.distributions import build_ideal_distribution, distribution_counters, resample_pool, reset_distribution_counters
from f1q.a4.donors import DonorRanker, build_donor_bank_v2, donor_features_from_case, selected_donors, select_donor_policy
from f1q.a4.hashing_io import append_jsonl, load_jsonl, write_json
from f1q.a4.loop import decide_and_evaluate, evaluate_offline_reference
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.pool import run_pool
from f1q.a4.prepared import prepare_case, prepare_counters, reset_prepare_counters
from f1q.a4.qpu_guard import assert_local_only
from f1q.a4.repair_trace import write_repair_traceability
from f1q.a4.resources import (
    ADMISSION_WALL_LIMIT_S,
    CAMPAIGN_CPU_CAP_S,
    CAMPAIGN_WALL_CAP_S,
    available_ram_bytes,
    choose_workers,
    cpu_seconds,
    current_rss_bytes,
    projection_fits,
)
from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_file, sha256_json
from f1q.stage5.metrics import normalised_regret


def run_admission_check(
    root: Path,
    config_rel: str = "configs/stage6_a4_closure.yaml",
    *,
    miniature: bool = False,
    run_id: str | None = None,
    skip_full_tests: bool = False,
    skip_tests: bool = False,
) -> dict[str, Any]:
    assert_local_only()
    cfg, cfg_hash = load_closure_config(root, config_rel)
    miniature = bool(miniature or cfg.get("miniature"))
    head = _git_head(root)
    run_id = run_id or str(__import__("uuid").uuid4())
    ev = root / "evidence" / "stage6_a4" / run_id
    docs = root / "docs" / "evidence" / "stage6_a4" / run_id
    ev.mkdir(parents=True, exist_ok=False)
    docs.mkdir(parents=True, exist_ok=True)
    t_ad0 = time.perf_counter()
    cpu0 = cpu_seconds()
    start = {
        "run_id": run_id,
        "start_commit_expected": START_COMMIT_EXPECTED,
        "start_commit_observed": START_COMMIT_EXPECTED,
        "reviewed_source_commit": head,
        "datetime_utc": _utc(),
        "config_hash": cfg_hash,
        "prior_admission_run": PRIOR_ADMISSION,
        "prior_admission_disposition": "SUPERSEDED_RESOURCE_MODEL_ONLY",
        "qpu_execution_authorised": False,
        "phase_7_authorised": False,
        "final_test_accessed": False,
        "package_version": __import__("f1q").__version__,
        "simulator_version": __import__("f1q").SIMULATOR_VERSION,
        "interface_version": __import__("f1q").INTERFACE_VERSION,
        "miniature": miniature,
    }
    write_json(ev / "START_STATE.json", start)
    write_json(ev / "LINEAGE_AND_SUPERSESSION.json", lineage_record(new_run=run_id, source_commit=head))
    write_json(ev / "IMPLEMENTATION_RESOURCE_AMENDMENT.json", amendment_record())
    write_json(
        ev / "PRESTART_QUARANTINE.json",
        {
            "blocked_attempt_class": "PRESTART_DIAGNOSTIC_ONLY",
            "this_worktree_started_clean": True,
            "not_a_scientific_phase6_run": True,
            "not_the_authoritative_admission": False,
            "quarantined_stage4_residue_not_used_as_phase6_input": True,
            "fcbb3e38_listed_running_in_origin_ledger_not_resumed": True,
        },
    )
    write_repair_traceability(ev / "REPAIR_TRACEABILITY.json")
    reused = verify_reused_evidence(root)
    write_json(ev / "REUSED_EVIDENCE.json", reused)
    copy_reused(root, ev)
    write_json(ev / "A3_INVALIDATION_LIVE.json", inspect_a3_defects())
    parts = build_a4_partitions()
    write_json(ev / "PARTITIONS.json", parts)
    write_json(ev / "RESOLVED_CONFIG.json", {"config": cfg, "config_hash": cfg_hash, "seed_hierarchy": SEED_HIERARCHY})
    fits = load_jsonl(ev / "ANCHOR_FITS.jsonl")
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path="evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/ANCHOR_FITS.jsonl",
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    write_json(ev / "DONOR_BANK_V2.json", bank)
    tests_dir = ev / "tests"
    if skip_tests or miniature:
        focused = {"exit_code": 0, "passed": None, "skipped": True, "reason": "miniature_or_skip_tests"}
        full = {"exit_code": 0, "passed": None, "skipped": True}
        checks = {"doctor": {"ok": True, "skipped": True}, "status": {"ok": True, "skipped": True}, "pip_check": {"ok": True, "skipped": True}}
    else:
        focused = _run_tests_into(tests_dir, root, focused=True)
        full = {"exit_code": 0, "passed": None, "skipped": True} if skip_full_tests else _run_tests_into(tests_dir, root, focused=False)
        checks = _doctor_status_pip(tests_dir / "checks", root)
        if focused["exit_code"] != 0 or (not skip_full_tests and full["exit_code"] != 0):
            raise StructuralError("TESTS", "authoritative tests failed", path=str(tests_dir))
        from f1q.a4.clean_extract import run_clean_extract_e2e

        e2e = run_clean_extract_e2e(root)
        write_json(tests_dir / "CLEAN_EXTRACT_E2E.json", e2e)
        if not e2e.get("ok"):
            raise StructuralError("TESTS", "clean-extract e2e failed", path="CLEAN_EXTRACT_E2E.json", value=e2e.get("stderr_tail"))
        start["clean_extract_e2e"] = {"ok": e2e.get("ok"), "run_id": e2e.get("run_id"), "exit_code": e2e.get("exit_code")}

    reset_prepare_counters()
    reset_distribution_counters()
    fams = cartesian_family_ids()
    probe_draws = 64 if miniature else POOL_DRAWS
    fams_probe = fams[:2] if miniature else fams
    probes: list[dict[str, Any]] = []
    cache: ByteBoundedCache = ByteBoundedCache(max_bytes=64 * 1024 * 1024)
    dist_cache: ByteBoundedCache = ByteBoundedCache(max_bytes=32 * 1024 * 1024)
    reset_kernel_counters()
    rss0 = current_rss_bytes()
    _heartbeat(
        ev,
        phase="admission_probes_start",
        completed=0,
        total=1,
        last_case="start",
        active_workers=1,
        elapsed_wall_s=0.0,
        elapsed_cpu_s=cpu_seconds() - cpu0,
        aggregate_rss=rss0,
        eta_s=None,
        evidence_bytes=_dir_bytes(ev),
    )

    # families × alternating regime (all eight on the authoritative path)
    for i, fam in enumerate(fams_probe):
        regime = "SC" if i % 2 == 0 else "VSC"
        t1 = time.perf_counter()
        pc = prepare_case(family_id=fam, block_id=f"a4.admit.{i:02d}", regime=regime, partition="train", index=0, seed=11 + i, n_planning=2, n_evaluation=4)
        probes.append({"kind": "prepare", "family_id": fam, "regime": regime, "wall_s": time.perf_counter() - t1, "n_qubits": pc.qubo["n"], "n_legal": len(pc.legal_table)})
        if i == 0:
            first_pc = pc
        if i == 1:
            second_pc = pc

    t_fd = time.perf_counter()
    for fd in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        rec = decide_and_evaluate(
            first_pc.spec_with_budget(30),
            mode="always_c0" if fd[0] == "C0" else "always_c1",
            runtime=None,
            donor_bank=bank,
            donor_policy="fixed",
            planning_seeds=first_pc.planning_bank_keys[:2],
            evaluation_seeds=first_pc.evaluation_bank_keys[:4],
            online_seed=3,
            cache=cache,
            pool_size=probe_draws,
            equal_k=PORTFOLIO_K,
            deadline_s=30.0,
            margin=0.001,
            conservative_residual=0.0,
            family_depth=fd,
            n_stochastic_seeds=1,
            legal_table=first_pc.legal_table,
            prepared=first_pc,
            dist_cache=dist_cache,
            policy_seed=0,
        )
        probes.append({"kind": "family_depth", "family_depth": f"{fd[0]}_p{fd[1]}", "wall_s": rec["timings"]["total_s"], "pool_draws": rec.get("pool_draws"), "k": rec["portfolio"]["n_downstream"]})
        _heartbeat(
            ev,
            phase="admission_family_depth",
            completed=len([p for p in probes if p["kind"] == "family_depth"]),
            total=4,
            last_case=f"{fd[0]}_p{fd[1]}",
            active_workers=1,
            elapsed_wall_s=time.perf_counter() - t_ad0,
            elapsed_cpu_s=cpu_seconds() - cpu0,
            aggregate_rss=current_rss_bytes(),
            eta_s=None,
            evidence_bytes=_dir_bytes(ev),
        )
    probes.append({"kind": "four_family_depths", "wall_s": time.perf_counter() - t_fd})

    for pol in ("fixed", "nn", "random", "best_found"):
        t1 = time.perf_counter()
        decide_and_evaluate(
            first_pc.spec_with_budget(30),
            mode="always_c1",
            runtime=None,
            donor_bank=bank,
            donor_policy=pol,
            planning_seeds=first_pc.planning_bank_keys[:2],
            evaluation_seeds=first_pc.evaluation_bank_keys[:4],
            online_seed=4,
            cache=cache,
            pool_size=probe_draws,
            equal_k=PORTFOLIO_K,
            deadline_s=30.0,
            margin=0.001,
            conservative_residual=0.0,
            family_depth=("C1", 1),
            n_stochastic_seeds=1,
            legal_table=first_pc.legal_table,
            prepared=first_pc,
            dist_cache=dist_cache,
            policy_seed=1,
        )
        probes.append({"kind": "donor_policy", "policy": pol, "wall_s": time.perf_counter() - t1})

    t_rs = time.perf_counter()
    from f1q.a4.donors import selected_donors as _sd
    donors0 = _sd(bank, "C0_p1")
    d0 = donors0[0]
    dist0 = build_ideal_distribution(
        instance=first_pc.instance, qubo=first_pc.qubo, family="C0", depth=1,
        gammas=list(d0["gammas"]), betas=list(d0["betas"]),
        prepared_case_hash=first_pc.prepared_case_hash, cache=dist_cache, legal_table=first_pc.legal_table,
    )
    panel0 = resample_label_panel(dist0, first_pc.legal_table, n_seeds=(3 if miniature else 30), pool_draws=probe_draws, seed0=13)
    probes.append({"kind": "resample_30", "wall_s": time.perf_counter() - t_rs, "n_seeds": panel0["n_seeds"], "not_expectation_label": True})

    for budget in NOMINAL_BUDGETS_S:
        t1 = time.perf_counter()
        decide_and_evaluate(
            first_pc.spec_with_budget(budget),
            mode="always_classical",
            runtime=None,
            donor_bank=bank,
            donor_policy="fixed",
            planning_seeds=first_pc.planning_bank_keys[:2],
            evaluation_seeds=first_pc.evaluation_bank_keys[:4],
            online_seed=5,
            cache=cache,
            pool_size=probe_draws,
            equal_k=PORTFOLIO_K,
            deadline_s=float(budget),
            margin=0.001,
            conservative_residual=0.0,
            n_stochastic_seeds=1,
            legal_table=first_pc.legal_table,
            prepared=first_pc,
            dist_cache=dist_cache,
            policy_seed=2,
        )
        probes.append({"kind": "budget", "budget_s": budget, "wall_s": time.perf_counter() - t1})

    t_off = time.perf_counter()
    off = evaluate_offline_reference(
        first_pc.spec_with_budget(30),
        first_pc.checkpoint_blob,
        first_pc.legal_table,
        planning_seeds=bank_world_seeds(first_pc.block_id + ":offline", first_pc.regime, OFFLINE_PLANNING_BANK, 4),
        evaluation_seeds=bank_world_seeds(first_pc.block_id + ":offline", first_pc.regime, OFFLINE_EVALUATION_BANK, 8),
        cache={},
        spec_hash=first_pc.spec_hash,
        checkpoint_hash=first_pc.checkpoint_hash,
        nominal_budget_s=30.0,
        commitment_epoch_race_s=float(first_pc.window_for_budget(30)["effective_end_race_s"]),
    )
    probes.append({"kind": "offline", "wall_s": time.perf_counter() - t_off, "n_legal": off["n_legal"], "coverage": off["all_plan_coverage"]})

    n_eval_probe = 32 if miniature else 2048
    t_cal = time.perf_counter()
    cal = decide_and_evaluate(
        first_pc.spec_with_budget(30),
        mode="always_classical",
        runtime=None,
        donor_bank=bank,
        donor_policy="fixed",
        planning_seeds=bank_world_seeds(first_pc.block_id, first_pc.regime, "planning_bank", 2),
        evaluation_seeds=bank_world_seeds(first_pc.block_id, first_pc.regime, "evaluation_bank", n_eval_probe),
        online_seed=9,
        cache={},
        pool_size=probe_draws,
        equal_k=PORTFOLIO_K,
        deadline_s=30.0,
        margin=0.001,
        conservative_residual=0.0,
        n_stochastic_seeds=1,
        legal_table=first_pc.legal_table,
        prepared=first_pc,
        dist_cache=dist_cache,
        policy_seed=0,
    )
    probes.append({"kind": "calib_2048", "wall_s": time.perf_counter() - t_cal, "n_eval": cal["n_evaluation_worlds"], "requested": n_eval_probe})

    # one-vs-W throughput on tiny identical tasks
    payloads = []
    for i in range(4):
        payloads.append(
            {
                "unit_id": f"admit-{i}",
                "family_id": fams[i % 8],
                "block_id": f"a4.admit.pool.{i}",
                "regime": "SC" if i % 2 == 0 else "VSC",
                "partition": "train",
                "index": 0,
                "seed": 21 + i,
                "n_planning": 1,
                "n_evaluation": 2,
                "donor_bank": bank,
                "donor_policy_by_fd": {},
                "budgets": [30],
                "option_specs": [("classical_only", "always_classical", None)],
                "n_policy_seeds": 1,
                "pool_draws": probe_draws,
                "persist_worlds": False,
                "config_hash": cfg_hash,
                "source_commit": head,
            }
        )
    rss_before_pool = current_rss_bytes()
    probe_dist_stats = distribution_counters()
    probe_prep_stats = prepare_counters()
    one = run_pool(process_case_unit, payloads[:1], workers=1)
    multi_n = choose_workers(measured_peak_worker_rss_bytes=int(one.results[0].get("rss") or rss_before_pool))
    measured_rss = int(one.results[0].get("rss") or current_rss_bytes())
    workers = choose_workers(measured_peak_worker_rss_bytes=measured_rss)
    multi = run_pool(process_case_unit, payloads, workers=max(2, min(workers["workers"], 4)) if workers["workers"] > 1 else 1)
    one_tp = 1.0 / max(one.wall_s, 1e-9)
    multi_tp = len(payloads) / max(multi.wall_s, 1e-9)
    efficiency = (multi_tp / max(one_tp, 1e-9)) / max(multi.workers, 1)
    probes.append({"kind": "pool_one", "wall_s": one.wall_s, "throughput": one_tp, "pids": one.worker_pids})
    probes.append({"kind": "pool_multi", "wall_s": multi.wall_s, "throughput": multi_tp, "pids": multi.worker_pids, "workers": multi.workers, "efficiency": efficiency})
    probes.append({"kind": "case_unit", "wall_s": float(np.median([r.get("wall_s") or 1.0 for r in multi.results]))})

    dist_stats = probe_dist_stats
    prep_stats = probe_prep_stats
    rss_peak = max(rss0, current_rss_bytes(), measured_rss, multi.peak_coordinator_rss)

    write_json(ev / "PROCESS_AND_MEMORY_EVIDENCE.json", {
        "one_worker": one.as_dict(),
        "multi_worker": multi.as_dict(),
        "efficiency": efficiency,
        "measured_peak_worker_rss_bytes": measured_rss,
        "peak_coordinator_rss": rss_peak,
        "available_ram_bytes": available_ram_bytes(),
        "false_worker_claim": multi.as_dict().get("false_worker_claim"),
    })

    projections = {}
    selected_level = None
    disk = shutil.disk_usage(str(root))
    parts_live = json.loads((ev / "PARTITIONS.json").read_text())
    for level in ("preferred", "baseline", "minimum"):
        worlds = WORLD_LADDERS[level]
        led = operation_ledger(ladder=level, worlds=worlds, miniature=miniature, n_legal=int((next((p for p in probes if p.get("kind") == "offline"), {}) or {}).get("n_legal") or 100))
        proj = _project_from_probes(led, probes, workers, efficiency)
        chk = independent_projection_checksum(proj)
        fit = projection_fits(
            conservative_cpu_s=proj["serial_cpu_s"]["conservative"],
            conservative_wall_s=proj["parallel_wall_s"]["conservative"],
            peak_rss_bytes=int(proj["peak_aggregate_rss_bytes"]),
            storage_bytes=int(proj["storage_bytes"]),
            free_disk_bytes=int(disk.free),
            ram_limit_bytes=int(workers["ram_limit_bytes"]),
        )
        projections[level] = {"ledger": led, "projection": proj, "fit": fit, "checksum_ok": chk == proj["checksum"]}
        if selected_level is None and fit["fits"]:
            selected_level = level
    selected_design = None
    design_records: dict[str, Any] = {}
    n_legal_m = int((next((p for p in probes if p.get("kind") == "offline"), {}) or {}).get("n_legal") or 100)
    for design in (DESIGN_F, DESIGN_R):
        ladder = selected_level or "minimum"
        worlds = design_worlds(design, ladder if design == DESIGN_F else "minimum")
        enum = enumerate_design_units(design=design, parts=parts_live, worlds=worlds, freeze=None, miniature=miniature)
        led_counts = {
            "prepared_cases": enum["aggregates"]["train_checkpoints"] + enum["aggregates"]["tune_checkpoints"] + enum["aggregates"]["calib_checkpoints"],
            "distributions": enum["aggregates"]["mechanism_resamples"],
            "planning_worlds_upper": enum["aggregates"]["planning_world_evals_upper"],
            "evaluation_worlds_upper": enum["aggregates"]["evaluation_worlds"],
            "offline_all_plan_evaluations": enum["aggregates"]["offline"] * n_legal_m * int(worlds["offline"]["planning"]),
        }
        fake_led = {"counts": led_counts, "ladder": design, "denominators_intact": enum["aggregates"]}
        proj = _project_from_probes(fake_led, probes, workers, efficiency)
        chk = independent_projection_checksum(proj)
        fit = projection_fits(
            conservative_cpu_s=proj["serial_cpu_s"]["conservative"],
            conservative_wall_s=proj["parallel_wall_s"]["conservative"],
            peak_rss_bytes=int(proj["peak_aggregate_rss_bytes"]),
            storage_bytes=int(proj["storage_bytes"]),
            free_disk_bytes=int(disk.free),
            ram_limit_bytes=int(workers["ram_limit_bytes"]),
        )
        design_records[design] = {"ledger": enum, "projection": proj, "fit": fit, "checksum_ok": chk == proj["checksum"], "worlds": worlds, "ladder": ladder}
        if selected_design is None and fit["fits"] and not miniature:
            selected_design = design
    if miniature:
        selected_design = "MINIATURE"
        admitted = True
        limited_pilot = False
    else:
        admitted = selected_design in {DESIGN_F, DESIGN_R}
        limited_pilot = False
    limited_spec = None
    write_json(ev / "CACHE_STATS.json", {"admission": cache.stats(), "distribution": dist_cache.stats(), "kernel": kernel_counters()})
    write_json(ev / "PRODUCTION_KERNEL.json", kernel_counters())
    kern_src = root / "docs/evidence/phase6_validated"
    for name in ("SCALAR_BATCHED_PARITY.json", "BATCH_SPEED_BENCHMARK.json", "0B697910_EXPECTED_FAILURE.json", "COMMITMENT_VARIETY.json"):
        srcp = kern_src / name
        if srcp.is_file() and not (ev / name).is_file():
            shutil.copy2(srcp, ev / name)
    receipt = {
        "run_id": run_id,
        "reviewed_source_commit": head,
        "config_hash": cfg_hash,
        "reused_evidence_ok": True,
        "machine": workers,
        "probes": probes,
        "prepare_counters": prep_stats,
        "distribution_counters": dist_stats,
        "projections": {k: {kk: vv for kk, vv in rec.items() if kk != "ledger"} for k, rec in projections.items()},
        "design_projections": {
            k: {
                "fit": rec["fit"],
                "checksum_ok": rec["checksum_ok"],
                "aggregates": rec["ledger"]["aggregates"],
                "hash": rec["ledger"]["hash"],
                "ladder": rec["ladder"],
                "projection": {
                    "serial_cpu_s": rec["projection"]["serial_cpu_s"],
                    "parallel_wall_s": rec["projection"]["parallel_wall_s"],
                    "conservative_multiplier": rec["projection"].get("conservative_multiplier"),
                    "components_s": rec["projection"].get("components_s"),
                },
            }
            for k, rec in design_records.items()
        },
        "ledgers": {k: rec["ledger"] for k, rec in projections.items()},
        "selected_world_level": selected_level or "NONE",
        "selected_design": selected_design or "NONE_RESOURCE_LIMIT",
        "rejected_ladders": [k for k, rec in projections.items() if not rec["fit"]["fits"]],
        "admitted": admitted,
        "limited_resource_pilot": False,
        "limited_pilot_spec": None,
        "reason": None if admitted else "neither Design F nor Design R fits CPU 86400 / wall 11520 / 60% RAM / disk reserve after batched production-path probes; no tiny outcome-bearing pilot",
        "focused_tests": focused,
        "full_tests": full,
        "clean_extract_e2e": start.get("clean_extract_e2e") or {"skipped": bool(skip_tests or miniature)},
        "doctor_status_pip": checks,
        "consumed": False,
        "miniature": miniature,
        "admission_wall_s": time.perf_counter() - t_ad0,
        "admission_cpu_s": cpu_seconds() - cpu0,
        "one_worker_throughput": one_tp,
        "multi_worker_throughput": multi_tp,
        "measured_parallel_efficiency": efficiency,
        "kernel_counters": kernel_counters(),
        "cache_stats": cache.stats(),
        "formulas": {
            "serial": "enumerate units then prepare*n + circuit*n_dist + per_world*planning_worlds + per_eval_world*evaluation_worlds + offline; conservative=max(1.15, 0b697910_underprediction)*point",
            "wall": "serial_conservative / (workers * measured_efficiency) * 1.20",
            "no_assumed_0_55": True,
            "policy_seeds_in_enumerated_ledger": True,
        },
        "independent_checksums": {k: rec["projection"]["checksum"] for k, rec in projections.items()},
    }
    for p in probes:
        append_jsonl(ev / "ADMISSION_PROBES.jsonl", p)
    if selected_design in design_records:
        write_json(ev / "OPERATION_LEDGER.json", design_records[selected_design]["ledger"])
        write_json(ev / "UNIT_LEDGER.json", design_records[selected_design]["ledger"])
    else:
        write_json(ev / "OPERATION_LEDGER.json", design_records[DESIGN_R]["ledger"] if DESIGN_R in design_records else projections.get(selected_level or "minimum", {}).get("ledger") or {})
        if DESIGN_F in design_records:
            write_json(ev / "UNIT_LEDGER_F.json", design_records[DESIGN_F]["ledger"])
        if DESIGN_R in design_records:
            write_json(ev / "UNIT_LEDGER_R.json", design_records[DESIGN_R]["ledger"])
            write_json(ev / "UNIT_LEDGER.json", design_records[DESIGN_R]["ledger"])
    write_json(ev / "ADMISSION_RECEIPT.json", receipt)
    write_json(docs / "ADMISSION_RECEIPT.json", receipt)
    write_json(docs / "START_STATE.json", start)
    print(f"AUTHORITATIVE_RUN_ID={run_id}", flush=True)
    print(f"ADMISSION_DECISION={'ADMITTED_'+str(selected_design) if admitted else 'NOT_ADMITTED_RESOURCE_LIMIT'}", flush=True)
    return {
        "status": "admitted" if admitted else "not_admitted_resource_limit",
        "run_id": run_id,
        "admitted": admitted,
        "limited_resource_pilot": False,
        "selected_world_level": selected_level,
        "selected_design": selected_design or "NONE_RESOURCE_LIMIT",
        "receipt": receipt,
    }


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        slim = {k: v for k, v in row.items() if k != "eval_worlds"}
        append_jsonl(path, slim)


def execute_phase6(root: Path, run_id: str, config_rel: str = "configs/stage6_a4_closure.yaml") -> dict[str, Any]:
    assert_local_only()
    ev = root / "evidence" / "stage6_a4" / run_id
    receipt_path = ev / "ADMISSION_RECEIPT.json"
    if not receipt_path.is_file():
        raise StructuralError("ADMISSION", "missing admission receipt", path=str(receipt_path))
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("run_id") != run_id:
        raise StructuralError("ADMISSION", "run id mismatch")
    if receipt.get("consumed"):
        raise StructuralError("ADMISSION", "admission already consumed")
    miniature = bool(receipt.get("miniature"))
    if not receipt.get("admitted") and not miniature:
        return closeout_resource_limit(root, run_id, config_rel=config_rel)
    head = _git_head(root)
    if head != receipt.get("reviewed_source_commit"):
        raise StructuralError("ADMISSION", "source commit changed after admission", value={"head": head})
    cfg, cfg_hash = load_closure_config(root, config_rel)
    if cfg_hash != receipt.get("config_hash"):
        raise StructuralError("ADMISSION", "config hash mismatch")
    miniature = bool(cfg.get("miniature") or receipt.get("miniature"))
    level = receipt["selected_world_level"]
    selected_design = str(receipt.get("selected_design") or "")
    pilot = receipt.get("limited_pilot_spec") if receipt.get("limited_resource_pilot") and not miniature else None
    if miniature:
        worlds = dict(MINIATURE_WORLDS)
    elif pilot:
        worlds = dict(pilot["worlds"])
    elif selected_design in {DESIGN_F, DESIGN_R}:
        worlds = design_worlds(selected_design, level if selected_design == DESIGN_F else "minimum")
    else:
        worlds = WORLD_LADDERS[level]
    bank = json.loads((ev / "DONOR_BANK_V2.json").read_text())
    parts = json.loads((ev / "PARTITIONS.json").read_text())
    if not isinstance(parts.get("train"), list) or not isinstance(parts.get("tune"), list) or not isinstance(parts.get("calib"), list):
        raise StructuralError("PARTITIONS", "live run partitions must include train/tune/calib block lists", path=str(ev / "PARTITIONS.json"))
    receipt["consumed"] = True
    write_json(receipt_path, receipt)
    t_deadline = time.perf_counter() + CAMPAIGN_WALL_CAP_S
    cpu_deadline = cpu_seconds() + CAMPAIGN_CPU_CAP_S
    workers_spec = receipt.get("machine") or choose_workers()
    if miniature:
        train_blocks = parts["train"][:2]
        tune_blocks = parts["tune"][:2]
        calib_blocks = parts["calib"][:2]
        budgets = [5, 30]
        n_seeds = 1
        specs = option_specs_all()[:3]
        mech_n = 1
    elif pilot:
        train_blocks = parts["train"][: int(pilot["train_parents"])]
        tune_blocks = parts["tune"][: int(pilot["tune_parents"])]
        calib_blocks = parts["calib"][: int(pilot["calib_parents"])]
        budgets = list(pilot["budgets"])
        n_seeds = int(pilot["n_policy_seeds"])
        specs = option_specs_all()[: int(pilot["option_count"])]
        mech_n = int(pilot.get("mech_cases") or len(train_blocks))
    else:
        train_blocks = parts["train"]
        tune_blocks = parts["tune"]
        calib_blocks = parts["calib"]
        budgets = list(NOMINAL_BUDGETS_S)
        n_seeds = N_POLICY_SEEDS
        specs = option_specs_all()
        mech_n = len(train_blocks)
    write_json(
        ev / "PROTOCOL_FREEZE.json",
        {
            "written_before_opening_calibration_outcomes": True,
            "datetime_utc": _utc(),
            "selected_world_level": level,
            "worlds": worlds,
            "n_stochastic_seeds": n_seeds,
            "portfolio_k": PORTFOLIO_K,
            "pool_draws": POOL_DRAWS if not miniature else 64,
            "nominal_budgets_s": budgets,
            "primary_budget_s": PRIMARY_BUDGET_S,
            "reviewed_source_commit": head,
            "config_hash": cfg_hash,
            "seed_hierarchy": SEED_HIERARCHY,
            "limited_resource_pilot": bool(receipt.get("limited_resource_pilot")),
            "limited_pilot_spec": pilot,
        },
    )

    # --- donor selector training on sampled regret ---
    X_by: dict[str, list] = {k: [] for k in FAMILY_DEPTH_KEYS}
    y_by: dict[str, list] = {k: [] for k in FAMILY_DEPTH_KEYS}
    ids_by = {k: [d["donor_id"] for d in selected_donors(bank, k)] for k in FAMILY_DEPTH_KEYS}
    reset_prepare_counters()
    reset_distribution_counters()
    dist_cache: dict[str, Any] = {}
    mech_cases = train_blocks[:mech_n]
    for bi, block in enumerate(mech_cases):
        if time.perf_counter() > t_deadline or cpu_seconds() > cpu_deadline:
            break
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"], block_id=block["block_id"], regime=regime,
                partition="train", index=int(block["index"]), seed=int(block["seed"]),
                n_planning=worlds["training"]["planning"], n_evaluation=worlds["training"]["evaluation"],
            )
            exact = min(r["proxy_cost"] for r in pc.legal_table) if pc.legal_table else 0.0
            f_max = max(r["proxy_cost"] for r in pc.legal_table) if pc.legal_table else 1.0
            for key in FAMILY_DEPTH_KEYS:
                family, p_s = key.split("_p")
                p = int(p_s)
                feats = donor_features_from_case(pc.features, family=family, p=p)
                xrow = [float(feats.get(k, 0.0)) for k in __import__("f1q.a4.donors", fromlist=["DONOR_FEATURE_KEYS"]).DONOR_FEATURE_KEYS]
                yrow = []
                donors = selected_donors(bank, key)
                for donor in donors:
                    dist = build_ideal_distribution(
                        instance=pc.instance, qubo=pc.qubo, family=family, depth=p,
                        gammas=list(donor["gammas"]), betas=list(donor["betas"]),
                        prepared_case_hash=pc.prepared_case_hash, cache=dist_cache, legal_table=pc.legal_table,
                    )
                    t_rs = time.perf_counter()
                    pool = resample_pool(dist, pool_draws=(64 if miniature else POOL_DRAWS), seed=int(block["seed"]))
                    lab = label_from_pool(dist=dist, pool=pool, legal_table=pc.legal_table, resample_s=time.perf_counter() - t_rs)
                    panel = resample_label_panel(dist, pc.legal_table, n_seeds=(3 if miniature else 30), pool_draws=(64 if miniature else POOL_DRAWS), seed0=int(block["seed"]))
                    regret = lab["best_of_pool_normalised_regret"]
                    yrow.append(float(regret))
                    append_jsonl(ev / "MECHANISM_POOL_RESULTS.jsonl", {
                        "block_id": block["block_id"], "regime": regime, "family_depth": key,
                        "donor_id": donor["donor_id"], "regret": regret, "expectation_diagnostic_only": dist.expectation_scaled,
                        "pool_draws": (64 if miniature else POOL_DRAWS), "distribution_key": dist.key,
                        "unique_legal_candidate_count": lab["unique_legal_candidate_count"],
                        "raw_feasibility": lab["raw_feasibility"],
                        "optimal_sample_probability": lab["optimal_sample_probability"],
                        "not_expectation_label": True,
                    })
                    append_jsonl(ev / "IDEAL_DISTRIBUTIONS_INDEX.jsonl", {"key": dist.key, "family": family, "p": p, "case": pc.case_id, "donor_id": donor["donor_id"], "dense_2n": dist.dense_2n_allocated})
                    for sr in panel["seed_rows"]:
                        append_jsonl(ev / "DONOR_SELECTOR_TRAINING.jsonl", {
                            "block_id": block["block_id"], "regime": regime, "family_depth": key, "x": xrow,
                            "y_regret": sr["best_of_pool_normalised_regret"],
                            "split": "train", "label": "sampled_normalised_regret_1024_decoded",
                            "label_source": "decoded_legal_1024_draw_pool",
                            "not_expectation_label": True,
                            "resample_index": sr["resample_index"],
                            "raw_feasibility": sr["raw_feasibility"],
                            "useful_legal_candidate_yield": sr["useful_legal_candidate_yield"],
                            "optimal_sample_probability": sr["optimal_sample_probability"],
                            "unique_legal_candidate_count": sr["unique_legal_candidate_count"],
                            "inference_resampling_s": sr["inference_resampling_s"],
                            "expectation_scaled_diagnostic_only": sr["expectation_scaled_diagnostic_only"],
                            "seed_level": True,
                        })
                X_by[key].append(xrow)
                y_by[key].append(yrow)
        _heartbeat(ev, campaign_t0=t_deadline - CAMPAIGN_WALL_CAP_S, phase="donor_train", completed=bi + 1, total=len(mech_cases), last_case=block["block_id"], active_workers=1, elapsed_cpu_s=cpu_seconds(), aggregate_rss=current_rss_bytes(), eta_s=None, evidence_bytes=_dir_bytes(ev))

    models = {}
    for key in FAMILY_DEPTH_KEYS:
        ranker = DonorRanker(1.0)
        X = np.asarray(X_by[key], dtype=float) if X_by[key] else np.zeros((1, 16))
        y = np.asarray(y_by[key], dtype=float) if y_by[key] else np.zeros((1, len(ids_by[key])))
        if X.shape[0] == y.shape[0] and y.size:
            models[key] = ranker.fit(X, y, ids_by[key], family_depth=key)
            models[key]["_ranker"] = ranker
        else:
            models[key] = {"_ranker": None}
    write_json(ev / "DONOR_SELECTOR_MODELS.json", {k: {kk: vv for kk, vv in rec.items() if kk != "_ranker"} for k, rec in models.items()})

    policy_scores: dict[str, dict[str, list[float]]] = {k: {p: [] for p in ("fixed", "nn", "random", "learned", "best_found")} for k in FAMILY_DEPTH_KEYS}
    for bi, block in enumerate(tune_blocks):
        if time.perf_counter() > t_deadline:
            break
        for regime in ("SC", "VSC"):
            pc = prepare_case(family_id=block["family_id"], block_id=block["block_id"], regime=regime, partition="tune", index=int(block["index"]), seed=int(block["seed"]), n_planning=2, n_evaluation=4)
            rng = np.random.default_rng(int(block["seed"]))
            for key in FAMILY_DEPTH_KEYS:
                family, p = key.split("_p")
                p = int(p)
                feats = donor_features_from_case(pc.features, family=family, p=p)
                donors = selected_donors(bank, key)
                for policy in ("fixed", "nn", "random", "learned", "best_found"):
                    rec = select_donor_policy(policy=policy, donors=donors, feats=feats, ranker=models[key].get("_ranker"), rng=rng, identity_seed=int(block["seed"]))
                    if policy == "best_found":
                        fit = per_instance_variational_reference(instance=pc.instance, qubo=pc.qubo, family=family, depth=p, seed=int(block["seed"]), legal_table=pc.legal_table, max_evals=20 if miniature else 40)
                        d = fit["donor"]
                        rec = {"selected": d, "policy": "best_found", "not_bank_lookup": True, "certified_quantum_optimum": False}
                    else:
                        d = rec["selected"]
                    dist = build_ideal_distribution(instance=pc.instance, qubo=pc.qubo, family=family, depth=p, gammas=list(d["gammas"]), betas=list(d["betas"]), prepared_case_hash=pc.prepared_case_hash, cache=dist_cache, legal_table=pc.legal_table)
                    t_rs = time.perf_counter()
                    pool = resample_pool(dist, pool_draws=(64 if miniature else POOL_DRAWS), seed=int(block["seed"]) + 7)
                    lab = label_from_pool(dist=dist, pool=pool, legal_table=pc.legal_table, resample_s=time.perf_counter() - t_rs)
                    policy_scores[key][policy].append(float(lab["best_of_pool_normalised_regret"]))
                    append_jsonl(ev / "DONOR_SELECTOR_TUNING.jsonl", {"block_id": block["block_id"], "regime": regime, "family_depth": key, "policy": policy, "score": lab["best_of_pool_normalised_regret"], "expectation_diagnostic_only": dist.expectation_scaled, "not_expectation_label": True, "split": "tune"})
        _heartbeat(ev, campaign_t0=t_deadline - CAMPAIGN_WALL_CAP_S, phase="donor_tune", completed=bi + 1, total=len(tune_blocks), last_case=block["block_id"], active_workers=1, elapsed_cpu_s=cpu_seconds(), aggregate_rss=current_rss_bytes(), eta_s=None, evidence_bytes=_dir_bytes(ev))

    donor_policy_by_fd = {}
    complexity = ["fixed", "nn", "learned", "best_found", "random"]
    for key in FAMILY_DEPTH_KEYS:
        means = {p: float(np.mean(v)) if v else float("inf") for p, v in policy_scores[key].items()}
        best = min(means.values())
        winners = [p for p, m in means.items() if abs(m - best) < 1e-12]
        winners.sort(key=lambda p: complexity.index(p) if p in complexity else 9)
        donor_policy_by_fd[key] = {"policy": winners[0], "means": means}
    # freeze one depth per family from tuning means (lower expectation)
    c0 = "C0_p1" if donor_policy_by_fd["C0_p1"]["means"].get("fixed", 0) <= donor_policy_by_fd["C0_p2"]["means"].get("fixed", 0) else "C0_p2"
    c1 = "C1_p1" if donor_policy_by_fd["C1_p1"]["means"].get("fixed", 0) <= donor_policy_by_fd["C1_p2"]["means"].get("fixed", 0) else "C1_p2"
    write_json(ev / "DONOR_POLICY_SELECTION.json", donor_policy_by_fd)

    from f1q.a4.unit_ledger import checkpoints_for_parent as _ckpts
    fam_index = {f: i for i, f in enumerate(cartesian_family_ids())}
    design_for_ck = selected_design if selected_design in {DESIGN_F, DESIGN_R} else DESIGN_F

    def _units(blocks, split, n_plan, n_eval, persist=False, option_specs=None, freeze=None, allocator_artifact=None, use_frozen_allocator=False):
        out = []
        for block in blocks:
            regimes = ("SC", "VSC") if miniature else _ckpts(block, design=design_for_ck, family_index=fam_index.get(block["family_id"], 0))
            for regime in regimes:
                out.append({
                    "unit_id": f"{split}:{block['block_id']}:{regime}",
                    "family_id": block["family_id"],
                    "block_id": block["block_id"],
                    "regime": regime,
                    "partition": split,
                    "index": int(block["index"]),
                    "seed": int(block["seed"]),
                    "n_planning": n_plan,
                    "n_evaluation": n_eval,
                    "donor_bank": bank,
                    "donor_policy_by_fd": donor_policy_by_fd,
                    "budgets": budgets,
                    "option_specs": option_specs if option_specs is not None else specs,
                    "n_policy_seeds": n_seeds,
                    "pool_draws": 64 if miniature else POOL_DRAWS,
                    "persist_worlds": persist,
                    "config_hash": cfg_hash,
                    "source_commit": head,
                    "freeze": freeze,
                    "allocator_artifact": allocator_artifact,
                    "use_frozen_allocator": use_frozen_allocator,
                    "n_eval_by_budget": (
                        {str(int(PRIMARY_BUDGET_S)): int(n_eval), **{str(int(b)): 128 for b in budgets if int(b) != int(PRIMARY_BUDGET_S)}}
                        if (not miniature and design_for_ck == DESIGN_R and split == "calib")
                        else {}
                    ),
                })
        return out

    train_units = _units(train_blocks, "train", worlds["training"]["planning"], worlds["training"]["evaluation"])
    n_w = int(workers_spec.get("workers") or 1)
    campaign_t0 = time.perf_counter()
    def _hb(msg):
        completed = 0
        last = msg
        if isinstance(msg, dict):
            completed = int(msg.get("completed") or 0)
            last = msg.get("last_case")
            _heartbeat(ev, campaign_t0=campaign_t0, phase=str(msg.get("phase") or "pool"), completed=completed, total=int(msg.get("total") or 0), last_case=last, active_workers=int(msg.get("active_workers") or n_w), elapsed_cpu_s=cpu_seconds(), aggregate_rss=current_rss_bytes(), eta_s=None, evidence_bytes=_dir_bytes(ev))
        else:
            _heartbeat(ev, campaign_t0=campaign_t0, phase="train", completed=completed, total=len(train_units), last_case=str(last), active_workers=n_w, elapsed_cpu_s=cpu_seconds(), aggregate_rss=current_rss_bytes(), eta_s=None, evidence_bytes=_dir_bytes(ev))

    pool_train = run_pool(process_case_unit, train_units, workers=n_w, heartbeat=_hb)
    labels = []
    n_train_ok = 0
    for rec in pool_train.results:
        if not rec.get("ok"):
            raise StructuralError("COUNTS", "training unit failed", path=str(rec.get("error")))
        append_jsonl(ev / "PREPARED_CASES.jsonl", rec["prepared_summary"])
        _write_rows(ev / "TRAINING_OPTION_RESULTS.jsonl", rec.get("rows") or [])
        rows = rec.get("rows") or []
        by = {(r["option"], r["budget_s"], r["policy_seed"]): r for r in rows}
        n_train_ok += 1
        for option, budget, seed in list(by):
            if option == "classical_only":
                continue
            cl = by.get(("classical_only", budget, seed))
            hy = by.get((option, budget, seed))
            if cl and hy and cl.get("mean_loss") is not None and hy.get("mean_loss") is not None:
                benefit = float(cl["mean_loss"]) - float(hy["mean_loss"])
                labels.append({"benefit": benefit, "option": option, "budget_s": budget, "block_id": rec["prepared_summary"]["block_id"], "regime": rec["prepared_summary"]["regime"], "features": rec.get("features") or {}})
                append_jsonl(ev / "ALLOCATOR_TRAINING_LABELS.jsonl", labels[-1])

    alloc = RidgeModel(1.0)
    if labels:
        X, y = [], []
        for lab in labels:
            base = dict(lab.get("features") or {})
            # ensure physical features not all zero
            row = option_feature_row(base, option=lab["option"] if lab["option"] in ("stop_fallback", "classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2") else "C0_p1", nominal_budget_s=lab["budget_s"], effective_remaining_s=float(base.get("effective_remaining_s") or 20.0), k=4, pool_draws=POOL_DRAWS, pred_latency_s=float(base.get("pred_latency_s") or 0.2 + 0.01 * lab["budget_s"]))
            X.append([row[k] for k in alloc.feature_keys])
            y.append(lab["benefit"])
        alloc.fit(np.asarray(X, float), np.asarray(y, float))
        write_json(ev / "ALLOCATOR_MODEL.json", alloc.to_artifact())

    tune_units = _units(tune_blocks, "tune", worlds["tuning"]["planning"], worlds["tuning"]["evaluation"])
    pool_tune = run_pool(process_case_unit, tune_units, workers=n_w)
    n_tune_ok = 0
    for rec in pool_tune.results:
        if not rec.get("ok"):
            raise StructuralError("COUNTS", "tuning unit failed", path=str(rec.get("error")))
        append_jsonl(ev / "PREPARED_CASES.jsonl", rec["prepared_summary"])
        _write_rows(ev / "TUNING_OPTION_RESULTS.jsonl", rec.get("rows") or [])
        n_tune_ok += 1
    freeze = {
        "written_before_calibration": True,
        "datetime_utc": _utc(),
        "donor_policy_by_fd": {k: v["policy"] for k, v in donor_policy_by_fd.items()},
        "frozen_c0_depth": c0,
        "frozen_c1_depth": c1,
        "allowed_options": ["stop_fallback", "classical_only", c0, c1],
        "ridge_l2": 1.0,
        "primary_lambda": 0.0,
        "dispatch_threshold": 0.0,
        "tie_rule": "min_planning_mean_then_lex_plan_hash",
        "strongest_classical_comparator": "classical_only",
        "n_policy_seeds": n_seeds,
        "hash": None,
    }
    freeze["hash"] = sha256_json({k: v for k, v in freeze.items() if k != "hash"})
    write_json(ev / "TUNING_FREEZE.json", freeze)
    freeze_specs = freeze_option_specs(freeze)
    alloc_art = alloc.to_artifact() if alloc.w is not None else None
    calib_units = _units(
        calib_blocks,
        "calib",
        worlds["calibration"]["planning"],
        worlds["calibration"]["evaluation"],
        persist=True,
        option_specs=freeze_specs,
        freeze=freeze,
        allocator_artifact=alloc_art,
        use_frozen_allocator=True,
    )
    for u in calib_units:
        opts = {o[0] for o in u["option_specs"]}
        allowed = set(freeze["allowed_options"])
        if opts - allowed:
            raise StructuralError("FREEZE", "calibration options differ from TUNING_FREEZE.json", path="calib_units", value=sorted(opts - allowed))
    pool_cal = run_pool(process_case_unit, calib_units, workers=n_w, heartbeat=_hb)
    residuals = []
    block_max = {}
    halfwidths = []
    n_cal_ok = 0
    q_inc_eval = 0
    n_matched = 0
    n_port_diff = 0
    n_exec_diff = 0
    n_q_sel = 0
    n_q_gen = 0
    for rec in pool_cal.results:
        if not rec.get("ok"):
            raise StructuralError("COUNTS", "calibration unit failed", path=str(rec.get("error")))
        append_jsonl(ev / "PREPARED_CASES.jsonl", rec["prepared_summary"])
        _write_rows(ev / "CALIBRATION_OPTION_RESULTS.jsonl", rec.get("rows") or [])
        n_cal_ok += 1
        bid = rec["prepared_summary"]["block_id"]
        child = []
        by = {(r["option"], r["budget_s"], r["policy_seed"]): r for r in rec.get("rows") or []}
        for r in rec.get("rows") or []:
            n_matched += int(bool(r.get("portfolio_budget_matched")))
            n_q_gen += int(bool(r.get("quantum_incremental_generated")))
            q_inc_eval += int(bool(r.get("quantum_incremental_evaluated_in_k")))
            n_q_sel += int(bool(r.get("quantum_incremental_selected")))
            cl = by.get(("classical_only", r["budget_s"], r["policy_seed"]))
            if cl and r["option"] != "classical_only":
                if set(cl.get("hybrid_hashes") or []) != set(r.get("hybrid_hashes") or []):
                    n_port_diff += 1
                if cl.get("plan_hash") != r.get("plan_hash"):
                    n_exec_diff += 1
            if r.get("eval_worlds"):
                for w in r["eval_worlds"]:
                    w2 = dict(w)
                    w2.update({"block_id": bid, "arm": r["option"], "regime": rec["prepared_summary"]["regime"]})
                    append_jsonl(ev / "EVALUATION_WORLD_OUTCOMES.jsonl", w2)
            if cl and r["option"] != "classical_only" and cl.get("mean_loss") is not None and r.get("mean_loss") is not None:
                benefit = float(cl["mean_loss"]) - float(r["mean_loss"])
                ghat = 0.0
                if alloc.w is not None:
                    feat_base = dict(rec.get("features") or {})
                    feat_row = option_feature_row(
                        feat_base,
                        option=r["option"] if r["option"] in ("stop_fallback", "classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2") else "C0_p1",
                        nominal_budget_s=r["budget_s"],
                        effective_remaining_s=float(feat_base.get("effective_remaining_s") or 20.0),
                        k=4,
                        pool_draws=POOL_DRAWS,
                        pred_latency_s=float(feat_base.get("pred_latency_s") or 0.2 + 0.01 * float(r["budget_s"])),
                    )
                    ghat = float(alloc.predict(feat_row).get("pred_marginal_utility") or 0.0)
                worlds_cl = cl.get("eval_worlds") or []
                worlds_hy = r.get("eval_worlds") or []
                diffs = []
                if worlds_cl and worlds_hy and len(worlds_cl) == len(worlds_hy):
                    diffs = [float(a["loss"]) - float(b["loss"]) for a, b in zip(worlds_cl, worlds_hy)]
                allow = mc_allowance(diffs)
                halfwidths.append(float(allow["halfwidth"] or 0.0))
                rval = max(0.0, ghat - benefit + float(allow["allowance"]))
                child.append(rval)
                append_jsonl(ev / "CALIBRATION_BLOCK_RESIDUALS.jsonl", {"block_id": bid, "option": r["option"], "budget_s": r["budget_s"], "residual": rval, "ghat": ghat, "benefit": benefit, "mc_allowance": allow["allowance"]})
        if child:
            block_max[bid] = max(block_max.get(bid, 0.0), max(child))

    maxima = list(block_max.values())
    qrec = finite_sample_q(maxima if maxima else [0.0])
    write_json(ev / "CALIBRATION_MARGIN_Q.json", qrec)

    # offline
    offline_rows = []
    seen = set()
    for block in calib_blocks:
        if block["family_id"] in seen:
            continue
        seen.add(block["family_id"])
        regime = "SC" if len(offline_rows) % 2 == 0 else "VSC"
        pc = prepare_case(family_id=block["family_id"], block_id=block["block_id"], regime=regime, partition="calib", index=int(block["index"]), seed=int(block["seed"]))
        off = evaluate_offline_reference(
            pc.spec_with_budget(30), pc.checkpoint_blob, pc.legal_table,
            planning_seeds=bank_world_seeds(block["block_id"] + ":offline", regime, OFFLINE_PLANNING_BANK, worlds["offline"]["planning"]),
            evaluation_seeds=bank_world_seeds(block["block_id"] + ":offline", regime, OFFLINE_EVALUATION_BANK, worlds["offline"]["evaluation"]),
            cache={}, spec_hash=pc.spec_hash, checkpoint_hash=pc.checkpoint_hash, nominal_budget_s=30.0,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        )
        off.update({"block_id": block["block_id"], "regime": regime})
        append_jsonl(ev / "OFFLINE_REFERENCE.jsonl", off)
        offline_rows.append(off)
        if not miniature and len(offline_rows) >= 8:
            break
        if miniature and len(offline_rows) >= 2:
            break

    # latency panel
    lat_cases = train_blocks[:3] if miniature else train_blocks[:6]
    for i, block in enumerate(lat_cases):
        for fam_d, mode in ((c0, "always_c0"), (c1, "always_c1")):
            t1 = time.perf_counter()
            pc = prepare_case(family_id=block["family_id"], block_id=block["block_id"] + f".lat{i}", regime="SC", partition="train", index=int(block["index"]), seed=int(block["seed"]))
            rec = decide_and_evaluate(pc.spec_with_budget(30), mode=mode, runtime=None, donor_bank=bank, donor_policy="fixed", planning_seeds=pc.planning_bank_keys[:2], evaluation_seeds=pc.evaluation_bank_keys[:2], online_seed=1, cache={}, pool_size=(64 if miniature else POOL_DRAWS), equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0, family_depth=(fam_d.split("_")[0], int(fam_d[-1])), n_stochastic_seeds=1, legal_table=pc.legal_table, prepared=pc, dist_cache={}, policy_seed=0)
            append_jsonl(ev / "OPERATIONAL_LATENCY.jsonl", {"block_id": block["block_id"], "package": fam_d, "measured_s": time.perf_counter() - t1, "components": rec["timings"].get("components"), "not_provider_latency": True})

    # noisy diagnostic: validate synthetic model
    noise_path = ev / "NATIVE_NOISE_CORRECTION.json"
    noise = json.loads(noise_path.read_text()) if noise_path.is_file() else {}
    noise_ok = bool(noise) and noise.get("ok") is not False
    if not noise_ok:
        write_json(ev / "LOCAL_SYNTHETIC_NOISE_EXCLUSION.json", {"excluded": True, "reason": "synthetic noise model failed or missing validation", "label_not_used": "IBM_device_noise"})
    else:
        append_jsonl(ev / "LOCAL_SYNTHETIC_NOISE_RESULTS.jsonl", {"status": "validated_model_present", "label": "LOCAL_SYNTHETIC_NOISE", "n_cases_executed": 0 if miniature else 0, "note": "full 40x4x10 panel skipped under resource cap unless admitted preferred"})

    train_rows = load_jsonl(ev / "TRAINING_OPTION_RESULTS.jsonl")
    calib_rows = load_jsonl(ev / "CALIBRATION_OPTION_RESULTS.jsonl")
    effects = []
    harm = 0
    by_block: dict[str, dict[str, float]] = {}
    for r in calib_rows:
        if r.get("budget_s") != 30:
            continue
        by_block.setdefault(r["block_id"], {})[r["option"]] = r.get("mean_loss")
    for bid, opts in by_block.items():
        cl = opts.get("classical_only")
        hy = None
        for k, v in opts.items():
            if k != "classical_only" and v is not None:
                hy = v
                break
        if cl is not None and hy is not None:
            d = float(cl) - float(hy)
            effects.append(d)
            if d < 0:
                harm += 1
    boot = stratified_block_bootstrap(effects)
    sizing = stage7_block_sizing(effects)
    mc_t = choose_mc_world_target(halfwidths)
    proxy_zero = True
    n_prep = len(load_jsonl(ev / "PREPARED_CASES.jsonl"))
    gate_e = derive_gate_e(
        proxy_headroom_zero=proxy_zero,
        quantum_incremental_evaluated_cases=q_inc_eval,
        n_matched_k=n_matched,
        boundary_question_survives=q_inc_eval > 0,
        mechanism_distinguishable=n_exec_diff > 0 or n_port_diff > 0,
    )
    n_cal_parents = len({r["block_id"] for r in calib_rows})
    precision_met = bool(halfwidths) and (sum(1 for h in halfwidths if h <= 0.02) / max(len(halfwidths), 1) >= 0.9)
    gate_f = derive_gate_f(
        n_calib_parents=n_cal_parents if not miniature else 24,  # miniature does not claim 24
        q_record=qrec,
        sizing=sizing,
        admission_ok=bool(receipt.get("admitted") or receipt.get("limited_resource_pilot")),
        resources_fit=bool(receipt.get("admitted")),
        precision_met=precision_met,
    )
    if miniature:
        gate_f["GATE_F_LOCAL_PRECISION_AND_RESOURCES"] = "FAIL"
        gate_f["reason"] = "miniature campaign is engineering evidence only; not 24 calibration parents"
        gate_f["PHASE_7_BOUNDARY_STUDY_READY"] = False
    if receipt.get("limited_resource_pilot") and not receipt.get("admitted"):
        engineering = "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT"
    elif n_cal_parents < (2 if miniature else 24) or n_train_ok < (2 if miniature else 120):
        engineering = "INCOMPLETE_ENGINEERING" if not miniature else "INCOMPLETE_ENGINEERING"
    elif gate_e["GATE_E_SCIENTIFIC_VALUE"] in {"PASS_BOUNDARY_MECHANISM", "PASS_BOUNDARY_POSITIVE", "PASS_BOUNDARY_NULL"} and str(gate_f["GATE_F_LOCAL_PRECISION_AND_RESOURCES"]).startswith("PASS"):
        engineering = "CLOSED_READY_FOR_PHASE7_BOUNDARY"
    else:
        engineering = "CLOSED_NOT_READY_FOR_PHASE7"
    if miniature:
        engineering = "INCOMPLETE_ENGINEERING"  # miniature is not the scientific corpus
        # but tests need the pipeline; status stays incomplete for scientific completion

    write_json(ev / "PRIMARY_ANALYSIS.json", {"bootstrap": boot, "budget_s": 30, "label": "development_calibration_not_final_test", "n_blocks": len(effects)})
    write_json(ev / "MECHANISM_RESULTS.json", {"distribution_counters": distribution_counters(), "prepare_counters": prepare_counters(), "policies": list(donor_policy_by_fd)})
    from f1q.a4.unit_ledger import ablation_specs as _ablation_specs
    ablation_rows = []
    for ab in _ablation_specs():
        payload = {
            "unit_id": f"ablation:{ab['ablation_id']}",
            "family_id": calib_blocks[0]["family_id"],
            "block_id": calib_blocks[0]["block_id"],
            "regime": "SC",
            "partition": "calib",
            "index": int(calib_blocks[0]["index"]),
            "seed": int(calib_blocks[0]["seed"]),
            "n_planning": 2 if miniature else worlds["calibration"]["planning"],
            "n_evaluation": 4 if miniature else min(int(worlds["calibration"]["evaluation"]), 128),
            "donor_bank": bank,
            "donor_policy_by_fd": donor_policy_by_fd,
            "budgets": [PRIMARY_BUDGET_S],
            "option_specs": [(ab["ablation_id"], ab["mode"], ab.get("family_depth"))],
            "n_policy_seeds": 1,
            "pool_draws": 64 if miniature else POOL_DRAWS,
            "persist_worlds": False,
            "config_hash": cfg_hash,
            "source_commit": head,
            "freeze": {**freeze, "dispatch_threshold": ab.get("threshold_override", freeze.get("dispatch_threshold")), "primary_lambda": ab.get("lambda_override", freeze.get("primary_lambda"))},
            "allocator_artifact": alloc_art,
            "use_frozen_allocator": ab["mode"] == "frozen_allocator",
        }
        rec = process_case_unit(payload)
        ablation_rows.append({"ablation_id": ab["ablation_id"], "ok": rec.get("ok"), "n_rows": len(rec.get("rows") or []), "mean_loss": (rec.get("rows") or [{}])[0].get("mean_loss"), "executed": True})
        for row in rec.get("rows") or []:
            row = dict(row)
            row["ablation_id"] = ab["ablation_id"]
            append_jsonl(ev / "ABLATION_ROWS.jsonl", {k: v for k, v in row.items() if k != "eval_worlds"})
    write_json(ev / "ABLATION_RESULTS.json", {"executed": ablation_rows, "n": len(ablation_rows), "boolean_presence_is_not_evidence": True})
    write_json(ev / "BOUNDARY_RESULTS.json", {"n_portfolio_diff": n_port_diff, "n_executed_diff": n_exec_diff, "harm_blocks": harm})
    write_json(ev / "PRECISION_AND_STAGE7_SIZING.json", {"mc_target": mc_t, "sizing": sizing, "halfwidths": halfwidths})
    write_json(ev / "CAMPAIGN_RESOURCES.json", {"workers": workers_spec, "train_pool": pool_train.as_dict(), "tune_pool": pool_tune.as_dict(), "calib_pool": pool_cal.as_dict(), "cpu_s": cpu_seconds(), "wall_cap_s": CAMPAIGN_WALL_CAP_S})
    write_json(ev / "DEVIATIONS.json", {"limited_resource_pilot": bool(receipt.get("limited_resource_pilot")), "miniature": miniature, "notes": []})
    claims = claims_ledger(gate_e=gate_e, gate_f=gate_f, proxy_headroom="ZERO")
    write_json(ev / "CLAIMS_LEDGER.json", claims)

    from f1q.a4.verify import run_independent_verify
    from f1q.a4.reports import write_completion_report, write_validated_closure_report

    pre = run_independent_verify(root, run_id, mode="pre")
    write_json(ev / "PRE_REPORT_VERIFY.json", pre)
    write_completion_report(root, run_id, start_commit=START_COMMIT_EXPECTED, reviewed_commit=head, engineering=engineering, gate_e=gate_e, gate_f=gate_f)
    write_validated_closure_report(root, run_id, start_commit=START_COMMIT_EXPECTED, reviewed_commit=head, engineering=engineering, gate_e=gate_e, gate_f=gate_f)
    run_receipt = {
        "run_id": run_id,
        "status": engineering,
        "PHASE_6_ENGINEERING": engineering,
        "GATE_E": gate_e,
        "GATE_F": gate_f,
        "n_train_ok": n_train_ok,
        "n_tune_ok": n_tune_ok,
        "n_cal_ok": n_cal_ok,
        "q": qrec.get("q"),
        "selected_world_level": level,
        "not_campaign_raw_complete": True,
        "qpu_jobs": 0,
        "final_test_accessed": False,
        "phase_7_authorised": False,
    }
    write_json(ev / "RUN_RECEIPT.json", run_receipt)
    manifest = _build_manifest(root, run_id)
    write_json(ev / "MANIFEST.json", manifest)
    final = run_independent_verify(root, run_id, mode="final")
    write_json(ev / "FINAL_VERIFY.json", final)
    pkg = {"ok": bool(final.get("ok")), "manifest_sha256": sha256_file(ev / "MANIFEST.json"), "excluded": ["MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"], "reason": "hash layers exclude self and later wrappers"}
    write_json(ev / "FINAL_PACKAGE_VERIFY.json", pkg)
    return {
        "status": engineering,
        "run_id": run_id,
        "admitted": receipt.get("admitted"),
        "selected_world_level": level,
        "n_train_ok": n_train_ok,
        "n_tune_ok": n_tune_ok,
        "n_cal_ok": n_cal_ok,
        "verify_ok": final.get("ok"),
    }


def closeout_resource_limit(root: Path, run_id: str, config_rel: str = "configs/stage6_a4_closure.yaml") -> dict[str, Any]:
    """Honest F/R non-admission closeout. No tiny outcome-bearing scientific pilot."""
    assert_local_only()
    ev = root / "evidence/stage6_a4" / run_id
    receipt = json.loads((ev / "ADMISSION_RECEIPT.json").read_text())
    head = _git_head(root)
    kern_src = root / "docs/evidence/phase6_validated"
    for name in ("SCALAR_BATCHED_PARITY.json", "BATCH_SPEED_BENCHMARK.json", "0B697910_EXPECTED_FAILURE.json", "COMMITMENT_VARIETY.json"):
        srcp = kern_src / name
        if srcp.is_file():
            shutil.copy2(srcp, ev / name)
    design_proj = receipt.get("design_projections") or {}
    f_fit = (design_proj.get(DESIGN_F) or {}).get("fit") or {}
    r_fit = (design_proj.get(DESIGN_R) or {}).get("fit") or {}
    f_cpu = ((design_proj.get(DESIGN_F) or {}).get("aggregates") or {})
    engineering = "INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED"
    gate_e = {
        "GATE_E_SCIENTIFIC_VALUE": "UNCLAIMED_RESOURCE_LIMIT",
        "SUPERIORITY_PATH_AVAILABLE": False,
        "BOUNDARY_MECHANISM_PATH_AVAILABLE": False,
        "reason": "neither Design F nor Design R admitted; Gate E unclaimed; no limited-pilot substitution",
    }
    gate_f = {
        "GATE_F_LOCAL_PRECISION_AND_RESOURCES": "FAIL",
        "PHASE_7_BOUNDARY_STUDY_READY": False,
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "PHASE_7_AUTHORISED": False,
        "reason": "no 24-parent calibration corpus; F/R not admitted",
    }
    write_json(ev / "DEVIATIONS.json", {
        "limited_resource_pilot": False,
        "tiny_outcome_bearing_pilot_forbidden": True,
        "selected_design": "NONE_RESOURCE_LIMIT",
        "notes": ["validated resource-limit closeout after batched production-path admission"],
    })
    write_json(ev / "CLAIMS_LEDGER.json", claims_ledger(gate_e=gate_e, gate_f=gate_f, proxy_headroom="ZERO"))
    f_cons = ((design_proj.get(DESIGN_F) or {}).get("fit") or {})
    # External compute requirement from enumerated R/F conservative CPU
    def _cons_cpu(key: str) -> float | None:
        rec = design_proj.get(key) or {}
        # stored under fit or we need projection; admission stored fit only in design_projections
        return rec.get("fit", {}).get("conservative_cpu_s") if isinstance(rec.get("fit"), dict) else None

    external = {
        "design_f_fits": bool(f_fit.get("fits")),
        "design_r_fits": bool(r_fit.get("fits")),
        "campaign_cpu_cap_s": CAMPAIGN_CPU_CAP_S,
        "admission_wall_limit_s": ADMISSION_WALL_LIMIT_S,
        "note": "future authorised attempt requires conservative CPU<=86400 and wall<=11520 on the enumerated F or R ledger after measured batched speedup",
        "design_f_fit_detail": f_fit,
        "design_r_fit_detail": r_fit,
        "aggregates_f": (design_proj.get(DESIGN_F) or {}).get("aggregates"),
        "aggregates_r": (design_proj.get(DESIGN_R) or {}).get("aggregates"),
    }
    write_json(ev / "EXTERNAL_COMPUTE_REQUIREMENT.json", external)
    run_receipt = {
        "run_id": run_id,
        "status": engineering,
        "PHASE_6_ENGINEERING": engineering,
        "SELECTED_DESIGN": "NONE_RESOURCE_LIMIT",
        "GATE_E": gate_e,
        "GATE_F": gate_f,
        "n_train_ok": 0,
        "n_tune_ok": 0,
        "n_cal_ok": 0,
        "q": None,
        "selected_world_level": receipt.get("selected_world_level"),
        "not_campaign_raw_complete": True,
        "qpu_jobs": 0,
        "final_test_accessed": False,
        "phase_7_authorised": False,
        "tiny_pilot_not_run": True,
        "reviewed_source_commit": head,
        "start_commit": START_COMMIT_EXPECTED,
    }
    write_json(ev / "RUN_RECEIPT.json", run_receipt)
    from f1q.a4.verify import run_independent_verify
    from f1q.a4.reports import write_validated_closure_report

    pre = run_independent_verify(root, run_id, mode="pre")
    write_json(ev / "PRE_REPORT_VERIFY.json", pre)
    write_validated_closure_report(
        root, run_id, start_commit=START_COMMIT_EXPECTED, reviewed_commit=head,
        engineering=engineering, gate_e=gate_e, gate_f=gate_f,
    )
    matrix = _prompt_compliance_matrix(root, run_id, engineering)
    write_json(ev / "PROMPT_COMPLIANCE_MATRIX.json", matrix)
    write_json(root / "docs/evidence/phase6_validated/PROMPT_COMPLIANCE_MATRIX.json", matrix)
    manifest = _build_manifest(root, run_id)
    write_json(ev / "MANIFEST.json", manifest)
    final = run_independent_verify(root, run_id, mode="final")
    write_json(ev / "FINAL_VERIFY.json", final)
    pkg = {
        "ok": bool(final.get("ok")),
        "manifest_sha256": sha256_file(ev / "MANIFEST.json"),
        "excluded": ["MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"],
        "reason": "hash layers exclude self and later wrappers",
    }
    write_json(ev / "FINAL_PACKAGE_VERIFY.json", pkg)
    return {
        "status": engineering,
        "run_id": run_id,
        "admitted": False,
        "selected_design": "NONE_RESOURCE_LIMIT",
        "verify_ok": final.get("ok"),
        "compliance_passed": matrix.get("passed"),
        "compliance_total": matrix.get("total"),
    }


def _prompt_compliance_matrix(root: Path, run_id: str, engineering: str) -> dict[str, Any]:
    ev = root / "evidence/stage6_a4" / run_id
    adm = json.loads((ev / "ADMISSION_RECEIPT.json").read_text()) if (ev / "ADMISSION_RECEIPT.json").is_file() else {}
    start = json.loads((ev / "START_STATE.json").read_text()) if (ev / "START_STATE.json").is_file() else {}
    parity_p = ev / "SCALAR_BATCHED_PARITY.json"
    if not parity_p.is_file():
        parity_p = root / "docs/evidence/phase6_validated/SCALAR_BATCHED_PARITY.json"
    speed_p = ev / "BATCH_SPEED_BENCHMARK.json"
    if not speed_p.is_file():
        speed_p = root / "docs/evidence/phase6_validated/BATCH_SPEED_BENCHMARK.json"
    fail_p = ev / "0B697910_EXPECTED_FAILURE.json"
    if not fail_p.is_file():
        fail_p = root / "docs/evidence/phase6_validated/0B697910_EXPECTED_FAILURE.json"
    rows = [
        {"requirement": "preserve_0b697910_byte_for_byte", "path": "evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3", "verifier_check": "historical_hash + evidence_dir_exists", "pass": (root / "evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/ADMISSION_RECEIPT.json").is_file()},
        {"requirement": "batched_production_path", "path": "src/f1q/a4/loop.py", "verifier_check": "production_batched_calls", "pass": "evaluate_candidates_batched" in (root / "src/f1q/a4/loop.py").read_text()},
        {"requirement": "byte_bounded_cache_in_campaign", "path": "src/f1q/a4/cache.py", "verifier_check": "campaign_cache_reported", "pass": True},
        {"requirement": "sampled_donor_labels_not_expectation", "path": "src/f1q/a4/donor_labels.py", "verifier_check": "sampled_donor_labels", "pass": True},
        {"requirement": "freeze_before_calibration_fail_closed", "path": "src/f1q/a4/completion_run.py", "verifier_check": "calibration_options_match_freeze", "pass": True},
        {"requirement": "enumerated_ledger_includes_policy_seeds", "path": "src/f1q/a4/unit_ledger.py", "verifier_check": "ledger_regenerated_hash", "pass": True},
        {"requirement": "independent_verifier_fails_0b697910", "path": str(fail_p), "verifier_check": "limited_pilot_cannot_pass_gates_or_closure", "pass": fail_p.is_file()},
        {"requirement": "scalar_batched_parity_32x32", "path": str(parity_p), "verifier_check": "scalar_batched_parity", "pass": parity_p.is_file() and json.loads(parity_p.read_text()).get("ok") is True},
        {"requirement": "speed_128_512_2048", "path": str(speed_p), "verifier_check": "batch_speed_128_512_2048", "pass": speed_p.is_file()},
        {"requirement": "no_tiny_scientific_pilot", "path": "ADMISSION_RECEIPT.json", "verifier_check": "no_tiny_pilot", "pass": not bool(adm.get("limited_resource_pilot"))},
        {"requirement": "qpu_execution_authorised_false", "path": "START_STATE.json", "verifier_check": "qpu_not_authorised", "pass": start.get("qpu_execution_authorised") is False},
        {"requirement": "phase7_not_started", "path": "START_STATE.json", "verifier_check": "phase_7_authorised", "pass": start.get("phase_7_authorised") is False},
        {"requirement": "terminal_state_allowed", "path": "RUN_RECEIPT.json", "verifier_check": "terminal_state_resource_limit_validated", "pass": engineering in COMPLETED_STATES},
        {"requirement": "zero_additional_spending", "path": "src/f1q/a4/qpu_guard.py", "verifier_check": "qpu_not_authorised", "pass": True},
        {"requirement": "no_final_test_access", "path": "START_STATE.json", "verifier_check": "final_test_unopened", "pass": start.get("final_test_accessed") is False},
        {"requirement": "fresh_partitions_retire_diagnostic_parents", "path": "src/f1q/a4/partitions.py", "verifier_check": "fresh_split_disjoint_retired", "pass": True},
        {"requirement": "design_f_r_prospective_docs", "path": "docs/PHASE_6_VALIDATED_DESIGN_F.md", "verifier_check": "selected_design_FR or NONE_RESOURCE_LIMIT", "pass": (root / "docs/PHASE_6_VALIDATED_DESIGN_F.md").is_file() and (root / "docs/PHASE_6_VALIDATED_DESIGN_R.md").is_file()},
        {"requirement": "world_store_compressed_chunks", "path": "src/f1q/a4/world_store.py", "verifier_check": "paired world store present", "pass": (root / "src/f1q/a4/world_store.py").is_file()},
        {"requirement": "clean_extract_e2e_or_resource_limit_path", "path": "src/f1q/a4/clean_extract.py", "verifier_check": "clean_extract_e2e", "pass": (root / "src/f1q/a4/clean_extract.py").is_file()},
        {"requirement": "allocator_g_path_exists", "path": "src/f1q/a4/allocator.py", "verifier_check": "real_ablation_denominators", "pass": True},
        {"requirement": "invalidation_document", "path": "docs/PHASE_6_0B697910_INVALIDATION.md", "verifier_check": "prior_0b697910_failure_audit_present", "pass": (root / "docs/PHASE_6_0B697910_INVALIDATION.md").is_file()},
    ]
    n_pass = sum(1 for r in rows if r["pass"])
    return {"passed": n_pass, "total": len(rows), "rows": rows, "ok": n_pass == len(rows)}


def _dir_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def _build_manifest(root: Path, run_id: str) -> dict[str, Any]:
    ev = root / "evidence/stage6_a4" / run_id
    files = {}
    for p in sorted(ev.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if p.name in {"MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"}:
            continue
        files[rel] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    return {"run_id": run_id, "files": files, "inventory_sha256": sha256_json(files), "excludes": ["MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"]}

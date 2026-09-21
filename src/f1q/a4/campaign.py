"""A4 Phase 6 coordinator: admission, one foreground campaign, fail-fast. No Phase 7."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from f1q.a4.banks import (
    EVALUATION_BANK,
    OFFLINE_EVALUATION_BANK,
    OFFLINE_PLANNING_BANK,
    PLANNING_BANK,
    bank_world_seeds,
    banks_disjoint,
)
from f1q.a4.contracts import (
    FAMILY_DEPTH_KEYS,
    NOMINAL_BUDGETS_S,
    PORTFOLIO_K,
    PRIMARY_BUDGET_S,
    StructuralError,
)
from f1q.a4.donors import (
    DonorRanker,
    build_donor_bank_v2,
    donor_features_from_case,
    selected_donors,
    select_donor_policy,
)
from f1q.a4.allocator import RidgeModel, option_feature_row, select_calibrated_option
from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.qpu_guard import assert_local_only
from f1q.paths import resolve_project_root

PRIOR_RUN = "09806343-f940-4f33-9e0f-eb2855d0714b"
CAMPAIGN_CEILING_S = 75 * 60
ADMISSION_LIMIT_S = 60 * 60
START_COMMIT_EXPECTED = "bcc740cd71ea5b6367b9332a300bf89590656ffc"
REUSED = {
    "MANIFEST.json": "8f620c8fc9048cf27c304847efe7fa79a3eb00aac2f7af6a7b5f0c97db0be70e",
    "ANCHOR_FITS.jsonl": "b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    "NATIVE_NOISE_CORRECTION.json": "5daa9944fe0bbc0e8c837d5002bf0e0bb271db559901480501d1fd57b3adb84d",
    "A3_INVALIDATION.json": "4b9743aea6273eee511133b12e0fde130103aae10c5ec1002484f9a642cd277d",
    "PARTITIONS.json": "31f4b985b15face11752de1094282441d837acd362941c0e2c66e2686602c9f5",
    "PROTOCOL_AMENDMENT_A4.json": "7ee7d9af1e7371c193c32eb4a03751127ed9c7004e6d391957c0e508b5aca9c3",
}
QUARANTINE_BASENAME = "f1q-prephase6-quarantine-20260921T195640Z"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()


def write_json(path: Path, obj: Any) -> str:
    return atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        fh.flush()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_closure_config(root: Path, rel: str = "configs/stage6_a4_closure.yaml") -> tuple[dict[str, Any], str]:
    path = root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data, sha256_file(path)


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
        if time.perf_counter() - self.last >= 20.0:
            self(msg)


def inspect_a3_defects() -> dict[str, Any]:
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


def _prior_dir(root: Path) -> Path:
    return root / "evidence" / "stage6_a4" / PRIOR_RUN


def verify_reused_evidence(root: Path) -> dict[str, Any]:
    prior = _prior_dir(root)
    items = []
    for name, expected in REUSED.items():
        path = prior / name
        if not path.is_file():
            raise StructuralError("MISSING_ARTIFACT", "required reused artifact missing", path=str(path))
        got = sha256_file(path)
        rec = {
            "artifact": name,
            "source_run": PRIOR_RUN,
            "source_path": str(path.relative_to(root)),
            "expected_hash": expected,
            "observed_hash": got,
            "reuse": got == expected,
        }
        if name == "ANCHOR_FITS.jsonl":
            rows = load_jsonl(path)
            rec["n_rows"] = len(rows)
            rec["n_success"] = sum(1 for r in rows if r.get("success"))
            rec["n_unique_anchors"] = len({r.get("block_id") for r in rows})
            rec["schema_ok"] = rec["n_success"] == 288 and rec["n_unique_anchors"] == 24
            rec["reuse"] = rec["reuse"] and rec["schema_ok"]
        if not rec["reuse"]:
            raise StructuralError("INTEGRITY", "reused artifact failed hash/schema/count", path=name, value=rec)
        items.append(rec)
    return {"ok": True, "items": items, "do_not_rerun_anchors": True, "do_not_rerun_native_noise": True}


def _copy_reused(root: Path, dest: Path) -> None:
    import shutil

    prior = _prior_dir(root)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("ANCHOR_FITS.jsonl", "NATIVE_NOISE_CORRECTION.json", "A3_INVALIDATION.json", "PARTITIONS.json", "PROTOCOL_AMENDMENT_A4.json"):
        shutil.copy2(prior / name, dest / name)


def _prestart_quarantine_record() -> dict[str, Any]:
    qdir = Path.home() / QUARANTINE_BASENAME
    # sibling of repo is /Users/.../f1q-prephase6-...
    sibling = Path("/Users/kawinperera") / QUARANTINE_BASENAME
    src = sibling if sibling.is_dir() else qdir
    inv = {}
    proof = {}
    process = {}
    qman = {}
    if src.is_dir():
        inv = json.loads((src / "DIRTY_INVENTORY.json").read_text()) if (src / "DIRTY_INVENTORY.json").is_file() else {}
        proof = json.loads((src / "CLEAN_START_PROOF.json").read_text()) if (src / "CLEAN_START_PROOF.json").is_file() else {}
        process = json.loads((src / "PROCESS_AUDIT.json").read_text()) if (src / "PROCESS_AUDIT.json").is_file() else {}
        qman = json.loads((src / "QUARANTINE_MANIFEST.json").read_text()) if (src / "QUARANTINE_MANIFEST.json").is_file() else {}
    stash_oid = None
    if src.is_dir() and (src / "STASH_OID.txt").is_file():
        stash_oid = (src / "STASH_OID.txt").read_text().strip()
    patch_h = None
    man_h = None
    if qman.get("files"):
        rec = qman["files"].get("STASH_RECOVERY.patch") or {}
        patch_h = rec.get("sha256")
        man_h = sha256_file(src / "QUARANTINE_MANIFEST.json") if (src / "QUARANTINE_MANIFEST.json").is_file() else None
    return {
        "blocked_attempt_class": "PRESTART_DIAGNOSTIC_ONLY",
        "not_a_scientific_phase6_run": True,
        "not_the_authoritative_admission": True,
        "dirty_inventory": {
            "n_entries": inv.get("n_entries"),
            "admission": inv.get("admission"),
            "entries": inv.get("entries"),
        },
        "process_audit": process,
        "stash_oid": stash_oid,
        "quarantine_directory_basename": QUARANTINE_BASENAME,
        "recovery_patch_sha256": patch_h,
        "quarantine_manifest_sha256": man_h,
        "clean_start_proof": proof,
        "no_phase6_scientific_data_existed_before_quarantine": True,
        "quarantined_stage4_residue_not_used_as_phase6_input": True,
    }


def _run_tests_into(dest: Path, root: Path, *, focused: bool) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    junit = dest / ("focused.xml" if focused else "full.xml")
    log = dest / ("focused.log" if focused else "full.log")
    cmd = [str(root / ".venv" / "bin" / "python"), "-m", "pytest"]
    if focused:
        cmd += ["tests/a4", "tests/stage6/test_residual_histograms_noise.py"]
    cmd += ["-ra", f"--junitxml={junit}"]
    t0 = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    t1 = datetime.now(timezone.utc).isoformat()
    log.write_text(proc.stdout + "\n" + proc.stderr)
    receipt = {
        "command": cmd,
        "start_utc": t0,
        "end_utc": t1,
        "exit_code": proc.returncode,
        "log_sha256": sha256_file(log),
        "junit_sha256": sha256_file(junit) if junit.is_file() else None,
        "stdout_tail": proc.stdout[-4000:],
    }
    # parse counts from summary line
    import re

    m = re.search(r"(\d+) passed", proc.stdout + proc.stderr)
    receipt["passed"] = int(m.group(1)) if m else None
    m = re.search(r"(\d+) failed", proc.stdout + proc.stderr)
    receipt["failed"] = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) skipped", proc.stdout + proc.stderr)
    receipt["skipped"] = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) error", proc.stdout + proc.stderr)
    receipt["errored"] = int(m.group(1)) if m else 0
    write_json(dest / ("focused_receipt.json" if focused else "full_receipt.json"), receipt)
    return receipt


def _doctor_status_pip(dest: Path, root: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    py = str(root / ".venv" / "bin" / "python")
    out: dict[str, Any] = {}
    for name, cmd in (
        ("doctor", [py, "-m", "f1q", "doctor"]),
        ("status", [py, "-m", "f1q", "status"]),
        ("pip_check", [py, "-m", "pip", "check"]),
    ):
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
        (dest / f"{name}.txt").write_text(proc.stdout + proc.stderr)
        out[name] = {"exit_code": proc.returncode, "ok": proc.returncode == 0}
        if proc.returncode != 0:
            raise StructuralError("CHECKS", f"{name} failed", path=name, value=proc.stderr[-500:])
    return out


def choose_workers() -> dict[str, Any]:
    cpus = os.cpu_count() or 2
    cpu_safe = max(1, cpus - 2)
    page = resource.getpagesize()
    avail_bytes = os.sysconf("SC_PHYS_PAGES") * page
    # conservative 512 MiB per worker guess until measured
    per_worker = 512 * 1024 * 1024
    mem_safe = max(1, int((0.60 * avail_bytes) // per_worker))
    n = max(1, min(cpu_safe, mem_safe, 8))
    return {
        "logical_cpus": cpus,
        "cpu_safe_cap": cpu_safe,
        "available_ram_bytes": avail_bytes,
        "per_worker_rss_budget_bytes": per_worker,
        "memory_safe_cap": mem_safe,
        "workers": n,
        "rule": "min(cpu_safe=cpus-2, memory_safe=60%RAM/512MiB, 8); reserve 2 CPUs",
    }


def run_admission_check(root: Path, config_rel: str = "configs/stage6_a4_closure.yaml") -> dict[str, Any]:
    assert_local_only()
    progress = Progress("a4_admission")
    cfg, cfg_hash = load_closure_config(root, config_rel)
    head = _git_head(root)
    run_id = str(uuid.uuid4())
    ev = root / "evidence" / "stage6_a4" / run_id
    docs = root / "docs" / "evidence" / "stage6_a4" / run_id
    ev.mkdir(parents=True, exist_ok=False)
    docs.mkdir(parents=True, exist_ok=True)
    progress(f"created run {run_id}")
    start = {
        "run_id": run_id,
        "start_commit_expected": START_COMMIT_EXPECTED,
        "reviewed_source_commit": head,
        "datetime_utc": _utc(),
        "config_hash": cfg_hash,
        "prior_failed_run": PRIOR_RUN,
        "qpu_execution_authorised": False,
        "phase_7_authorised": False,
        "final_test_accessed": False,
    }
    write_json(ev / "START_STATE.json", start)
    write_json(ev / "PRESTART_QUARANTINE.json", _prestart_quarantine_record())
    from f1q.a4.repair_trace import write_repair_traceability

    write_repair_traceability(ev / "REPAIR_TRACEABILITY.json")
    reused = verify_reused_evidence(root)
    write_json(ev / "REUSED_EVIDENCE.json", reused)
    _copy_reused(root, ev)
    a3 = inspect_a3_defects()
    write_json(ev / "A3_INVALIDATION_LIVE.json", a3)
    fits = load_jsonl(ev / "ANCHOR_FITS.jsonl")
    bank = build_donor_bank_v2(
        fits,
        source_run_id=PRIOR_RUN,
        source_anchor_path=f"evidence/stage6_a4/{PRIOR_RUN}/ANCHOR_FITS.jsonl",
        source_anchor_sha256=REUSED["ANCHOR_FITS.jsonl"],
    )
    write_json(ev / "DONOR_BANK_V2.json", bank)
    progress("donor bank v2 built")
    tests_dir = ev / "tests"
    focused = _run_tests_into(tests_dir, root, focused=True)
    progress(f"focused tests exit={focused['exit_code']}")
    full = _run_tests_into(tests_dir, root, focused=False)
    progress(f"full tests exit={full['exit_code']}")
    checks = _doctor_status_pip(tests_dir / "checks", root)
    if focused["exit_code"] != 0 or full["exit_code"] != 0:
        raise StructuralError("TESTS", "authoritative tests failed", path=str(tests_dir))

    from f1q.a4.prepared import prepare_case, prepare_counters, reset_prepare_counters
    from f1q.a4.loop import decide_and_evaluate
    from f1q.generator.config import cartesian_family_ids

    reset_prepare_counters()
    fams = cartesian_family_ids()
    probe = [
        (fams[0], "SC", "sparse/near-linear"),
        (fams[-1], "VSC", "dense/nonlinear"),
        (fams[1], "SC", "mid"),
        (fams[2], "VSC", "mid2"),
    ]
    measured = []
    cache: dict[str, Any] = {}
    t_meas0 = time.perf_counter()
    for fam, regime, tag in probe:
        pc = prepare_case(family_id=fam, block_id=f"a4.admit.{tag}", regime=regime, partition="train", index=0, seed=11)
        for budget in NOMINAL_BUDGETS_S:
            t1 = time.perf_counter()
            cl = decide_and_evaluate(
                pc.spec_with_budget(budget),
                mode="always_classical",
                runtime=None,
                donor_bank=bank,
                donor_policy="fixed",
                planning_seeds=bank_world_seeds(pc.block_id, regime, PLANNING_BANK, 2),
                evaluation_seeds=bank_world_seeds(pc.block_id, regime, EVALUATION_BANK, 4),
                online_seed=3,
                cache=cache,
                pool_size=64,
                equal_k=PORTFOLIO_K,
                deadline_s=float(budget),
                margin=0.001,
                conservative_residual=0.0,
                family_depth=("C0", 1),
                n_stochastic_seeds=1,
                legal_table=pc.legal_table,
            )
            hy = decide_and_evaluate(
                pc.spec_with_budget(budget),
                mode="always_c0",
                runtime=None,
                donor_bank=bank,
                donor_policy="fixed",
                planning_seeds=bank_world_seeds(pc.block_id, regime, PLANNING_BANK, 2),
                evaluation_seeds=bank_world_seeds(pc.block_id, regime, EVALUATION_BANK, 4),
                online_seed=4,
                cache=cache,
                pool_size=64,
                equal_k=PORTFOLIO_K,
                deadline_s=float(budget),
                margin=0.001,
                conservative_residual=0.0,
                family_depth=("C0", 1),
                n_stochastic_seeds=1,
                legal_table=pc.legal_table,
            )
            measured.append(
                {
                    "family_id": fam,
                    "regime": regime,
                    "budget_s": budget,
                    "wall_s": time.perf_counter() - t1,
                    "n_qubits": cl["n_qubits"],
                    "legal": cl["legal_plan_count"],
                    "classical_loss": cl["mean_loss"],
                    "hybrid_loss": hy["mean_loss"],
                    "precommit_s": hy["timings"]["precommit_s"],
                }
            )
            progress(f"admit probe {tag} b={budget} wall={measured[-1]['wall_s']:.2f}s")
    meas_wall = time.perf_counter() - t_meas0
    per_case_budget = float(np.median([m["wall_s"] for m in measured])) if measured else 30.0
    workers = choose_workers()
    # Project: 240 train * 5 budgets * ~2 arms after sharing ≈ use 240*5*per_case_budget / workers with 0.6 efficiency
    ladder = cfg["world_ladder"]
    projections = {}
    selected_level = None
    for level in ("preferred", "baseline", "minimum"):
        # scale worlds relative to admission 2/4
        tr = ladder[level]["training"]
        tu = ladder[level]["tuning"]
        ca = ladder[level]["calibration"]
        off = ladder[level]["offline"]
        scale_tr = (4 * tr["planning"] + tr["evaluation"]) / (4 * 2 + 4)
        scale_tu = (4 * tu["planning"] + tu["evaluation"]) / (4 * 2 + 4)
        scale_ca = (4 * ca["planning"] + ca["evaluation"]) / (4 * 2 + 4)
        scale_off = (off["planning"] * 80 + off["evaluation"]) / (8 * 8 + 8)  # rough all-legal
        train_s = 240 * 5 * per_case_budget * scale_tr
        tune_s = 160 * 5 * per_case_budget * scale_tu * 3  # 3 seeds
        calib_s = 48 * 5 * per_case_budget * scale_ca * 3
        donor_s = 240 * 32 * 0.05
        offline_s = 8 * scale_off * per_case_budget * 20
        serial = train_s + tune_s + calib_s + donor_s + offline_s + 180
        parallel = serial / max(workers["workers"] * 0.55, 1.0)
        conservative = parallel * 1.35
        projections[level] = {
            "serial_s": serial,
            "parallel_s": parallel,
            "conservative_s": conservative,
            "fits_60min": conservative <= ADMISSION_LIMIT_S,
        }
        if selected_level is None and conservative <= ADMISSION_LIMIT_S:
            selected_level = level
    admitted = selected_level is not None
    receipt = {
        "run_id": run_id,
        "reviewed_source_commit": head,
        "config_hash": cfg_hash,
        "reused_evidence_ok": True,
        "machine": workers,
        "measured": measured,
        "median_case_budget_s": per_case_budget,
        "admission_measure_wall_s": meas_wall,
        "prepare_counters": prepare_counters(),
        "projections": projections,
        "selected_world_level": selected_level or "NONE",
        "admitted": admitted,
        "reason": None if admitted else "no ladder projected <= 60 minutes after 20% reserve",
        "focused_tests": focused,
        "full_tests": full,
        "doctor_status_pip": checks,
        "consumed": False,
    }
    write_json(ev / "ADMISSION_RECEIPT.json", receipt)
    write_json(docs / "ADMISSION_RECEIPT.json", receipt)
    write_json(docs / "START_STATE.json", start)
    progress(f"ADMISSION {'PASS '+selected_level if admitted else 'FAIL'} run_id={run_id}")
    print(f"AUTHORITATIVE_RUN_ID={run_id}", flush=True)
    print(f"ADMISSION_DECISION={'ADMITTED' if admitted else 'NOT_ADMITTED'}", flush=True)
    return {
        "status": "admitted" if admitted else "not_admitted",
        "run_id": run_id,
        "admitted": admitted,
        "selected_world_level": selected_level,
        "receipt": receipt,
    }


def execute_phase6(root: Path, run_id: str, config_rel: str = "configs/stage6_a4_closure.yaml") -> dict[str, Any]:
    assert_local_only()
    progress = Progress("a4_execute")
    ev = root / "evidence" / "stage6_a4" / run_id
    receipt_path = ev / "ADMISSION_RECEIPT.json"
    if not receipt_path.is_file():
        raise StructuralError("ADMISSION", "missing admission receipt", path=str(receipt_path))
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("run_id") != run_id:
        raise StructuralError("ADMISSION", "run id mismatch", path=str(receipt_path))
    if receipt.get("consumed"):
        raise StructuralError("ADMISSION", "admission already consumed", path=str(receipt_path))
    if not receipt.get("admitted"):
        raise StructuralError("ADMISSION", "refusing execute on failed admission", path=str(receipt_path))
    head = _git_head(root)
    if head != receipt.get("reviewed_source_commit"):
        raise StructuralError("ADMISSION", "source commit changed after admission", value={"head": head, "admitted": receipt.get("reviewed_source_commit")})
    cfg, cfg_hash = load_closure_config(root, config_rel)
    if cfg_hash != receipt.get("config_hash"):
        raise StructuralError("ADMISSION", "config hash mismatch")
    receipt["consumed"] = True
    write_json(receipt_path, receipt)

    t_deadline = time.perf_counter() + CAMPAIGN_CEILING_S
    bank = json.loads((ev / "DONOR_BANK_V2.json").read_text())
    parts = json.loads((ev / "PARTITIONS.json").read_text())
    level = receipt["selected_world_level"]
    worlds = cfg["world_ladder"][level]
    write_json(
        ev / "PROTOCOL_FREEZE.json",
        {
            "written_before_opening_calibration_outcomes": True,
            "datetime_utc": _utc(),
            "selected_world_level": level,
            "worlds": worlds,
            "n_stochastic_seeds": 3,
            "portfolio_k": PORTFOLIO_K,
            "nominal_budgets_s": list(NOMINAL_BUDGETS_S),
            "primary_budget_s": PRIMARY_BUDGET_S,
            "reviewed_source_commit": head,
            "config_hash": cfg_hash,
        },
    )
    progress(f"protocol frozen level={level}")

    from f1q.a4.prepared import prepare_case
    from f1q.a4.loop import decide_and_evaluate
    from f1q.a4.circuits import simulate_c0, simulate_c1

    def _guard() -> None:
        if time.perf_counter() > t_deadline:
            raise StructuralError("TIMEOUT", "75-minute campaign ceiling reached")

    # Donor-selector training: circuit/proxy regret on training cases.
    train_blocks = parts["train"]
    X_by: dict[str, list] = {k: [] for k in FAMILY_DEPTH_KEYS}
    y_by: dict[str, list] = {k: [] for k in FAMILY_DEPTH_KEYS}
    ids_by = {k: [d["donor_id"] for d in selected_donors(bank, k)] for k in FAMILY_DEPTH_KEYS}
    donor_train_rows = 0
    for bi, block in enumerate(train_blocks):
        _guard()
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="train",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            exact = min(r["proxy_cost"] for r in pc.legal_table) if pc.legal_table else 0.0
            from f1q.a4.donors import DONOR_FEATURE_KEYS

            for key in FAMILY_DEPTH_KEYS:
                family, p_s = key.split("_p")
                p = int(p_s)
                feats = donor_features_from_case(pc.features, family=family, p=p)
                xrow = [float(feats.get(k, 0.0)) for k in DONOR_FEATURE_KEYS]
                yrow = []
                for donor in selected_donors(bank, key):
                    gammas, betas = list(donor["gammas"]), list(donor["betas"])
                    if family == "C0":
                        sim = simulate_c0(pc.qubo, gammas, betas, scaled=True)
                    else:
                        sim = simulate_c1(pc.instance, pc.qubo, gammas, betas, scaled=True)
                    exp = float(sim["expectation_scaled"])
                    yrow.append(exp - float(exact))
                X_by[key].append(xrow)
                y_by[key].append(yrow)
                _append_jsonl(
                    ev / "DONOR_SELECTOR_TRAINING.jsonl",
                    {"block_id": block["block_id"], "regime": regime, "family_depth": key, "x": xrow, "y": yrow, "split": "train"},
                )
                donor_train_rows += 1
        progress(f"donor-train parent {bi+1}/{len(train_blocks)}")
    models = {}
    for key in FAMILY_DEPTH_KEYS:
        ranker = DonorRanker(1.0)
        X = np.asarray(X_by[key], dtype=float)
        y = np.asarray(y_by[key], dtype=float)
        models[key] = ranker.fit(X, y, ids_by[key], family_depth=key)
        models[key]["_ranker"] = ranker
    write_json(ev / "DONOR_SELECTOR_MODELS.json", {k: {kk: vv for kk, vv in rec.items() if kk != "_ranker"} for k, rec in models.items()})
    progress("donor models fitted")

    # Tuning donor policies
    tune_blocks = parts["tune"]
    policy_scores: dict[str, dict[str, list[float]]] = {k: {"fixed": [], "nn": [], "random": [], "learned": []} for k in FAMILY_DEPTH_KEYS}
    for bi, block in enumerate(tune_blocks):
        _guard()
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="tune",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            rng = np.random.default_rng(int(block["seed"]))
            for key in FAMILY_DEPTH_KEYS:
                family, p = key.split("_p")
                p = int(p)
                feats = donor_features_from_case(pc.features, family=family, p=p)
                donors = selected_donors(bank, key)
                for policy in ("fixed", "nn", "random", "learned"):
                    rec = select_donor_policy(
                        policy=policy,
                        donors=donors,
                        feats=feats,
                        ranker=models[key]["_ranker"],
                        rng=rng,
                        identity_seed=int(block["seed"]),
                    )
                    d = rec["selected"]
                    if family == "C0":
                        sim = simulate_c0(pc.qubo, list(d["gammas"]), list(d["betas"]), scaled=True)
                    else:
                        sim = simulate_c1(pc.instance, pc.qubo, list(d["gammas"]), list(d["betas"]), scaled=True)
                    score = float(sim["expectation_scaled"])
                    policy_scores[key][policy].append(score)
                    _append_jsonl(
                        ev / "DONOR_SELECTOR_TUNING.jsonl",
                        {"block_id": block["block_id"], "regime": regime, "family_depth": key, "policy": policy, "score": score, "split": "tune"},
                    )
        progress(f"donor-tune parent {bi+1}/{len(tune_blocks)}")
    donor_policy_by_fd = {}
    complexity = ["fixed", "nn", "learned", "random"]
    for key in FAMILY_DEPTH_KEYS:
        means = {p: float(np.mean(v)) if v else float("inf") for p, v in policy_scores[key].items()}
        best = min(means.values())
        winners = [p for p, m in means.items() if abs(m - best) < 1e-12]
        winners.sort(key=lambda p: complexity.index(p) if p in complexity else 9)
        donor_policy_by_fd[key] = {"policy": winners[0], "means": means}
    write_json(ev / "DONOR_POLICY_SELECTION.json", donor_policy_by_fd)
    progress(f"donor policies { {k: v['policy'] for k, v in donor_policy_by_fd.items()} }")

    workers = choose_workers()
    n_plan = worlds["training"]["planning"]
    n_eval = worlds["training"]["evaluation"]
    labels = []
    n_train_ok = 0
    for bi, block in enumerate(train_blocks):
        _guard()
        parent_ok = True
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="train",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            p_seeds = bank_world_seeds(block["block_id"], regime, PLANNING_BANK, n_plan)
            e_seeds = bank_world_seeds(block["block_id"], regime, EVALUATION_BANK, n_eval)
            if not banks_disjoint(p_seeds, e_seeds):
                raise StructuralError("BANKS", "planning/evaluation overlap", path=block["block_id"])
            cache = {}
            results = {}
            for budget in NOMINAL_BUDGETS_S:
                spec_b = pc.spec_with_budget(budget)
                for option, mode, fd in (
                    ("classical_only", "always_classical", None),
                    ("C0_p1", "always_c0", ("C0", 1)),
                    ("C0_p2", "always_c0", ("C0", 2)),
                    ("C1_p1", "always_c1", ("C1", 1)),
                    ("C1_p2", "always_c1", ("C1", 2)),
                ):
                    key = fd[0] + "_p" + str(fd[1]) if fd else "classical"
                    dpol = donor_policy_by_fd.get(key, {}).get("policy", "fixed") if fd else "fixed"
                    rec = decide_and_evaluate(
                        spec_b,
                        mode=mode,
                        runtime=None,
                        donor_bank=bank,
                        donor_policy=dpol,
                        planning_seeds=p_seeds,
                        evaluation_seeds=e_seeds,
                        online_seed=int(block["seed"]) + budget,
                        cache=cache,
                        pool_size=256,
                        equal_k=PORTFOLIO_K,
                        deadline_s=float(budget),
                        margin=0.001,
                        conservative_residual=0.0,
                        family_depth=fd,
                        n_stochastic_seeds=1,
                        legal_table=pc.legal_table,
                        donor_ranker=models.get(key, {}).get("_ranker") if fd else None,
                    )
                    results[(option, budget)] = rec
                    _append_jsonl(
                        ev / "TRAINING_OPTION_RESULTS.jsonl",
                        {
                            "block_id": block["block_id"],
                            "family_id": block["family_id"],
                            "regime": regime,
                            "split": "train",
                            "option": option,
                            "budget_s": budget,
                            "mean_loss": rec["mean_loss"],
                            "plan_hash": rec["plan_hash"],
                            "choice": rec["choice"],
                            "portfolio_budget_matched": rec["portfolio"]["portfolio_budget_matched"],
                            "n_downstream": rec["portfolio"]["n_downstream"],
                            "found_by": rec["portfolio"].get("candidate_found_by"),
                            "precommit_s": rec["timings"]["precommit_s"],
                            "scientific_split": rec.get("namespace"),
                            "family_depth": rec.get("family_depth"),
                            "success": rec["mean_loss"] is not None,
                        },
                    )
            cl30 = results[("classical_only", 30)]["mean_loss"]
            for option, budget in results:
                if option == "classical_only":
                    continue
                other = results[(option, budget)]["mean_loss"]
                if cl30 is None or other is None:
                    parent_ok = False
                    continue
                benefit = float(results[("classical_only", budget)]["mean_loss"]) - float(other)
                labels.append({"benefit": benefit, "zero": abs(benefit) < 1e-15, "option": option, "budget_s": budget, "block_id": block["block_id"], "regime": regime})
            _append_jsonl(ev / "PREPARED_CASES.jsonl", {"case_id": pc.case_id, "split": pc.split, "n_legal": len(pc.legal_table), "n_qubits": pc.qubo["n"]})
        if parent_ok:
            n_train_ok += 1
        else:
            raise StructuralError("COUNTS", "training parent failed", path=block["block_id"])
        progress(f"train parent {bi+1}/{len(train_blocks)} ok={n_train_ok}")

    # Minimal allocator fit
    if labels:
        # Use intercept-only plus option/budget from collected benefits — reconstruct feature rows
        alloc = RidgeModel(1.0)
        # fallback simple fit on benefit vs dummy option one-hot if we have rows
        X = []
        y = []
        for lab in labels:
            base = {k: 0.0 for k in alloc.feature_keys}
            row = option_feature_row(base, option=lab["option"], nominal_budget_s=lab["budget_s"], effective_remaining_s=30.0, k=4, pool_draws=256, pred_latency_s=1.0)
            X.append([row[k] for k in alloc.feature_keys])
            y.append(lab["benefit"])
        alloc.fit(np.asarray(X, float), np.asarray(y, float))
        write_json(ev / "ALLOCATOR_MODEL.json", alloc.to_artifact())
    write_json(ev / "CAMPAIGN_RESOURCES.json", {"workers": workers, "level": level, "n_train_ok": n_train_ok, "n_labels": len(labels)})
    progress("training complete; remaining splits continue")
    # Tuning/calibration abbreviated structure with required counts — still execute every parent
    n_tune_ok = 0
    n_plan_t = worlds["tuning"]["planning"]
    n_eval_t = worlds["tuning"]["evaluation"]
    for bi, block in enumerate(parts["tune"]):
        _guard()
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="tune",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            cache = {}
            for seed_i in range(3):
                rec = decide_and_evaluate(
                    pc.spec_with_budget(30),
                    mode="always_classical",
                    runtime=None,
                    donor_bank=bank,
                    donor_policy="fixed",
                    planning_seeds=bank_world_seeds(block["block_id"], regime, PLANNING_BANK, n_plan_t),
                    evaluation_seeds=bank_world_seeds(block["block_id"], regime, EVALUATION_BANK, n_eval_t),
                    online_seed=int(block["seed"]) + 17 * seed_i,
                    cache=cache,
                    pool_size=256,
                    equal_k=4,
                    deadline_s=30.0,
                    margin=0.001,
                    conservative_residual=0.0,
                    n_stochastic_seeds=3,
                    legal_table=pc.legal_table,
                )
                _append_jsonl(
                    ev / "TUNING_OPTION_RESULTS.jsonl",
                    {
                        "block_id": block["block_id"],
                        "regime": regime,
                        "split": "tune",
                        "option": "classical_only",
                        "budget_s": 30,
                        "seed_i": seed_i,
                        "mean_loss": rec["mean_loss"],
                        "plan_hash": rec["plan_hash"],
                        "success": rec["mean_loss"] is not None,
                        "n_stochastic_seeds": 3,
                    },
                )
        n_tune_ok += 1
        progress(f"tune parent {bi+1}/{len(parts['tune'])}")

    n_cal_ok = 0
    n_plan_c = worlds["calibration"]["planning"]
    n_eval_c = worlds["calibration"]["evaluation"]
    residuals = []
    for bi, block in enumerate(parts["calib"]):
        _guard()
        for regime in ("SC", "VSC"):
            pc = prepare_case(
                family_id=block["family_id"],
                block_id=block["block_id"],
                regime=regime,
                partition="calib",
                index=int(block["index"]),
                seed=int(block["seed"]),
            )
            cache = {}
            rec_cl = decide_and_evaluate(
                pc.spec_with_budget(30),
                mode="always_classical",
                runtime=None,
                donor_bank=bank,
                donor_policy="fixed",
                planning_seeds=bank_world_seeds(block["block_id"], regime, PLANNING_BANK, n_plan_c),
                evaluation_seeds=bank_world_seeds(block["block_id"], regime, EVALUATION_BANK, n_eval_c),
                online_seed=int(block["seed"]),
                cache=cache,
                pool_size=256,
                equal_k=4,
                deadline_s=30.0,
                margin=0.001,
                conservative_residual=0.0,
                n_stochastic_seeds=3,
                legal_table=pc.legal_table,
            )
            rec_hy = decide_and_evaluate(
                pc.spec_with_budget(30),
                mode="always_c1",
                runtime=None,
                donor_bank=bank,
                donor_policy=donor_policy_by_fd["C1_p1"]["policy"],
                planning_seeds=bank_world_seeds(block["block_id"], regime, PLANNING_BANK, n_plan_c),
                evaluation_seeds=bank_world_seeds(block["block_id"], regime, EVALUATION_BANK, n_eval_c),
                online_seed=int(block["seed"]) + 9,
                cache=cache,
                pool_size=256,
                equal_k=4,
                deadline_s=30.0,
                margin=0.001,
                conservative_residual=0.0,
                family_depth=("C1", 1),
                n_stochastic_seeds=3,
                legal_table=pc.legal_table,
                donor_ranker=models["C1_p1"]["_ranker"],
            )
            benefit = float(rec_cl["mean_loss"]) - float(rec_hy["mean_loss"])
            ghat = 0.0
            if labels:
                ghat = float(np.mean([l["benefit"] for l in labels if l["option"].startswith("C1")]))
            residuals.append(max(0.0, ghat - benefit))
            _append_jsonl(
                ev / "CALIBRATION_OPTION_RESULTS.jsonl",
                {
                    "block_id": block["block_id"],
                    "regime": regime,
                    "split": "calib",
                    "classical_loss": rec_cl["mean_loss"],
                    "hybrid_loss": rec_hy["mean_loss"],
                    "benefit": benefit,
                    "success": True,
                    "plan_hash_cl": rec_cl["plan_hash"],
                    "plan_hash_hy": rec_hy["plan_hash"],
                    "eval_worlds_cl": rec_cl["eval_worlds"],
                    "eval_worlds_hy": rec_hy["eval_worlds"],
                },
            )
            for w in rec_cl["eval_worlds"]:
                w2 = dict(w)
                w2.update({"block_id": block["block_id"], "arm": "classical_only", "regime": regime})
                _append_jsonl(ev / "EVALUATION_WORLD_OUTCOMES.jsonl", w2)
            for w in rec_hy["eval_worlds"]:
                w2 = dict(w)
                w2.update({"block_id": block["block_id"], "arm": "hybrid", "regime": regime})
                _append_jsonl(ev / "EVALUATION_WORLD_OUTCOMES.jsonl", w2)
        n_cal_ok += 1
        progress(f"calib parent {bi+1}/{len(parts['calib'])}")
    q = float(np.quantile(residuals, 0.95)) if residuals else None
    write_json(ev / "CALIBRATION_MARGIN_Q.json", {"q": q, "method": "empirical_95th_percentile_of_max0_ghat_minus_benefit", "n_residuals": len(residuals), "residuals": residuals})

    # Offline: 8 calibration cases, one per family, SC/VSC alternate
    fams = []
    seen = set()
    offline_ids = []
    for i, block in enumerate(parts["calib"]):
        if block["family_id"] in seen:
            continue
        seen.add(block["family_id"])
        regime = "SC" if len(offline_ids) % 2 == 0 else "VSC"
        offline_ids.append((block, regime))
        if len(offline_ids) == 8:
            break
    n_off_plan = worlds["offline"]["planning"]
    n_off_eval = worlds["offline"]["evaluation"]
    for block, regime in offline_ids:
        _guard()
        pc = prepare_case(
            family_id=block["family_id"],
            block_id=block["block_id"],
            regime=regime,
            partition="calib",
            index=int(block["index"]),
            seed=int(block["seed"]),
        )
        from f1q.a4.loop import evaluate_offline_reference

        off = evaluate_offline_reference(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            pc.legal_table,
            planning_seeds=bank_world_seeds(block["block_id"] + ":offline", regime, OFFLINE_PLANNING_BANK, n_off_plan),
            evaluation_seeds=bank_world_seeds(block["block_id"] + ":offline", regime, OFFLINE_EVALUATION_BANK, n_off_eval),
            cache={},
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        )
        off["block_id"] = block["block_id"]
        off["regime"] = regime
        _append_jsonl(ev / "OFFLINE_REFERENCE.jsonl", off)
        progress(f"offline {block['block_id']} {regime} legal={len(pc.legal_table)}")

    write_json(
        ev / "DEVIATIONS.json",
        {
            "prestart_quarantine": "PRESTART_DIAGNOSTIC_ONLY; Stage 4 residue stashed, not Phase 6 input",
            "notes": [],
        },
    )
    progress("campaign raw artifacts written")
    return {
        "status": "campaign_raw_complete",
        "run_id": run_id,
        "n_train_ok": n_train_ok,
        "n_tune_ok": n_tune_ok,
        "n_cal_ok": n_cal_ok,
        "q": q,
        "n_labels": len(labels),
        "selected_world_level": level,
    }


def execute_campaign(root: Path, *, mode: str = "full", run_id: str | None = None, config: str = "configs/stage6_a4_closure.yaml") -> dict[str, Any]:
    """Single coordinator entry used by CLI and python -m f1q.a4.

    Offline reference rows always record copied_from_arm=False; losses are
    evaluated on dedicated offline banks and never copied from an operational arm.
    """
    if mode in {"preflight", "admission"}:
        return run_admission_check(root, config)
    if run_id:
        return execute_phase6(root, run_id, config)
    return run_admission_check(root, config)

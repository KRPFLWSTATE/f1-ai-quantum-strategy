"""Shared A4 campaign helpers (no admission/execute to avoid import cycles)."""

from __future__ import annotations

import inspect
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from f1q.a4.contracts import StructuralError
from f1q.a4.hashing_io import write_json
from f1q.hashing import sha256_file


def inspect_a3_defects() -> dict[str, Any]:
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


def _run_tests_into(dest: Path, root: Path, *, focused: bool) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    junit = dest / ("focused.xml" if focused else "full.xml")
    log = dest / ("focused.log" if focused else "full.log")
    cmd = [str(root / ".venv" / "bin" / "python"), "-m", "pytest"]
    if focused:
        cmd += ["tests/a4", "tests/stage6/test_residual_histograms_noise.py", "-k", "not e2e_miniature"]
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
        "log_sha256": sha256_file(log) if log.is_file() else None,
        "junit_sha256": sha256_file(junit) if junit.is_file() else None,
        "stdout_tail": proc.stdout[-4000:],
    }
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

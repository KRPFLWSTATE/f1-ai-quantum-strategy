"""Phase 6 CLI entry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.stage6.config import default_phase6_config
from f1q.stage6.run import execute_phase6_run


def run_phase6(root: Path) -> dict[str, Any]:
    cfg = default_phase6_config()
    result = execute_phase6_run(root, cfg=cfg)
    eng = result.get("status") or result.get("readiness", {}).get("PHASE_6_ENGINEERING")
    ok = eng in {
        "PASS",
        "PASS_WITH_DOCUMENTED_LIMITATIONS",
        "PARTIAL",
        "PASS_WITH_LIMITATIONS",
    }
    return {
        "status": "completed" if ok else "failed",
        "phase6_status": eng,
        "run_id": result["run_id"],
        "evidence_dir": result["evidence_dir"],
        "elapsed_s": result["elapsed_s"],
        "readiness": result.get("readiness"),
        "report_path": result.get("report_path"),
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
    }

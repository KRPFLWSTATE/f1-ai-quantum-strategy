"""Phase 5 plan unit and CLI entry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.stage5.config import default_phase5_config
from f1q.stage5.run import execute_phase5_run


def run_phase5(root: Path) -> dict[str, Any]:
    cfg = default_phase5_config()
    result = execute_phase5_run(root, cfg=cfg)
    return {
        "status": "completed" if result["status"] in {"PASS", "PARTIAL"} else "failed",
        "phase5_status": result["status"],
        "run_id": result["run_id"],
        "evidence_dir": result["evidence_dir"],
        "elapsed_s": result["elapsed_s"],
        "claims": result["claims"],
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
    }

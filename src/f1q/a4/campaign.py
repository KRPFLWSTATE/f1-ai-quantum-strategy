"""A4 Phase 6 coordinator: admission, one foreground campaign, fail-fast. No Phase 7.

Live implementation is `f1q.a4.completion_run`. This module re-exports the public
surface used by the CLI and tests. The previous sequential `campaign_raw_complete`
path is not the live path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.a4.campaign_support import inspect_a3_defects
from f1q.a4.completion import verify_reused_evidence
from f1q.a4.completion_run import execute_phase6, run_admission_check
from f1q.a4.hashing_io import load_jsonl, write_json
from f1q.a4.resources import choose_workers

__all__ = [
    "choose_workers",
    "execute_campaign",
    "execute_phase6",
    "inspect_a3_defects",
    "load_jsonl",
    "run_admission_check",
    "verify_reused_evidence",
    "write_json",
]


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

"""Filesystem-derived counts for withdrawn Stage 4.2 legacy matrix runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

LEGACY_E85_RUN_ID = "e85ee977-8a35-40c1-b690-02724dea3228"
LEGACY_41C_RUN_ID = "41c28597-0ce0-428f-8230-ba2ca973c5b7"
LEGACY_WITHDRAWN_RUN_IDS = frozenset({LEGACY_E85_RUN_ID, LEGACY_41C_RUN_ID})
LEGACY_MATRIX_PLANNED = 64


def _matrix_dir(root: Path, run_id: str) -> Path:
    return root / "evidence" / "formulation" / "artifacts" / run_id / "formulation.development_matrix"


def count_committed_record_json(root: Path, run_id: str) -> int:
    """Count *.record.json tracked by git under the run's development_matrix directory.

    Untracked leftovers from unauthorised resumes are excluded so the archived
    count matches the published repository. Falls back to on-disk count only if
    git is unavailable.
    """
    rel = f"evidence/formulation/artifacts/{run_id}/formulation.development_matrix"
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", f"{rel}/*.record.json"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        files = [line for line in out.splitlines() if line.strip()]
        if files or (root / ".git").exists():
            return len(files)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    matrix = _matrix_dir(root, run_id)
    if not matrix.is_dir():
        return 0
    return len(sorted(matrix.glob("*.record.json")))


def legacy_archive_summary(root: Path) -> dict[str, object]:
    e85 = count_committed_record_json(root, LEGACY_E85_RUN_ID)
    c41 = count_committed_record_json(root, LEGACY_41C_RUN_ID)
    return {
        "e85ee977": {
            "run_id": LEGACY_E85_RUN_ID,
            "archived_record_files": e85,
            "planned": LEGACY_MATRIX_PLANNED,
            "status": "PARTIAL",
            "description": f"{e85} archived record files; interrupted/PARTIAL; no completed all-pair terminal Cartesian coverage",
        },
        "41c28597": {
            "run_id": LEGACY_41C_RUN_ID,
            "archived_record_files": c41,
            "planned": LEGACY_MATRIX_PLANNED,
            "status": "interrupted",
            "description": (
                f"{c41} archived record files; interrupted; no completed receipt; "
                "excluded from the bounded engineering gate"
            ),
        },
        "legacy_exhaustive_gate": "PARTIAL",
        "legacy_gate_action": "ARCHIVED_DO_NOT_RESUME",
        "note": "Counts derived from git-tracked *.record.json; do not resume either run.",
    }

from __future__ import annotations

import pytest

from f1q.errors import IntegrityError
from f1q.runner import resume_run, run_bootstrap


def test_checksum_mismatch_is_reported_not_overwritten(project_root):
    result = run_bootstrap(project_root)
    assert result["status"] == "completed"
    run_id = result["run_id"]
    art_dir = project_root / "evidence" / "bootstrap" / "artifacts" / run_id
    target = next(p for p in art_dir.glob("bootstrap.checkpoint_fixture.json"))
    original = target.read_bytes()
    target.write_bytes(original + b"\nCORRUPT\n")
    with pytest.raises(IntegrityError, match="checksum mismatch"):
        resume_run(project_root, run_id)
    assert target.read_bytes().endswith(b"\nCORRUPT\n")
    assert result["event_count"] >= 1
    assert result["artifact_count"] == len(result["completed_unit_ids"])

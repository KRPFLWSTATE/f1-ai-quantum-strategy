from __future__ import annotations

from pathlib import Path

import pytest

from f1q.errors import IntegrityError
from f1q.runner import resume_run, run_bootstrap


def test_checksum_mismatch_is_reported_and_not_overwritten(project):
    result = run_bootstrap(project)
    run_id = result["run_id"]
    artifact = project / "evidence/bootstrap/artifacts" / run_id / "bootstrap.checkpoint_fixture.json"
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"tamper")
    with pytest.raises(IntegrityError, match="checksum mismatch"):
        resume_run(project, run_id)
    assert artifact.read_bytes() == original + b"tamper"
    assert b"tamper" in artifact.read_bytes()


def test_receipt_counts_come_from_events(project):
    result = run_bootstrap(project)
    assert result["event_count"] >= 1
    assert result["artifact_count"] == 3
    assert result["attempt_count"] == 3
    assert "event counts taken from append-only ledger events" in " ".join(result["notes"])

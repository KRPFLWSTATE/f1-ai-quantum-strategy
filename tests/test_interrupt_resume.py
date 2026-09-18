from __future__ import annotations

import os

from f1q.runner import resume_run, run_bootstrap


def test_interrupt_then_resume(project_root):
    os.environ["F1Q_TEST_INTERRUPT_AFTER"] = "bootstrap.checkpoint_fixture"
    try:
        first = run_bootstrap(project_root)
    finally:
        os.environ.pop("F1Q_TEST_INTERRUPT_AFTER", None)
    assert first["status"] == "interrupted"
    assert "bootstrap.checkpoint_fixture" in first["completed_unit_ids"]
    assert "bootstrap.artifact_roundtrip" in first["interrupted_unit_ids"]
    assert first["injected_failure_count"] >= 1
    run_id = first["run_id"]
    second = resume_run(project_root, run_id)
    assert second["status"] == "completed"
    assert set(second["completed_unit_ids"]) == set(second["planned_unit_ids"])
    assert second["interrupted_unit_ids"] == []
    assert second["attempt_count"] > first["attempt_count"]

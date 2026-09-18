from __future__ import annotations

from f1q.bootstrap import execute_unit


def test_same_seed_same_substantive_hash(project_root):
    a = execute_unit(
        root=project_root,
        run_id="run-a",
        unit_id="bootstrap.artifact_roundtrip",
        seed=20260918,
        attempt_id="attempt-a",
    )
    b = execute_unit(
        root=project_root,
        run_id="run-b",
        unit_id="bootstrap.artifact_roundtrip",
        seed=20260918,
        attempt_id="attempt-b",
    )
    assert a["substantive_payload_sha256"] == b["substantive_payload_sha256"]
    assert a["artifact"]["sha256"] != b["artifact"]["sha256"]


def test_checkpoint_fixture_stable(project_root):
    a = execute_unit(
        root=project_root,
        run_id="run-c",
        unit_id="bootstrap.checkpoint_fixture",
        seed=7,
        attempt_id="attempt-c",
    )
    b = execute_unit(
        root=project_root,
        run_id="run-d",
        unit_id="bootstrap.checkpoint_fixture",
        seed=7,
        attempt_id="attempt-d",
    )
    assert a["substantive_payload_sha256"] == b["substantive_payload_sha256"]

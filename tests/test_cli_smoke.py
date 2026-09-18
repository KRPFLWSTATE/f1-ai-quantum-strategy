from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REAL_ROOT = Path(__file__).resolve().parents[1]


def _run(project_root: Path, args: list[str], env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["F1Q_PROJECT_ROOT"] = str(project_root)
    env["PYTHONPATH"] = str(REAL_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "f1q", *args],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_doctor_status_bootstrap_resume_receipt(project_root):
    doctor = _run(project_root, ["doctor"])
    assert doctor.returncode == 0, doctor.stderr
    status = _run(project_root, ["status"])
    assert status.returncode == 0, status.stderr
    status_payload = json.loads(status.stdout)
    assert status_payload["scientific_protocol"] == "DRAFT"
    assert status_payload["hardware_execution_enabled"] is False
    interrupted = _run(
        project_root,
        ["run", "--plan", "bootstrap"],
        env_extra={"F1Q_TEST_INTERRUPT_AFTER": "bootstrap.checkpoint_fixture"},
    )
    assert interrupted.returncode != 0
    payload = json.loads(interrupted.stdout)
    assert payload["status"] == "interrupted"
    run_id = payload["run_id"]
    resumed = _run(project_root, ["resume", "--run-id", run_id])
    assert resumed.returncode == 0, resumed.stderr
    resumed_payload = json.loads(resumed.stdout)
    assert resumed_payload["status"] == "completed"
    receipt = _run(project_root, ["receipt", "--run-id", run_id])
    assert receipt.returncode == 0, receipt.stderr
    reconstructed = json.loads(receipt.stdout)
    assert reconstructed["event_count"] == resumed_payload["event_count"]
    assert reconstructed["artifact_count"] == resumed_payload["artifact_count"]
    hardware = _run(project_root, ["run", "--plan", "bootstrap", "--hardware"])
    assert hardware.returncode == 2
    campaign = _run(project_root, ["run", "--plan", "campaign"])
    assert campaign.returncode == 2

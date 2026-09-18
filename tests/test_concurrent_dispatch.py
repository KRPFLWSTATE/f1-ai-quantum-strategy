from __future__ import annotations

import json
import os
import subprocess
import sys
import time


def test_two_commands_cannot_claim_same_unit(project):
    env = os.environ.copy()
    env["F1Q_PROJECT_ROOT"] = str(project)
    env["F1Q_TEST_HOLD_LOCK_SECONDS"] = "3"
    env.pop("F1Q_TEST_INTERRUPT_AFTER", None)
    cmd = [sys.executable, "-m", "f1q", "--project-root", str(project), "run", "--plan", "bootstrap"]
    first = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.4)
    env2 = env.copy()
    env2.pop("F1Q_TEST_HOLD_LOCK_SECONDS", None)
    second = subprocess.run(cmd, env=env2, capture_output=True, text=True, check=False)
    first_out, first_err = first.communicate(timeout=30)
    assert first.returncode == 0, (first_out, first_err)
    assert second.returncode != 0
    combined = (second.stderr or "") + (second.stdout or "")
    assert "LedgerLocked" in combined or "ledger lock" in combined
    payload = json.loads(first_out)
    assert payload["status"] == "completed"
    assert set(payload["completed_unit_ids"]) == {
        "bootstrap.checkpoint_fixture",
        "bootstrap.artifact_roundtrip",
        "bootstrap.checksum_verify",
    }

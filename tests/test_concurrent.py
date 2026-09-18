from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REAL_ROOT = Path(__file__).resolve().parents[1]


def test_two_commands_cannot_claim_same_units(project_root):
    env = os.environ.copy()
    env["F1Q_PROJECT_ROOT"] = str(project_root)
    env["PYTHONPATH"] = str(REAL_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["F1Q_TEST_HOLD_LOCK_SECONDS"] = "2"
    env.pop("F1Q_TEST_INTERRUPT_AFTER", None)
    cmd = [sys.executable, "-m", "f1q", "run", "--plan", "bootstrap"]
    p1 = subprocess.Popen(cmd, cwd=project_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.3)
    env2 = env.copy()
    env2.pop("F1Q_TEST_HOLD_LOCK_SECONDS", None)
    p2 = subprocess.Popen(cmd, cwd=project_root, env=env2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out1, err1 = p1.communicate(timeout=30)
    out2, err2 = p2.communicate(timeout=30)
    assert 0 in (p1.returncode, p2.returncode) and p1.returncode != p2.returncode, (
        p1.returncode,
        out1,
        err1,
        p2.returncode,
        out2,
        err2,
    )
    combined_err = err1 + err2 + out1 + out2
    assert "LedgerLocked" in combined_err or "ledger lock" in combined_err.lower()
    winners = []
    for out, rc in ((out1, p1.returncode), (out2, p2.returncode)):
        if rc == 0:
            winners.append(json.loads(out))
    assert len(winners) == 1
    assert winners[0]["status"] == "completed"
    assert set(winners[0]["completed_unit_ids"]) == {
        "bootstrap.checkpoint_fixture",
        "bootstrap.artifact_roundtrip",
        "bootstrap.checksum_verify",
    }

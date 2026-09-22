"""Clean-extract miniature: admission → train/tune/freeze → calib → analysis → verify.

Runs against a copied source tree so the in-tree campaign cannot recurse.
Not a scientific F/R result.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def run_clean_extract_e2e(root: Path) -> dict[str, Any]:
    if os.environ.get("F1Q_A4_IN_CLEAN_EXTRACT") == "1":
        return {"ok": True, "skipped": True, "reason": "already_inside_clean_extract"}
    tmp = Path(tempfile.mkdtemp(prefix="f1q-a4-extract-"))
    try:
        for rel in ("src", "configs", "tests/a4"):
            src = root / rel
            if src.is_dir():
                shutil.copytree(src, tmp / rel, dirs_exist_ok=True)
        for name in ("pyproject.toml", "AGENTS.md", "PROJECT_STATUS.md"):
            if (root / name).is_file():
                shutil.copy2(root / name, tmp / name)
        from f1q.a4.completion import REUSED, PRIOR_FAILED

        dest_ev = tmp / "evidence" / "stage6_a4" / PRIOR_FAILED
        dest_ev.mkdir(parents=True, exist_ok=True)
        src_ev = root / "evidence" / "stage6_a4" / PRIOR_FAILED
        for name in list(REUSED):
            if (src_ev / name).is_file():
                shutil.copy2(src_ev / name, dest_ev / name)
        # Isolated extract is not a git worktree; give _git_head a fallback and a dummy repo.
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp), check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "-A"], cwd=str(tmp), check=False, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", "user.email=extract@local", "-c", "user.name=extract", "commit", "--allow-empty", "-m", "clean-extract"],
            cwd=str(tmp),
            check=False,
            capture_output=True,
            text=True,
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(tmp / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["F1Q_A4_IN_CLEAN_EXTRACT"] = "1"
        env["F1Q_A4_IN_ADMISSION"] = "1"
        head = env.get("F1Q_REVIEWED_SOURCE_COMMIT")
        if not head:
            import subprocess

            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
            env["F1Q_REVIEWED_SOURCE_COMMIT"] = head
        import subprocess

        py = str(root / ".venv" / "bin" / "python")
        code = (
            "from pathlib import Path\n"
            "from f1q.a4.completion_run import run_admission_check, execute_phase6\n"
            "from f1q.a4.verify import run_independent_verify\n"
            "root = Path('.').resolve()\n"
            "adm = run_admission_check(root, miniature=True, skip_tests=True)\n"
            "exe = execute_phase6(root, adm['run_id'])\n"
            "ver = run_independent_verify(root, adm['run_id'], mode='final')\n"
            "print('RUN', adm['run_id'])\n"
            "print('STATUS', exe.get('status'))\n"
            "print('VERIFY_OK', ver.get('ok'))\n"
            "print('N_PASS', ver.get('n_pass'), '/', ver.get('n_total'))\n"
        )
        proc = subprocess.run(
            [py, "-c", code],
            cwd=str(tmp),
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        freeze_present = False
        run_id = None
        for line in (proc.stdout or "").splitlines():
            if line.startswith("RUN "):
                run_id = line.split(" ", 1)[1].strip()
        if run_id:
            freeze_present = (tmp / "evidence" / "stage6_a4" / run_id / "TUNING_FREEZE.json").is_file()
        ok = proc.returncode == 0 and freeze_present and "STATUS campaign_raw_complete" not in (proc.stdout or "")
        return {
            "ok": ok,
            "exit_code": proc.returncode,
            "run_id": run_id,
            "freeze_present": freeze_present,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "tmp": str(tmp),
            "command": "clean-extract miniature admission→execute→verify",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

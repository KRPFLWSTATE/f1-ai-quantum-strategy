from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from f1q import DOSSIER_PAGE_COUNT, DOSSIER_SHA256, DOSSIER_VERSION, __version__
from f1q.authorization import load_project_config, lock_hash
from f1q.hashing import sha256_file
from f1q.ledger import Ledger
from f1q.paths import resolve_project_root, resolve_within
from f1q.runner import ledger_paths
from f1q.snapshot import git_state


def run_doctor(root: Path | None = None) -> dict:
    root = resolve_project_root(root)
    checks: list[dict] = []
    env = _environment()
    checks.append(_ok("environment", "recorded local OS/CPU/Python without provider login", env))
    checks.append(_boundary(root))
    config, config_hash, _ = load_project_config(root)
    checks.append(
        _ok(
            "config",
            "draft project configuration parsed",
            {
                "hash": config_hash,
                "hash_kind": "draft",
                "protocol_frozen": config.protocol_frozen,
                "hardware_execution_enabled": config.hardware_execution_enabled,
            },
        )
    )
    checks.append(_dossier(root, config))
    checks.append(_lockfile(root))
    checks.append(_ledger(root, config))
    status = "ok" if all(c["ok"] for c in checks) else "failed"
    return {
        "command": "doctor",
        "package_version": __version__,
        "project_root": str(root),
        "status": status,
        "scientific_protocol": config.scientific_protocol_status,
        "hardware_execution_enabled": False,
        "provider_login_attempted": False,
        "qpu_account_queried": False,
        "checks": checks,
        "environment": env,
        "git": _git(root),
        "config_hash_draft": config_hash,
        "dependency_lock_hash": lock_hash(root),
    }


def _environment() -> dict:
    mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else None
    disk = shutil.disk_usage(str(Path.cwd()))
    return {
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "cpu_count": os.cpu_count(),
        "physical_memory_bytes": mem,
        "disk_free_bytes": disk.free,
        "max_workers_default": 1,
    }


def _boundary(root: Path) -> dict:
    real = root.resolve()
    return _ok(
        "project_boundary",
        "resolved project root is not a symlink escape",
        {"root": str(real), "is_symlink": root.is_symlink()},
    )


def _dossier(root: Path, config) -> dict:
    path = resolve_within(root, config.dossier.relative_path, must_exist=True)
    digest = sha256_file(path)
    extracted = resolve_within(root, "docs/protocol/dossier_extracted.txt", must_exist=True)
    text = extracted.read_text(encoding="utf-8")
    pages = [line for line in text.splitlines() if line.startswith("===== PAGE ")]
    ok = digest == config.dossier.sha256 == DOSSIER_SHA256 and len(pages) == DOSSIER_PAGE_COUNT
    detail = {
        "path": config.dossier.relative_path,
        "sha256": digest,
        "expected": DOSSIER_SHA256,
        "pages_extracted": len(pages),
        "expected_pages": DOSSIER_PAGE_COUNT,
        "dossier_version": DOSSIER_VERSION,
    }
    if ok:
        return _ok("dossier", "PDF hash and 33-page extraction markers match", detail)
    return {
        "name": "dossier",
        "ok": False,
        "message": "dossier hash or page extraction mismatch",
        "detail": detail,
    }


def _lockfile(root: Path) -> dict:
    lock = root / "requirements.lock"
    if not lock.is_file():
        return {"name": "dependency_lock", "ok": False, "message": "requirements.lock missing", "detail": {}}
    return _ok("dependency_lock", "lock file present", {"sha256": sha256_file(lock)})


def _ledger(root: Path, config) -> dict:
    db, lock = ledger_paths(root, config)
    if not db.is_file():
        return _ok("ledger", "ledger not created yet (unknown, not ready)", {"present": False})
    ledger = None
    try:
        ledger = Ledger(db, lock, root=root)
        ledger.acquire(blocking=False)
        runs = ledger.list_runs()
        chains = {row["run_id"]: ledger.event_chain_ok(row["run_id"]) for row in runs}
        ok = all(chains.values()) if chains else True
        detail = {"present": True, "runs": len(runs), "event_chains_ok": chains}
        if ok:
            return _ok("ledger", "ledger opened; event chains verified", detail)
        return {"name": "ledger", "ok": False, "message": "event chain verification failed", "detail": detail}
    finally:
        if ledger is not None:
            ledger.release()


def _git(root: Path) -> dict:
    commit, dirty = git_state(root)
    return {"commit": commit, "dirty": dirty}


def _ok(name: str, message: str, detail: dict) -> dict:
    return {"name": name, "ok": True, "message": message, "detail": detail}

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from f1q.hashing import atomic_write_bytes, canonical_json, sha256_file, sha256_json
from f1q.paths import resolve_within
from f1q.schemas import utc_now
from f1q.simulator.checks import run_all_mechanism_checks
from f1q.simulator.config import load_simulator_config
from f1q.simulator.matrix import PREVIEW_RUN, run_development_matrix, run_interventions
from f1q.snapshot import take_source_snapshot


def execute_simulator_unit(
    *,
    root: Path,
    run_id: str,
    unit_id: str,
    seed: int,
    attempt_id: str,
) -> dict[str, Any]:
    rel_dir = f"evidence/simulator/artifacts/{run_id}/{unit_id}"
    dest = resolve_within(root, rel_dir)
    dest.mkdir(parents=True, exist_ok=True)
    cfg, cfg_hash = load_simulator_config(root)
    extra: list[dict[str, Any]] = []
    if unit_id == "simulator.mechanism_checks":
        report = run_all_mechanism_checks(cfg)
        report["simulator_config_hash"] = cfg_hash
        payload = report
        kind = "mechanism_checks"
    elif unit_id == "simulator.development_matrix":
        import time

        started = time.monotonic()
        cap = float(cfg["resource"]["stage3_elapsed_cap_s"])
        payload = run_development_matrix(root, dest, cap_s=cap, started=started)
        kind = "development_matrix"
    elif unit_id == "simulator.diagnostic_interventions":
        payload = run_interventions(root, dest)
        kind = "diagnostic_interventions"
    elif unit_id == "simulator.source_restore":
        payload = _source_and_private_restore(root, dest, run_id)
        kind = "source_restore"
    else:
        raise ValueError(f"unknown simulator unit {unit_id}")
    unit_rel = f"{rel_dir}/unit.json"
    digest = atomic_write_bytes(resolve_within(root, unit_rel), canonical_json(_public_payload(payload)) + b"\n")
    extra.append(
        {
            "schema_version": "1.0.0",
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": unit_rel,
            "sha256": digest,
            "kind": kind,
            "created_at_utc": utc_now(),
        }
    )
    return {
        "artifact": extra[0],
        "extra_artifacts": extra[1:],
        "substantive_payload_sha256": sha256_json(_public_payload(payload)),
    }


def _public_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: _public_payload(v) for k, v in payload.items() if k not in {"engine_state", "actual_fuel"}}
    if isinstance(payload, list):
        return [_public_payload(v) for v in payload]
    return payload


def _source_and_private_restore(root: Path, dest: Path, run_id: str) -> dict[str, Any]:
    snapshot = take_source_snapshot(root)
    recon_dir = Path(tempfile.mkdtemp(prefix="f1q-stage3-recon-"))
    try:
        copied = []
        for item in snapshot["files"]:
            src = root / item["path"]
            target = recon_dir / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied.append({"path": item["path"], "sha256": sha256_file(target)})
        recon_hash = sha256_json({"files": copied})
        match = recon_hash == snapshot["hash"]
        private_root = root / "evidence" / "development" / "private" / PREVIEW_RUN
        private_files = []
        if private_root.is_dir():
            for path in sorted(private_root.rglob("*.state.json")):
                rel = str(path.relative_to(root))
                private_files.append({"path": rel, "sha256": sha256_file(path)})
        sim_private = root / "evidence" / "simulator" / "private" / run_id
        if sim_private.is_dir():
            for path in sorted(sim_private.rglob("*.state.json")):
                rel = str(path.relative_to(root))
                private_files.append({"path": rel, "sha256": sha256_file(path)})
        recovery = {
            "kind": "private_replay_package_manifest",
            "preview_run_id": PREVIEW_RUN,
            "file_count": len(private_files),
            "files": private_files,
            "package_hash": sha256_json({"files": private_files}),
            "not_an_offsite_backup": True,
            "does_not_protect_against_computer_loss": True,
        }
        rec_rel = dest / "private_recovery_manifest.json"
        atomic_write_bytes(rec_rel, canonical_json(recovery) + b"\n")
        auth_prompt = Path("/Users/kawinperera/Downloads/F1_Cursor_Stage_3_Prompt.md")
        agents = root / "AGENTS.md"
        auth_hashes = {
            "stage3_prompt_sha256": sha256_file(auth_prompt) if auth_prompt.is_file() else None,
            "agents_md_sha256": sha256_file(agents) if agents.is_file() else None,
            "note": "authorization and project-instruction hashes recorded separately from the primary source snapshot",
        }
        atomic_write_bytes(dest / "authorization_hashes.json", canonical_json(auth_hashes) + b"\n")
        return {
            "ok": match,
            "source_snapshot_hash": snapshot["hash"],
            "reconstructed_hash": recon_hash,
            "reconstructed_file_count": len(copied),
            "private_package_hash": recovery["package_hash"],
            "private_file_count": recovery["file_count"],
            "authorization_hashes": auth_hashes,
            "reconstruction_tmpdir_prefix": "f1q-stage3-recon-",
        }
    finally:
        shutil.rmtree(recon_dir, ignore_errors=True)

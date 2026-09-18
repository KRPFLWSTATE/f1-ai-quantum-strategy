from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from f1q.hashing import atomic_write_bytes, canonical_json, sha256_json
from f1q.paths import resolve_within
from f1q.schemas import parse_checkpoint, utc_now


def execute_unit(
    *,
    root: Path,
    run_id: str,
    unit_id: str,
    seed: int,
    attempt_id: str,
) -> dict[str, Any]:
    if unit_id == "bootstrap.checkpoint_fixture":
        return _validate_checkpoint(root, run_id, unit_id, seed, attempt_id)
    if unit_id == "bootstrap.artifact_roundtrip":
        return _write_artifact(root, run_id, unit_id, seed, attempt_id)
    if unit_id == "bootstrap.checksum_verify":
        return _verify_checksums(root, run_id, unit_id, seed, attempt_id)
    raise ValueError(f"unknown bootstrap unit {unit_id}")


def _validate_checkpoint(root: Path, run_id: str, unit_id: str, seed: int, attempt_id: str) -> dict[str, Any]:
    path = resolve_within(root, "fixtures/fictional_checkpoint.json", must_exist=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = parse_checkpoint(data)
    payload = {
        "unit_id": unit_id,
        "seed": seed,
        "checkpoint_id": checkpoint.checkpoint_id,
        "fixture_kind": checkpoint.fixture_kind,
        "not_a_scientific_observation": True,
        "split": checkpoint.split,
        "car_ids": [car.car_id for car in checkpoint.cars],
    }
    substantive = sha256_json(payload)
    artifact_rel = f"evidence/bootstrap/artifacts/{run_id}/{unit_id}.json"
    artifact_path = resolve_within(root, artifact_rel)
    envelope = {
        "payload": payload,
        "substantive_sha256": substantive,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "written_at_utc": utc_now(),
    }
    digest = atomic_write_bytes(artifact_path, canonical_json(envelope) + b"\n")
    return {
        "substantive_payload_sha256": substantive,
        "artifact": {
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": artifact_rel,
            "sha256": digest,
            "kind": "setup_fixture_checkpoint_validation",
            "created_at_utc": utc_now(),
        },
    }


def _write_artifact(root: Path, run_id: str, unit_id: str, seed: int, attempt_id: str) -> dict[str, Any]:
    body = f"f1q-bootstrap-artifact:{seed}:setup_fixture"
    payload = {
        "unit_id": unit_id,
        "seed": seed,
        "body": body,
        "not_a_scientific_observation": True,
    }
    substantive = sha256_json(payload)
    artifact_rel = f"evidence/bootstrap/artifacts/{run_id}/{unit_id}.json"
    artifact_path = resolve_within(root, artifact_rel)
    envelope = {
        "payload": payload,
        "substantive_sha256": substantive,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "written_at_utc": utc_now(),
    }
    digest = atomic_write_bytes(artifact_path, canonical_json(envelope) + b"\n")
    return {
        "substantive_payload_sha256": substantive,
        "artifact": {
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": artifact_rel,
            "sha256": digest,
            "kind": "setup_fixture_artifact",
            "created_at_utc": utc_now(),
        },
    }


def _verify_checksums(root: Path, run_id: str, unit_id: str, seed: int, attempt_id: str) -> dict[str, Any]:
    from f1q.hashing import sha256_file
    from f1q.errors import IntegrityError

    art_dir = resolve_within(root, f"evidence/bootstrap/artifacts/{run_id}", must_exist=True)
    verified = []
    for path in sorted(art_dir.glob("*.json")):
        if path.name.startswith(unit_id):
            continue
        digest = sha256_file(path)
        verified.append({"path": str(path.relative_to(root)), "sha256": digest})
    if len(verified) < 1:
        raise IntegrityError("checksum unit found no prior artifacts to verify")
    payload = {
        "unit_id": unit_id,
        "seed": seed,
        "verified": verified,
        "not_a_scientific_observation": True,
    }
    substantive = sha256_json(payload)
    artifact_rel = f"evidence/bootstrap/artifacts/{run_id}/{unit_id}.json"
    artifact_path = resolve_within(root, artifact_rel)
    envelope = {
        "payload": payload,
        "substantive_sha256": substantive,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "written_at_utc": utc_now(),
    }
    digest = atomic_write_bytes(artifact_path, canonical_json(envelope) + b"\n")
    return {
        "substantive_payload_sha256": substantive,
        "artifact": {
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": artifact_rel,
            "sha256": digest,
            "kind": "setup_fixture_checksum_verify",
            "created_at_utc": utc_now(),
        },
    }

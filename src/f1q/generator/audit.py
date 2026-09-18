from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from f1q.generator.config import GeneratorConfigFile, cartesian_family_ids
from f1q.generator.validate import structural_errors
from f1q.hashing import sha256_file, sha256_json
from f1q.paths import resolve_within

SCIENTIFIC = {"training", "tuning", "calibration", "test", "shift"}


def audit_spec_directory(
    root: Path,
    specs_dir: str | Path,
    config: GeneratorConfigFile,
    *,
    generator_config_hash: str,
    source_snapshot_hash: str | None = None,
) -> dict[str, Any]:
    """Recompute membership from serialized specs. Does not ask the generator for expected totals."""
    directory = resolve_within(root, specs_dir, must_exist=True)
    files = sorted(path for path in directory.rglob("*.spec.json") if path.is_file())
    specs = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    block_ids = [spec["block_id"] for spec in specs]
    episode_ids = [spec["episode_id"] for spec in specs]
    spec_ids = [spec["spec_id"] for spec in specs]
    families = [spec["family_id"] for spec in specs]
    partitions = [spec["partition"] for spec in specs]
    regimes = [spec["checkpoint_request"]["requested_regime"] for spec in specs]
    unique_blocks = sorted(set(block_ids))
    unique_episodes = sorted(set(episode_ids))
    unique_specs = sorted(set(spec_ids))
    schema_rejections = []
    for spec in specs:
        for code, reason in structural_errors(spec):
            schema_rejections.append({"spec_id": spec.get("spec_id"), "code": code, "reason": reason})
    scientific_leaks = [spec_id for spec_id, part in zip(spec_ids, partitions) if part in SCIENTIFIC]
    configured_preview = dict(config.development_preview)
    fingerprints = sorted(spec.get("substantive_fingerprint", "") for spec in specs)
    family_counts = dict(Counter(families))
    regime_counts = dict(Counter(regimes))
    block_regime = {}
    for spec in specs:
        block_regime.setdefault(spec["block_id"], Counter())[spec["checkpoint_request"]["requested_regime"]] += 1
    per_block_balance = {
        block_id: {"SC": counts.get("SC", 0), "VSC": counts.get("VSC", 0)}
        for block_id, counts in block_regime.items()
    }
    audit = {
        "kind": "independent_development_audit",
        "specs_dir": str(directory.relative_to(root.resolve()) if directory.is_absolute() else directory),
        "configured_development_preview": configured_preview,
        "realized": {
            "spec_files": len(files),
            "blocks": len(unique_blocks),
            "specifications": len(unique_specs),
            "episodes": len(unique_episodes),
            "families": len(set(families)),
            "SC": regime_counts.get("SC", 0),
            "VSC": regime_counts.get("VSC", 0),
        },
        "family_counts": family_counts,
        "declared_family_ids": cartesian_family_ids(),
        "partitions": dict(Counter(partitions)),
        "unique_block_ids": unique_blocks,
        "duplicate_block_rows": len(block_ids) - len(unique_blocks),
        "duplicate_episode_ids": len(episode_ids) - len(unique_episodes),
        "duplicate_spec_ids": len(spec_ids) - len(unique_specs),
        "scientific_split_membership": scientific_leaks,
        "per_block_sc_vsc": per_block_balance,
        "schema_rejections": schema_rejections,
        "assumption_provenance": _assumption_table(specs),
        "source_snapshot_hash": source_snapshot_hash,
        "generator_config_hash": generator_config_hash,
        "deterministic_fingerprints": fingerprints,
        "pending_simulator_validation": all(spec.get("awaiting_simulator_validation") for spec in specs),
        "validated_race_checkpoints": 0,
        "reserved_partitions_materialized": False,
        "file_sha256": {str(path.relative_to(root)): sha256_file(path) for path in files},
        "audit_input_hash": sha256_json([sha256_file(path) for path in files]),
    }
    audit["ok"] = (
        audit["realized"]["blocks"] == configured_preview.get("blocks")
        and audit["realized"]["specifications"] == configured_preview.get("blocks") * configured_preview.get("episodes_per_block")
        and audit["realized"]["families"] == 8
        and set(families) == set(cartesian_family_ids())
        and audit["realized"]["SC"] == 32
        and audit["realized"]["VSC"] == 32
        and not scientific_leaks
        and not schema_rejections
        and audit["duplicate_episode_ids"] == 0
        and audit["duplicate_spec_ids"] == 0
        and all(bal["SC"] == 4 and bal["VSC"] == 4 for bal in per_block_balance.values())
        and audit["pending_simulator_validation"]
        and audit["validated_race_checkpoints"] == 0
    )
    return audit


def _assumption_table(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for spec in specs:
        for item in spec.get("assumptions") or []:
            key = (item.get("field"), item.get("note"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
        pit = spec.get("block_parameters", {})
        key = ("green_pit_loss_includes_service_and_transit", str(pit.get("green_pit_loss_includes_service_and_transit")))
        if key not in seen:
            seen.add(key)
            rows.append(
                {
                    "field": "green_pit_loss_s",
                    "status": "assumed",
                    "note": "combined pit-lane transit and stationary service versus a green flying lap",
                }
            )
    return rows

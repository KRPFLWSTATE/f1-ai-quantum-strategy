from __future__ import annotations

from typing import Any

from f1q.errors import AuthorizationError
from f1q.generator.config import GeneratorConfigFile, cartesian_family_ids, sorted_families
from f1q.generator.streams import block_id, identity_digest

MAIN_PARTITIONS = ("training", "tuning", "calibration", "test")
TEST_BLOCK_CHOICES = tuple(range(80, 161, 8))


def planned_counts(*, test_blocks: int, include_shift: bool) -> dict[str, Any]:
    if test_blocks not in TEST_BLOCK_CHOICES:
        raise AuthorizationError(
            "test planned blocks must be a multiple of eight from the dossier floor 80 through 160 inclusive"
        )
    training, tuning, calibration = 120, 16, 24
    shift = 40 if include_shift else 0
    blocks = training + tuning + calibration + test_blocks + shift
    checkpoints = blocks * 8
    return {
        "training_blocks": training,
        "training_checkpoints_planned": 960,
        "tuning_blocks": tuning,
        "tuning_checkpoints_planned": 128,
        "calibration_blocks": calibration,
        "calibration_checkpoints_planned": 192,
        "test_blocks": test_blocks,
        "test_checkpoints_planned": test_blocks * 8,
        "shift_blocks": shift,
        "shift_checkpoints_planned": shift * 8,
        "main_blocks_without_shift": training + tuning + calibration + test_blocks,
        "main_checkpoints_without_shift": (training + tuning + calibration + test_blocks) * 8,
        "total_blocks_including_shift": blocks if include_shift else training + tuning + calibration + test_blocks,
        "total_checkpoints_including_shift": checkpoints if include_shift else (training + tuning + calibration + test_blocks) * 8,
        "materialized": False,
        "completed_counts": None,
        "completed_counts_reason": "Stage 2 stores planned counts only; reserved partitions are not materialized.",
    }


def build_split_plan(config: GeneratorConfigFile, *, test_blocks: int = 80) -> dict[str, Any]:
    families = [fam.id for fam in sorted_families(config)]
    if families != cartesian_family_ids():
        raise AuthorizationError("split plan requires the eight declared families")
    per_family = {
        "training": int(config.splits["training"]["per_family"]),
        "tuning": int(config.splits["tuning"]["per_family"]),
        "calibration": int(config.splits["calibration"]["per_family"]),
        "test": test_blocks // 8,
        "shift": int(config.splits["shift"]["draft_per_family"]),
    }
    if test_blocks == 80 and per_family["test"] != config.splits["test"]["floor_per_family"]:
        raise AuthorizationError("test floor per-family count mismatch")
    if test_blocks == 160 and per_family["test"] != config.splits["test"]["maximum_per_family"]:
        raise AuthorizationError("test maximum per-family count mismatch")
    if test_blocks % 8 != 0:
        raise AuthorizationError("test-block increases must preserve the multiple-of-eight family balance")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for partition in (*MAIN_PARTITIONS, "shift"):
        for family_id in families:
            for index in range(per_family[partition]):
                ident = block_id(namespace="scientific", partition=partition, family_id=family_id, index=index)
                if ident in seen:
                    raise AuthorizationError(f"duplicate planned identity {ident}")
                seen.add(ident)
                record = {
                    "block_id": ident,
                    "partition": partition,
                    "family_id": family_id,
                    "index_in_family_partition": index,
                    "planned_episodes": 8,
                    "planned_sc": 4,
                    "planned_vsc": 4,
                    "materialized": False,
                    "identity_digest": identity_digest(
                        {
                            "block_id": ident,
                            "partition": partition,
                            "family_id": family_id,
                            "generator_version": config.generator_version,
                        }
                    ),
                }
                if partition == "shift":
                    record["allocation_status"] = "draft_unfrozen"
                    record["not_a_finalized_shift_study"] = True
                records.append(record)
    counts = planned_counts(test_blocks=test_blocks, include_shift=True)
    return {
        "kind": "split_plan",
        "generator_version": config.generator_version,
        "test_blocks": test_blocks,
        "families": families,
        "per_family": per_family,
        "planned_counts": counts,
        "shift_panel": {
            "status": config.splits["shift"]["allocation_status"],
            "planned_blocks": config.splits["shift"]["blocks"],
            "draft_per_family": config.splits["shift"]["draft_per_family"],
            "predeclared_shift_schema": config.splits["shift"]["predeclared_shift_schema"],
            "not_a_finalized_shift_study": True,
            "must_freeze_before_use": True,
        },
        "records": records,
        "inferential_unit": "block",
        "note": (
            "Distinct IDs do not establish statistical independence. Shared block "
            "parameters and stream construction are retained. Do not materialize."
        ),
    }

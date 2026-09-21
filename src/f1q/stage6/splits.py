"""Phase 6 calibration cohort — isolated from training/tuning/final-test."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json
from f1q.stage5.splits import build_phase5_splits

CALIB_PER_FAMILY = 3


def _block_id(family_id: str, index: int) -> str:
    return f"phase6.calib.{family_id}.{index:04d}"


def _seed_for(block_id: str, salt: str) -> int:
    h = hashlib.sha256(f"{salt}:{block_id}".encode()).hexdigest()
    return int(h[:16], 16) % (2**31 - 1)


def build_calibration_splits(
    *,
    source_hash: str,
    phase5_source_hash: str,
    salt: str = "phase6.calibration.v1",
) -> dict[str, Any]:
    """Create 24 calibration blocks (3/family) with no overlap vs Phase 5 train/tune.

    Final-test / shift / reserved scientific partitions are NOT materialized.
    Calibration IDs use a distinct namespace (phase6.calib.*) so they cannot collide
    with phase5.* training/tuning IDs by construction.
    """
    families = cartesian_family_ids()
    assert len(families) == 8
    phase5 = build_phase5_splits(source_hash=phase5_source_hash)
    forbidden_ids = {
        b["block_id"]
        for b in phase5["anchors"] + phase5["training_extra"] + phase5["tuning"]
    }

    calibration: list[dict[str, Any]] = []
    for fam in families:
        for i in range(CALIB_PER_FAMILY):
            bid = _block_id(fam, i)
            if bid in forbidden_ids:
                raise RuntimeError(f"calibration id collided with Phase 5: {bid}")
            calibration.append(
                {
                    "block_id": bid,
                    "partition": "calibration",
                    "family_id": fam,
                    "index": i,
                    "seed": _seed_for(bid, salt),
                    "cases": [
                        {
                            "case_id": f"{bid}.SC",
                            "regime": "SC",
                            "microcase": "force_branching",
                            "seed_offset": 0,
                            "note": "restricted-menu SC-labelled branching case",
                        },
                        {
                            "case_id": f"{bid}.VSC",
                            "regime": "VSC",
                            "microcase": "standard",
                            "seed_offset": 10007,
                            "note": "restricted-menu VSC-labelled shared-duration case",
                        },
                    ],
                }
            )

    calib_ids = [b["block_id"] for b in calibration]
    case_ids = [c["case_id"] for b in calibration for c in b["cases"]]
    overlap = sorted(set(calib_ids) & forbidden_ids)
    audit = {
        "n_families": 8,
        "calibration_blocks": len(calibration),
        "expected_blocks": 24,
        "cases_total": len(case_ids),
        "expected_cases": 48,
        "per_family": CALIB_PER_FAMILY,
        "overlap_with_phase5_train_tune": overlap,
        "final_test_accessed": False,
        "final_test_materialized": False,
        "shift_materialized": False,
        "source_hash": source_hash,
        "phase5_source_hash": phase5_source_hash,
        "salt": salt,
        "split_hash": sha256_json({"ids": calib_ids, "cases": case_ids, "salt": salt}),
        "ok": len(calibration) == 24 and not overlap and len(case_ids) == 48,
    }
    return {"calibration": calibration, "audit": audit, "phase5_forbidden_n": len(forbidden_ids)}

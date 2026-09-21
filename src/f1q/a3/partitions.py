"""Fresh A3 partitions: deterministic fingerprints; final-test sealed by count+hash only."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json

ANCHORS = 24
TRAIN = 120
TUNE = 80
CALIB = 24
FINALTEST = 80  # registered, unmaterialised
SALT = "a3.partitions.v1.20260921"


def _bid(kind: str, family_id: str, index: int) -> str:
    return f"a3.{kind}.{family_id}.{index:04d}"


def _seed(block_id: str) -> int:
    return int(hashlib.sha256(f"{SALT}:{block_id}".encode()).hexdigest()[:16], 16) % (2**31 - 1)


def _blocks(kind: str, per_family: int) -> list[dict[str, Any]]:
    fams = cartesian_family_ids()
    assert len(fams) == 8
    rows = []
    for fam in fams:
        for i in range(per_family):
            bid = _bid(kind, fam, i)
            rows.append(
                {
                    "block_id": bid,
                    "partition": kind,
                    "family_id": fam,
                    "index": i,
                    "seed": _seed(bid),
                    "regimes": ["SC", "VSC"],
                    "parent_block_independent": True,
                }
            )
    return rows


def build_a3_partitions() -> dict[str, Any]:
    anchors = _blocks("anchor", ANCHORS // 8)
    train = _blocks("train", TRAIN // 8)
    tune = _blocks("tune", TUNE // 8)
    calib = _blocks("calib", CALIB // 8)
    finaltest_ids = [_bid("finaltest", fam, i) for fam in cartesian_family_ids() for i in range(FINALTEST // 8)]
    all_open = [b["block_id"] for b in anchors + train + tune + calib]
    overlap = set(all_open) & set(finaltest_ids)
    a2_forbidden_prefix = ("phase5.", "phase6.calib.")
    leaked_a2 = [b for b in all_open if b.startswith(a2_forbidden_prefix)]
    return {
        "salt": SALT,
        "planned": {
            "anchors": ANCHORS,
            "training": TRAIN,
            "tuning": TUNE,
            "calibration": CALIB,
            "final_test_registered": FINALTEST,
        },
        "anchors": anchors,
        "train": train,
        "tune": tune,
        "calib": calib,
        "final_test": {
            "n_blocks": len(finaltest_ids),
            "id_sha256": sha256_json(finaltest_ids),
            "outcomes_materialised": False,
            "outcomes_opened": False,
            "note": "IDs and hash commitment only; specs and outcomes unmaterialised",
        },
        "n_open_ids": len(all_open),
        "overlap_open_vs_finaltest": sorted(overlap),
        "a2_id_reuse": leaked_a2,
        "sc_vsc_balanced_within_parent": True,
        "parent_blocks_independent_units": True,
        "a2_calibration_cannot_confirm_a3": True,
        "ok": not overlap and not leaked_a2 and len(finaltest_ids) == FINALTEST,
    }


def reduced_execution_subset(plan: dict[str, Any], *, per_family: int = 1) -> dict[str, Any]:
    """Scientifically honest reduced subset when 45 min cannot fit full 224+."""

    def take(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by = {}
        for r in rows:
            by.setdefault(r["family_id"], []).append(r)
        out = []
        for fam, items in by.items():
            out.extend(items[:per_family])
        return out

    return {
        "anchors": take(plan["anchors"]),
        "train": take(plan["train"]),
        "tune": take(plan["tune"]),
        "calib": take(plan["calib"]),
        "shortfall": {
            "anchors": ANCHORS - 8 * per_family,
            "training": TRAIN - 8 * per_family,
            "tuning": TUNE - 8 * per_family,
            "calibration": CALIB - 8 * per_family,
            "reason": "aggregate local compute ceiling 45 min; machinery implements full plan",
            "phase7_implication": "Phase 7 must execute remaining blocks under freeze; do not relabel reduced as full",
        },
        "eight_family_balanced": True,
        "per_family": per_family,
    }

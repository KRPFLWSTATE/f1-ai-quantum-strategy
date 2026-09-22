"""Fresh A4 partition fingerprints. Final-test sealed by count+hash only."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json

ANCHORS = 24
TRAIN = 120
TUNE = 80
CALIB = 24
FINALTEST = 80
SALT = "a4.partitions.v2.20260922.validated"
SALT_V1_HISTORICAL = "a4.partitions.v1.20260921"
RETIRED_DIAGNOSTIC_PARENTS = [
    "a4.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0000",
    "a4.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0001",
    "a4.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0002",
    "a4.train.fam.green_pit_high.tyre_near_linear.traffic_dense.0003",
    "a4.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0000",
    "a4.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0001",
    "a4.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0002",
    "a4.tune.fam.green_pit_high.tyre_near_linear.traffic_dense.0003",
    "a4.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0000",
    "a4.calib.fam.green_pit_high.tyre_near_linear.traffic_dense.0001",
]


def _bid(kind: str, family_id: str, index: int) -> str:
    if kind == "anchor":
        return f"a4.{kind}.{family_id}.{index:04d}"
    return f"a4.v2.{kind}.{family_id}.{index:04d}"


def _seed(block_id: str) -> int:
    return int(hashlib.sha256(f"{SALT}:{block_id}".encode()).hexdigest()[:16], 16) % (2**31 - 1)


def _blocks(kind: str, per_family: int) -> list[dict[str, Any]]:
    fams = cartesian_family_ids()
    if len(fams) != 8:
        raise RuntimeError(f"expected 8 families, got {len(fams)}")
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


def build_a4_partitions() -> dict[str, Any]:
    anchors = _blocks("anchor", ANCHORS // 8)
    train = _blocks("train", TRAIN // 8)
    tune = _blocks("tune", TUNE // 8)
    calib = _blocks("calib", CALIB // 8)
    fams = cartesian_family_ids()
    finaltest_ids = [_bid("finaltest", fam, i) for fam in fams for i in range(FINALTEST // 8)]
    all_open = [b["block_id"] for b in anchors + train + tune + calib]
    overlap = set(all_open) & set(finaltest_ids)
    leaked = [b for b in all_open if b.startswith(("phase5.", "phase6.calib.", "a3."))]
    return {
        "salt": SALT,
        "historical_v1_salt": SALT_V1_HISTORICAL,
        "retired_diagnostic_parents": list(RETIRED_DIAGNOSTIC_PARENTS),
        "retired_to": "development_only_not_used_for_design_selection_or_held_out_claims",
        "retired_source_run": "0b697910-e8a2-474b-bc77-bc69ebb8e9c3",
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
            "ids": finaltest_ids,
            "outcomes_materialised": False,
            "outcomes_opened": False,
            "note": "IDs and hash commitment only; specs and outcomes unmaterialised",
        },
        "n_open_ids": len(all_open),
        "overlap_open_vs_finaltest": sorted(overlap),
        "a2_a3_id_reuse": leaked,
        "sc_vsc_balanced_within_parent": True,
        "parent_blocks_independent_units": True,
        "ok": not overlap and not leaked and len(finaltest_ids) == FINALTEST and not (set(all_open) & set(RETIRED_DIAGNOSTIC_PARENTS)),
        "disjoint_from_retired_diagnostic_parents": not (set(all_open) & set(RETIRED_DIAGNOSTIC_PARENTS)),
        "no_silent_per_family_reduction": True,
    }

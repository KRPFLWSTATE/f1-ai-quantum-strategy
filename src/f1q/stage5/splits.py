"""Phase 5 training/tuning split construction — no calib/eval/test materialisation."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json

# 24 anchors (3/family) + 120 further training (15/family) + 80 tuning (10/family) = 224
ANCHORS_PER_FAMILY = 3
TRAIN_EXTRA_PER_FAMILY = 15
TUNING_PER_FAMILY = 10


def _block_id(kind: str, family_id: str, index: int) -> str:
    return f"phase5.{kind}.{family_id}.{index:04d}"


def _seed_for(block_id: str, salt: str) -> int:
    h = hashlib.sha256(f"{salt}:{block_id}".encode()).hexdigest()
    return int(h[:16], 16) % (2**31 - 1)


def build_phase5_splits(*, source_hash: str, generator_version: str = "2.0.0") -> dict[str, Any]:
    families = cartesian_family_ids()
    assert len(families) == 8
    anchors: list[dict[str, Any]] = []
    train_extra: list[dict[str, Any]] = []
    tuning: list[dict[str, Any]] = []
    for fam in families:
        for i in range(ANCHORS_PER_FAMILY):
            bid = _block_id("anchor", fam, i)
            anchors.append(
                {
                    "block_id": bid,
                    "partition": "training_anchor",
                    "family_id": fam,
                    "index": i,
                    "seed": _seed_for(bid, source_hash),
                }
            )
        for i in range(TRAIN_EXTRA_PER_FAMILY):
            bid = _block_id("train", fam, i)
            train_extra.append(
                {
                    "block_id": bid,
                    "partition": "training",
                    "family_id": fam,
                    "index": i,
                    "seed": _seed_for(bid, source_hash),
                }
            )
        for i in range(TUNING_PER_FAMILY):
            bid = _block_id("tune", fam, i)
            tuning.append(
                {
                    "block_id": bid,
                    "partition": "tuning",
                    "family_id": fam,
                    "index": i,
                    "seed": _seed_for(bid, source_hash),
                }
            )

    all_ids = [b["block_id"] for b in anchors + train_extra + tuning]
    seeds = [b["seed"] for b in anchors + train_extra + tuning]
    overlap_failures = []
    if len(all_ids) != len(set(all_ids)):
        overlap_failures.append("duplicate_block_id")
    if len(seeds) != len(set(seeds)):
        # seeds may theoretically collide — check and record
        if len(seeds) != len(set(seeds)):
            overlap_failures.append("duplicate_seed")

    # Forbidden partitions never listed
    forbidden_touch = []
    for p in ("calibration", "evaluation", "test", "shift", "held_out"):
        if any(p in b["partition"] for b in anchors + train_extra + tuning):
            forbidden_touch.append(p)

    audit = {
        "n_families": 8,
        "anchors": len(anchors),
        "training_extra": len(train_extra),
        "training_total": len(anchors) + len(train_extra),
        "tuning": len(tuning),
        "total_blocks": len(all_ids),
        "expected_total": 224,
        "balanced_per_family": {
            "anchors": ANCHORS_PER_FAMILY,
            "training_extra": TRAIN_EXTRA_PER_FAMILY,
            "tuning": TUNING_PER_FAMILY,
        },
        "overlap_failures": overlap_failures,
        "forbidden_partition_access": forbidden_touch,
        "calib_eval_test_materialized": False,
        "source_hash": source_hash,
        "generator_version": generator_version,
        "split_hash": sha256_json({"ids": all_ids, "source_hash": source_hash}),
    }
    return {
        "anchors": anchors,
        "training_extra": train_extra,
        "tuning": tuning,
        "audit": audit,
    }


FORBIDDEN_FEATURE_KEYS = frozenset(
    {
        "exact_optimum",
        "optimum",
        "optimal_cost",
        "hidden_tau",
        "future_event",
        "final_outcome",
        "test_label",
        "test_result",
        "held_out_outcome",
    }
)


def assert_features_clean(features: dict[str, Any]) -> None:
    bad = FORBIDDEN_FEATURE_KEYS.intersection(features.keys())
    if bad:
        raise ValueError(f"forbidden leakage features: {sorted(bad)}")

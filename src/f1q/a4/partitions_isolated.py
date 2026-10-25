"""Fresh Design R split. Does not edit or replace the historical partition module."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from f1q.a4.isolation import spec_fingerprint
from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_json

SALT = "a4.partitions.v3.isolated.20261025.9a32a40a"
NAMESPACE = "a4.v3.iso"
TRAIN = 120
TUNE = 80
CALIB = 24
FINALTEST = 80


def _seed(block_id: str) -> int:
    return int(hashlib.sha256(f"{SALT}:{block_id}".encode()).hexdigest()[:16], 16) % (2**31 - 1)


def _bid(kind: str, family_id: str, index: int) -> str:
    return f"{NAMESPACE}.{kind}.{family_id}.{index:04d}"


def _rows(kind: str, per_family: int) -> list[dict[str, Any]]:
    families = cartesian_family_ids()
    if len(families) != 8:
        raise RuntimeError(f"expected 8 families, got {len(families)}")
    rows = []
    for fam in families:
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
                    "namespace": NAMESPACE,
                }
            )
    return rows


def build_isolated_partitions(exposed: dict[str, Any]) -> dict[str, Any]:
    """120/80/24 parents whose ids, seeds, and spec fingerprints miss the retired set."""
    train = _rows("train", TRAIN // 8)
    tune = _rows("tune", TUNE // 8)
    calib = _rows("calib", CALIB // 8)
    families = cartesian_family_ids()
    finaltest_ids = [_bid("finaltest", fam, i) for fam in families for i in range(FINALTEST // 8)]
    open_rows = train + tune + calib
    blocked_ids = set(exposed.get("block_ids") or [])
    blocked_seeds = {int(s) for s in exposed.get("seeds") or []}
    blocked_specs = set(exposed.get("spec_fingerprints") or [])
    collisions: list[str] = []
    spec_fps: list[str] = []
    for row in open_rows:
        if row["block_id"] in blocked_ids:
            collisions.append(f"id:{row['block_id']}")
        if int(row["seed"]) in blocked_seeds:
            collisions.append(f"seed:{row['block_id']}")
        if row["block_id"] in finaltest_ids or ".shift." in row["block_id"]:
            collisions.append(f"sealed:{row['block_id']}")
        for regime in ("SC", "VSC"):
            fp = spec_fingerprint(family_id=row["family_id"], seed=int(row["seed"]), index=int(row["index"]), regime=regime)
            spec_fps.append(fp)
            if fp in blocked_specs:
                collisions.append(f"spec:{row['block_id']}:{regime}")
    if len({r["block_id"] for r in open_rows}) != len(open_rows):
        collisions.append("duplicate_ids")
    if len({int(r["seed"]) for r in open_rows}) != len(open_rows):
        collisions.append("duplicate_seeds")
    if collisions:
        raise RuntimeError("isolated split collides with retired identities: " + ",".join(collisions[:12]))
    return {
        "salt": SALT,
        "namespace": NAMESPACE,
        "historical_partition_module_unchanged": True,
        "replaces_old_partition_files": False,
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
        "planned": {"training": TRAIN, "tuning": TUNE, "calibration": CALIB, "final_test_registered": FINALTEST},
        "block_ids": [r["block_id"] for r in open_rows],
        "seed_by_id": {r["block_id"]: int(r["seed"]) for r in open_rows},
        "spec_fingerprints": spec_fps,
        "n_train": len(train),
        "n_tune": len(tune),
        "n_calib": len(calib),
        "ok": True,
        "parent_blocks_independent_units": True,
        "sc_vsc_balanced_within_parent": True,
        "exclusion": {
            "exposed_block_ids": len(blocked_ids),
            "exposed_seeds": len(blocked_seeds),
            "exposed_spec_fingerprints": len(blocked_specs),
            "collisions": [],
        },
    }


def write_registry(root: Path, exposed: dict[str, Any]) -> dict[str, Any]:
    parts = build_isolated_partitions(exposed)
    payload = dict(parts)
    payload["registry_sha256"] = sha256_json({k: v for k, v in payload.items() if k != "registry_sha256"})
    path = root / "configs" / "design_r_isolated_registry.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lineage = root / "docs" / "DESIGN_R_ISOLATED_SPLIT_LINEAGE.md"
    lineage.write_text(
        "\n".join(
            [
                "# Design R isolated split lineage",
                "",
                "Prospective registry. No registered outcome has been opened under this namespace.",
                "",
                f"- Namespace: `{NAMESPACE}`",
                f"- Salt: `{SALT}`",
                f"- Parents: {TRAIN} train / {TUNE} tune / {CALIB} calibration",
                f"- Registry SHA-256: `{payload['registry_sha256']}`",
                "- Historical `src/f1q/a4/partitions.py` is not edited.",
                "- Exposed miniature parents, their seeds and specification fingerprints, retired diagnostic parents, anchors, and sealed final-test/shift identities are excluded.",
                "- Identifiers are not a rename of `a4.v2` seeds.",
                "- Final-test and shift outcomes are not materialised.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload

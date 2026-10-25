"""Measured artifact bytes. The historical 2_000_000-byte unit constant is not used as a gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.a4.world_store import write_world_chunk
from f1q.hashing import canonical_json

HISTORICAL_BYTES_PER_UNIT = 2_000_000
HISTORICAL_BYTES_PER_EVAL_WORLD = 200

SCIENTIFIC_RECORD_SCHEMA = {
    "schema": "design_r_scientific_record.v1",
    "frozen_before_outcomes": True,
    "stores_once": [
        "checkpoint_snapshot",
        "distribution_record",
        "paired_world_chunk",
    ],
    "stores_as_reference": ["operation_index_row", "manifest_pointer"],
    "paired_world_compression": "gzip compresslevel 6 via f1q.a4.world_store.write_world_chunk",
    "paired_world_lossless": True,
    "parity_traces_included": False,
    "fields_per_world_row": [
        "arrival_delay_s",
        "bank",
        "cache_hit",
        "changed_state",
        "checkpoint_time_race_s",
        "commit",
        "commitment_classification",
        "commitment_race_s",
        "evaluator",
        "event_ordering",
        "fallback",
        "fallback_plan",
        "fallback_reason",
        "late_vs_effective_end",
        "late_vs_registered_epoch",
        "legality",
        "loss",
        "nominal_budget_s",
        "not_proxy_qubo",
        "plan_hash",
        "registered_commitment_epoch_race_s",
        "selected_or_fallback_plan",
        "selected_plan",
        "stale",
        "team_loss",
        "timely",
        "trace_id",
        "world_seed",
    ],
}


def historical_storage_bytes(*, n_units: int, evaluation_worlds: int) -> int:
    """The expression previously used in six_hour.py. Reported, not used as the gate."""
    return int(n_units) * HISTORICAL_BYTES_PER_UNIT + int(evaluation_worlds) * HISTORICAL_BYTES_PER_EVAL_WORLD


def identity_ledger(units: list[dict[str, Any]]) -> dict[str, Any]:
    """Distinct objects. Repeated operation rows do not repeat a checkpoint snapshot."""
    checkpoints: set[str] = set()
    distributions: set[str] = set()
    chunks: dict[tuple[Any, ...], int] = {}
    operations = 0
    for unit in units:
        operations += 1
        checkpoints.add(str(unit.get("checkpoint_id")))
        distributions.add(
            "|".join(
                [
                    str(unit.get("checkpoint_id")),
                    str(unit.get("family_depth")),
                    str(unit.get("donor_policy")),
                    str(unit.get("policy_seed")),
                ]
            )
        )
        n_eval = int(unit.get("n_evaluation_worlds") or 0)
        if n_eval <= 0:
            continue
        key = (
            str(unit.get("checkpoint_id")),
            str(unit.get("option")),
            float(unit.get("budget_s") or 0.0),
            int(unit.get("policy_seed") or 0),
            str(unit.get("role")),
        )
        chunks[key] = max(chunks.get(key, 0), n_eval)
    return {
        "n_operation_rows": operations,
        "n_checkpoint_snapshots": len(checkpoints),
        "n_distribution_records": len(distributions),
        "n_world_chunks": len(chunks),
        "world_chunk_rows": sorted(chunks.values()),
        "checkpoint_ids": sorted(checkpoints),
        "chunk_keys": [list(key) for key in chunks],
    }


def _worst_world_row(template: dict[str, Any], index: int) -> dict[str, Any]:
    row = json.loads(json.dumps(template))
    row["world_seed"] = 900000 + index
    row["trace_id"] = f"synthetic-trace-{index:06d}"
    row["loss"] = float(index)
    ordering = list(row.get("event_ordering") or [])
    if ordering:
        extra = []
        for k in range(3):
            extra.append([float(index + k), "synthetic_event", f"car.synthetic.{k}", "{'note': 'measured worst-row padding'}"])
        row["event_ordering"] = ordering + extra
    return row


def measure_representative_bytes(root: Path) -> dict[str, Any]:
    """Serialize one real synthetic world chunk with the production compressor."""
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.a4.prepared import prepare_case

    dest = root / "evidence" / "tmp_storage_probe"
    dest.mkdir(parents=True, exist_ok=True)
    select_evaluation_backend("candidate")
    try:
        pc = prepare_case(
            family_id="fam.green_pit_low.tyre_nonlinear.traffic_dense",
            block_id="engfix.storage.probe",
            regime="SC",
            partition="development",
            index=0,
            seed=61001,
            n_planning=2,
            n_evaluation=2,
        )
        worlds = evaluate_candidates_on_bank(
            pc.spec_with_budget(30),
            pc.checkpoint_blob,
            [{"plan": pc.legal_table[0]["plan"], "plan_hash": pc.legal_table[0]["plan_hash"]}],
            [910000 + i for i in range(8)],
            bank=EVALUATION_BANK,
            arrival_delay_s=0.02,
            commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
            cache={},
            spec_hash=pc.spec_hash,
            checkpoint_hash=pc.checkpoint_hash,
            nominal_budget_s=30.0,
        )
        rows = list((worlds.get("worlds") or {}).get(pc.legal_table[0]["plan_hash"]) or [])
        if len(rows) < 1:
            raise RuntimeError("storage probe produced no world rows")
        template = max(rows, key=lambda row: len(canonical_json(row)))
        samples = {}
        for n in (8, 32):
            synthetic = [_worst_world_row(template, i) for i in range(n)]
            meta = write_world_chunk(dest, synthetic, prefix=f"engfix.storage.n{n}")
            samples[str(n)] = {
                "n_rows": n,
                "raw_bytes": int(meta["raw_bytes"]),
                "gzip_bytes": int(meta["gzip_bytes"]),
                "bytes_per_row_gzip": int(meta["gzip_bytes"]) / n,
            }
        checkpoint_bytes = len(canonical_json(pc.checkpoint_blob))
        operation_row = {
            "unit_id": "engfix.storage.op",
            "checkpoint_id": pc.case_id,
            "checkpoint_sha256": pc.checkpoint_hash,
            "n_evaluation_worlds": 16,
            "world_chunk_sha256": samples["8"] and "reference",
        }
        operation_bytes = len(canonical_json(operation_row))
        distribution_bytes = len(canonical_json({"key": "engfix.dist", "gammas": [0.1, 0.2], "betas": [0.2, 0.3], "checkpoint": pc.checkpoint_hash}))
        manifest_bytes = len(canonical_json({"schema": SCIENTIFIC_RECORD_SCHEMA["schema"], "n": 1}))
    finally:
        select_evaluation_backend("legacy")
    per_row = max(samples["8"]["bytes_per_row_gzip"], samples["32"]["bytes_per_row_gzip"])
    return {
        "samples": samples,
        "conservative_gzip_bytes_per_world_row": per_row,
        "checkpoint_snapshot_bytes": checkpoint_bytes,
        "operation_reference_bytes": operation_bytes,
        "distribution_record_bytes": distribution_bytes,
        "manifest_bytes": manifest_bytes,
        "production_serializer": "f1q.a4.world_store.write_world_chunk gzip compresslevel 6",
        "parity_traces_excluded": True,
    }


def project_storage(identities: dict[str, Any], measured: dict[str, Any], *, n_units: int, evaluation_worlds: int) -> dict[str, Any]:
    per_row = float(measured["conservative_gzip_bytes_per_world_row"])
    world_bytes = int(sum(int(per_row * int(n) + 64) for n in identities["world_chunk_rows"]))
    checkpoints = int(identities["n_checkpoint_snapshots"]) * int(measured["checkpoint_snapshot_bytes"])
    operations = int(identities["n_operation_rows"]) * int(measured["operation_reference_bytes"])
    distributions = int(identities["n_distribution_records"]) * int(measured["distribution_record_bytes"])
    manifests = 12 * int(measured["manifest_bytes"])
    indexes = int(identities["n_world_chunks"]) * 128
    finals = world_bytes + checkpoints + operations + distributions + manifests + indexes
    largest = max(
        int(measured["checkpoint_snapshot_bytes"]),
        int(max(identities["world_chunk_rows"] or [1]) * per_row),
        int(measured["manifest_bytes"]),
    )
    # Crash-safe atomic replace can keep the new bytes beside the previous tree.
    peak = finals + largest
    return {
        "historical_formula_bytes": historical_storage_bytes(n_units=n_units, evaluation_worlds=evaluation_worlds),
        "measured_peak_bytes": int(peak),
        "measured_final_bytes": int(finals),
        "components_bytes": {
            "paired_world_chunks_gzip": world_bytes,
            "checkpoint_snapshots_once": checkpoints,
            "operation_references": operations,
            "distribution_records": distributions,
            "manifests": manifests,
            "indexes": indexes,
            "crash_safe_coexistence": int(largest),
        },
        "n_checkpoint_snapshots": identities["n_checkpoint_snapshots"],
        "n_world_chunks": identities["n_world_chunks"],
        "n_operation_rows": identities["n_operation_rows"],
        "n_distribution_records": identities["n_distribution_records"],
        "schema": SCIENTIFIC_RECORD_SCHEMA["schema"],
    }

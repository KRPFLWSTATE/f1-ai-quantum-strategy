"""Independent storage recount. Does not call storage_account.project_storage."""

from __future__ import annotations

from typing import Any


def recount(units: list[dict[str, Any]], measured: dict[str, Any], *, n_units: int, evaluation_worlds: int) -> dict[str, Any]:
    checkpoints: set[str] = set()
    distributions: set[str] = set()
    chunks: dict[tuple[Any, ...], int] = {}
    operations = 0
    for unit in units:
        operations += 1
        checkpoints.add(str(unit.get("checkpoint_id")))
        distributions.add((str(unit.get("checkpoint_id")), str(unit.get("family_depth")), str(unit.get("donor_policy")), str(unit.get("policy_seed"))))
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
        chunks[key] = max(int(chunks.get(key, 0)), n_eval)
    per_row = float(measured["conservative_gzip_bytes_per_world_row"])
    world_bytes = 0
    largest_chunk = 0
    for n in chunks.values():
        chunk = int(per_row * int(n) + 64)
        world_bytes += chunk
        largest_chunk = max(largest_chunk, chunk)
    checkpoints_b = len(checkpoints) * int(measured["checkpoint_snapshot_bytes"])
    operations_b = operations * int(measured["operation_reference_bytes"])
    distributions_b = len(distributions) * int(measured["distribution_record_bytes"])
    manifests = 12 * int(measured["manifest_bytes"])
    indexes = len(chunks) * 128
    finals = world_bytes + checkpoints_b + operations_b + distributions_b + manifests + indexes
    largest = max(int(measured["checkpoint_snapshot_bytes"]), largest_chunk, int(measured["manifest_bytes"]))
    historical = int(n_units) * 2_000_000 + int(evaluation_worlds) * 200
    return {
        "independent": True,
        "calls_project_storage": False,
        "n_checkpoint_snapshots": len(checkpoints),
        "n_world_chunks": len(chunks),
        "n_operation_rows": operations,
        "n_distribution_records": len(distributions),
        "measured_peak_bytes": int(finals + largest),
        "historical_formula_bytes": historical,
        "duplicated_checkpoint_references_not_duplicated_bytes": True,
    }

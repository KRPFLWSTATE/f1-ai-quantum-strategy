"""Independent storage and resource arithmetic. No registered outcomes."""

from f1q.a4.resource_check import project_from_raw
from f1q.a4.storage_account import historical_storage_bytes, identity_ledger, project_storage
from f1q.a4.storage_check import recount


def test_duplicated_checkpoint_references_are_stored_once():
    units = [
        {"checkpoint_id": "c1", "family_depth": "C0_p1", "donor_policy": "fixed", "policy_seed": 0, "option": "classical_only", "budget_s": 30, "role": "train_option", "n_evaluation_worlds": 16},
        {"checkpoint_id": "c1", "family_depth": "C0_p1", "donor_policy": "fixed", "policy_seed": 0, "option": "C0_p1", "budget_s": 30, "role": "train_option", "n_evaluation_worlds": 16},
    ]
    measured = {
        "conservative_gzip_bytes_per_world_row": 10,
        "checkpoint_snapshot_bytes": 1000,
        "operation_reference_bytes": 50,
        "distribution_record_bytes": 80,
        "manifest_bytes": 20,
    }
    led = identity_ledger(units)
    assert led["n_checkpoint_snapshots"] == 1
    assert led["n_distribution_records"] == 1
    assert led["n_world_chunks"] == 2
    left = project_storage(led, measured, n_units=2, evaluation_worlds=32)
    right = recount(units, measured, n_units=2, evaluation_worlds=32)
    assert left["measured_peak_bytes"] == right["measured_peak_bytes"]
    assert left["historical_formula_bytes"] == historical_storage_bytes(n_units=2, evaluation_worlds=32) == 2 * 2_000_000 + 32 * 200
    assert left["components_bytes"]["checkpoint_snapshots_once"] == 1000


def test_distinct_arrival_keys_do_not_share_a_world_chunk():
    units = []
    for seed in (0, 1):
        units.append(
            {
                "checkpoint_id": "c1",
                "family_depth": "C0_p1",
                "donor_policy": "fixed",
                "policy_seed": seed,
                "option": "classical_only",
                "budget_s": 30,
                "role": "calib_primary",
                "n_evaluation_worlds": 4,
            }
        )
    led = identity_ledger(units)
    assert led["n_world_chunks"] == 2
    assert led["n_checkpoint_snapshots"] == 1


def test_worst_row_rate_is_the_gate_not_the_smaller_sample():
    measured = {
        "conservative_gzip_bytes_per_world_row": 30,
        "checkpoint_snapshot_bytes": 1,
        "operation_reference_bytes": 1,
        "distribution_record_bytes": 1,
        "manifest_bytes": 1,
    }
    units = [{"checkpoint_id": "c", "family_depth": "C0_p1", "donor_policy": "fixed", "policy_seed": 0, "option": "a", "budget_s": 5, "role": "train_option", "n_evaluation_worlds": 10}]
    led = identity_ledger(units)
    out = project_storage(led, measured, n_units=1, evaluation_worlds=10)
    assert out["components_bytes"]["paired_world_chunks_gzip"] == int(30 * 10 + 64)


def test_resource_projection_does_not_divide_schedule_twice():
    raw = {
        "per_cell_wall_s": [0.02, 0.04],
        "underprediction_historical": 1.25,
        "probe_cells": 100,
        "pooled_race_cells": 1000,
        "serial_race_cells": 100,
        "pool_makespan_s": 5.0,
        "serial_wall_s": 10.0,
        "serial_cpu_s": 12.0,
        "cold_wall_s": 1.0,
        "cold_cpu_s": 1.0,
        "coordinator_cpu_s": 2.0,
        "processes": [{"pid": 7, "cpu_s": 8.0}, {"pid": 7, "cpu_s": 9.0}, {"pid": 8, "cpu_s": 4.0}],
        "solo_wall_s": 3.0,
        "solo_cpu_s": 3.0,
    }
    out = project_from_raw(raw)
    assert out["calls_project_resources"] is False
    assert out["efficiency_applied_again"] is False
    assert out["schedule_per_cell_wall_s"] == 5.0 / 100
    assert out["pooled_wall_s"] == (5.0 / 100) * 1000
    assert out["serial_cell_wall_s"] == 0.04 * 100
    assert out["n_processes"] == 3
    assert out["probe_cpu_s"] == 2.0 + 9.0 + 4.0

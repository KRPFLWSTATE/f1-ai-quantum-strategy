from __future__ import annotations

from f1q.generator.config import cartesian_family_ids, load_generator_config
from f1q.generator.splits import build_split_plan, planned_counts


def test_eight_families_are_the_cartesian_product(project_root):
    config, _, _ = load_generator_config(project_root)
    ids = cartesian_family_ids()
    assert len(ids) == 8
    assert ids == sorted(fam.id for fam in config.families)
    assert "fam.green_pit_low.tyre_near_linear.traffic_sparse" in ids
    assert "fam.green_pit_high.tyre_nonlinear.traffic_dense" in ids


def test_main_split_counts_at_floor_and_maximum(project_root):
    config, _, _ = load_generator_config(project_root)
    floor = planned_counts(test_blocks=80, include_shift=True)
    maximum = planned_counts(test_blocks=160, include_shift=True)
    assert floor["training_blocks"] == 120
    assert floor["tuning_blocks"] == 16
    assert floor["calibration_blocks"] == 24
    assert floor["test_blocks"] == 80
    assert floor["main_blocks_without_shift"] == 240
    assert floor["main_checkpoints_without_shift"] == 1920
    assert floor["total_blocks_including_shift"] == 280
    assert floor["total_checkpoints_including_shift"] == 2240
    assert maximum["test_blocks"] == 160
    assert maximum["total_blocks_including_shift"] == 360
    assert maximum["total_checkpoints_including_shift"] == 2880
    assert floor["completed_counts"] is None
    plan = build_split_plan(config, test_blocks=80)
    assert plan["per_family"]["training"] == 15
    assert plan["per_family"]["tuning"] == 2
    assert plan["per_family"]["calibration"] == 3
    assert plan["per_family"]["test"] == 10
    assert plan["per_family"]["shift"] == 5
    assert all(not rec["materialized"] for rec in plan["records"])
    assert plan["shift_panel"]["not_a_finalized_shift_study"] is True
    blocks = [rec for rec in plan["records"] if rec["partition"] == "training"]
    assert len(blocks) == 120
    assert all(rec["planned_sc"] == 4 and rec["planned_vsc"] == 4 for rec in plan["records"])

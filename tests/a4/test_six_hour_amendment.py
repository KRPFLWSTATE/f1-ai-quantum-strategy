"""Prospective six-hour amendment arithmetic. No registered outcomes."""

from f1q.a4.corrected_cost import HISTORICAL_UNDERPREDICTION
from f1q.a4.partitions import build_a4_partitions
from f1q.a4.resources import ADMISSION_WALL_LIMIT_S, CAMPAIGN_CPU_CAP_S, CAMPAIGN_WALL_CAP_S
from f1q.a4.six_hour import (
    ADMISSION_WALL_S,
    CAMPAIGN_WALL_S,
    CPU_CAP_S,
    RUN_ID,
    independent_recompute,
    operation_counts,
    project_resources,
    six_hour_caps,
    verify_sealed_splits,
)
from f1q.a4.unit_ledger import DESIGN_R, design_worlds, enumerate_design_units
from f1q.paths import resolve_project_root


def test_historical_wall_constants_stay_put():
    assert ADMISSION_WALL_LIMIT_S == 11520.0
    assert CAMPAIGN_WALL_CAP_S == 14400.0
    assert CAMPAIGN_CPU_CAP_S == 86400.0


def test_six_hour_caps_are_prospective():
    caps = six_hour_caps({"campaign_wall_cap_s": 21600, "admission_wall_limit_s": 17280, "campaign_cpu_cap_s": 86400})
    assert caps["campaign_wall_cap_s"] == CAMPAIGN_WALL_S == 21600.0
    assert caps["admission_wall_limit_s"] == ADMISSION_WALL_S == 17280.0
    assert abs(caps["admission_wall_limit_s"] - 0.8 * caps["campaign_wall_cap_s"]) < 1e-9
    assert caps["campaign_cpu_cap_s"] == CPU_CAP_S
    assert caps["historical_admission_wall_s"] == 11520.0
    assert RUN_ID == "ed37296f-55c5-44e5-8ffd-77410d4789de"


def test_registered_split_is_sealed():
    root = resolve_project_root()
    sealed = verify_sealed_splits(root)
    assert sealed["ok"], sealed["defects"]
    assert sealed["n_train"] == 120
    assert sealed["n_tune"] == 80
    assert sealed["n_calib"] == 24
    assert sealed["final_test_outcomes_read"] is False
    assert sealed["opened_outcome_files"] == []


def test_design_r_counts_apply_k_once_and_do_not_pretend_2400():
    parts = build_a4_partitions()
    enum = enumerate_design_units(design=DESIGN_R, parts=parts, worlds=design_worlds(DESIGN_R, "minimum"), freeze=None)
    keys = [("c", "C0_p1", (0.1,), (0.2,), "ideal_noiseless", "local_statevector", "v")] * 10
    checked = independent_recompute(
        enum["units"],
        keys,
        {
            "scalar_s_per_cell": 0.5,
            "speedup": 20.0,
            "build_cpu_s": 100.0,
            "resample_s": 0.01,
            "optimiser_s": 50.0,
            "prepare_s": 36.157,
            "other_fixed_s": 1.0,
        },
        n_legal=100,
        n_donors=8,
        efficiency=0.5,
        cold_wall_s=10.0,
        underprediction=HISTORICAL_UNDERPREDICTION,
    )
    counts = checked["counts"]
    assert counts["k_applied_once"] is True
    assert counts["portfolio_k_values"] == [4]
    assert counts["plan_matches_helper"] is True
    assert counts["mechanism_policy_rows"] == 72000
    assert counts["ablation_specifications"] == 7
    assert counts["offline_cases"] == 8
    assert counts["offline_continuations"] == 8 * 100 * 16
    assert counts["builds_2400_proven"] is False
    assert counts["charged_builds"] == 1
    again = operation_counts(enum["units"], n_legal=100, n_donors=8, unique_parameter_builds=1)
    assert again["plan_world_evaluations_k_once"] == counts["plan_world_evaluations_k_once"]
    wall = project_resources(
        counts,
        {
            "scalar_s_per_cell": 0.5,
            "speedup": 20.0,
            "build_cpu_s": 100.0,
            "resample_s": 0.01,
            "optimiser_s": 50.0,
            "prepare_s": 36.157,
            "other_fixed_s": 1.0,
        },
        efficiency=0.5,
        cold_wall_s=10.0,
        underprediction=HISTORICAL_UNDERPREDICTION,
    )
    assert wall["admission_wall_s"] == wall["steady_wall_s"] + 10.0
    assert wall["workers"] == 8

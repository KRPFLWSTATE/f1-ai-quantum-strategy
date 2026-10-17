"""Small-fixture arithmetic for the corrected cost model.

These checks are engineered so the historical formulas fail them.
"""

from __future__ import annotations

from f1q.a4.corrected_cost import (
    CAMPAIGN_CPU_CAP_S,
    ContinuationIdentity,
    DistributionIdentity,
    ResampleRequest,
    apply_historical_underprediction,
    component_cpu_s,
    count_continuations,
    count_distribution_operations,
    decompose_cpu,
    legacy_operation_ledger_distribution_count,
    legacy_planning_charge_applies_k_again,
    legacy_resamples_charged_as_builds,
    mechanism_distribution_counts,
    plan_world_evaluations,
    plan_world_evals_from_units,
    project_wall_s,
    variational_objective_cap,
)


def _ident(case: str, circuit: str, depth: int, params: tuple[float, ...], policy_tag: str = "") -> DistributionIdentity:
    return DistributionIdentity(
        case_id=case,
        qubo_id=case + ":qubo",
        circuit=circuit,
        depth=depth,
        parameters=params if not policy_tag else params + (hash(policy_tag) % 997,),
        noise_id="ideal_noiseless",
        numeric_backend="local_statevector",
        simulator_version="1.0.4",
    )


def test_four_plans_six_worlds_cost_24_and_old_k_does_not():
    corrected = plan_world_evaluations(4, 6)
    assert corrected == 24
    stored_including_k = 6 * 4
    legacy = legacy_planning_charge_applies_k_again(stored_including_k, 4)
    assert legacy == 96
    assert legacy != corrected


def test_unit_aggregate_does_not_apply_k_twice():
    units = [
        {
            "role": "train_option",
            "n_planning_worlds": 6,
            "portfolio_k": 4,
        }
    ]
    stored = plan_world_evals_from_units(units)
    assert stored == 24
    assert legacy_planning_charge_applies_k_again(stored, 4) != stored


def test_one_distribution_sampled_thirty_times_is_one_build():
    spec = _ident("case-a", "C0", 1, (0.1, 0.2))
    reqs = [ResampleRequest(spec, resample_seed=i, pool_draws=1024) for i in range(30)]
    counts = count_distribution_operations(reqs)
    assert counts["unique_builds"] == 1
    assert counts["resamples"] == 30
    assert counts["pool_sampling_operations"] == 30
    assert legacy_resamples_charged_as_builds(30) == 30
    assert legacy_resamples_charged_as_builds(30) != counts["unique_builds"]


def test_distinct_policies_and_distinct_parameters_are_distinct_builds():
    a = _ident("case-a", "C0", 2, (0.1, 0.2, 0.3, 0.4))
    b = _ident("case-a", "C0", 2, (0.5, 0.6, 0.7, 0.8))
    reqs = [
        ResampleRequest(a, resample_seed=0, pool_draws=8),
        ResampleRequest(b, resample_seed=0, pool_draws=8),
    ]
    counts = count_distribution_operations(reqs)
    assert counts["unique_builds"] == 2
    assert counts["resamples"] == 2


def test_mechanism_rows_do_not_collapse_policies_or_use_the_3840_expression():
    units = []
    for policy in ("fixed", "nn", "random", "learned", "best_found"):
        for seed in range(30):
            units.append(
                {
                    "role": "mechanism_resample",
                    "checkpoint_id": "parent:SC",
                    "parent_id": "parent",
                    "family_depth": "C0_p1",
                    "donor_policy": policy,
                    "resample_seed": seed,
                }
            )
    counts = mechanism_distribution_counts(units)
    assert counts["resamples"] == 150
    assert counts["unique_builds"] == 5
    assert legacy_resamples_charged_as_builds(counts["resamples"]) != counts["unique_builds"]
    assert legacy_operation_ledger_distribution_count(1) == 32
    assert legacy_operation_ledger_distribution_count(1) != counts["unique_builds"]


def test_same_parameters_collapse_and_resample_seed_does_not():
    units = []
    for policy, params in (("fixed", (0.2, 0.3)), ("nn", (0.2, 0.3)), ("random", (0.9, 0.1))):
        for seed in range(30):
            units.append(
                {
                    "role": "mechanism_resample",
                    "checkpoint_id": "parent:VSC",
                    "family_depth": "C1_p2",
                    "donor_policy": policy,
                    "donor_parameters": params,
                    "resample_seed": seed,
                    "simulator_version": "1.0.4",
                }
            )
    counts = mechanism_distribution_counts(units)
    assert counts["resamples"] == 90
    assert counts["unique_builds"] == 2


def test_distinct_arrival_and_commitment_are_not_deduped():
    base = dict(
        simulator_version="1.0.4",
        bank="evaluation_bank",
        world_seed=7,
        state_id="checkpoint",
        plan_id="plan",
        nominal_budget_s=30.0,
    )
    reqs = [
        ContinuationIdentity(**base, arrival_delay_s=0.02, commitment_s=0.05),
        ContinuationIdentity(**base, arrival_delay_s=0.20, commitment_s=0.05),
        ContinuationIdentity(**base, arrival_delay_s=0.02, commitment_s=0.05),
    ]
    counts = count_continuations(reqs)
    assert counts["requested"] == 3
    assert counts["cold_unique"] == 2
    assert counts["proven_duplicate_hits"] == 1


def test_infinite_kernel_floor_keeps_unaccelerated_work():
    parts = component_cpu_s(
        n_prepare=1,
        prepare_s=10.0,
        n_builds=1,
        build_s=2.0,
        n_resamples=30,
        resample_s=0.04,
        n_plan_world=24,
        plan_world_s=1.0,
        n_eval_world=0,
        eval_world_s=1.0,
        n_offline=0,
        offline_s=1.0,
        n_optimiser_evals=40,
        optimiser_eval_s=0.5,
        other_fixed_s=1.0,
    )
    assert parts["accelerated_s"] == 24.0
    assert parts["infinite_kernel_floor_s"] == parts["fixed_s"]
    assert parts["infinite_kernel_floor_s"] > 0.0
    assert parts["components_s"]["resamples"] == 30 * 0.04
    assert parts["components_s"]["distribution_builds"] == 2.0
    # Charging resamples as builds would be a different number.
    assert legacy_resamples_charged_as_builds(30) * 2.0 != parts["components_s"]["resamples"]


def test_floor_above_cap_is_reported_and_wall_needs_matching_workers():
    decomp = decompose_cpu(fixed_s=CAMPAIGN_CPU_CAP_S + 1.0, accelerated_s=10.0, overhead_s=0.0)
    assert decomp["floor_exceeds_campaign_cpu_cap"] is True
    refused = project_wall_s(
        conservative_cpu_s=100.0,
        workers=8,
        efficiency=0.5,
        efficiency_measured_at_workers=4,
    )
    assert refused["wall_claim_allowed"] is False
    allowed = project_wall_s(
        conservative_cpu_s=100.0,
        workers=4,
        efficiency=0.5,
        efficiency_measured_at_workers=4,
    )
    assert allowed["wall_claim_allowed"] is True
    assert allowed["conservative_wall_s"] == 100.0 / (4 * 0.5) * 1.20


def test_variational_cap_is_not_one_distribution_per_fit():
    cap = variational_objective_cap(3)
    assert cap["objective_evaluations_cap"] == 120
    assert cap["measured"] == 0
    assert cap["objective_evaluations_cap"] != cap["fits"]


def test_historical_projection_still_multiplies_k_again():
    """The preserved design formula is not rewritten. It fails the 24-count fixture."""
    from f1q.a4.completion import _project_from_probes

    ledger = {
        "counts": {
            "prepared_cases": 1,
            "distributions": 30,
            "planning_worlds_upper": 24,
            "evaluation_worlds_upper": 0,
            "offline_all_plan_evaluations": 0,
        }
    }
    probes = [
        {"kind": "prepare", "wall_s": 1.0},
        {"kind": "family_depth", "wall_s": 3.0},
        {"kind": "budget", "wall_s": 1.0},
        {"kind": "case_unit", "wall_s": 1.0},
        {"kind": "offline", "wall_s": 12.0, "n_legal": 1},
        {"kind": "calib_2048", "wall_s": 0.0, "n_eval": 1},
    ]
    proj = _project_from_probes(ledger, probes, {"workers": 1, "per_worker_rss_budget_bytes": 1}, 1.0)
    # offline denominator is n_legal*4+8 = 12, so per_world = 1.
    assert proj["components_s"]["per_world_s"] == 1.0
    assert proj["components_s"]["planning_worlds"] == 24 * 4
    assert proj["components_s"]["planning_worlds"] != plan_world_evaluations(4, 6)
    assert proj["components_s"]["distributions"] == 30 * proj["components_s"]["circuit_s"]


def test_historical_multiplier_applied_once():
    out = apply_historical_underprediction(100.0)
    assert out["multiplier"] == 26010.0 / 20752.0
    assert out["conservative_cpu_s"] == 100.0 * out["multiplier"]

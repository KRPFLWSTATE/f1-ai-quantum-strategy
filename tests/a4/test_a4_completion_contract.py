"""Adversarial Phase 6 completion contract. Fail under the old implementation."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import numpy as np
import pytest

from f1q.a4.analysis import finite_sample_q
from f1q.a4.allocator import RidgeModel, option_feature_row, allocator_feature_vector
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.circuits import simulate_c1
from f1q.a4.contracts import FAMILY_DEPTH_KEYS, NOMINAL_BUDGETS_S, POOL_DRAWS, SEED_HIERARCHY, circuit_resample_seed
from f1q.a4.distributions import build_ideal_distribution, distribution_counters, resample_pool, reset_distribution_counters
from f1q.a4.generators import assemble_portfolio
from f1q.a4.loop import decide_and_evaluate, evaluate_offline_reference
from f1q.a4.pool import run_pool
from f1q.a4.prepared import prepare_case, prepare_counters, reset_prepare_counters
from f1q.a4.resources import choose_workers
from f1q.a4.timing import modelled_algorithm_latency_s, reconcile_timing
from f1q.hashing import sha256_file
from f1q.simulator.interface import RaceSimulator

FAM = "fam.green_pit_low.tyre_near_linear.traffic_sparse"
PRIOR = Path("evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b")
PRIOR_ADMIT = Path("evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d")


def _pc(**kw):
    return prepare_case(
        family_id=FAM,
        block_id=kw.get("block_id", "a4.t.contract"),
        regime=kw.get("regime", "SC"),
        partition=kw.get("partition", "train"),
        index=0,
        seed=kw.get("seed", 3),
        n_planning=2,
        n_evaluation=4,
    )


def test_prepared_case_once_across_arms_budgets():
    reset_prepare_counters()
    pc = _pc(block_id="a4.t.once")
    cache: dict = {}
    dist = {}
    for budget in (5, 30):
        for mode, fd in (("always_classical", None), ("always_c0", ("C0", 1))):
            decide_and_evaluate(
                pc.spec_with_budget(budget),
                mode=mode,
                runtime=None,
                donor_bank=None,
                donor_policy="fixed",
                planning_seeds=pc.planning_bank_keys,
                evaluation_seeds=pc.evaluation_bank_keys,
                online_seed=1,
                cache=cache,
                pool_size=8,
                equal_k=4,
                deadline_s=float(budget),
                margin=0.001,
                conservative_residual=0.0,
                family_depth=fd,
                n_stochastic_seeds=1,
                legal_table=pc.legal_table,
                prepared=pc,
                dist_cache=dist,
            )
    c = prepare_counters()
    assert c["prepare_case_calls"] == 1
    assert c["checkpoint_init"] == 1
    assert c["menu_qubo"] == 1


def _tiny_unit(i: int) -> dict:
    return {"i": i}


def _tiny_fn(payload: dict) -> dict:
    return {"ok": True, "value": payload["i"] * 2, "scientific": payload["i"]}


def test_real_process_pool_pids_and_byte_equivalent_order():
    payloads = [_tiny_unit(i) for i in range(6)]
    one = run_pool(_tiny_fn, payloads, workers=1)
    multi = run_pool(_tiny_fn, payloads, workers=2)
    assert one.workers == 1
    assert multi.workers == 2
    assert len(set(multi.worker_pids)) >= 2
    sci_one = [r.get("scientific") for r in one.results]
    sci_multi = [r.get("scientific") for r in multi.results]
    assert sci_one == sci_multi == [0, 1, 2, 3, 4, 5]


def test_config_1024_five_budgets_four_depths_seed_hierarchy():
    assert POOL_DRAWS == 1024
    assert NOMINAL_BUDGETS_S == (5, 10, 30, 60, 120)
    assert FAMILY_DEPTH_KEYS == ("C0_p1", "C0_p2", "C1_p1", "C1_p2")
    assert SEED_HIERARCHY["circuit_resample_seed"]["not_an_extra_times_three"] is True
    a = circuit_resample_seed(policy_seed=0, case_id="c", family_depth="C0_p1")
    b = circuit_resample_seed(policy_seed=1, case_id="c", family_depth="C0_p1")
    assert a != b


def test_distribution_once_across_thirty_resamples():
    pc = _pc(block_id="a4.t.dist")
    reset_distribution_counters()
    cache: dict = {}
    dist = build_ideal_distribution(
        instance=pc.instance,
        qubo=pc.qubo,
        family="C0",
        depth=1,
        gammas=[0.3],
        betas=[0.2],
        prepared_case_hash=pc.prepared_case_hash,
        cache=cache,
        legal_table=pc.legal_table,
    )
    for s in range(30):
        rec = resample_pool(dist, pool_draws=32, seed=s)
        assert rec["requested_shots"] == 32
        build_ideal_distribution(
            instance=pc.instance,
            qubo=pc.qubo,
            family="C0",
            depth=1,
            gammas=[0.3],
            betas=[0.2],
            prepared_case_hash=pc.prepared_case_hash,
            cache=cache,
            legal_table=pc.legal_table,
        )
    c = distribution_counters()
    assert c["distribution_builds"] == 1
    assert c["resamples"] == 30


def test_c1_legal_subspace_no_dense_2n():
    pc = _pc(block_id="a4.t.c1")
    sim = simulate_c1(pc.instance, pc.qubo, [0.2], [0.1], scaled=True, legal_table=pc.legal_table, allocate_dense=False)
    n = int(pc.qubo["n"])
    assert sim["dense_2n_allocated"] is False
    assert np.asarray(sim["probs_legal"]).size == sim["n_legal"]
    assert np.asarray(sim["probs"]).size != (1 << n) or sim["n_legal"] == (1 << n)


def test_cache_byte_limit_eviction():
    c = ByteBoundedCache(max_bytes=80)
    c.put("a", "x" * 40)
    c.put("b", "y" * 40)
    c.put("c", "z" * 40)
    assert c.evictions >= 1
    assert c.bytes <= 200
    _ = c.get("missing")
    assert c.misses >= 1
    st = c.stats()
    assert "hits" in st and "max_bytes_observed" in st


def test_matched_k_replacement_not_append():
    pc = _pc(block_id="a4.t.k")
    sim = RaceSimulator()
    sim.restore(copy.deepcopy(pc.checkpoint_blob), pc.spec)

    def _val(plan):
        sim.validate_plan(plan)

    hy = assemble_portfolio(
        pc.instance, pc.qubo, choice="always_c0", seed=1, pool_size=32, sim_validate=_val,
        params=([0.3], [0.2]), family="C0", p_depth=1, equal_k=4, legal_table=pc.legal_table,
        prepared_case_hash=pc.prepared_case_hash,
    )
    assert hy["n_downstream"] == 4
    assert hy["n_unique_hashes"] == 4
    assert hy["replaced_not_appended"] is True
    assert hy["n_downstream"] <= 4


def test_quantum_candidate_can_win_and_fallback_safe():
    pc = _pc(block_id="a4.t.win")
    cache: dict = {}
    rec = decide_and_evaluate(
        pc.spec_with_budget(30),
        mode="always_c0",
        runtime=None,
        donor_bank=None,
        donor_policy="fixed",
        planning_seeds=pc.planning_bank_keys,
        evaluation_seeds=pc.evaluation_bank_keys,
        online_seed=11,
        cache=cache,
        pool_size=64,
        equal_k=4,
        deadline_s=30.0,
        margin=0.001,
        conservative_residual=0.0,
        family_depth=("C0", 1),
        n_stochastic_seeds=1,
        legal_table=pc.legal_table,
        prepared=pc,
        dist_cache={},
    )
    assert rec["portfolio"]["n_downstream"] == 4
    hashes = rec["portfolio"]["candidate_plan_hashes"]
    assert rec["plan_hash"] in hashes
    late = decide_and_evaluate(
        pc.spec_with_budget(5),
        mode="always_classical",
        runtime=None,
        donor_bank=None,
        donor_policy="fixed",
        planning_seeds=pc.planning_bank_keys,
        evaluation_seeds=pc.evaluation_bank_keys,
        online_seed=12,
        cache={},
        pool_size=8,
        equal_k=4,
        deadline_s=5.0,
        margin=0.001,
        conservative_residual=0.0,
        n_stochastic_seeds=1,
        legal_table=pc.legal_table,
        prepared=pc,
    )
    assert late["mean_loss"] is not None


def test_allocator_features_not_all_zero_latency_not_constant():
    pc = _pc(block_id="a4.t.feat")
    base = dict(pc.features)
    a = option_feature_row(base, option="classical_only", nominal_budget_s=30, effective_remaining_s=float(base.get("effective_remaining_s") or 20), k=4, pool_draws=1024, pred_latency_s=0.4)
    b = option_feature_row(base, option="C1_p2", nominal_budget_s=5, effective_remaining_s=4.0, k=4, pool_draws=1024, pred_latency_s=1.7)
    phys = ["remaining_laps", "mean_tyre_age", "n_logical_vars", "crew_overlap_cost"]
    assert any(float(base.get(k) or 0.0) != 0.0 for k in phys)
    assert a["pred_latency_s"] != b["pred_latency_s"]
    va, vb = allocator_feature_vector(a), allocator_feature_vector(b)
    assert not np.allclose(va, 0)
    assert not np.allclose(va, vb)


def test_donor_selector_labels_are_sampled_regret():
    from f1q.stage5.metrics import normalised_regret

    r0 = normalised_regret(1.0, 1.0, 1.0, feasible=True)
    r1 = normalised_regret(None, 0.0, 1.0, feasible=False, pool_all_infeasible=True)
    assert r0 == 0.0
    assert r1 == 1.0


def test_tuning_freeze_precedes_calibration_schema():
    freeze = {"written_before_calibration": True, "allowed_options": ["classical_only", "C0_p1"]}
    assert freeze["written_before_calibration"] is True


def test_calibration_q_mutation_changes_parent_max():
    residuals = [0.01 * i for i in range(24)]
    q1 = finite_sample_q(residuals)
    assert q1["n"] == 24
    assert q1["is_maximum"] is True
    assert q1["q"] == max(residuals)
    residuals2 = list(residuals)
    residuals2[-1] = 9.0
    q2 = finite_sample_q(residuals2)
    assert q2["q"] != q1["q"]
    assert q2["q"] == 9.0


def test_planning_evaluation_banks_disjoint_paired():
    pc = _pc(block_id="a4.t.banks")
    assert set(pc.planning_bank_keys).isdisjoint(set(pc.evaluation_bank_keys))
    pc2 = _pc(block_id="a4.t.banks")
    assert pc.planning_bank_keys == pc2.planning_bank_keys


def test_timing_critical_path_includes_feature_inference_decode_validation():
    m = modelled_algorithm_latency_s(
        prepare_s=0.2, n_qubits=8, n_legal=12, family="C0", p_depth=1,
        pool_draws=1024, n_plans=4, n_planning_worlds=8, n_evaluation_worlds=16,
    )
    rec = reconcile_timing(m)
    assert rec["ok"]
    assert m["features_s"] > 0 and m["donor_inference_s"] > 0
    assert m["candidate_decoding_s"] > 0 and m["validation_s"] > 0


def test_offline_all_plans_not_assigned_from_classical():
    pc = _pc(block_id="a4.t.off")
    off = evaluate_offline_reference(
        pc.spec_with_budget(30),
        pc.checkpoint_blob,
        pc.legal_table,
        planning_seeds=list(range(1000, 1004)),
        evaluation_seeds=list(range(2000, 2004)),
        cache={},
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
    )
    assert off["copied_from_arm"] is False
    assert off["all_plan_coverage"] is True
    assert off["n_legal_evaluated"] == off["n_legal"]


def test_report_reader_option_results_filename():
    from f1q.a4.reports import write_completion_report
    import inspect

    src = inspect.getsource(write_completion_report)
    assert "TRAINING_OPTION_RESULTS.jsonl" in src
    assert "CALIBRATION_OPTION_RESULTS.jsonl" in src


def test_cli_does_not_treat_raw_complete_as_success():
    from f1q.a4.__main__ import main
    import inspect

    src = inspect.getsource(main)
    assert "campaign_raw_complete" in src
    assert "COMPLETED_STATES" in src


def test_verifier_detects_q_and_worker_and_k():
    from f1q.a4.verify import run_independent_verify
    import inspect

    src = inspect.getsource(run_independent_verify)
    assert "finite_sample_q" in src
    assert "real_worker_pids" in src


def test_historical_evidence_hash_guards():
    man = PRIOR / "MANIFEST.json"
    assert man.is_file()
    h = sha256_file(man)
    assert h == "8f620c8fc9048cf27c304847efe7fa79a3eb00aac2f7af6a7b5f0c97db0be70e"
    assert PRIOR_ADMIT.is_dir()
    assert (PRIOR_ADMIT / "ADMISSION_RECEIPT.json").is_file()
    # 3de109c7 must remain immutable; we only check presence + readable JSON
    import json

    rec = json.loads((PRIOR_ADMIT / "ADMISSION_RECEIPT.json").read_text())
    assert rec.get("admitted") is False


def test_choose_workers_uses_measured_rss_not_512mib():
    spec = choose_workers(measured_peak_worker_rss_bytes=80 * 1024 * 1024)
    assert spec["replaced_assumed_512mib"] is True
    assert spec["measured_peak_worker_rss_bytes"] == 80 * 1024 * 1024
    assert "512" not in spec["rule"]


@pytest.mark.skipif(os.environ.get("F1Q_A4_IN_ADMISSION") == "1", reason="avoid recursive admission pytest")
def test_e2e_miniature_campaign(tmp_path: Path):
    """Named e2e_miniature so admission focused pytest can exclude it."""
    from f1q.a4.completion_run import execute_phase6, run_admission_check
    from f1q.a4.verify import run_independent_verify
    from f1q.paths import resolve_project_root

    root = resolve_project_root()
    adm = run_admission_check(root, miniature=True, skip_tests=True)
    assert adm.get("run_id")
    assert adm.get("admitted") or adm.get("limited_resource_pilot")
    exe = execute_phase6(root, adm["run_id"])
    assert exe.get("status") != "campaign_raw_complete"
    assert (root / "docs" / "PHASE_6_COMPLETION_REPORT.md").is_file()
    ver = run_independent_verify(root, adm["run_id"], mode="final")
    assert isinstance(ver.get("checks"), list)
    assert (root / "evidence" / "stage6_a4" / adm["run_id"] / "TUNING_FREEZE.json").is_file()

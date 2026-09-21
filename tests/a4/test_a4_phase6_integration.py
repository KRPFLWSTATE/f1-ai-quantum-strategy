"""Phase 6 A4 integration witnesses on real prepared cases and reused banks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from f1q.a4.donors import DonorRanker, build_donor_bank_v2, selected_donors, select_donor_policy
from f1q.a4.generators import assemble_portfolio, quantum_candidates
from f1q.a4.loop import decide_and_evaluate, evaluate_offline_reference, family_spec
from f1q.a4.prepared import prepare_case
from f1q.a4.problem import enumerate_legal_policies
from f1q.simulator.interface import RaceSimulator

PRIOR = Path("evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b")
ANCHORS = PRIOR / "ANCHOR_FITS.jsonl"


def _bank():
    rows = []
    with ANCHORS.open() as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return build_donor_bank_v2(
        rows,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path=str(ANCHORS),
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )


@pytest.mark.skipif(not ANCHORS.is_file(), reason="pinned reused anchors missing")
def test_real_quantum_candidate_not_fake_hash():
    bank = _bank()
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.int.q",
        regime="SC",
        partition="train",
        index=0,
        seed=9,
    )
    sim = RaceSimulator()
    sim.restore(copy.deepcopy(pc.checkpoint_blob), pc.spec)
    donor = selected_donors(bank, "C0_p1")[0]

    def _val(plan):
        sim.validate_plan(plan)

    q = quantum_candidates(
        pc.instance,
        pc.qubo,
        family="C0",
        p=1,
        params=(list(donor["gammas"]), list(donor["betas"])),
        pool_size=64,
        seed=3,
        sim_validate=_val,
    )
    assert q["decoded"]
    ph = q["decoded"][0]["plan_hash"]
    legal = {r["plan_hash"] for r in pc.legal_table}
    assert ph in legal
    assert ph != "quantum-best-hash"
    hy = assemble_portfolio(
        pc.instance, pc.qubo, choice="C0_p1", seed=3, pool_size=64, sim_validate=_val,
        params=(list(donor["gammas"]), list(donor["betas"])), family="C0", p_depth=1, equal_k=4,
        legal_table=pc.legal_table, donor_id=donor["donor_id"],
    )
    assert hy["n_downstream"] == 4
    assert all(c["plan_hash"] in legal for c in hy["downstream_candidates"])


@pytest.mark.skipif(not ANCHORS.is_file(), reason="pinned reused anchors missing")
def test_provenance_merge_not_quantum_incremental_duplicate():
    bank = _bank()
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.int.merge",
        regime="SC",
        partition="train",
        index=0,
        seed=11,
    )
    sim = RaceSimulator()
    sim.restore(copy.deepcopy(pc.checkpoint_blob), pc.spec)
    donor = selected_donors(bank, "C0_p1")[0]

    def _val(plan):
        sim.validate_plan(plan)

    hy = assemble_portfolio(
        pc.instance, pc.qubo, choice="C0_p1", seed=1, pool_size=128, sim_validate=_val,
        params=(list(donor["gammas"]), list(donor["betas"])), family="C0", p_depth=1, equal_k=4,
        legal_table=pc.legal_table,
    )
    cl = assemble_portfolio(
        pc.instance, pc.qubo, choice="classical_only", seed=1, pool_size=8, sim_validate=_val,
        params=None, family=None, p_depth=1, equal_k=4, legal_table=pc.legal_table,
    )
    cl_set = set(cl["classical_k_hashes"])
    for c in hy["downstream_candidates"]:
        if c["plan_hash"] in cl_set and "quantum" in (c.get("found_by") or []):
            assert c.get("quantum_incremental_at_k") is False
            assert "classical" in (c.get("found_by") or [])


@pytest.mark.skipif(not ANCHORS.is_file(), reason="pinned reused anchors missing")
def test_planning_outcomes_can_select_or_reject_incremental():
    bank = _bank()
    pc = prepare_case(
        family_id="fam.green_pit_high.tyre_nonlinear.traffic_dense",
        block_id="a4.int.sel",
        regime="SC",
        partition="train",
        index=1,
        seed=13,
    )
    rec_cl = decide_and_evaluate(
        pc.spec, mode="always_classical", runtime=None, donor_bank=bank, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12], online_seed=3, cache={},
        pool_size=64, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
        family_depth=("C0", 1), legal_table=pc.legal_table,
    )
    rec_hy = decide_and_evaluate(
        pc.spec, mode="always_c0", runtime=None, donor_bank=bank, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12], online_seed=3, cache={},
        pool_size=64, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
        family_depth=("C0", 1), legal_table=pc.legal_table,
    )
    cl_h = set(rec_cl["portfolio"]["candidate_plan_hashes"])
    hy_h = set(rec_hy["portfolio"]["candidate_plan_hashes"])
    assert rec_cl["portfolio"]["n_downstream"] == rec_hy["portfolio"]["n_downstream"] == 4
    # Difference is allowed to be empty; if membership differs it must be real hashes.
    if cl_h != hy_h:
        assert (hy_h - cl_h).issubset({r["plan_hash"] for r in pc.legal_table})


def test_all_four_family_depths_and_three_seeds():
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.int.depth",
        regime="VSC",
        partition="tune",
        index=0,
        seed=2,
    )
    hashes = []
    for fam, p in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        rec = decide_and_evaluate(
            pc.spec, mode="always_c0" if fam == "C0" else "always_c1", runtime=None,
            donor_bank=None, donor_policy="fixed",
            planning_seeds=[1], evaluation_seeds=[11], online_seed=8, cache={},
            pool_size=16, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
            family_depth=(fam, p), n_stochastic_seeds=3, legal_table=pc.legal_table,
        )
        assert rec["family_depth"] == f"{fam}_p{p}"
        hashes.append(rec["plan_hash"])
        if rec["portfolio"].get("quantum_pool"):
            assert rec["portfolio"]["quantum_pool"]["requested_shots"] == 16
            assert rec["portfolio"].get("n_stochastic_seeds") == 3
            assert len(rec["portfolio"].get("quantum_seed_receipts") or []) == 3
    assert len(hashes) == 4


def test_zero_utility_same_plan_label_retained():
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.int.zero",
        regime="SC",
        partition="train",
        index=0,
        seed=4,
    )
    cache = {}
    a = decide_and_evaluate(
        pc.spec, mode="always_classical", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12], online_seed=1, cache=cache,
        pool_size=8, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
        legal_table=pc.legal_table,
    )
    b = decide_and_evaluate(
        pc.spec, mode="always_classical", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12], online_seed=1, cache=cache,
        pool_size=8, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
        legal_table=pc.legal_table,
    )
    benefit = (a["mean_loss"] or 0) - (b["mean_loss"] or 0)
    assert a["plan_hash"] == b["plan_hash"]
    assert abs(benefit) < 1e-12


def test_offline_helper_covers_all_legal_not_copy():
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.int.off",
        regime="SC",
        partition="calib",
        index=0,
        seed=6,
    )
    legal = enumerate_legal_policies(pc.instance)
    assert len(legal) == len(pc.legal_table)
    rec = decide_and_evaluate(
        pc.spec, mode="always_classical", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1], evaluation_seeds=[11], online_seed=1, cache={},
        pool_size=8, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
        legal_table=pc.legal_table,
    )
    off = evaluate_offline_reference(
        pc.spec_with_budget(30.0),
        pc.checkpoint_blob,
        pc.legal_table,
        planning_seeds=[101, 102],
        evaluation_seeds=[201, 202],
        cache={},
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
        commitment_epoch_race_s=float(pc.window_for_budget(30.0)["effective_end_race_s"]),
    )
    assert off["all_plan_coverage"] is True
    assert off["n_legal_evaluated"] == len(legal)
    assert off["copied_from_arm"] is False
    assert rec["mean_loss"] is not None
    assert off["evaluation_loss"] is not None
    assert len(legal) >= rec["portfolio"]["n_downstream"]


def test_donor_save_reload_rejects_order_change():
    rng = np.random.default_rng(0)
    donors = [{"donor_id": f"d{i}", "features": {"n_logical_vars": float(i)}} for i in range(4)]
    X = rng.normal(size=(10, 16))
    y = rng.normal(size=(10, 4))
    r = DonorRanker(1.0)
    art = r.fit(X, y, [d["donor_id"] for d in donors], family_depth="C0_p1")
    r2 = DonorRanker.from_artifact(art)
    feats = {k: 0.0 for k in r.feature_keys}
    a = r.predict_scores(feats)
    b = r2.predict_scores(feats)
    assert np.allclose(a, b)
    shuffled = list(reversed(donors))
    with pytest.raises(Exception):
        r2.select(feats, shuffled)

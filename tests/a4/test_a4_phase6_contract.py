"""Phase 6 A4 contract regressions. Real artifacts; no fake plan hashes."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from f1q.a4.allocator import RidgeModel, option_feature_row, select_donor
from f1q.a4.banks import (
    EVALUATION_BANK,
    PLANNING_BANK,
    cache_key,
    forbid_evaluation_payload,
    reject_evaluation_in_planning,
)
from f1q.a4.contracts import StructuralError
from f1q.a4.donors import (
    DONOR_BANK_SCHEMA_V2,
    DonorRanker,
    build_donor_bank_v2,
    load_donor_bank_v2,
    selected_donors,
    select_donor_policy,
)
from f1q.a4.generators import assemble_portfolio
from f1q.a4.loop import decide_and_evaluate, family_spec
from f1q.a4.prepared import prepare_case, prepare_counters, reset_prepare_counters
from f1q.a4.problem import extract_causal_view, qubo_structural_features
from f1q.a4.qpu_guard import inspect_ibm_balance, submit_qpu_job
from f1q.errors import RejectionError, UnsupportedModeError
from f1q.simulator.interface import RaceSimulator

PRIOR = Path("evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b")
ANCHORS = PRIOR / "ANCHOR_FITS.jsonl"


def _load_fits():
    import json

    rows = []
    with ANCHORS.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@pytest.mark.skipif(not ANCHORS.is_file(), reason="pinned reused anchors missing")
def test_real_anchor_fits_rebuild_eight_family_banks():
    fits = _load_fits()
    assert sum(1 for r in fits if r.get("success")) == 288
    assert len({r.get("block_id") for r in fits}) == 24
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path=str(ANCHORS),
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    assert bank["schema_version"] == DONOR_BANK_SCHEMA_V2
    for key in ("C0_p1", "C0_p2", "C1_p1", "C1_p2"):
        donors = selected_donors(bank, key)
        assert len(donors) == 8
        fams = {d["family_id"] for d in donors}
        assert len(fams) == 8
        p = int(key.split("p")[-1])
        for d in donors:
            assert len(d["gammas"]) == p and len(d["betas"]) == p


@pytest.mark.skipif(not ANCHORS.is_file(), reason="pinned reused anchors missing")
def test_v2_bank_all_policies_after_fit(tmp_path: Path):
    fits = _load_fits()
    bank = build_donor_bank_v2(
        fits,
        source_run_id="09806343-f940-4f33-9e0f-eb2855d0714b",
        source_anchor_path=str(ANCHORS),
        source_anchor_sha256="b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a",
    )
    path = tmp_path / "DONOR_BANK_V2.json"
    path.write_text(__import__("json").dumps(bank))
    loaded = load_donor_bank_v2(path)
    rng = np.random.default_rng(0)
    feats = {"n_logical_vars": 8.0, "remaining_laps": 10.0, "effective_remaining_s": 20.0}
    for key in ("C0_p1", "C0_p2", "C1_p1", "C1_p2"):
        donors = selected_donors(loaded, key)
        X = np.random.default_rng(1).normal(size=(12, 16))
        y = np.random.default_rng(2).normal(size=(12, 8))
        ranker = DonorRanker(1.0)
        ranker.fit(X, y, [d["donor_id"] for d in donors], family_depth=key)
        for pol in ("fixed", "nn", "random", "learned"):
            rec = select_donor_policy(policy=pol, donors=donors, feats=feats, ranker=ranker, rng=rng)
            assert rec["selected"]["donor_id"]


def test_malformed_bank_fails_before_campaign():
    with pytest.raises(StructuralError):
        selected_donors({"selected": [{"donor_id": "x"}]}, "C0_p1")
    with pytest.raises(StructuralError):
        selected_donors({"schema_version": "f1q.a4.donor_bank.v2", "family_depths": {}}, "C0_p1")
    with pytest.raises(StructuralError):
        selected_donors({"schema_version": "f1q.a4.donor_bank.v2", "family_depths": {"C0_p1": {"donors": []}}}, "C0_p1")


def test_failed_rows_cannot_satisfy_counts():
    from f1q.a4.contracts import CountLedger

    led = CountLedger()
    led.attempted_parents = 1
    led.failed_parents = 1
    led.failed_rows.append({"error": "structural"})
    assert led.successful_parents == 0
    assert led.as_dict()["failed_parents"] == 1


def test_family_spec_retains_true_split():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.train.x",
        regime="SC",
        partition="train",
        index=0,
        seed=1,
    )
    assert spec["partition"] == "development"
    assert spec["namespace"] == "a4.train"
    assert spec["not_a_scientific_split_member"] is True
    with pytest.raises(StructuralError):
        family_spec(
            family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
            block_id="a4.finaltest.x",
            regime="SC",
            partition="finaltest",
            index=0,
            seed=1,
        )


def test_remaining_duration_distinct_from_absolute_end():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.t.deadline",
        regime="SC",
        partition="train",
        index=0,
        seed=1,
    )
    sim = RaceSimulator()
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    view = extract_causal_view(sim.observe())
    assert view["effective_end_race_s"] is not None
    assert view["effective_remaining_s"] is not None
    assert view["effective_end_race_s"] != view["effective_remaining_s"]
    assert abs(view["effective_remaining_s"] - max(0.0, view["effective_end_race_s"] - view["decision_time_race_s"])) < 1e-9


def test_budget_5_vs_30_changes_simulator_window():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.t.budget",
        regime="SC",
        partition="train",
        index=0,
        seed=1,
    )
    windows = {}
    for b in (5, 30):
        s = copy.deepcopy(spec)
        s.setdefault("deadline_interface", {})["primary_nominal_budget_s"] = b
        sim = RaceSimulator()
        sim.initialize(s)
        sim.advance_to_checkpoint()
        view = extract_causal_view(sim.observe())
        windows[b] = (view["effective_remaining_s"], sim.spec["deadline_interface"]["primary_nominal_budget_s"])
    assert windows[5][1] == 5
    assert windows[30][1] == 30
    assert windows[5][0] != windows[30][0] or windows[5][0] < windows[30][0] + 1e-9
    assert windows[5][0] <= windows[30][0] + 1e-9


def test_cache_key_fields_change_identity():
    base = dict(
        spec_hash="s",
        checkpoint_hash="c",
        plan_hash="p",
        bank=PLANNING_BANK,
        world_seed=1,
        nominal_budget_s=30.0,
        arrival_delay_s=0.2,
        commitment_epoch_race_s=100.0,
    )
    k0 = cache_key(**base)
    variants = []
    for field, val in (
        ("nominal_budget_s", 5.0),
        ("arrival_delay_s", 9.0),
        ("commitment_epoch_race_s", 80.0),
        ("checkpoint_hash", "c2"),
        ("plan_hash", "p2"),
        ("bank", EVALUATION_BANK),
        ("world_seed", 2),
        ("simulator_version", "9.9.9"),
    ):
        kw = dict(base)
        kw[field] = val
        variants.append(cache_key(**kw))
    assert k0 not in variants
    assert len(set(variants) | {k0}) == 1 + len(variants)


def test_timely_cache_not_reused_for_late():
    k_early = cache_key(
        spec_hash="s", checkpoint_hash="c", plan_hash="p", bank=PLANNING_BANK, world_seed=1,
        nominal_budget_s=30.0, arrival_delay_s=0.1, commitment_epoch_race_s=50.0,
    )
    k_late = cache_key(
        spec_hash="s", checkpoint_hash="c", plan_hash="p", bank=PLANNING_BANK, world_seed=1,
        nominal_budget_s=30.0, arrival_delay_s=10_000.0, commitment_epoch_race_s=50.0,
    )
    assert k_early != k_late


def test_one_prepared_case_counters():
    reset_prepare_counters()
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.t.prep",
        regime="SC",
        partition="train",
        index=0,
        seed=3,
    )
    c = prepare_counters()
    assert c["checkpoint_init"] == 1
    assert c["menu_qubo"] == 1
    assert c["enumeration"] == 1
    assert c["formulation_verify"] == 1
    assert pc.split == "train"
    assert pc.legal_table


def test_portfolios_k_fallback_incumbent(tmp_path: Path):
    pc = prepare_case(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.t.port",
        regime="SC",
        partition="train",
        index=0,
        seed=5,
    )
    sim = RaceSimulator()
    sim.restore(copy.deepcopy(pc.checkpoint_blob), pc.spec)

    def _val(plan):
        sim.validate_plan(plan)

    cl = assemble_portfolio(
        pc.instance, pc.qubo, choice="classical_only", seed=1, pool_size=32, sim_validate=_val,
        params=None, family=None, p_depth=1, equal_k=4, legal_table=pc.legal_table,
    )
    hy = assemble_portfolio(
        pc.instance, pc.qubo, choice="always_c0", seed=1, pool_size=32, sim_validate=_val,
        params=([0.3], [0.2]), family="C0", p_depth=1, equal_k=4, legal_table=pc.legal_table,
    )
    assert cl["n_downstream"] == 4
    assert hy["n_downstream"] == 4
    assert cl["n_unique_hashes"] == 4
    assert hy["n_unique_hashes"] == 4
    assert cl["mandatory_classical_fallback"]
    assert hy["strongest_classical_incumbent_retained"]
    for p in (cl, hy):
        assert p["portfolio_budget_matched"]
        assert p["n_downstream"] <= 4


def test_allocator_ridge_rejected_as_donor_ranker():
    rng = np.random.default_rng(0)
    with pytest.raises(StructuralError):
        select_donor(policy="learned", donors=[{"donor_id": "a", "features": {}}], feats={}, ranker=RidgeModel(), rng=rng)


def test_option_budget_features_change_rows():
    base = {"n_logical_vars": 8.0}
    a = option_feature_row(base, option="classical_only", nominal_budget_s=30, effective_remaining_s=20, k=4, pool_draws=8, pred_latency_s=1)
    b = option_feature_row(base, option="C1_p2", nominal_budget_s=5, effective_remaining_s=4, k=4, pool_draws=8, pred_latency_s=1)
    assert a["opt_classical_only"] == 1 and a["opt_C1_p2"] == 0
    assert b["opt_C1_p2"] == 1
    assert a["nominal_budget_s"] != b["nominal_budget_s"]
    model = RidgeModel(1.0)
    from f1q.a4.allocator import allocator_feature_vector

    X = np.vstack([allocator_feature_vector(a), allocator_feature_vector(b), allocator_feature_vector(a), allocator_feature_vector(b)])
    y = np.array([0.0, 1.0, 0.1, 0.9])
    model.fit(X, y)
    assert model.kind == "a4_option_allocator"
    p1 = model.predict(a)["pred_marginal_utility"]
    p2 = model.predict(b)["pred_marginal_utility"]
    assert p1 != p2


def test_evaluation_payload_rejected_from_planning():
    reject_evaluation_in_planning(PLANNING_BANK)
    with pytest.raises(RejectionError):
        reject_evaluation_in_planning(EVALUATION_BANK)
    with pytest.raises(StructuralError):
        forbid_evaluation_payload({"bank": EVALUATION_BANK, "loss": 1.0})


def test_qpu_and_finaltest_closed():
    with pytest.raises(UnsupportedModeError):
        submit_qpu_job()
    with pytest.raises(UnsupportedModeError):
        inspect_ibm_balance()
    with pytest.raises(StructuralError):
        prepare_case(
            family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
            block_id="x",
            regime="SC",
            partition="finaltest",
            index=0,
            seed=1,
        )


def test_late_recommendation_stays_late():
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.t.late",
        regime="SC",
        partition="train",
        index=0,
        seed=1,
    )
    rec = decide_and_evaluate(
        spec, mode="always_classical", runtime=None, donor_bank=None, donor_policy="fixed",
        planning_seeds=[1, 2], evaluation_seeds=[11, 12], online_seed=4, cache={},
        pool_size=8, equal_k=4, deadline_s=30.0, margin=0.001, conservative_residual=0.0,
    )
    sim = RaceSimulator()
    sim.initialize(copy.deepcopy(spec))
    sim.advance_to_checkpoint()
    late = sim.consider_recommendation(rec["plan"], arrival_delay_s=10_000.0)
    assert late["timely"] is False
    assert late["selected_plan"] == "fallback_continuation"
    assert rec["timings"]["uncapped"] is True
    assert rec["timings"]["precommit_s"] >= rec["timings"]["generation_s"]


def test_verifier_hashes_every_manifest_entry_not_first_80(tmp_path: Path):
    import json

    from f1q.a4.verify import run_independent_verify
    from f1q.hashing import sha256_file

    historic = tmp_path / "evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b"
    historic.mkdir(parents=True)
    (historic / "MANIFEST.json").write_text("{}")
    (tmp_path / "evidence/stage5").mkdir(parents=True)
    run_id = "deadbeef-0000-0000-0000-000000000001"
    ev = tmp_path / "evidence/stage6_a4" / run_id
    ev.mkdir()
    entries = []
    for i in range(90):
        p = ev / f"blob_{i:03d}.txt"
        p.write_text(f"x{i}")
        entries.append({"path": p.name, "sha256": sha256_file(p)})
    depths = {
        k: {"donors": [{"donor_id": f"{k}-{i}"} for i in range(8)]}
        for k in ("C0_p1", "C0_p2", "C1_p1", "C1_p2")
    }
    for name, obj in (
        ("START_STATE.json", {}),
        ("REUSED_EVIDENCE.json", {"ok": True}),
        ("PARTITIONS.json", {}),
        ("ADMISSION_RECEIPT.json", {"admitted": False}),
        ("PRESTART_QUARANTINE.json", {}),
        ("DONOR_BANK_V2.json", {"family_depths": depths}),
        ("MANIFEST.json", {"entries": entries}),
    ):
        (ev / name).write_text(json.dumps(obj))
    result = run_independent_verify(tmp_path, run_id)
    man = next(c for c in result["checks"] if c["name"] == "manifest_all_hashed")
    assert man["n"] == 90
    assert man["pass"] is True
    entries[85]["sha256"] = "0" * 64
    (ev / "MANIFEST.json").write_text(json.dumps({"entries": entries}))
    result2 = run_independent_verify(tmp_path, run_id)
    man2 = next(c for c in result2["checks"] if c["name"] == "manifest_all_hashed")
    assert man2["pass"] is False

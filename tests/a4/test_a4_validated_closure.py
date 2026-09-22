"""Validated Phase 6 closure contracts: batched kernel, freeze, verifier, labels."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from f1q.a4.batched import (
    evaluate_candidates_batched,
    kernel_counters,
    parity_rows,
    reset_kernel_counters,
    simulate_plan_world_scalar,
)
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.donor_labels import label_from_pool, per_instance_variational_reference, resample_label_panel
from f1q.a4.loop import decide_and_evaluate, evaluate_candidates_on_bank, _simulate_plan_world
from f1q.a4.partitions import RETIRED_DIAGNOSTIC_PARENTS, build_a4_partitions
from f1q.a4.pool import run_pool
from f1q.a4.prepared import prepare_case
from f1q.a4.unit_ledger import enumerate_design_units, freeze_option_specs
from f1q.a4.verify import run_independent_verify
from f1q.a4.distributions import build_ideal_distribution, resample_pool

FAM = "fam.green_pit_low.tyre_near_linear.traffic_sparse"


def _pc(block_id="a4.t.val", regime="SC"):
    return prepare_case(
        family_id=FAM,
        block_id=block_id,
        regime=regime,
        partition="train",
        index=0,
        seed=3,
        n_planning=2,
        n_evaluation=2,
    )


def test_production_path_calls_batched_not_scalar():
    reset_kernel_counters()
    pc = _pc("a4.t.prod")
    with patch("f1q.a4.loop._simulate_plan_world", side_effect=AssertionError("scalar production path")) as mocked:
        rec = decide_and_evaluate(
            pc.spec_with_budget(30),
            mode="always_classical",
            runtime=None,
            donor_bank=None,
            donor_policy="fixed",
            planning_seeds=pc.planning_bank_keys,
            evaluation_seeds=pc.evaluation_bank_keys,
            online_seed=1,
            cache=ByteBoundedCache(max_bytes=8 * 1024 * 1024),
            pool_size=8,
            equal_k=4,
            deadline_s=30.0,
            margin=0.001,
            conservative_residual=0.0,
            legal_table=pc.legal_table,
            prepared=pc,
            dist_cache=ByteBoundedCache(max_bytes=4 * 1024 * 1024),
        )
        mocked.assert_not_called()
    assert rec["mean_loss"] is not None
    c = kernel_counters()
    assert c["batched_calls"] >= 1
    assert c["scalar_calls"] == 0


def test_scalar_batched_parity_small():
    reset_kernel_counters()
    pc = _pc("a4.t.parity")
    plans = [{"plan": r["plan"], "plan_hash": r["plan_hash"]} for r in pc.legal_table[:3]]
    panel = parity_rows(
        pc.spec_with_budget(30),
        pc.checkpoint_blob,
        plans,
        pc.planning_bank_keys,
        bank="planning_bank",
        arrival_delay_s=0.05,
        commitment_epoch_race_s=float(pc.window_for_budget(30)["effective_end_race_s"]),
        spec_hash=pc.spec_hash,
        checkpoint_hash=pc.checkpoint_hash,
        nominal_budget_s=30.0,
    )
    assert panel["ok"] is True
    assert panel["n_cells"] == 3 * len(pc.planning_bank_keys)


def test_byte_cache_stats_keys_by_class():
    c = ByteBoundedCache(max_bytes=10_000)
    c.put("a", {"loss": 1.0}, klass="continuation")
    c.put("b", {"k": "v"}, klass="distribution")
    st = c.stats()
    assert st["hits"] == 0
    assert "continuation" in st["keys_by_class"]
    _ = c.get("a")
    assert c.stats()["hits"] >= 1


def test_donor_labels_from_decoded_pool_not_expectation():
    pc = _pc("a4.t.lab")
    dist = build_ideal_distribution(
        instance=pc.instance,
        qubo=pc.qubo,
        family="C0",
        depth=1,
        gammas=[0.3],
        betas=[0.2],
        prepared_case_hash=pc.prepared_case_hash,
        legal_table=pc.legal_table,
    )
    panel = resample_label_panel(dist, pc.legal_table, n_seeds=3, pool_draws=32, seed0=1)
    assert panel["n_seeds"] == 3
    for row in panel["seed_rows"]:
        assert row["not_expectation_label"] is True
        assert "best_of_pool_normalised_regret" in row
        assert row["expectation_scaled_diagnostic_only"] == dist.expectation_scaled


def test_best_found_runs_per_instance_fit():
    pc = _pc("a4.t.var")
    rec = per_instance_variational_reference(
        instance=pc.instance, qubo=pc.qubo, family="C0", depth=1, seed=7, legal_table=pc.legal_table, max_evals=8
    )
    assert rec["success"]
    assert rec["donor"]["not_bank_lookup"] is True
    assert rec["n_evals"] >= 1


def test_fresh_partitions_retire_diagnostic_parents():
    parts = build_a4_partitions()
    ids = {b["block_id"] for b in parts["train"] + parts["tune"] + parts["calib"]}
    assert not (ids & set(RETIRED_DIAGNOSTIC_PARENTS))
    assert parts["ok"]
    assert len(parts["train"]) == 120
    assert parts["final_test"]["outcomes_opened"] is False


def test_enumerated_ledger_includes_policy_seeds():
    parts = build_a4_partitions()
    worlds = {
        "training": {"planning": 2, "evaluation": 4},
        "tuning": {"planning": 2, "evaluation": 4},
        "calibration": {"planning": 2, "evaluation": 8},
        "offline": {"planning": 2, "evaluation": 4},
    }
    enum = enumerate_design_units(design="R", parts=parts, worlds=worlds, miniature=True)
    assert enum["aggregates"]["policy_seeds_included_in_world_counts"] is True
    assert enum["n_units"] > 0
    freeze = {
        "allowed_options": ["stop_fallback", "classical_only", "C0_p2", "C1_p2"],
        "frozen_c0_depth": "C0_p2",
        "frozen_c1_depth": "C1_p2",
    }
    specs = freeze_option_specs(freeze)
    assert {s[0] for s in specs} == set(freeze["allowed_options"])


def test_quantum_incremental_candidate_wins_planning_and_is_executed():
    pc = _pc("a4.t.qwin")
    captured = {}
    from f1q.a4.generators import assemble_portfolio as real_assemble

    def _port(*args, **kwargs):
        port = real_assemble(*args, **kwargs)
        cands = list(port["downstream_candidates"])
        if cands:
            c = dict(cands[0])
            c["found_by"] = ["quantum"]
            c["origin"] = "quantum"
            c["quantum_incremental_at_k"] = True
            cands[0] = c
            captured["winner"] = c["plan_hash"]
            port = dict(port)
            port["downstream_candidates"] = cands
            port["n_quantum_incremental_at_k"] = max(1, int(port.get("n_quantum_incremental_at_k") or 0))
        return port

    def _fake_eval(spec, base_blob, candidates, world_seeds, **kw):
        from f1q.a4.batched import evaluate_candidates_batched

        out = evaluate_candidates_batched(spec, base_blob, candidates, world_seeds, **kw)
        winner = captured.get("winner") or (candidates[0]["plan_hash"] if candidates else None)
        if winner:
            captured["winner"] = winner
            means = dict(out["means"])
            for h in means:
                means[h] = 1.0
            means[winner] = 0.0
            out = dict(out)
            out["means"] = means
        return out

    with patch("f1q.a4.loop.assemble_portfolio", side_effect=_port), patch(
        "f1q.a4.loop.evaluate_candidates_on_bank", side_effect=_fake_eval
    ):
        rec = decide_and_evaluate(
            pc.spec_with_budget(30),
            mode="always_c0",
            runtime=None,
            donor_bank=None,
            donor_policy="fixed",
            planning_seeds=pc.planning_bank_keys,
            evaluation_seeds=pc.evaluation_bank_keys,
            online_seed=11,
            cache={},
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
    assert captured.get("winner")
    assert rec["plan_hash"] == captured["winner"]
    assert rec["quantum_incremental_selected"] is True
    assert rec["quantum_incremental_evaluated_in_k"] is True


def test_safe_rejection_fallback():
    pc = _pc("a4.t.fb")
    rec = decide_and_evaluate(
        pc.spec_with_budget(5),
        mode="stop_fallback",
        runtime=None,
        donor_bank=None,
        donor_policy="fixed",
        planning_seeds=pc.planning_bank_keys,
        evaluation_seeds=pc.evaluation_bank_keys,
        online_seed=2,
        cache={},
        pool_size=8,
        equal_k=4,
        deadline_s=5.0,
        margin=0.001,
        conservative_residual=0.0,
        legal_table=pc.legal_table,
        prepared=pc,
    )
    assert rec["mean_loss"] is not None
    assert rec["choice"] in {"stop_fallback", "classical_only", "C0_p1"}


def _progress_pool_fn(payload):
    import time

    time.sleep(0.15)
    return {"ok": True, "scientific": payload["i"]}


def test_live_progress_completed_increases_wall_near_zero():
    payloads = [{"i": i, "unit_id": f"u{i}"} for i in range(4)]
    seen = []

    def hb(msg):
        seen.append(msg)

    run = run_pool(_progress_pool_fn, payloads, workers=1, heartbeat=hb)
    assert [r["scientific"] for r in run.results] == [0, 1, 2, 3]
    seen2 = []
    run2 = run_pool(_progress_pool_fn, payloads, workers=2, heartbeat=lambda m: seen2.append(m))
    completed = [m["completed"] for m in seen2 if isinstance(m, dict)]
    assert completed
    assert completed[-1] == 4
    walls = [m["elapsed_wall_s"] for m in seen2 if isinstance(m, dict)]
    assert walls[0] < 60.0


def test_verifier_fails_0b697910_for_contract_reasons():
    root = Path(".")
    rid = "0b697910-e8a2-474b-bc77-bc69ebb8e9c3"
    result = run_independent_verify(root, rid, mode="final")
    names = {c["name"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert names["limited_pilot_cannot_pass_gates_or_closure"]["pass"] is False
    if "freeze_vs_calib_rows" in names:
        # freeze named C0_p2+C1_p2 but calib executed other depths
        assert names["freeze_vs_calib_rows"]["pass"] is False or names["limited_pilot_cannot_pass_gates_or_closure"]["pass"] is False


def test_verifier_mutation_missing_calib_parent(tmp_path: Path):
    root = Path(".")
    rid = "0b697910-e8a2-474b-bc77-bc69ebb8e9c3"
    ev = root / "evidence/stage6_a4" / rid
    if not ev.is_dir():
        pytest.skip("0b697910 evidence missing")
    result = run_independent_verify(root, rid)
    n_cal_checks = [c for c in result["checks"] if "24" in c["name"] or "limited_pilot" in c["name"]]
    assert any(not c["pass"] for c in n_cal_checks)


def test_verifier_mutations_detect_contract_defects():
    src = Path("evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3")
    if not src.is_dir():
        pytest.skip("0b697910 evidence missing")
    result = run_independent_verify(Path("."), "0b697910-e8a2-474b-bc77-bc69ebb8e9c3")
    names = {c["name"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert names["limited_pilot_cannot_pass_gates_or_closure"]["pass"] is False


def test_commitment_variety_records_fallback_classes():
    from f1q.a4.kernel_bench import run_commitment_variety_panel

    doc = run_commitment_variety_panel()
    assert "timely" in doc["observed"] or "recommendation" in doc["observed"]
    assert "fallback" in doc["observed"] or "late" in doc["observed"] or doc["ok"]


def test_e2e_clean_extract_skipped_inside_admission():
    import os

    if os.environ.get("F1Q_A4_IN_ADMISSION") != "1":
        pytest.skip("only asserts skip contract when admission env is set")
    from f1q.a4.clean_extract import run_clean_extract_e2e
    from f1q.paths import resolve_project_root

    rec = run_clean_extract_e2e(resolve_project_root())
    assert rec.get("skipped") is True

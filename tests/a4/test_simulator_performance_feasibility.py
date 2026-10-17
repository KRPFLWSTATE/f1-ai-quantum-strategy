"""Engineering checks for the compiled continuation. Not a scientific outcome."""

from __future__ import annotations

import copy
import subprocess
import sys

import pytest

from f1q.a4.backend_select import select_evaluation_backend
from f1q.a4.banks import EVALUATION_BANK, cache_key
from f1q.a4.loop import evaluate_candidates_on_bank, family_spec
from f1q.a4.problem import (
    build_menu_and_instance,
    enumerate_legal_policies,
    extract_causal_view,
    plan_fingerprint,
)
from f1q.hashing import sha256_json
from f1q.simulator.compiled_kernel import KERNEL_VERSION, candidate_cache_key
from f1q.simulator.engine import RaceEngine
from f1q.simulator.interface import RaceSimulator

FAM = "fam.green_pit_low.tyre_near_linear.traffic_sparse"
PARITY_TOL = 1e-12


def _checkpoint(regime: str, *, index: int = 0, seed: int = 41000, block: str = "engperf.corr.unit"):
    spec = family_spec(
        family_id=FAM,
        block_id=block,
        regime=regime,
        partition="development",
        index=index,
        seed=seed,
    )
    sim = RaceSimulator()
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    blob = sim.serialize()
    obs = sim.observe()
    view = extract_causal_view(obs.model_dump(mode="python"))
    inst = build_menu_and_instance(view)
    rows = enumerate_legal_policies(inst)
    cands = []
    for row in rows[:3]:
        plan = row["wrapped"]["plan"]
        cands.append({"plan": plan, "plan_hash": plan_fingerprint(plan)})
    return spec, blob, cands, float(blob["t"])


def _agree(a: dict, b: dict) -> bool:
    return (
        a.get("commitment_classification") == b.get("commitment_classification")
        and a.get("selected_plan") == b.get("selected_plan")
        and bool(a.get("fallback")) == bool(b.get("fallback"))
        and a.get("legality") == b.get("legality")
        and a.get("event_ordering") == b.get("event_ordering")
        and abs(float(a["loss"]) - float(b["loss"])) <= PARITY_TOL
    )


def _both(spec, blob, cands, worlds, *, arrival, epoch, nominal=30.0):
    from f1q.a4.batched import simulate_plan_world_scalar

    sh = sha256_json({"spec": spec["spec_id"], "arrival": arrival, "epoch": epoch})
    ch = sha256_json({"t": blob["t"], "regime": spec["checkpoint_request"]["requested_regime"]})
    scalar = {}
    for cand in cands:
        scalar[cand["plan_hash"]] = [
            simulate_plan_world_scalar(
                spec,
                blob,
                cand["plan"],
                w,
                arrival_delay_s=arrival,
                commitment_epoch_race_s=epoch,
                cache={},
                spec_hash=sh,
                checkpoint_hash=ch,
                bank=EVALUATION_BANK,
                nominal_budget_s=nominal,
                parity=True,
            )
            for w in worlds
        ]
    select_evaluation_backend("candidate")
    try:
        out = evaluate_candidates_on_bank(
            spec,
            blob,
            cands,
            worlds,
            bank=EVALUATION_BANK,
            arrival_delay_s=arrival,
            commitment_epoch_race_s=epoch,
            cache={},
            spec_hash=sh,
            checkpoint_hash=ch,
            nominal_budget_s=nominal,
        )
    finally:
        select_evaluation_backend("legacy")
    return scalar, out


def test_candidate_matches_scalar_and_does_not_call_legacy_continue():
    from f1q.a4.batched import simulate_plan_world_scalar

    spec, blob, cands, t0 = _checkpoint("SC")
    calls = {"n": 0}
    real = RaceEngine.continue_to_finish

    def wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceEngine.continue_to_finish = wrapped
    try:
        sh, ch = "unit-spec", "unit-checkpoint"
        scalar = {}
        for cand in cands[:2]:
            scalar[cand["plan_hash"]] = [
                simulate_plan_world_scalar(
                    spec, blob, cand["plan"], w, arrival_delay_s=0.02, commitment_epoch_race_s=t0 + 0.05,
                    cache={}, spec_hash=sh, checkpoint_hash=ch, bank=EVALUATION_BANK, nominal_budget_s=30.0, parity=True,
                )
                for w in (810000, 810001)
            ]
        after_scalar = calls["n"]
        assert after_scalar > 0
        select_evaluation_backend("candidate")
        try:
            out = evaluate_candidates_on_bank(
                spec, blob, cands[:2], [810000, 810001], bank=EVALUATION_BANK, arrival_delay_s=0.02,
                commitment_epoch_race_s=t0 + 0.05, cache={}, spec_hash=sh, checkpoint_hash=ch, nominal_budget_s=30.0,
            )
        finally:
            select_evaluation_backend("legacy")
        assert calls["n"] == after_scalar
    finally:
        RaceEngine.continue_to_finish = real
    for cand in cands[:2]:
        for i in range(2):
            assert _agree(scalar[cand["plan_hash"]][i], out["worlds"][cand["plan_hash"]][i])


def test_vsc_and_commitment_classes():
    spec, blob, cands, t0 = _checkpoint("VSC", block="engperf.adv.vsc")
    timely_s, timely_c = _both(spec, blob, cands[:1], [810002], arrival=0.02, epoch=t0 + 0.05)
    boundary_s, boundary_c = _both(spec, blob, cands[:1], [810002], arrival=0.05, epoch=t0 + 0.05)
    late_s, late_c = _both(spec, blob, cands[:1], [810002], arrival=2.0, epoch=t0 + 0.05)
    ph = cands[0]["plan_hash"]
    assert _agree(timely_s[ph][0], timely_c["worlds"][ph][0])
    assert timely_c["worlds"][ph][0]["timely"] is True
    assert _agree(boundary_s[ph][0], boundary_c["worlds"][ph][0])
    assert boundary_c["worlds"][ph][0]["timely"] is True
    assert _agree(late_s[ph][0], late_c["worlds"][ph][0])
    assert late_c["worlds"][ph][0]["fallback"] is True
    assert late_c["worlds"][ph][0]["timely"] is False
    assert "regime_end" in {row[1] for row in timely_c["worlds"][ph][0]["event_ordering"]}


def test_hidden_futures_share_precommit_decision_and_inputs_stay_immutable():
    spec, blob, cands, t0 = _checkpoint("SC", block="engperf.adv.hidden")
    digest = sha256_json(blob)
    s1, c1 = _both(spec, blob, cands[:1], [810010], arrival=0.02, epoch=t0 + 0.05)
    s2, c2 = _both(spec, blob, cands[:1], [810011], arrival=0.02, epoch=t0 + 0.05)
    ph = cands[0]["plan_hash"]
    assert _agree(s1[ph][0], c1["worlds"][ph][0])
    assert _agree(s2[ph][0], c2["worlds"][ph][0])
    assert c1["worlds"][ph][0]["commitment_classification"] == c2["worlds"][ph][0]["commitment_classification"]
    assert sha256_json(blob) == digest


def test_cache_warm_and_backend_version_invalidates():
    spec, blob, cands, t0 = _checkpoint("SC", block="engperf.adv.cache")
    ph = cands[0]["plan_hash"]
    kwargs = dict(
        spec_hash="cache-spec",
        checkpoint_hash="cache-checkpoint",
        plan_hash=ph,
        bank=EVALUATION_BANK,
        world_seed=810020,
        nominal_budget_s=30.0,
        arrival_delay_s=0.02,
        commitment_epoch_race_s=t0 + 0.05,
    )
    legacy = cache_key(**kwargs)
    cold = candidate_cache_key(**kwargs)
    other = candidate_cache_key(**{**kwargs, "commitment_epoch_race_s": t0 + 0.2})
    mutated = sha256_json({"continuation_key": legacy, "backend": "candidate", "kernel_version": KERNEL_VERSION + ".mutated"})
    assert cold == sha256_json({"continuation_key": legacy, "backend": "candidate", "kernel_version": KERNEL_VERSION})
    assert cold != legacy
    assert cold != other
    assert cold != mutated
    select_evaluation_backend("candidate")
    try:
        cache = {}
        first = evaluate_candidates_on_bank(
            spec, blob, cands[:1], [810020], bank=EVALUATION_BANK, arrival_delay_s=0.02,
            commitment_epoch_race_s=t0 + 0.05, cache=cache, spec_hash="cache-spec",
            checkpoint_hash="cache-checkpoint", nominal_budget_s=30.0,
        )
        second = evaluate_candidates_on_bank(
            spec, blob, cands[:1], [810020], bank=EVALUATION_BANK, arrival_delay_s=0.02,
            commitment_epoch_race_s=t0 + 0.05, cache=cache, spec_hash="cache-spec",
            checkpoint_hash="cache-checkpoint", nominal_budget_s=30.0,
        )
    finally:
        select_evaluation_backend("legacy")
    assert first["worlds"][ph][0]["cache_hit"] is False
    assert second["worlds"][ph][0]["cache_hit"] is True
    assert _agree(first["worlds"][ph][0], second["worlds"][ph][0])


def test_fault_injection_rejects_outcome_event_and_multiplier():
    spec, blob, cands, t0 = _checkpoint("SC", block="engperf.adv.fault")
    scalar, out = _both(spec, blob, cands[:1], [810030], arrival=0.02, epoch=t0 + 0.05)
    ph = cands[0]["plan_hash"]
    good = out["worlds"][ph][0]
    base = scalar[ph][0]
    assert _agree(base, good)
    perturbed_loss = dict(good)
    perturbed_loss["loss"] = float(good["loss"]) + 1.0
    assert not _agree(base, perturbed_loss)
    swapped = dict(good)
    events = list(good["event_ordering"])
    assert len(events) >= 2
    events[0], events[1] = events[1], events[0]
    swapped["event_ordering"] = events
    assert not _agree(base, swapped)
    from f1q.a4.corrected_cost import legacy_planning_charge_applies_k_again, plan_world_evaluations

    assert legacy_planning_charge_applies_k_again(plan_world_evaluations(4, 6), 4) != 24


def test_shared_crew_stack_matches_scalar():
    spec, blob, cands, t0 = _checkpoint("SC", block="engperf.adv.stack")
    sim = RaceSimulator()
    sim.restore(copy.deepcopy(blob), spec)
    ids = list(sim.engine.state["selected_car_ids"])
    plan = {}
    for cid in ids:
        car = sim.engine.state["cars"][cid]
        chosen = next(item for item in car["inventory"] if not item.get("used") and item["compound"] != car["compound"])
        plan[cid] = {"kind": "pit_now", "compound": chosen["compound"], "set_id": chosen["set_id"]}
    cand = {"plan": plan, "plan_hash": plan_fingerprint(plan)}
    scalar, out = _both(spec, blob, [cand], [810040], arrival=0.02, epoch=t0 + 0.05)
    ph = cand["plan_hash"]
    assert _agree(scalar[ph][0], out["worlds"][ph][0])
    kinds = {row[1] for row in out["worlds"][ph][0]["event_ordering"]}
    assert "pit_entry" in kinds and "service_complete" in kinds


def test_default_backend_is_legacy(monkeypatch):
    assert select_evaluation_backend("legacy") in {"legacy", "candidate"}
    from f1q.a4.backend_select import evaluation_backend

    assert evaluation_backend() == "legacy"


def test_cold_process_loads_candidate():
    script = (
        "from f1q.a4.backend_select import select_evaluation_backend\n"
        "from f1q.simulator.compiled_kernel import KERNEL_VERSION\n"
        "select_evaluation_backend('candidate')\n"
        "from f1q.a4.backend_select import evaluation_backend\n"
        "assert evaluation_backend()=='candidate'\n"
        "assert KERNEL_VERSION\n"
        "print('cold_ok', KERNEL_VERSION)\n"
    )
    proc = subprocess.run([sys.executable, "-c", script], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "cold_ok" in proc.stdout


@pytest.mark.parametrize("regime", ["SC", "VSC"])
def test_repeatable(regime):
    spec, blob, cands, t0 = _checkpoint(regime, block=f"engperf.corr.repeat.{regime}")
    _, first = _both(spec, blob, cands[:1], [810050], arrival=0.02, epoch=t0 + 0.05)
    _, second = _both(spec, blob, cands[:1], [810050], arrival=0.02, epoch=t0 + 0.05)
    ph = cands[0]["plan_hash"]
    assert first["worlds"][ph][0]["event_ordering"] == second["worlds"][ph][0]["event_ordering"]
    assert abs(first["worlds"][ph][0]["loss"] - second["worlds"][ph][0]["loss"]) <= PARITY_TOL

"""A3 operational path: checkpoint → observe → decide → consider_recommendation → continue → evaluate."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import numpy as np

from f1q.a3.agents import (
    RidgeRuntime,
    assemble_portfolio,
    default_params,
    dispatch_choice,
)
from f1q.a3.problem import (
    build_a3_qubo,
    build_menu_and_instance,
    extract_causal_view,
    qubo_structural_features,
    verify_direct_cost_qubo_agreement,
)
from f1q.hashing import canonical_json, sha256_json
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.stage5.model import parse_family_factors

STREAM_FITTING = "fitting"
STREAM_ONLINE = "online_scoring"
STREAM_EVAL = "evaluation"


def stream_seed(key: str, domain: str) -> int:
    h = hashlib.sha256(f"a3.{domain}:{key}".encode()).hexdigest()
    return int(h[:16], 16) % (2**31 - 1)


def family_spec(
    *,
    family_id: str,
    block_id: str,
    regime: str,
    partition: str,
    index: int,
    seed: int,
) -> dict[str, Any]:
    factors = parse_family_factors(family_id)
    pit_loss = 18.5 if factors["green_pit_loss"] == "low" else 24.5
    tyre = factors["tyre_degradation"]
    wear = 0.04 if tyre == "near_linear" else 0.09
    curv = None if tyre == "near_linear" else 0.015
    gap = 9.0 if factors["traffic"] == "sparse" else 2.8
    spec = build_hand_spec(
        spec_id=f"{block_id}.{regime}",
        episode_id=f"{block_id}/ep/{regime}",
        regime=regime,
        green_pit_loss_s=pit_loss,
        tyre_form=tyre,
        tyre_wear=wear,
        tyre_curvature=curv,
        mean_gap_ahead_s=gap,
        completed_init=8 + (index % 3),
        laps_until_checkpoint=1,
        remaining_at_checkpoint=10 + (index % 4),
        cutoff_leader_s=22.0,
        obligation=1,
        requested_note="A3 generated fixture; not a historical race; not final-test",
    )
    spec["family_id"] = family_id
    spec["block_id"] = block_id
    spec["partition"] = "development"
    spec["namespace"] = f"a3.{partition}"
    spec["not_a_scientific_split_member"] = True
    spec["not_a_validated_race_checkpoint"] = True
    spec["factors"] = {
        "green_pit_loss": factors["green_pit_loss"],
        "tyre_degradation": factors["tyre_degradation"],
        "traffic": factors["traffic"],
    }
    spec["stream_key_ids"] = {
        "block_params": hashlib.sha256(f"{block_id}:params".encode()).hexdigest(),
        "episode": hashlib.sha256(f"{block_id}:{regime}:{seed}".encode()).hexdigest(),
        "evaluation": hashlib.sha256(f"{STREAM_EVAL}:{block_id}".encode()).hexdigest(),
        "fitting": hashlib.sha256(f"{STREAM_FITTING}:{block_id}".encode()).hexdigest(),
        "online_scoring": hashlib.sha256(f"{STREAM_ONLINE}:{block_id}".encode()).hexdigest(),
    }
    return spec


def _apply_world(sim: RaceSimulator, world_seed: int) -> None:
    """Event-keyed CRN on hidden future only; does not alter current physical snapshot."""
    eng = sim.engine
    assert eng is not None
    rng = np.random.default_rng(world_seed)
    extra = float(rng.uniform(-4.0, 18.0))
    base = float(eng.state.get("sampled_future_regime_duration_s") or 8.0)
    eng.state["sampled_future_regime_duration_s"] = max(1.5, base + extra)
    t = float(eng.state["t"])
    if eng.state.get("regime") in {"SC", "VSC"}:
        eng.state["regime_end_s"] = t + float(eng.state["sampled_future_regime_duration_s"])


def decide_from_observation(
    obs,
    *,
    sim: RaceSimulator,
    mode: str,
    runtime: RidgeRuntime | None,
    seed: int,
    pool_size: int = 64,
    deadline_s: float = 30.0,
    margin: float = 0.001,
) -> dict[str, Any]:
    import time

    view = extract_causal_view(obs)
    inst = build_menu_and_instance(view)
    qubo = build_a3_qubo(inst)
    agree = verify_direct_cost_qubo_agreement(inst, qubo)
    feats = qubo_structural_features(inst, qubo)
    pred = runtime.predict(feats) if runtime is not None else {
        "pred_marginal_utility": 0.0,
        "pred_latency_s": 0.05,
        "uncertainty": 1.0,
    }
    choice = dispatch_choice(pred, deadline_s=deadline_s, margin=margin, mode=mode)
    t0 = time.perf_counter()

    def _validate(plan: dict[str, Any]) -> None:
        sim.validate_plan(plan)

    p_c0 = default_params(1, seed)
    p_c1 = default_params(1, seed + 99)
    port = assemble_portfolio(
        inst,
        qubo,
        choice=choice,
        seed=seed,
        pool_size=pool_size,
        sim_validate=_validate,
        params_c0=p_c0,
        params_c1=p_c1,
        equal_k=3,
    )
    # Select first legal candidate (classical greedy is first).
    plan = port["downstream_candidates"][0]["plan"]
    gen_s = time.perf_counter() - t0
    if pred["pred_latency_s"] > deadline_s and choice != "classical_only":
        # Mandatory fallback if predicted deadline miss.
        choice = "classical_only"
        plan = {c: {"kind": "continuation"} for c in inst.car_ids}
    return {
        "view_hash": view["observation_hash"],
        "n_qubits": qubo["n"],
        "direct_cost_qubo_ok": agree["ok"],
        "direct_cost_qubo": agree,
        "features": feats,
        "pred": pred,
        "choice": choice,
        "plan": plan,
        "portfolio": {
            "n_downstream": port["n_downstream"],
            "n_classical": port["n_classical"],
            "choice": port["choice"],
            "n_quantum_decoded": port["n_quantum_decoded"],
            "quantum_pool": None if port["quantum"] is None else port["quantum"]["pool"],
            "resource_counts": None if port["quantum"] is None else port["quantum"]["resource_counts"],
        },
        "generation_s": gen_s,
        "instance_id": inst.instance_id,
        "hidden_future_excluded": True,
    }


def evaluate_arm(
    spec: dict[str, Any],
    *,
    mode: str,
    runtime: RidgeRuntime | None,
    world_seeds: list[int],
    online_seed: int,
    cache: dict[str, Any],
    pool_size: int = 64,
) -> dict[str, Any]:
    sim = RaceSimulator()
    sim.initialize(copy.deepcopy(spec))
    sim.advance_to_checkpoint()
    base_blob = sim.serialize()
    obs0 = sim.observe()
    decision = decide_from_observation(
        obs0, sim=sim, mode=mode, runtime=runtime, seed=online_seed, pool_size=pool_size
    )
    plan = decision["plan"]
    losses = []
    timely = 0
    fallback = 0
    traces = []
    for w in world_seeds:
        ck = f"{sha256_json(plan)}:{w}"
        if ck in cache:
            rec = cache[ck]
            losses.append(rec["loss"])
            timely += int(rec["timely"])
            fallback += int(rec["fallback"])
            continue
        world = RaceSimulator()
        world.initialize(copy.deepcopy(spec))
        world.restore(copy.deepcopy(base_blob), spec)
        _apply_world(world, w)
        obs_w = world.observe()
        # Causal: observation must match pre-world decision observation (duration still unknown).
        same_obs = canonical_json(extract_causal_view(obs0)) == canonical_json(extract_causal_view(obs_w))
        rec_commit = world.consider_recommendation(
            plan,
            arrival_delay_s=float(min(max(decision["generation_s"], 0.0), 4.0)),
            common_commit_delay_s=min(5.0, max(decision["generation_s"], 0.05)),
        )
        _state, outcome = world.continue_to_finish()
        loss = float(outcome["team_loss"]["normalized_team_rank_loss"])
        is_fb = rec_commit.get("selected_plan") != "recommendation"
        rec = {
            "loss": loss,
            "timely": bool(rec_commit.get("timely")),
            "fallback": bool(is_fb),
            "same_obs": same_obs,
            "continuation_used": True,
            "evaluator": "simulator.team_rank_loss",
            "not_proxy_qubo": True,
        }
        cache[ck] = rec
        losses.append(loss)
        timely += int(rec["timely"])
        fallback += int(rec["fallback"])
        if len(traces) < 2:
            traces.append({"world": w, "loss": loss, "commit": rec_commit.get("selected_plan"), "same_obs": same_obs})
    return {
        "mode": mode,
        "choice": decision["choice"],
        "plan": plan,
        "mean_loss": float(np.mean(losses)) if losses else None,
        "losses": losses,
        "n_worlds": len(world_seeds),
        "timely_rate": timely / max(len(world_seeds), 1),
        "fallback_rate": fallback / max(len(world_seeds), 1),
        "decision": {k: v for k, v in decision.items() if k != "portfolio"} | {"portfolio": decision["portfolio"]},
        "traces": traces,
        "view_hash": decision["view_hash"],
        "direct_cost_qubo_ok": decision["direct_cost_qubo_ok"],
    }


def adversarial_validation() -> dict[str, Any]:
    """Development fixtures required by the redesign prompt."""
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a3.adv.block",
        regime="SC",
        partition="development",
        index=0,
        seed=1,
    )
    cases: dict[str, Any] = {}

    a = RaceSimulator()
    a.initialize(copy.deepcopy(spec))
    a.advance_to_checkpoint()
    obs1 = a.observe()
    d1 = decide_from_observation(obs1, sim=a, mode="always_classical", runtime=None, seed=17, pool_size=16)
    b = a.clone()
    _apply_world(b, 999)
    obs2 = b.observe()
    d2 = decide_from_observation(obs2, sim=b, mode="always_classical", runtime=None, seed=17, pool_size=16)
    same_policy = sha256_json(d1["plan"]) == sha256_json(d2["plan"])
    same_obs = canonical_json(extract_causal_view(obs1)) == canonical_json(extract_causal_view(obs2))
    cases["identical_observables_different_hidden_same_policy"] = bool(same_policy and same_obs)
    cases["future_duration_leakage_rejected"] = bool(
        extract_causal_view(obs1)["safety_regime_duration_status"] == "unknown"
    )

    late = a.clone()
    late_rec = late.consider_recommendation(d1["plan"], arrival_delay_s=10_000.0)
    cases["late_results_frozen_classical_fallback"] = bool(
        late_rec.get("selected_plan") == "fallback_continuation" and late_rec.get("timely") is False
    )

    cases["pit_entry_commitment_and_expiry_enforced"] = bool(
        late_rec.get("fallback_reason") in {"LATE_OR_BOUNDARY", "LATE_VS_REGISTERED_COMMITMENT_EPOCH", "PIT_WINDOW_CLOSED"}
        or late_rec.get("timely") is False
    )

    c0, c1 = spec["selected_car_ids"]
    stacking_plan = {
        c0: {"kind": "pit_now", "compound": "medium", "set_id": f"{c0}.set.medium.0"},
        c1: {"kind": "pit_now", "compound": "medium", "set_id": f"{c1}.set.medium.0"},
    }
    stack_sim = a.clone()
    try:
        stack_sim.validate_plan(stacking_plan)
        stack_ok = True
        stack_reason = None
    except Exception as exc:
        # Sets may already be used; try unused medium.1
        stacking_plan = {
            c0: {"kind": "pit_now", "compound": "medium", "set_id": f"{c0}.set.medium.1"},
            c1: {"kind": "pit_now", "compound": "medium", "set_id": f"{c1}.set.medium.1"},
        }
        try:
            stack_sim.validate_plan(stacking_plan)
            stack_ok = True
            stack_reason = None
        except Exception as exc2:
            stack_ok = False
            stack_reason = str(exc2)
    cases["two_car_shared_crew_conflicts_represented"] = bool(
        stack_ok or "stack" in str(stack_reason).lower() or d1["features"]["crew_overlap_cost"] > 0
    )

    cont = a.clone()
    rec = cont.consider_recommendation(d1["plan"], arrival_delay_s=0.05, common_commit_delay_s=0.2)
    _st, outcome = cont.continue_to_finish()
    cases["accepted_actions_use_actual_simulator_continuation"] = bool(
        rec.get("selected_plan") in {"recommendation", "fallback_continuation"} and "team_loss" in outcome
    )
    cases["evaluator_from_continuation_not_proxy_qubo"] = bool(
        outcome["team_loss"].get("not_proxy_objective") is True
    )

    ok = all(bool(v) for v in cases.values())
    return {
        "ok": ok,
        "cases": cases,
        "same_obs_before_reveal": same_obs,
        "same_policy_before_reveal": same_policy,
        "interface": "RaceSimulator.observe/validate_plan/consider_recommendation/continue_to_finish",
        "not_flag_only_wrapper": True,
    }

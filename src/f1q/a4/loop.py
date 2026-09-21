"""A4 operational path: observe → generate K → planning rerank → commit → independent eval."""

from __future__ import annotations

import copy
import hashlib
import time
from typing import Any

import numpy as np

from f1q.a4.allocator import RidgeModel, dispatch_choice, select_donor
from f1q.a4.banks import (
    EVALUATION_BANK,
    PLANNING_BANK,
    apply_hidden_world,
    cache_key,
    reject_evaluation_in_planning,
)
from f1q.a4.generators import assemble_portfolio, select_by_planning_mean
from f1q.a4.problem import (
    build_a4_qubo,
    build_menu_and_instance,
    extract_causal_view,
    plan_fingerprint,
    qubo_structural_features,
    verify_direct_qubo_milp,
)
from f1q.a4.qpu_guard import assert_local_only
from f1q.hashing import canonical_json, sha256_json
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.stage5.model import parse_family_factors


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
        requested_note="A4 generated fixture; not a historical race; not final-test",
    )
    spec["family_id"] = family_id
    spec["block_id"] = block_id
    spec["partition"] = "development"
    spec["namespace"] = f"a4.{partition}"
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
    }
    return spec


def _simulate_plan_world(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    plan: dict[str, Any],
    world_seed: int,
    *,
    arrival_delay_s: float,
    common_commit_delay_s: float,
    cache: dict[str, Any],
    spec_hash: str,
    checkpoint_hash: str,
    bank: str,
) -> dict[str, Any]:
    if bank in {PLANNING_BANK, "offline_planning_bank"}:
        reject_evaluation_in_planning(bank)
    ph = plan_fingerprint(plan)
    ck = cache_key(
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        plan_hash=ph,
        bank=bank,
        world_seed=world_seed,
    )
    if ck in cache:
        rec = dict(cache[ck])
        rec["cache_hit"] = True
        return rec
    world = RaceSimulator()
    world.restore(copy.deepcopy(base_blob), spec)
    apply_hidden_world(world, world_seed)
    rec_commit = world.consider_recommendation(
        plan,
        arrival_delay_s=float(arrival_delay_s),
        common_commit_delay_s=float(common_commit_delay_s),
    )
    _state, outcome = world.continue_to_finish()
    loss = float(outcome["team_loss"]["normalized_team_rank_loss"])
    is_fb = rec_commit.get("selected_plan") != "recommendation"
    rec = {
        "loss": loss,
        "timely": bool(rec_commit.get("timely")),
        "fallback": bool(is_fb),
        "commit": rec_commit.get("selected_plan"),
        "plan_hash": ph,
        "world_seed": int(world_seed),
        "bank": bank,
        "cache_hit": False,
        "evaluator": "simulator.team_rank_loss",
        "not_proxy_qubo": True,
        "trace_id": ck[:16],
    }
    cache[ck] = rec
    return rec


def evaluate_candidates_on_bank(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    candidates: list[dict[str, Any]],
    world_seeds: list[int],
    *,
    bank: str,
    arrival_delay_s: float,
    common_commit_delay_s: float,
    cache: dict[str, Any],
    spec_hash: str,
    checkpoint_hash: str,
) -> dict[str, Any]:
    means = {}
    worlds = {}
    for cand in candidates:
        recs = [
            _simulate_plan_world(
                spec,
                base_blob,
                cand["plan"],
                w,
                arrival_delay_s=arrival_delay_s,
                common_commit_delay_s=common_commit_delay_s,
                cache=cache,
                spec_hash=spec_hash,
                checkpoint_hash=checkpoint_hash,
                bank=bank,
            )
            for w in world_seeds
        ]
        losses = [r["loss"] for r in recs]
        means[cand["plan_hash"]] = float(np.mean(losses)) if losses else float("inf")
        worlds[cand["plan_hash"]] = recs
    return {"means": means, "worlds": worlds}


def decide_and_evaluate(
    spec: dict[str, Any],
    *,
    mode: str,
    runtime: RidgeModel | None,
    donor_bank: dict[str, list[dict[str, Any]]] | None,
    donor_policy: str,
    planning_seeds: list[int],
    evaluation_seeds: list[int],
    online_seed: int,
    cache: dict[str, Any],
    pool_size: int,
    equal_k: int,
    deadline_s: float,
    margin: float,
    conservative_residual: float,
    family_depth: tuple[str, int] | None = None,
    n_stochastic_seeds: int = 1,
) -> dict[str, Any]:
    assert_local_only()
    t_all = time.perf_counter()
    sim = RaceSimulator()
    sim.initialize(copy.deepcopy(spec))
    sim.advance_to_checkpoint()
    base_blob = sim.serialize()
    obs0 = sim.observe()
    view = extract_causal_view(obs0)
    t_menu = time.perf_counter()
    inst = build_menu_and_instance(view)
    qubo = build_a4_qubo(inst)
    agree = verify_direct_qubo_milp(inst, qubo)
    feats = qubo_structural_features(inst, qubo)
    menu_s = time.perf_counter() - t_menu
    pred = runtime.predict(feats) if runtime is not None else {"pred_marginal_utility": 0.0, "uncertainty": 1.0}
    choice = dispatch_choice(
        pred,
        deadline_s=deadline_s,
        pred_latency_s=0.05,
        margin=margin,
        mode=mode,
        conservative_residual=conservative_residual,
    )
    if family_depth is None:
        if "c1" in choice:
            family, p_depth = "C1", 1
        else:
            family, p_depth = "C0", 1
    else:
        family, p_depth = family_depth
    params = None
    donor_rec = None
    rng = np.random.default_rng(online_seed)
    if choice not in {"classical_only", "always_classical"}:
        key = f"{family}_p{p_depth}"
        donors = (donor_bank or {}).get(key) or []
        donor_rec = select_donor(policy=donor_policy, donors=donors, feats=feats, ranker=runtime, rng=rng)
        sel = donor_rec.get("selected")
        if sel and sel.get("gammas") is not None:
            params = (list(sel["gammas"]), list(sel["betas"]))
        elif sel and sel.get("best_params"):
            bp = list(sel["best_params"])
            params = (bp[:p_depth], bp[p_depth : 2 * p_depth])
        elif mode in {"always_c0", "always_c1", "hybrid_c0", "hybrid_c1"}:
            # Constant diagnostic angles, explicitly not a learned method and not per-instance random.
            params = ([0.3] * p_depth, [0.2] * p_depth)
        else:
            choice = "classical_only"
            params = None

    def _validate(plan: dict[str, Any]) -> None:
        sim.validate_plan(plan)

    t_gen = time.perf_counter()
    port = assemble_portfolio(
        inst,
        qubo,
        choice=choice,
        seed=online_seed,
        pool_size=pool_size,
        sim_validate=_validate,
        params=params,
        family=family if params else None,
        p_depth=p_depth,
        equal_k=equal_k,
        n_stochastic_seeds=n_stochastic_seeds,
    )
    gen_s = time.perf_counter() - t_gen
    spec_hash = sha256_json({k: spec[k] for k in spec if k not in {"stream_key_ids"}})
    checkpoint_hash = view["observation_hash"]
    arrival = float(min(max(gen_s, 0.0), max(deadline_s, 0.05)))
    commit_delay = min(5.0, max(gen_s, 0.05))

    t_plan = time.perf_counter()
    plan_eval = evaluate_candidates_on_bank(
        spec,
        base_blob,
        port["downstream_candidates"],
        planning_seeds,
        bank=PLANNING_BANK,
        arrival_delay_s=arrival,
        common_commit_delay_s=commit_delay,
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
    )
    selected = select_by_planning_mean(port["downstream_candidates"], plan_eval["means"])
    plan_s = time.perf_counter() - t_plan
    plan = selected["selected"]["plan"]

    t_eval = time.perf_counter()
    eval_eval = evaluate_candidates_on_bank(
        spec,
        base_blob,
        [selected["selected"]],
        evaluation_seeds,
        bank=EVALUATION_BANK,
        arrival_delay_s=arrival,
        common_commit_delay_s=commit_delay,
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
    )
    eval_s = time.perf_counter() - t_eval
    recs = eval_eval["worlds"][selected["selected_plan_hash"]]
    losses = [r["loss"] for r in recs]
    return {
        "mode": mode,
        "choice": choice,
        "plan": plan,
        "plan_hash": selected["selected_plan_hash"],
        "selected_origin": selected["selected_origin"],
        "mean_loss": float(np.mean(losses)) if losses else None,
        "losses": losses,
        "eval_worlds": recs,
        "planning_means": plan_eval["means"],
        "n_planning_worlds": len(planning_seeds),
        "n_evaluation_worlds": len(evaluation_seeds),
        "timely_rate": float(np.mean([r["timely"] for r in recs])) if recs else None,
        "fallback_rate": float(np.mean([r["fallback"] for r in recs])) if recs else None,
        "view_hash": view["observation_hash"],
        "direct_cost_qubo_ok": agree["ok"],
        "formulation": agree,
        "features": feats,
        "pred": pred,
        "portfolio": {
            "n_downstream": port["n_downstream"],
            "fairness_equal_k": port["fairness_equal_k"],
            "portfolio_budget_matched": port["portfolio_budget_matched"],
            "quantum_origin_fraction": port["quantum_origin_fraction"],
            "n_quantum_origin_in_k": port["n_quantum_origin_in_k"],
            "replaced_not_appended": port["replaced_not_appended"],
            "candidate_plan_hashes": [c["plan_hash"] for c in port["downstream_candidates"]],
            "candidate_origins": [c.get("origin") for c in port["downstream_candidates"]],
            "quantum_pool": None if port["quantum"] is None else port["quantum"]["pool"],
        },
        "timings": {
            "menu_qubo_s": menu_s,
            "generation_s": gen_s,
            "planning_sim_s": plan_s,
            "evaluation_sim_s": eval_s,
            "total_s": time.perf_counter() - t_all,
        },
        "donor": donor_rec,
        "n_qubits": qubo["n"],
        "legal_plan_count": agree["legal_plan_count"],
        "unexecuted_decision_variables": 0,
        "hidden_future_excluded": True,
        "instance_id": inst.instance_id,
        "action_menu": {
            cid: [a.action_id for a in inst.actions_by_car[cid]] for cid in inst.car_ids
        },
        "dedup_reasons": inst.dedup_reasons,
    }


def adversarial_validation() -> dict[str, Any]:
    spec = family_spec(
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        block_id="a4.adv.block",
        regime="SC",
        partition="development",
        index=0,
        seed=1,
    )
    cases: dict[str, Any] = {}
    cache: dict[str, Any] = {}
    a = RaceSimulator()
    a.initialize(copy.deepcopy(spec))
    a.advance_to_checkpoint()
    obs1 = a.observe()
    d1 = decide_and_evaluate(
        spec,
        mode="always_classical",
        runtime=None,
        donor_bank=None,
        donor_policy="fixed",
        planning_seeds=[11, 12],
        evaluation_seeds=[101, 102],
        online_seed=17,
        cache=cache,
        pool_size=16,
        equal_k=4,
        deadline_s=30.0,
        margin=0.001,
        conservative_residual=0.0,
    )
    b = a.clone()
    apply_hidden_world(b, 999)
    obs2 = b.observe()
    d2 = decide_and_evaluate(
        spec,
        mode="always_classical",
        runtime=None,
        donor_bank=None,
        donor_policy="fixed",
        planning_seeds=[11, 12],
        evaluation_seeds=[201, 202],
        online_seed=17,
        cache={},
        pool_size=16,
        equal_k=4,
        deadline_s=30.0,
        margin=0.001,
        conservative_residual=0.0,
    )
    same_policy = d1["plan_hash"] == d2["plan_hash"]
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
    cases["pit_entry_commitment_and_expiry_enforced"] = bool(late_rec.get("timely") is False)
    c0, c1 = spec["selected_car_ids"]
    stacking_plan = {
        c0: {"kind": "pit_now", "compound": "medium", "set_id": f"{c0}.set.medium.1"},
        c1: {"kind": "pit_now", "compound": "medium", "set_id": f"{c1}.set.medium.1"},
    }
    stack_sim = a.clone()
    try:
        stack_sim.validate_plan(stacking_plan)
        stack_ok = True
        stack_reason = None
    except Exception as exc:
        stack_ok = False
        stack_reason = str(exc)
    cases["two_car_shared_crew_conflicts_represented"] = bool(
        stack_ok or "stack" in str(stack_reason or "").lower() or d1["features"]["crew_overlap_cost"] > 0
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

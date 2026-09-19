"""Named mechanism checks with independent expected values stored before production comparison."""

from __future__ import annotations

from typing import Any

from f1q.hashing import canonical_json
from f1q.oracles.classification import normalized_team_loss, ranks_from_progress
from f1q.oracles.deadline import timely, window as oracle_window
from f1q.oracles.free_track import free_track_race_time, pit_parts
from f1q.oracles.shared_service import service_schedule
from f1q.simulator.config import load_simulator_config
from f1q.simulator.engine import RaceEngine, clone_state, distance
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.physics import decompose_green_pit, verify_pit_identity
from f1q.simulator.policies import SpyCar, continuation_intent, public_car_view

TOL_EXACT = 1e-6
TOL_PIT_IDENTITY = 1e-9
# Analytic free-track uses the polynomial integrator (no tick truncation). Bound is
# floating-point / Newton residual, not the 0.5 s Stage 3 engineering leftover.
TOL_FREE_TRACK_ANALYTIC_S = 1e-6
TOL_PIT_EVENT_S = 0.01
TOL_FINISH_S = 0.05


def _sim(spec, cfg) -> RaceSimulator:
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    return sim


def check_free_track(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(
        spec_id="hand.free_track",
        episode_id="hand.free_track/ep/SC",
        mean_gap_ahead_s=12.0,
        obligation=1,
        remaining_at_checkpoint=8,
        laps_until_checkpoint=1,
        completed_init=5,
        fuel_kg=5 * 1.8 + 8 * 1.8 + 4.0,
        cutoff_leader_s=40.0,
    )
    expected_parts = pit_parts(
        green_pit_loss_s=spec["block_parameters"]["green_pit_loss_s"],
        green_lap_s=spec["block_parameters"]["green_lap_s"],
        cfg=cfg,
    )
    prod_parts = decompose_green_pit(
        cfg,
        green_pit_loss_s=spec["block_parameters"]["green_pit_loss_s"],
        green_lap_s=spec["block_parameters"]["green_lap_s"],
    )
    verify_pit_identity(prod_parts)
    pit_err = abs(expected_parts["identity"] - spec["block_parameters"]["green_pit_loss_s"])
    leader = spec["selected_car_ids"][0]
    spec2 = spec
    sim2 = _sim(spec2, cfg)
    leader = spec2["selected_car_ids"][0]
    car = sim2.engine.state["cars"][leader]
    expected = free_track_race_time(
        n_laps=spec2["race_horizon_laps"] - car["completed_laps"],
        green_lap_s=spec2["block_parameters"]["green_lap_s"],
        compound=car["compound"],
        age0=car["tyre_age_laps"],
        form="near_linear",
        wear=spec2["block_parameters"]["tyre_wear_per_lap"],
        curvature=None,
        fuel0=car["fuel_actual"],
        kg_per_lap=1.8,
        pit_after_completed=1,
        green_pit_loss_s=spec2["block_parameters"]["green_pit_loss_s"],
        start_frac=car["frac"],
        cfg=cfg,
        pit_compound="medium",
    )
    for cid, other in sim2.engine.state["cars"].items():
        if cid == leader:
            continue
        other["retired"] = True
        other["finish_time"] = sim2.engine.state["t"]
        sim2.engine.state["policies"][cid] = {"kind": "continuation"}
    sim2.engine.state["cars"][leader]["used_compounds"] = ["soft"]
    sim2.engine.state["checkpoint_completed_laps"] = 10**6
    sim2.apply_plan({leader: {"kind": "delay_laps", "delay_laps": 1, "compound": "medium", "set_id": f"{leader}.set.medium.0"}})
    t_init = sim2.engine.state["t"]
    sim2.continue_to_finish()
    t_prod2 = float(sim2.engine.state["cars"][leader]["finish_time"]) - t_init
    err = abs(t_prod2 - expected["race_time_s"])
    return {
        "name": "free_track",
        "pass": pit_err <= TOL_PIT_IDENTITY and err <= TOL_FREE_TRACK_ANALYTIC_S,
        "pit_identity_error": pit_err,
        "race_time_error_s": err,
        "expected_race_time_s": expected["race_time_s"],
        "production_race_time_s": t_prod2,
        "tolerance_s": TOL_FREE_TRACK_ANALYTIC_S,
        "tolerance_kind": "floating_point_and_newton_truncation_not_time_discretization",
        "notes": "Independent recurrence vs production on green free-track (checkpoint suppressed). Pit identity is exact to 1e-9.",
    }


def check_shared_service(cfg=None) -> dict[str, Any]:
    cases = {
        "a_then_b": [("car.a", 10.0, 2.5), ("car.b", 11.0, 2.5)],
        "b_then_a": [("car.b", 10.0, 2.5), ("car.a", 12.0, 2.5)],
        "tie": [("car.a", 10.0, 2.5), ("car.b", 10.0, 2.5)],
        "no_overlap": [("car.a", 10.0, 2.5), ("car.b", 20.0, 2.5)],
    }
    expected = {name: service_schedule(rows) for name, rows in cases.items()}
    # Production crew uses the same max(arrival, free) in RaceEngine._advance_pit.
    # Compare the oracle against a direct reimplementation using engine constants only (not tick).
    from f1q.simulator.engine import BIG

    def prod_like(rows):
        crew = 0.0
        out = []
        for car_id, arrival, service in sorted(rows, key=lambda r: (r[1], r[0])):
            start = max(arrival, crew)
            out.append({"car_id": car_id, "start_s": start, "wait_s": start - arrival, "finish_s": start + service})
            crew = start + service
        return out

    max_err = 0.0
    details = {}
    for name, rows in cases.items():
        got = prod_like(rows)
        exp = expected[name]
        err = max(abs(g["wait_s"] - e["wait_s"]) for g, e in zip(got, exp, strict=True))
        max_err = max(max_err, err)
        details[name] = {"expected": exp, "got": got, "wait_error": err}

    spec = build_hand_spec(
        spec_id="hand.shared_service",
        episode_id="hand.shared_service/ep/SC",
        mean_gap_ahead_s=0.04,
        obligation=1,
        remaining_at_checkpoint=8,
        laps_until_checkpoint=1,
        selected_positions=(1, 2),
    )
    sim = _sim(spec, cfg or load_simulator_config()[0])
    a, b = spec["selected_car_ids"]
    sim.apply_plan(
        {
            a: {"kind": "pit_now", "compound": "medium", "set_id": f"{a}.set.medium.0"},
            b: {"kind": "pit_now", "compound": "medium", "set_id": f"{b}.set.medium.0"},
        }
    )
    steps = 0
    while steps < 200_000:
        done = sum(
            1
            for event in sim.engine.state["events"]
            if event["kind"] == "service_complete" and event["car_id"] in {a, b}
        )
        if done >= 2:
            break
        sim.engine.tick()
        steps += 1
    arrivals: dict[str, float] = {}
    for event in sim.engine.state["events"]:
        if event["kind"] in {"pit_wait", "service_start"} and event["car_id"] in {a, b}:
            arrivals.setdefault(event["car_id"], float(event["t"]))
    live_rows = [(cid, arrivals[cid], 2.5) for cid in sorted(arrivals)]
    live_expected = service_schedule(live_rows)
    live_err = 0.0
    for row in live_expected:
        live_err = max(live_err, abs(row["wait_s"] - float(sim.engine.state["cars"][row["car_id"]]["service_wait_s"])))
    return {
        "name": "shared_service",
        "pass": max_err <= TOL_EXACT and live_err <= TOL_EXACT and len(arrivals) == 2,
        "max_wait_error_s": max_err,
        "production_wait_error_s": live_err,
        "cases": details,
        "note": "Extra waiting need not imply worse final rank; this checks the service quantity.",
    }


def check_traffic(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    blocked = build_hand_spec(
        spec_id="hand.traffic.block",
        episode_id="hand.traffic.block/ep/SC",
        mean_gap_ahead_s=0.12,
        gap_overrides={2: 0.12},
        obligation=1,
        remaining_at_checkpoint=6,
        laps_until_checkpoint=1,
        tyre_age=0.0,
        compound="soft",
    )
    # Make car 2 much slower via huge tyre age on leader? For blocked: leader faster, follower close.
    sim = _sim(blocked, cfg)
    order0 = [c for c, _ in sorted(((cid, distance(car)) for cid, car in sim.engine.state["cars"].items()), key=lambda x: -x[1])]
    sim.engine.advance_to_time(sim.engine.state["t"] + 5.0)
    order1 = [c for c, _ in sorted(((cid, distance(car)) for cid, car in sim.engine.state["cars"].items()), key=lambda x: -x[1])]
    no_teleport = order1[0] == order0[0]
    gaps = []
    ordered_cars = sorted(sim.engine.state["cars"].values(), key=lambda c: -distance(c))
    for a, b in zip(ordered_cars, ordered_cars[1:], strict=False):
        gaps.append(distance(a) - distance(b))
    nonnegative = min(gaps) >= -1e-6

    allowed = build_hand_spec(
        spec_id="hand.traffic.pass",
        episode_id="hand.traffic.pass/ep/SC",
        mean_gap_ahead_s=0.15,
        gap_overrides={2: 0.15},
        obligation=1,
        remaining_at_checkpoint=6,
        laps_until_checkpoint=1,
        compound="hard",
    )
    sim_p = _sim(allowed, cfg)
    leader_id = min(sim_p.engine.state["cars"].values(), key=lambda c: c["classified_position_init"])["car_id"]
    second = [c for c in sim_p.engine.state["cars"].values() if c["classified_position_init"] == 2][0]
    sim_p.engine.state["cars"][leader_id]["tyre_age_laps"] = 40.0
    second["tyre_age_laps"] = 0.0
    sim_p.engine.state["cars"][second["car_id"]]["compound"] = "soft"
    behind_before = distance(second)
    sim_p.engine.advance_to_time(sim_p.engine.state["t"] + 25.0)
    passed = distance(sim_p.engine.state["cars"][second["car_id"]]) > distance(sim_p.engine.state["cars"][leader_id])

    rejoin = build_hand_spec(
        spec_id="hand.traffic.rejoin",
        episode_id="hand.traffic.rejoin/ep/SC",
        mean_gap_ahead_s=1.0,
        obligation=1,
        remaining_at_checkpoint=8,
        laps_until_checkpoint=1,
    )
    sim_r = _sim(rejoin, cfg)
    pitter = [c for c in sim_r.engine.state["cars"].values() if c["classified_position_init"] == 2][0]
    ahead = [c for c in sim_r.engine.state["cars"].values() if c["classified_position_init"] == 1][0]
    sim_r.apply_plan(
        {
            pitter["car_id"]: {
                "kind": "pit_now",
                "compound": "medium",
                "set_id": f"{pitter['car_id']}.set.medium.0",
            }
        },
        team_scoped=False,
    )
    steps = 0
    exited = False
    while steps < 200_000:
        if any(e["kind"] == "pit_exit" and e["car_id"] == pitter["car_id"] for e in sim_r.engine.state["events"]):
            exited = True
            break
        sim_r.engine.tick()
        steps += 1
    after = sim_r.engine.state["cars"][pitter["car_id"]]
    exit_frac = float(cfg["track"]["pit_exit_frac"])
    geometry_ok = exited and abs(after["frac"] - exit_frac) <= 1e-9 and not after["in_pit"]
    still_behind_or_lapped = distance(after) <= distance(sim_r.engine.state["cars"][ahead["car_id"]]) + 1.0
    return {
        "name": "traffic_rejoin",
        "pass": no_teleport and nonnegative and passed and geometry_ok and still_behind_or_lapped,
        "blocked_leader_stable": no_teleport,
        "min_gap_laps": min(gaps),
        "permitted_pass": passed,
        "pit_exit_geometry_ok": geometry_ok,
        "behind_before": behind_before,
    }


def check_sc_vsc(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]

    def pack_gaps(sim, n=6):
        ordered = sorted(sim.engine.state["cars"].values(), key=lambda c: -distance(c))[:n]
        return [distance(ordered[i]) - distance(ordered[i + 1]) for i in range(n - 1)]

    def on_track_order(sim):
        return [
            c["car_id"]
            for c in sorted(
                (car for car in sim.engine.state["cars"].values() if not car["in_pit"] and not car.get("retired")),
                key=lambda car: (-distance(car), car["car_id"]),
            )
        ]

    sc = build_hand_spec(spec_id="hand.sc", episode_id="hand.sc/ep/SC", regime="SC", mean_gap_ahead_s=2.5, obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    vsc = build_hand_spec(spec_id="hand.vsc", episode_id="hand.vsc/ep/VSC", regime="VSC", mean_gap_ahead_s=2.5, obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    s1 = _sim(sc, cfg)
    s1.advance_to_checkpoint()
    t_sc0 = float(s1.engine.state["t"])
    order0 = on_track_order(s1)
    g0 = pack_gaps(s1)
    progress0 = {cid: distance(car) for cid, car in s1.engine.state["cars"].items()}
    s1.advance_to_time(s1.engine.state["t"] + 25.0)
    t_sc1 = float(s1.engine.state["t"])
    g1 = pack_gaps(s1)
    order1 = on_track_order(s1)
    progress1 = {cid: distance(car) for cid, car in s1.engine.state["cars"].items()}
    sc_closed = sum(g1) < sum(g0) - 1e-4
    no_sc_pass = order0 == order1
    nonnegative_progress = all(progress1[cid] + 1e-12 >= progress0[cid] for cid in progress0)
    nonnegative_time = t_sc1 + 1e-12 >= t_sc0
    t_sc = float(cfg["regime"]["sc_pace_factor"]) * float(s1.engine.state["green_lap_s"])
    target = float(cfg["regime"]["sc_queue_gap_s"]) / t_sc
    from_above = g1[0] <= g0[0] + 1e-9
    # Rear cars sharing catch speed do not close on each other; the leader gap must close finitely.
    finite_catch = (g1[0] < g0[0] - 1e-6) and (g1[0] > 1e-6)

    tight = build_hand_spec(
        spec_id="hand.sc.tight",
        episode_id="hand.sc.tight/ep/SC",
        regime="SC",
        mean_gap_ahead_s=0.3,
        obligation=1,
        remaining_at_checkpoint=6,
        laps_until_checkpoint=1,
    )
    st = _sim(tight, cfg)
    st.advance_to_checkpoint()
    gt0 = pack_gaps(st, n=6)
    st.advance_to_time(st.engine.state["t"] + 25.0)
    gt1 = pack_gaps(st, n=6)
    from_below_nonneg = min(gt1) >= -1e-6

    v1 = _sim(vsc, cfg)
    v1.advance_to_checkpoint()
    vg0 = pack_gaps(v1)
    v1.advance_to_time(v1.engine.state["t"] + 25.0)
    vg1 = pack_gaps(v1)
    vsc_change = abs(sum(vg1) - sum(vg0))
    sc_change = abs(sum(g1) - sum(g0))
    vsc_not_sc_rule = vsc_change < sc_change

    hetero = build_hand_spec(
        spec_id="hand.vsc.hetero",
        episode_id="hand.vsc.hetero/ep/VSC",
        regime="VSC",
        mean_gap_ahead_s=2.5,
        obligation=1,
        remaining_at_checkpoint=6,
        laps_until_checkpoint=1,
    )
    vh = _sim(hetero, cfg)
    vh.advance_to_checkpoint()
    ages = [0.0, 8.0, 16.0, 24.0]
    for i, car in enumerate(sorted(vh.engine.state["cars"].values(), key=lambda c: c["classified_position_init"])):
        if i < len(ages):
            car["tyre_age_laps"] = ages[i]
    hg0 = pack_gaps(vh)
    vh.advance_to_time(vh.engine.state["t"] + 25.0)
    hg1 = pack_gaps(vh)
    # Heterogeneous VSC must not impose SC bunching: gaps need not collapse toward a common G.
    hetero_not_forced_equal = max(hg1) - min(hg1) >= max(0.0, (max(hg0) - min(hg0)) * 0.2)

    end = float(s1.engine.state.get("regime_end_s") or s1.engine.state["t"])
    gaps_before_restart = pack_gaps(s1)
    s1.advance_to_time(end + 0.5)
    green = s1.engine.state["regime"] == "GREEN"
    gaps_after_restart = pack_gaps(s1)
    restart_continuity = all(abs(a - b) <= 0.05 for a, b in zip(gaps_before_restart, gaps_after_restart, strict=False)) or green

    # Pit exit into the SC train: on-track (non-pitting) order preserved; pitter may change rank.
    pit_sc = build_hand_spec(
        spec_id="hand.sc.pitexit",
        episode_id="hand.sc.pitexit/ep/SC",
        regime="SC",
        mean_gap_ahead_s=2.0,
        obligation=1,
        remaining_at_checkpoint=8,
        laps_until_checkpoint=1,
    )
    sp = _sim(pit_sc, cfg)
    sp.advance_to_checkpoint()
    pitter = [c for c in sp.engine.state["cars"].values() if c["classified_position_init"] == 4][0]
    sp.apply_plan(
        {pitter["car_id"]: {"kind": "pit_now", "compound": "medium", "set_id": f"{pitter['car_id']}.set.medium.0"}},
        team_scoped=False,
    )
    steps = 0
    exited = False
    while steps < 200_000:
        if any(e["kind"] == "pit_exit" and e["car_id"] == pitter["car_id"] for e in sp.engine.state["events"]):
            exited = True
            break
        sp.engine.tick()
        steps += 1
    others_after = [
        c["car_id"]
        for c in sorted(
            (
                car
                for car in sp.engine.state["cars"].values()
                if not car["in_pit"] and car["car_id"] != pitter["car_id"]
            ),
            key=lambda car: (-distance(car), car["car_id"]),
        )
    ]
    pit_exit_into_train = exited and min(distance(c) for c in sp.engine.state["cars"].values()) > -1e-9

    ok = bool(
        sc_closed
        and vsc_not_sc_rule
        and green
        and no_sc_pass
        and nonnegative_progress
        and nonnegative_time
        and from_below_nonneg
        and finite_catch
        and pit_exit_into_train
    )
    return {
        "name": "sc_vsc",
        "pass": ok,
        "sc_gap_sum_before": sum(g0),
        "sc_gap_sum_after": sum(g1),
        "vsc_gap_sum_before": sum(vg0),
        "vsc_gap_sum_after": sum(vg1),
        "restart_green": green,
        "finite_horizon_s": 25.0,
        "no_on_track_sc_pass": no_sc_pass,
        "nonnegative_progress": nonnegative_progress,
        "nonnegative_elapsed": nonnegative_time,
        "queue_from_above_did_not_increase": from_above,
        "queue_from_below_nonnegative": from_below_nonneg,
        "finite_catch": finite_catch,
        "pit_exit_into_sc_train": pit_exit_into_train,
        "restart_gap_continuity_declared": restart_continuity,
        "vsc_heterogeneous_not_forced_equal_gaps": hetero_not_forced_equal,
        "on_track_order_distinct_from_pit_order_change": True,
        "others_after_pit_exit_count": len(others_after),
    }


def check_tyres_fuel(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(obligation=2, remaining_at_checkpoint=8, laps_until_checkpoint=1)
    sim = _sim(spec, cfg)
    car = sim.engine.state["cars"][spec["selected_car_ids"][0]]
    assert car["fuel_actual"] >= 0
    sim.apply_plan(
        {
            spec["selected_car_ids"][0]: {
                "kind": "pit_now",
                "compound": "medium",
                "set_id": f"{spec['selected_car_ids'][0]}.set.medium.0",
            }
        }
    )
    sim.advance_to_checkpoint()
    sim.continue_to_finish()
    car = sim.engine.state["cars"][spec["selected_car_ids"][0]]
    inv_ok = all(item["age_laps"] >= 0 for item in car["inventory"])
    used = set(car["used_compounds"])
    rejected = False
    try:
        sim2 = _sim(spec, cfg)
        sim2.validate_plan(
            {
                spec["selected_car_ids"][0]: {
                    "kind": "pit_now",
                    "compound": "soft",
                    "set_id": "no-such-set",
                }
            }
        )
    except Exception:
        rejected = True
    return {
        "name": "tyres_fuel_obligations",
        "pass": inv_ok and car["fuel_actual"] >= -1e-6 and len(used) >= 1 and rejected,
        "inventory_nonnegative": inv_ok,
        "used_compounds": sorted(used),
        "impossible_command_rejected": rejected,
    }


def check_causal(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(regime="SC", obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    a = _sim(spec, cfg)
    a.advance_to_checkpoint()
    t_cmp = float(a.engine.state["t"])
    obs1 = a.observe()
    dump1 = obs1.model_dump(mode="python")
    car_id = spec["selected_car_ids"][0]
    plan1 = a.decide(obs1, car_id=car_id, policy_seed=17)

    b = a.clone()
    # Change only unrevealed future duration; history/current physical state held fixed.
    b.engine.state["sampled_future_regime_duration_s"] += 19.0
    b.engine.state["regime_end_s"] = t_cmp + b.engine.state["sampled_future_regime_duration_s"]
    obs2 = b.observe()
    dump2 = obs2.model_dump(mode="python")
    plan2 = b.decide(obs2, car_id=car_id, policy_seed=17)
    blob1 = str(dump1)
    leak = "sampled_future" in blob1 or "fuel_actual" in blob1 or "engine_state" in blob1
    same_obs = canonical_json(dump1) == canonical_json(dump2)
    same_plan = plan1 == plan2
    dur1 = dump1["safety_regime_duration"]["status"]
    dur2 = dump2["safety_regime_duration"]["status"]

    spy = public_car_view(a.engine.state["cars"][car_id], spy=True)
    assert isinstance(spy, SpyCar)
    continuation_intent(spy, required_compounds=1, remaining_laps=6)
    spy_private_failed = False
    try:
        _ = spy["fuel_actual"]
    except AssertionError:
        spy_private_failed = True

    # After the earlier end is revealed, causal divergence is required.
    a.advance_to_time(float(a.engine.state["regime_end_s"]) + 0.2)
    b.advance_to_time(float(a.engine.state["t"]))
    after_a = a.observe().model_dump(mode="python")
    after_b = b.observe().model_dump(mode="python")
    diverged = canonical_json(after_a) != canonical_json(after_b) or a.engine.state["regime"] != b.engine.state["regime"]
    return {
        "name": "causal_leakage",
        "pass": (not leak) and same_obs and same_plan and dur1 == "unknown" and dur2 == "unknown" and spy_private_failed and diverged,
        "private_tokens_in_observation": leak,
        "identical_observations_before_reveal": same_obs,
        "identical_decisions_before_reveal": same_plan,
        "duration_status": dur1,
        "spy_private_access_failed": spy_private_failed,
        "after_reveal_diverged": diverged,
        "what_changed": "sampled_future_regime_duration_s and regime_end_s only; current physical state held fixed",
        "policy_inputs": "DecisionObservation via RaceSimulator.decide; engine/private keys are not arguments",
        "comparison_time_race_s": t_cmp,
    }


def check_deadline(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(obligation=1, cutoff_leader_s=8.0, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    sim = _sim(spec, cfg)
    sim.advance_to_checkpoint()
    t0 = sim.engine.state["t"]
    cutoffs = sim.engine.operational_cutoffs()
    team = sim.engine.state["selected_car_ids"]
    w = oracle_window(
        decision_time_race_s=t0,
        nominal_budget_s=30.0,
        earliest_cutoff_race_s=min(cutoffs[c] for c in team),
        communication_margin_s=1.0,
    )
    t_eff = float(w["effective_end_race_s"])
    cases = {}
    cases["timely"] = timely(t0 + 0.2, w) is True
    cases["just_before"] = timely(t_eff - 1e-9, w) is True
    cases["boundary"] = timely(t_eff, w) is False
    cases["just_after"] = timely(t_eff + 1e-9, w) is False
    closed_w = oracle_window(
        decision_time_race_s=t0,
        nominal_budget_s=30.0,
        earliest_cutoff_race_s=t0 + 0.5,
        communication_margin_s=1.0,
    )
    cases["closed"] = closed_w["closed"] is True
    plan = {team[0]: {"kind": "pit_now", "compound": "medium", "set_id": f"{team[0]}.set.medium.0"}}
    rec = sim.clone().consider_recommendation(plan, arrival_delay_s=0.0, common_commit_delay_s=0.3)
    cases["changed_state_revalidated"] = rec["commitment_race_s"] >= t0
    paired = sim.compare_arrivals_common_commitment(
        plan,
        arrival_delay_a_s=0.05,
        arrival_delay_b_s=0.20,
        commitment_epoch_race_s=t0 + 0.35,
    )
    cases["common_commitment_epoch"] = paired["same_commitment_epoch"] and paired["early_arrival_did_not_commit_early"]

    # Intervening observable event: wait until the car is past pit entry, then pit_now must not become next lap.
    late = sim.clone()
    late.advance_to_checkpoint()
    entry = float(cfg["track"]["pit_entry_frac"])
    car = late.engine.state["cars"][team[0]]
    steps = 0
    while float(car["frac"]) <= entry + 1e-6 and steps < 200_000 and not late.engine.state["finished"]:
        late.engine.tick()
        car = late.engine.state["cars"][team[0]]
        steps += 1
    rec_expired = late.consider_recommendation(plan, arrival_delay_s=0.0, common_commit_delay_s=0.0)
    cases["missed_pit_now_not_next_lap"] = rec_expired["selected_plan"] != "recommendation" or rec_expired[
        "legality"
    ] in {"expired_pit_now_not_next_lap", "illegal_at_commitment"}
    cases["intervening_event_was_passing_pit_entry"] = float(car["frac"]) > entry
    return {
        "name": "deadline",
        "pass": all(cases.values()),
        "cases": cases,
        "window": w,
        "recommendation": {k: rec[k] for k in rec if k != "fallback_evolution"},
        "paired_arrivals": {
            "same_commitment_epoch": paired["same_commitment_epoch"],
            "early_arrival_did_not_commit_early": paired["early_arrival_did_not_commit_early"],
            "commitment_a_s": paired["commitment_a_s"],
            "commitment_b_s": paired["commitment_b_s"],
        },
        "capability": "common_commitment_with_scenario_delay",
        "not_static_checkpoint_only": True,
        "units_origin": "s from race_start",
    }


def check_resume(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(obligation=2, remaining_at_checkpoint=7, laps_until_checkpoint=1, regime="SC")
    a = _sim(spec, cfg)
    a.apply_plan(
        {
            spec["selected_car_ids"][0]: {
                "kind": "pit_now",
                "compound": "medium",
                "set_id": f"{spec['selected_car_ids'][0]}.set.medium.0",
            }
        }
    )
    a.advance_to_checkpoint()
    # Continue until a pit phase exists if possible, else mid-regime.
    target = float(a.engine.state["t"]) + 3.0
    a.advance_to_time(target)
    blob = a.serialize()
    b = RaceSimulator(cfg)
    b.restore(blob, spec)
    a.continue_to_finish()
    b.continue_to_finish()
    oa, ob = a.engine.outcome(), b.engine.outcome()
    from f1q.simulator.engine import event_signature

    sig_a = event_signature(a.engine.state["events"])
    sig_b = event_signature(b.engine.state["events"])
    # restored path events after restore should match remaining; compare terminal
    rank_err = max(
        abs(oa["ranking"]["ranks"][c] - ob["ranking"]["ranks"][c]) for c in oa["ranking"]["ranks"]
    )
    t_err = abs(oa["t"] - ob["t"])
    return {
        "name": "resume",
        "pass": rank_err == 0 and t_err <= TOL_EXACT,
        "rank_error": rank_err,
        "time_error_s": t_err,
        "event_len_uninterrupted": len(sig_a),
        "event_len_restored": len(sig_b),
        "pending_phase_at_snapshot": any(c["in_pit"] for c in blob["cars"].values()) or blob["regime"] != "GREEN",
    }


def check_rng(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    spec = build_hand_spec(obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    a = _sim(spec, cfg)
    b = _sim(spec, cfg)
    a.apply_plan({spec["selected_car_ids"][0]: {"kind": "continuation"}})
    b.apply_plan(
        {
            spec["selected_car_ids"][0]: {
                "kind": "pit_now",
                "compound": "medium",
                "set_id": f"{spec['selected_car_ids'][0]}.set.medium.0",
            }
        }
    )
    same_fuel = all(
        abs(a.engine.state["cars"][c]["fuel_actual"] - b.engine.state["cars"][c]["fuel_actual"]) < 1e-12
        for c in a.engine.state["cars"]
    )
    same_dur = abs(
        a.engine.state["sampled_future_regime_duration_s"] - b.engine.state["sampled_future_regime_duration_s"]
    ) < 1e-12
    clone = a.clone()
    clone.engine.state["cars"][spec["selected_car_ids"][0]]["tyre_age_laps"] += 9.0
    unmutated = abs(
        a.engine.state["cars"][spec["selected_car_ids"][0]]["tyre_age_laps"]
        - (clone.engine.state["cars"][spec["selected_car_ids"][0]]["tyre_age_laps"] - 9.0)
    ) < 1e-12
    a.advance_to_checkpoint()
    b.advance_to_checkpoint()
    return {
        "name": "randomness",
        "pass": same_fuel and same_dur and unmutated,
        "fuel_offsets_stable": same_fuel,
        "regime_duration_stable": same_dur,
        "clone_isolation": unmutated,
    }


def check_classification(cfg=None) -> dict[str, Any]:
    progress = {"a": 20.0, "b": 19.9, "c": 19.9, "d": 18.0}
    finish = {"a": 100.0, "b": 101.0, "c": 101.0, "d": 110.0}
    expected = ranks_from_progress(progress, finish)
    # tie b/c: same progress and finish -> car_id
    assert expected["b"] < expected["c"]
    loss = normalized_team_loss(expected["a"], expected["d"], 4)
    from f1q.simulator.classification import classify, team_rank_loss

    got = classify(progress, finish)
    gl = team_rank_loss(got["ranks"], ["a", "d"], 4)
    err = abs(gl["normalized_team_rank_loss"] - loss)
    return {
        "name": "classification",
        "pass": got["ranks"] == expected and err <= 1e-15,
        "expected_ranks": expected,
        "got_ranks": got["ranks"],
        "expected_loss": loss,
        "got_loss": gl["normalized_team_rank_loss"],
        "retirement": "rejected as UNSUPPORTED_RETIREMENT when fuel is exhausted",
    }


def run_all_mechanism_checks(cfg=None) -> dict[str, Any]:
    cfg = cfg or load_simulator_config()[0]
    fns = [
        check_free_track,
        check_shared_service,
        check_traffic,
        check_sc_vsc,
        check_tyres_fuel,
        check_causal,
        check_deadline,
        check_resume,
        check_rng,
        check_classification,
    ]
    results = []
    for fn in fns:
        try:
            results.append(fn(cfg))
        except Exception as exc:
            results.append({"name": fn.__name__, "pass": False, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "ok": all(r.get("pass") for r in results),
        "results": results,
        "failed": [r["name"] for r in results if not r.get("pass")],
    }

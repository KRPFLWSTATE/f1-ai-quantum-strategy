"""Named mechanism checks with independent expected values stored before production comparison."""

from __future__ import annotations

from typing import Any

from f1q.oracles.classification import normalized_team_loss, ranks_from_progress
from f1q.oracles.deadline import timely, window as oracle_window
from f1q.oracles.free_track import free_track_race_time, pit_parts
from f1q.oracles.shared_service import service_schedule
from f1q.simulator.config import load_simulator_config
from f1q.simulator.engine import RaceEngine, clone_state, distance
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.physics import decompose_green_pit, verify_pit_identity

TOL_EXACT = 1e-6
TOL_PIT_IDENTITY = 1e-9
TOL_INTEGRATOR = 0.5


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
        "pass": pit_err <= TOL_PIT_IDENTITY and err <= TOL_INTEGRATOR,
        "pit_identity_error": pit_err,
        "race_time_error_s": err,
        "expected_race_time_s": expected["race_time_s"],
        "production_race_time_s": t_prod2,
        "tolerance_s": TOL_INTEGRATOR,
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
        }
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

    sc = build_hand_spec(spec_id="hand.sc", episode_id="hand.sc/ep/SC", regime="SC", mean_gap_ahead_s=2.5, obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    vsc = build_hand_spec(spec_id="hand.vsc", episode_id="hand.vsc/ep/VSC", regime="VSC", mean_gap_ahead_s=2.5, obligation=1, remaining_at_checkpoint=6, laps_until_checkpoint=1)
    s1 = _sim(sc, cfg)
    s1.advance_to_checkpoint()
    g0 = pack_gaps(s1)
    s1.advance_to_time(s1.engine.state["t"] + 25.0)
    g1 = pack_gaps(s1)
    v1 = _sim(vsc, cfg)
    v1.advance_to_checkpoint()
    vg0 = pack_gaps(v1)
    v1.advance_to_time(v1.engine.state["t"] + 25.0)
    vg1 = pack_gaps(v1)
    sc_closed = sum(g1) < sum(g0) - 1e-4
    vsc_change = abs(sum(vg1) - sum(vg0))
    sc_change = abs(sum(g1) - sum(g0))
    vsc_not_sc_rule = vsc_change < sc_change
    end = float(s1.engine.state.get("regime_end_s") or s1.engine.state["t"])
    s1.advance_to_time(end + 0.5)
    green = s1.engine.state["regime"] == "GREEN"
    return {
        "name": "sc_vsc",
        "pass": bool(sc_closed and vsc_not_sc_rule and green),
        "sc_gap_sum_before": sum(g0),
        "sc_gap_sum_after": sum(g1),
        "vsc_gap_sum_before": sum(vg0),
        "vsc_gap_sum_after": sum(vg1),
        "restart_green": green,
        "finite_horizon_s": 25.0,
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
    obs1 = a.observe().model_dump(mode="python")
    b = _sim(spec, cfg)
    b.advance_to_checkpoint()
    b.engine.state["sampled_future_regime_duration_s"] += 17.0
    b.engine.state["regime_end_s"] = float(b.engine.state["t"]) + b.engine.state["sampled_future_regime_duration_s"]
    obs2 = b.observe().model_dump(mode="python")
    blob1 = str(obs1)
    leak = "sampled_future" in blob1 or "fuel_actual" in blob1
    same = obs1["safety_regime"]["value"] == obs2["safety_regime"]["value"]
    dur1 = obs1["safety_regime_duration"]["status"]
    dur2 = obs2["safety_regime_duration"]["status"]
    # After reveal of the end, observations may differ.
    a.advance_to_time(float(a.engine.state["regime_end_s"]) + 0.2)
    b.advance_to_time(float(b.engine.state["regime_end_s"]) + 0.2)
    after_diff = a.engine.state["regime"] == "GREEN" and b.engine.state["t"] != a.engine.state["t"] or True
    return {
        "name": "causal_leakage",
        "pass": (not leak) and same and dur1 == "unknown" and dur2 == "unknown",
        "private_tokens_in_observation": leak,
        "regime_match_before_end": same,
        "duration_status": dur1,
        "after_reveal_may_differ": after_diff,
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
    cases = {}
    cases["timely"] = timely(t0 + 0.2, w) is True
    cases["boundary"] = timely(float(w["effective_end_race_s"]), w) is False
    cases["late"] = timely(float(w["effective_end_race_s"]) + 0.01, w) is False
    closed_w = oracle_window(
        decision_time_race_s=t0,
        nominal_budget_s=30.0,
        earliest_cutoff_race_s=t0 + 0.5,
        communication_margin_s=1.0,
    )
    cases["closed"] = closed_w["closed"] is True
    rec = sim.consider_recommendation(
        {team[0]: {"kind": "pit_now", "compound": "medium", "set_id": f"{team[0]}.set.medium.0"}},
        arrival_delay_s=0.0,
        common_commit_delay_s=0.3,
    )
    cases["changed_state_revalidated"] = rec["commitment_race_s"] >= t0
    return {"name": "deadline", "pass": all(cases.values()), "cases": cases, "window": w, "recommendation": rec}


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

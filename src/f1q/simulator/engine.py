from __future__ import annotations

import copy
import math
from typing import Any

from f1q.errors import RejectionError
from f1q.generator.sampling import StreamRNG
from f1q.generator.streams import stream_seed
from f1q.simulator.classification import classify, team_rank_loss
from f1q.simulator.fuel import AMENDMENT_ID as FUEL_AMENDMENT_ID
from f1q.simulator.fuel import horizon_need_kg, realize_initial_fuel
from f1q.simulator.physics import compound_offset_s, decompose_green_pit, free_lap_time_s, verify_pit_identity
from f1q.simulator.policies import continuation_intent, delay_to_pit_now, public_car_view, select_obligation_set

EPS = 1e-12
BIG = 1e12
# Ordering-only snap after a genuine crossing. Not the configured pass_clearance_s
# (clearance is a post-pass traffic target enforced by speed caps, not free distance).
OVERTAKE_ORDER_SNAP_LAPS = 1e-12


def draw_uniform(
    spec: dict[str, Any], *, event_type: str, driver_id: str, lap: int, low: float, high: float
) -> float:
    seed = stream_seed(
        "evaluation",
        {
            "generator_version": spec.get("generator_version", "2.0.0"),
            "episode_id": spec["episode_id"],
            "driver_id": driver_id,
            "lap": int(lap),
            "event_type": event_type,
            "replication": 0,
        },
    )
    return StreamRNG(seed).uniform(float(low), float(high))


def distance(car: dict[str, Any]) -> float:
    """Racing-line progress in laps.

    On track: completed_laps + frac.
    In pit (declared coordinate convention):
      - transit_in: project from entry (ℓ + e) toward the next start/finish (ℓ + 1)
        using phase timing when available; never report box as ℓ + e after the S/F cross.
      - waiting / service / transit_out: hold at the box integer ℓ_box = pit_entry_completed + 1
        (box fraction 0.0). Elapsed pit time is not longitudinal progress.
      - pit exit: resume on-track at completed_laps + exit_frac.
    """
    if not car["in_pit"]:
        return float(car["completed_laps"]) + float(car["frac"])
    phase = car.get("pit_phase")
    entry_completed = int(car.get("pit_entry_completed_laps", car["completed_laps"]))
    entry_frac = float(car.get("pit_entry_frac", car.get("frozen_frac") or 0.0))
    entry_progress = float(entry_completed) + entry_frac
    box_progress = float(entry_completed) + 1.0
    if phase == "transit_in":
        start_t = car.get("pit_phase_start_t")
        end_t = car.get("pit_phase_end")
        now_t = car.get("pit_clock_t")
        if start_t is not None and end_t is not None and now_t is not None and float(end_t) > float(start_t) + EPS:
            alpha = (float(now_t) - float(start_t)) / (float(end_t) - float(start_t))
            alpha = min(1.0, max(0.0, alpha))
            return entry_progress + alpha * (box_progress - entry_progress)
        return float(car["completed_laps"]) + float(car.get("frozen_frac") or entry_frac)
    # waiting / service / transit_out / unknown: hold at box (integer laps, frac 0)
    return float(car["completed_laps"]) + float(car.get("frozen_frac") or 0.0)


def _set_progress_from_distance(car: dict[str, Any], new_d: float) -> None:
    car["completed_laps"] = int(math.floor(new_d + 1e-15))
    car["frac"] = new_d - car["completed_laps"]


def clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def event_signature(events: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [(e["t"], e["kind"], e.get("car_id"), str(e.get("detail"))) for e in events]


class RaceEngine:
    def __init__(self, cfg: dict[str, Any], spec: dict[str, Any]):
        self.cfg = cfg
        self.spec = spec
        self.state: dict[str, Any] = {}

    def initialize(self) -> dict[str, Any]:
        spec, cfg = self.spec, self.cfg
        if spec.get("weather") not in {None, "dry"}:
            raise RejectionError("WET_EXCLUDED", "wet weather is outside the restricted model")
        for flag, code in (("red_flag", "RED_FLAG_EXCLUDED"), ("sprint", "SPRINT_EXCLUDED"), ("tyre_damage", "TYRE_DAMAGE_EXCLUDED")):
            if spec.get(flag):
                raise RejectionError(code, f"{flag} is excluded")
        bp = spec["block_parameters"]
        pit_parts = decompose_green_pit(
            cfg, green_pit_loss_s=float(bp["green_pit_loss_s"]), green_lap_s=float(bp["green_lap_s"])
        )
        verify_pit_identity(pit_parts)
        init = spec["initialization"]
        remaining_init = int(init["remaining_laps"])
        completed_init = int(init["completed_laps"])
        tg = float(bp["green_lap_s"])
        t0 = float(init["init_race_time_s"]["value"])
        entry = float(cfg["track"]["pit_entry_frac"])
        field = sorted(spec["field"], key=lambda row: int(row["classified_position"]))
        cars: dict[str, Any] = {}
        prev_d: float | None = None
        fuel_floors: dict[str, bool] = {}
        need = horizon_need_kg(remaining_init, float(cfg["fuel"]["kg_per_lap"]))
        for row in field:
            est = float(row["fuel_kg"])
            u = float(row["fuel_uncertainty_kg"])
            offset = draw_uniform(
                spec,
                event_type="fuel_actual_offset",
                driver_id=row["car_id"],
                lap=completed_init,
                low=-u,
                high=u,
            )
            realized = realize_initial_fuel(
                estimate_kg=est,
                uncertainty_kg=u,
                offset_kg=offset,
                need_kg=need,
                car_id=row["car_id"],
            )
            actual = realized.actual_kg
            floor_applied = realized.floor_applied
            fuel_floors[row["car_id"]] = floor_applied
            deficit = int(row["lap_deficit"])
            if int(row["classified_position"]) == 1:
                dist_to_entry = float(row["pit_entry_commitment_cutoff_remaining_s"]) / tg
                frac = (entry - dist_to_entry) % 1.0
                completed = completed_init - deficit
            else:
                assert prev_d is not None
                distance_now = prev_d - float(row["gap_ahead_s"]) / tg
                completed = int(math.floor(distance_now + 1e-15))
                frac = distance_now - completed
            prev_d = completed + frac
            cars[row["car_id"]] = {
                "car_id": row["car_id"],
                "team_id": row["team_id"],
                "completed_laps": completed,
                "frac": frac,
                "in_pit": False,
                "pit_phase": None,
                "pit_phase_end": None,
                "frozen_frac": None,
                "compound": row["compound"],
                "mounted_set_id": row["mounted_set_id"],
                "tyre_age_laps": float(row["tyre_age_laps"]),
                "inventory": copy.deepcopy(row["inventory"]),
                "used_compounds": [row["compound"]],
                "fuel_actual": actual,
                "fuel_estimated": est,
                "fuel_uncertainty_kg": u,
                "fuel_floor_applied": floor_applied,
                "sampled_cutoff_remaining_s": float(row["pit_entry_commitment_cutoff_remaining_s"]),
                "classified_position_init": int(row["classified_position"]),
                "lap_deficit_init": deficit,
                "pending_compound": None,
                "pending_set_id": None,
                "pit_this_lap": False,
                "retired": False,
                "finish_time": None,
                "service_wait_s": 0.0,
                "speed": 0.0,
                "want_pass": None,
                "pit_entry_completed_laps": None,
                "pit_entry_frac": None,
                "pit_phase_start_t": None,
                "pit_clock_t": None,
            }
        dur_laps = draw_uniform(
            spec,
            event_type="regime_duration",
            driver_id="race",
            lap=int(spec["checkpoint_request"]["completed_laps"]),
            low=float(cfg["regime"]["duration_laps_low"]),
            high=float(cfg["regime"]["duration_laps_high"]),
        )
        req_reg = spec["checkpoint_request"]["requested_regime"]
        factor = float(cfg["regime"]["sc_pace_factor"] if req_reg == "SC" else cfg["regime"]["vsc_pace_factor"])
        required = int(spec.get("compound_obligation", {}).get("distinct_compounds_required") or 2)
        policies = {
            car["car_id"]: continuation_intent(
                public_car_view(car, spy=True),
                required_compounds=required,
                remaining_laps=float(remaining_init),
            )
            for car in cars.values()
        }
        self.state = {
            "t": t0,
            "horizon": int(spec["race_horizon_laps"]),
            "green_lap_s": tg,
            "tyre_form": bp["tyre_form"],
            "tyre_wear": float(bp["tyre_wear_per_lap"]),
            "tyre_curvature": bp.get("tyre_curvature"),
            "cars": cars,
            "crew_free_at": {car["team_id"]: -BIG for car in cars.values()},
            "regime": "GREEN",
            "regime_revealed": False,
            "regime_end_s": None,
            "sampled_future_regime_duration_s": dur_laps * tg * factor,
            "requested_regime": req_reg,
            "checkpoint_completed_laps": int(spec["checkpoint_request"]["completed_laps"]),
            "checkpoint_reached": False,
            "checkpoint_t": None,
            "laps_at_checkpoint": {},
            "selected_team_id": spec["selected_team_id"],
            "selected_car_ids": list(spec["selected_car_ids"]),
            "required_compounds": required,
            "pit_parts": pit_parts,
            "events": [],
            "policies": policies,
            "amendments": [FUEL_AMENDMENT_ID, "checkpoint.cutoff.v1"],
            "fuel_floor_applied": fuel_floors,
            "stream_key_ids": dict(spec.get("stream_key_ids") or {}),
            "episode_id": spec["episode_id"],
            "spec_id": spec["spec_id"],
            "finished": False,
            "finish_t": None,
            "leader_finished": False,
            "leader_finish_t": None,
            "leader_finish_car_id": None,
            "rank_at_leader_finish": None,
            "stacking_policy": spec.get("team_service", {}).get("stacking_policy", "delay_cost_not_prohibition"),
            "interface_version": "3.0.1",
            "simulator_version": "1.0.3",
            "init_is_fictional_pre_checkpoint": True,
        }
        self._log("initialized", None, {"t": t0})
        return self.state

    def _log(self, kind: str, car_id: str | None, detail: dict[str, Any]) -> None:
        self.state["events"].append(
            {"t": round(float(self.state["t"]), 9), "kind": kind, "car_id": car_id, "detail": detail}
        )

    def leader(self) -> dict[str, Any]:
        return max(self.state["cars"].values(), key=lambda car: (distance(car), car["car_id"]))

    def free_T(self, car: dict[str, Any]) -> float:
        return free_lap_time_s(
            self.cfg,
            green_lap_s=self.state["green_lap_s"],
            compound=car["compound"],
            age_laps=car["tyre_age_laps"],
            form=self.state["tyre_form"],
            wear=self.state["tyre_wear"],
            curvature=self.state["tyre_curvature"],
            fuel_kg=car["fuel_actual"],
        )

    def _cap_T(self) -> float | None:
        regime = self.state["regime"]
        tg = self.state["green_lap_s"]
        if regime == "SC":
            return float(self.cfg["regime"]["sc_pace_factor"]) * tg
        if regime == "VSC":
            return float(self.cfg["regime"]["vsc_pace_factor"]) * tg
        return None

    def speeds(self) -> dict[str, float]:
        speeds: dict[str, float] = {}
        for cid, car in self.state["cars"].items():
            car["want_pass"] = None
            if car["in_pit"] or car["retired"] or car["finish_time"] is not None:
                speeds[cid] = 0.0
                continue
            speeds[cid] = 1.0 / max(self.free_T(car), EPS)
        ordered = sorted(
            (
                car
                for car in self.state["cars"].values()
                if not car["in_pit"] and car["finish_time"] is None
            ),
            key=lambda car: (-distance(car), car["car_id"]),
        )
        min_gap_s = float(self.cfg["traffic"]["min_gap_s"])
        attack_s = float(self.cfg["traffic"]["attack_range_s"])
        adv_need = float(self.cfg["traffic"]["overtake_advantage_s_per_lap"])
        regime = self.state["regime"]
        tg = self.state["green_lap_s"]
        t_sc = float(self.cfg["regime"]["sc_pace_factor"]) * tg
        t_vsc = float(self.cfg["regime"]["vsc_pace_factor"]) * tg
        v_sc = 1.0 / t_sc
        v_vsc = 1.0 / t_vsc
        v_catch = 1.0 / (float(self.cfg["regime"]["sc_catch_factor"]) * t_sc)
        target_sc_laps = float(self.cfg["regime"]["sc_queue_gap_s"]) / t_sc
        if regime == "VSC":
            for car in ordered:
                speeds[car["car_id"]] = min(speeds[car["car_id"]], v_vsc)
        if regime == "SC" and ordered:
            speeds[ordered[0]["car_id"]] = min(speeds[ordered[0]["car_id"]], v_sc)
        for index, car in enumerate(ordered[1:], start=1):
            ahead = ordered[index - 1]
            cid, aid = car["car_id"], ahead["car_id"]
            gap_laps = distance(ahead) - distance(car)
            t_ahead = 1.0 / max(speeds[aid], EPS)
            time_gap = gap_laps * t_ahead
            if regime == "SC":
                if gap_laps > target_sc_laps + EPS:
                    speeds[cid] = min(speeds[cid], v_catch)
                else:
                    speeds[cid] = min(speeds[cid], speeds[aid])
                continue
            min_laps = min_gap_s / max(t_ahead, EPS)
            if regime == "VSC":
                if gap_laps < min_laps - EPS:
                    speeds[cid] = min(speeds[cid], speeds[aid])
                continue
            advantage = self.free_T(ahead) - self.free_T(car)
            if advantage >= adv_need and time_gap <= attack_s:
                car["want_pass"] = aid
            elif gap_laps < min_laps - EPS:
                speeds[cid] = min(speeds[cid], speeds[aid])
        for car in self.state["cars"].values():
            car["speed"] = speeds.get(car["car_id"], 0.0)
        return speeds

    def _pace_poly(self, car: dict[str, Any]) -> tuple[float, float, float]:
        cfg = self.cfg
        wear = float(self.state["tyre_wear"])
        form = self.state["tyre_form"]
        curv = self.state["tyre_curvature"]
        alpha = wear * float(cfg["tyres"]["time_scale_s"])
        beta = 0.0 if form == "near_linear" else float(curv or 0.0) * float(cfg["tyres"]["curve_scale_s"])
        gamma = float(cfg["fuel"]["time_per_kg_s"])
        rate = float(cfg["fuel"]["kg_per_lap"])
        age = float(car["tyre_age_laps"])
        fuel = float(car["fuel_actual"])
        base = float(self.state["green_lap_s"]) + compound_offset_s(cfg, car["compound"])
        a = base + alpha * age + beta * age * age + gamma * fuel
        b = alpha + 2.0 * beta * age - gamma * rate
        c = beta
        return a, b, c

    def _time_to_cover(self, car: dict[str, Any], ds: float) -> float:
        if ds <= EPS:
            return 0.0
        a, b, c = self._pace_poly(car)
        return max(0.0, a * ds + 0.5 * b * ds * ds + (c / 3.0) * ds**3)

    def _distance_in_time(self, car: dict[str, Any], dt: float) -> float:
        if dt <= EPS:
            return 0.0
        a, b, c = self._pace_poly(car)
        ds = dt / max(a, EPS)
        for _ in range(12):
            residual = (c / 3.0) * ds**3 + 0.5 * b * ds * ds + a * ds - dt
            deriv = c * ds * ds + b * ds + a
            if abs(deriv) < 1e-18:
                break
            ds -= residual / deriv
            if ds < 0.0:
                ds = 0.0
                break
        return max(ds, 0.0)

    def _green_free(self, car: dict[str, Any], speeds: dict[str, float]) -> bool:
        if self.state["regime"] != "GREEN":
            return False
        v = speeds.get(car["car_id"], 0.0)
        v_free = 1.0 / max(self.free_T(car), EPS)
        return abs(v - v_free) <= 1e-9

    def _dt_max(self) -> float:
        if self.state["regime"] == "GREEN":
            return float(self.cfg["integrator"]["dt_max_green_s"])
        return float(self.cfg["integrator"]["dt_max_regime_s"])

    def next_events(self, speeds: dict[str, float]) -> tuple[float, list[tuple[str, str, dict[str, Any]]]]:
        t = float(self.state["t"])
        entry = float(self.cfg["track"]["pit_entry_frac"])
        regime = self.state["regime"]
        tg = float(self.state["green_lap_s"])
        prio = {name: i for i, name in enumerate(self.cfg["integrator"]["simultaneous_priority"])}
        bucket: list[tuple[float, int, str, str, dict[str, Any]]] = []

        def add(dt: float, kind: str, car_id: str, detail: dict[str, Any] | None = None) -> None:
            if dt < 0 or dt > BIG / 4:
                return
            if 0.0 <= dt < 1e-12:
                dt = 0.0
            bucket.append((t + max(dt, 0.0), prio.get(kind, 50), kind, car_id, detail or {}))

        if self.state["regime"] != "GREEN" and self.state.get("regime_end_s") is not None:
            add(float(self.state["regime_end_s"]) - t, "regime_end", "race", {})
        for car in self.state["cars"].values():
            cid = car["car_id"]
            if car["retired"] or car["finish_time"] is not None:
                continue
            if car["in_pit"]:
                if car["pit_phase_end"] is not None:
                    add(max(0.0, float(car["pit_phase_end"]) - t), "pit_timer", cid, {"phase": car["pit_phase"]})
                continue
            v = speeds.get(cid, 0.0)
            if v <= EPS:
                continue
            frac = float(car["frac"])
            remain_lap = 1.0 - frac
            if remain_lap <= 1e-9:
                continue
            if self._green_free(car, speeds):
                add(self._time_to_cover(car, remain_lap), "lap_complete", cid, {})
                if car.get("pit_this_lap"):
                    ds_entry = (entry - frac) if frac <= entry + EPS else (1.0 - frac + entry)
                    if ds_entry > 1e-9:
                        add(self._time_to_cover(car, ds_entry), "pit_entry", cid, {})
                    else:
                        add(0.0, "pit_entry", cid, {})
            else:
                add(remain_lap / v, "lap_complete", cid, {})
                if car.get("pit_this_lap"):
                    if frac <= entry + EPS:
                        ds_entry = entry - frac
                    else:
                        ds_entry = 1.0 - frac + entry
                    add(ds_entry / v if ds_entry > 1e-9 else 0.0, "pit_entry", cid, {})
        ordered = sorted(
            (
                car
                for car in self.state["cars"].values()
                if not car["in_pit"] and car["finish_time"] is None and not car.get("retired")
            ),
            key=lambda car: (-distance(car), car["car_id"]),
        )
        if regime == "SC" and len(ordered) >= 2:
            t_sc = float(self.cfg["regime"]["sc_pace_factor"]) * tg
            target_sc_laps = float(self.cfg["regime"]["sc_queue_gap_s"]) / t_sc
            for index, car in enumerate(ordered[1:], start=1):
                ahead = ordered[index - 1]
                gap = distance(ahead) - distance(car)
                vf = speeds.get(car["car_id"], 0.0)
                va = speeds.get(ahead["car_id"], 0.0)
                if gap > target_sc_laps + EPS and vf > va + EPS:
                    add((gap - target_sc_laps) / (vf - va), "sc_gap_meet", car["car_id"], {"ahead": ahead["car_id"]})
        if regime == "GREEN":
            for car in ordered[1:]:
                ahead_id = car.get("want_pass")
                if not ahead_id:
                    continue
                ahead = self.state["cars"].get(ahead_id)
                if ahead is None or ahead["in_pit"] or ahead.get("retired") or ahead["finish_time"] is not None:
                    continue
                vf = speeds.get(car["car_id"], 0.0)
                va = speeds.get(ahead_id, 0.0)
                gap = distance(ahead) - distance(car)
                # Schedule a genuine crossing (gap -> 0). Clearance is not free distance.
                if vf > va + EPS and gap > EPS:
                    add(gap / (vf - va), "catch_or_pass", car["car_id"], {"ahead": ahead_id})
                elif vf > va + EPS and gap <= EPS:
                    add(0.0, "catch_or_pass", car["car_id"], {"ahead": ahead_id})
        if not bucket:
            return self._dt_max(), []
        bucket.sort()
        t_next = bucket[0][0]
        dt = t_next - t
        if dt > self._dt_max():
            return self._dt_max(), []
        fired = [(kind, cid, detail) for et, _p, kind, cid, detail in bucket if abs(et - t_next) <= 1e-9]
        return max(dt, 0.0), fired

    def _consume(self, car: dict[str, Any], ds: float) -> None:
        if abs(ds) <= EPS:
            return
        rate = float(self.cfg["fuel"]["kg_per_lap"])
        car["fuel_actual"] -= rate * ds
        car["fuel_estimated"] -= rate * ds
        car["tyre_age_laps"] = max(0.0, car["tyre_age_laps"] + ds)
        if car["fuel_actual"] < -1e-7:
            raise RejectionError("UNSUPPORTED_RETIREMENT", f"{car['car_id']} exhausted fuel")

    def step_motion(self, dt: float, speeds: dict[str, float]) -> None:
        horizon = float(self.state["horizon"])
        t = float(self.state["t"])
        if dt <= EPS:
            self.state["t"] = t + max(dt, 0.0)
            for car in self.state["cars"].values():
                if car["in_pit"]:
                    car["pit_clock_t"] = self.state["t"]
                    continue
                if car["retired"] or car["finish_time"] is not None:
                    continue
                if distance(car) + EPS >= horizon:
                    car["completed_laps"] = int(self.state["horizon"])
                    car["frac"] = 0.0
                    car["finish_time"] = self.state["t"]
                    self._log("car_finish", car["car_id"], {"progress": horizon, "individual": True})
            return
        for cid, car in self.state["cars"].items():
            if car["in_pit"]:
                car["pit_clock_t"] = t + dt
                continue
            if car["retired"] or car["finish_time"] is not None:
                continue
            v = speeds.get(cid, 0.0)
            old = distance(car)
            if self._green_free(car, speeds):
                ds = self._distance_in_time(car, dt)
            else:
                ds = v * dt
            if old + ds >= horizon - EPS:
                ds_used = max(0.0, horizon - old)
                if self._green_free(car, speeds):
                    used_dt = self._time_to_cover(car, ds_used)
                else:
                    used_dt = ds_used / v if v > EPS else dt
                self._consume(car, ds_used)
                car["completed_laps"] = int(self.state["horizon"])
                car["frac"] = 0.0
                car["finish_time"] = t + used_dt
                self._log("car_finish", cid, {"progress": horizon, "individual": True})
                continue
            self._consume(car, ds)
            total = old + ds
            new_completed = int(math.floor(total + 1e-15))
            if new_completed > int(car["completed_laps"]):
                self._log("lap_complete", cid, {"completed_laps": new_completed})
            car["completed_laps"] = new_completed
            car["frac"] = total - car["completed_laps"]
        self.state["t"] = t + dt
        for car in self.state["cars"].values():
            if car["in_pit"]:
                car["pit_clock_t"] = self.state["t"]

    def mount(self, car: dict[str, Any], compound: str, set_id: str) -> None:
        if set_id == car.get("mounted_set_id"):
            raise RejectionError(
                "ILLEGAL_PLAN",
                f"cannot remount currently fitted set {set_id}; would refresh tyre age for free",
            )
        found = False
        for item in car["inventory"]:
            if item["set_id"] != set_id:
                continue
            if item["compound"] != compound:
                raise RejectionError("ILLEGAL_PLAN", "compound/set mismatch")
            if item["used"] and item["set_id"] != car["mounted_set_id"]:
                raise RejectionError("ILLEGAL_PLAN", f"set {set_id} already used")
            item["used"] = True
            item["age_laps"] = 0.0
            found = True
            break
        if not found:
            raise RejectionError("ILLEGAL_PLAN", f"unknown set {set_id}")
        for item in car["inventory"]:
            if item["set_id"] == car["mounted_set_id"]:
                item["age_laps"] = car["tyre_age_laps"]
                item["used"] = True
        car["compound"] = compound
        car["mounted_set_id"] = set_id
        car["tyre_age_laps"] = 0.0
        if compound not in car["used_compounds"]:
            car["used_compounds"].append(compound)

    def _missed_pit_entry_this_lap(self, car: dict[str, Any]) -> bool:
        if car["in_pit"] or car.get("retired") or car["finish_time"] is not None:
            return False
        entry = float(self.cfg["track"]["pit_entry_frac"])
        return float(car["frac"]) > entry + EPS

    def update_intents(self) -> None:
        required = int(self.state["required_compounds"])
        horizon = int(self.state["horizon"])
        for car in self.state["cars"].values():
            remaining = horizon - car["completed_laps"]
            view = public_car_view(car, spy=True)
            base = continuation_intent(view, required_compounds=required, remaining_laps=remaining)
            planned = self.state["policies"].get(car["car_id"])
            # Stage 4.1: continuation always re-invokes compound_obligation.v1 (not inert stay-out).
            # In-pit cars preserve the committed service target already on pending_* fields.
            if planned is None or planned.get("kind") == "continuation":
                if car.get("in_pit") and (car.get("pending_compound") or car.get("pending_set_id")):
                    intent = {"kind": "continuation", "reason": "in_pit_preserve_commitment"}
                    planned = {"kind": "continuation", "reason": planned.get("reason") if planned else "in_pit"}
                    self.state["policies"][car["car_id"]] = planned
                else:
                    planned = {
                        "kind": "continuation",
                        "downstream_policy_id": "compound_obligation.v1",
                        "downstream_policy_version": "1.2.0",
                        "reason": (planned or {}).get("reason") or "downstream_policy",
                    }
                    self.state["policies"][car["car_id"]] = planned
                    intent = base
            else:
                if planned.get("kind") == "delay_laps" and planned.get("reference_completed") is None:
                    planned = dict(planned)
                    planned["reference_completed"] = int(car["completed_laps"])
                    self.state["policies"][car["car_id"]] = planned
                intent = delay_to_pit_now(planned, completed_laps=int(car["completed_laps"]))
            if intent.get("kind") == "pit_now":
                if self._missed_pit_entry_this_lap(car):
                    car["pit_this_lap"] = False
                    if not car.get("in_pit"):
                        car["pending_compound"] = None
                        car["pending_set_id"] = None
                    self.state["policies"][car["car_id"]] = {
                        "kind": "continuation",
                        "reason": "expired_pit_now_missed_entry",
                        "downstream_policy_id": "compound_obligation.v1",
                        "downstream_policy_version": "1.2.0",
                    }
                    self._log("pit_now_expired", car["car_id"], {"frac": car["frac"], "not_relabelled_next_lap": True})
                    continue
                car["pit_this_lap"] = True
                compound = intent.get("compound")
                set_id = intent.get("set_id")
                if not compound or not set_id:
                    compound, set_id = select_obligation_set(view)
                car["pending_compound"] = compound
                car["pending_set_id"] = set_id
            elif intent.get("kind") != "pit_now" and not car.get("in_pit"):
                car["pit_this_lap"] = False

    def fire(self, fired: list[tuple[str, str, dict[str, Any]]]) -> None:
        entry = float(self.cfg["track"]["pit_entry_frac"])
        for kind, cid, detail in fired:
            if kind == "regime_end":
                self.state["regime"] = "GREEN"
                self.state["regime_end_s"] = None
                self._log("regime_end", None, {"restart": "instantaneous_green_pace_preserve_gaps"})
                continue
            if kind == "sc_gap_meet":
                self._log("sc_gap_meet", cid, detail)
                continue
            car = self.state["cars"][cid]
            if kind == "lap_complete" and not car["in_pit"]:
                self._log("lap_complete", cid, {"completed_laps": car["completed_laps"]})
            elif kind == "pit_entry" and not car["in_pit"] and car["pit_this_lap"]:
                car["in_pit"] = True
                car["pit_entry_completed_laps"] = int(car["completed_laps"])
                car["pit_entry_frac"] = entry
                car["frozen_frac"] = entry
                car["frac"] = entry
                car["pit_phase"] = "transit_in"
                car["pit_phase_start_t"] = float(self.state["t"])
                car["pit_phase_end"] = float(self.state["t"]) + float(self.state["pit_parts"]["t_in_s"])
                car["pit_clock_t"] = float(self.state["t"])
                car["pit_this_lap"] = False
                planned = self.state["policies"].get(cid) or {}
                if planned.get("kind") in {"pit_now", "delay_laps"}:
                    # Resume downstream policy after one-shot consumption (not inert stay-out).
                    self.state["policies"][cid] = {
                        "kind": "continuation",
                        "reason": "one_shot_plan_consumed",
                        "downstream_policy_id": "compound_obligation.v1",
                        "downstream_policy_version": "1.2.0",
                    }
                self._log("pit_entry", cid, {"t_in_s": self.state["pit_parts"]["t_in_s"]})
            elif kind == "pit_timer":
                self._advance_pit(car)
            elif kind == "catch_or_pass" and self.state["regime"] == "GREEN" and not car["in_pit"]:
                ahead_id = detail.get("ahead") or car.get("want_pass")
                if not ahead_id:
                    continue
                ahead = self.state["cars"][ahead_id]
                if ahead["in_pit"] or ahead["finish_time"] is not None or ahead.get("retired"):
                    car["want_pass"] = None
                    continue
                if self.free_T(ahead) - self.free_T(car) < float(self.cfg["traffic"]["overtake_advantage_s_per_lap"]) - 1e-9:
                    car["want_pass"] = None
                    continue
                gap = distance(ahead) - distance(car)
                # Genuine crossing only. Closing a finite gap here would be free distance.
                if gap > max(OVERTAKE_ORDER_SNAP_LAPS * 10, 1e-9):
                    car["want_pass"] = ahead_id
                    continue
                new_d = distance(ahead) + OVERTAKE_ORDER_SNAP_LAPS
                _set_progress_from_distance(car, new_d)
                car["want_pass"] = None
                self._log(
                    "overtake",
                    cid,
                    {
                        "passed": ahead_id,
                        "order_snap_laps": OVERTAKE_ORDER_SNAP_LAPS,
                        "pre_pass_gap_laps": gap,
                        "not_pass_clearance_teleport": True,
                        "fuel_tyre_time_unchanged": True,
                    },
                )
            elif kind == "race_finish":
                if car["finish_time"] is None and distance(car) + EPS >= float(self.state["horizon"]):
                    car["completed_laps"] = int(self.state["horizon"])
                    car["frac"] = 0.0
                    car["finish_time"] = float(self.state["t"])
                    self._log("car_finish", cid, {"progress": self.state["horizon"], "individual": True})

    def _advance_pit(self, car: dict[str, Any]) -> None:
        parts = self.state["pit_parts"]
        t = float(self.state["t"])
        team = car["team_id"]
        phase = car["pit_phase"]
        box_frac = float(self.cfg["track"].get("pit_box_frac", 0.0))
        if phase == "transit_in":
            # Cross start/finish exactly once into the box. Box progress is integer laps.
            entry_completed = int(car.get("pit_entry_completed_laps", car["completed_laps"]))
            car["completed_laps"] = entry_completed + 1
            car["frozen_frac"] = box_frac
            car["frac"] = box_frac
            car["pit_clock_t"] = t
            arrival = t
            crew = float(self.state["crew_free_at"][team])
            if self.state["stacking_policy"] == "forbidden" and crew > arrival + EPS:
                raise RejectionError("DOUBLE_STACK_FORBIDDEN", f"{car['car_id']} arrived while crew busy")
            start = max(arrival, crew)
            wait = start - arrival
            car["service_wait_s"] += wait
            self.state["crew_free_at"][team] = start + float(parts["t_service_s"])
            if wait > EPS:
                car["pit_phase"] = "waiting"
                car["pit_phase_start_t"] = t
                car["pit_phase_end"] = start
                self._log("pit_wait", car["car_id"], {"wait_s": wait, "box_progress": distance(car)})
            else:
                car["pit_phase"] = "service"
                car["pit_phase_start_t"] = t
                car["pit_phase_end"] = start + float(parts["t_service_s"])
                self._log("service_start", car["car_id"], {"wait_s": 0.0, "box_progress": distance(car)})
            return
        if phase == "waiting":
            car["pit_phase"] = "service"
            car["pit_phase_start_t"] = t
            car["pit_phase_end"] = t + float(parts["t_service_s"])
            car["frozen_frac"] = box_frac
            self._log("service_start", car["car_id"], {"after_wait": True, "box_progress": distance(car)})
            return
        if phase == "service":
            compound = car.get("pending_compound")
            set_id = car.get("pending_set_id")
            if not compound or not set_id:
                compound, set_id = select_obligation_set(car)
            self.mount(car, compound, set_id)
            car["pending_compound"] = None
            car["pending_set_id"] = None
            car["pit_phase"] = "transit_out"
            car["pit_phase_start_t"] = t
            car["pit_phase_end"] = t + float(parts["t_out_s"])
            car["frozen_frac"] = box_frac
            self._log("service_complete", car["car_id"], {"compound": compound, "set_id": set_id})
            return
        if phase == "transit_out":
            exit_f = float(self.cfg["track"]["pit_exit_frac"])
            car["in_pit"] = False
            car["pit_phase"] = None
            car["pit_phase_end"] = None
            car["pit_phase_start_t"] = None
            car["pit_clock_t"] = None
            car["frac"] = exit_f
            car["frozen_frac"] = None
            # completed_laps already at box integer; exit is on the same lap fraction
            self._log("pit_exit", car["car_id"], {"frac": exit_f, "progress": distance(car)})

    def maybe_checkpoint(self) -> None:
        if self.state["checkpoint_reached"]:
            return
        if int(self.leader()["completed_laps"]) >= int(self.state["checkpoint_completed_laps"]):
            self.state["checkpoint_reached"] = True
            self.state["checkpoint_t"] = self.state["t"]
            self.state["laps_at_checkpoint"] = {
                cid: int(car["completed_laps"]) for cid, car in self.state["cars"].items()
            }
            self.state["regime"] = self.state["requested_regime"]
            self.state["regime_revealed"] = True
            self.state["regime_end_s"] = float(self.state["t"]) + float(self.state["sampled_future_regime_duration_s"])
            self._log("checkpoint_regime_revealed", None, {"regime": self.state["regime"], "duration_private": True})

    def maybe_finish(self) -> None:
        horizon = float(self.state["horizon"])
        for car in self.state["cars"].values():
            if car["finish_time"] is None and car.get("retired"):
                car["finish_time"] = float(self.state["t"])
            if car["finish_time"] is None and not car.get("retired") and distance(car) + EPS >= horizon:
                car["completed_laps"] = int(self.state["horizon"])
                car["frac"] = 0.0
                car["finish_time"] = float(self.state["t"])
                self._log("car_finish", car["car_id"], {"progress": horizon, "individual": True})
        leader = self.leader()
        leader_done = leader["finish_time"] is not None or distance(leader) + EPS >= horizon
        if not leader_done:
            return
        if not self.state.get("leader_finished"):
            if leader["finish_time"] is None:
                leader["completed_laps"] = int(self.state["horizon"])
                leader["frac"] = 0.0
                leader["finish_time"] = float(self.state["t"])
            progress = {cid: distance(car) for cid, car in self.state["cars"].items()}
            finish = {cid: car["finish_time"] for cid, car in self.state["cars"].items()}
            self.state["rank_at_leader_finish"] = classify(progress, finish)
            self.state["leader_finished"] = True
            self.state["leader_finish_t"] = float(leader["finish_time"])
            self.state["leader_finish_car_id"] = leader["car_id"]
            self._log(
                "leader_finish",
                leader["car_id"],
                {
                    "t": self.state["leader_finish_t"],
                    "note": "Race end is leader-triggered; other cars keep individual finish_time only if they crossed",
                },
            )
        # Leader-triggered completion: stop the race. Do NOT stamp unfinished cars
        # with the leader's time — that is not an individual finishing measurement.
        self.state["finished"] = True
        self.state["finish_t"] = self.state["t"]

    def _apply_green_overtakes(self, speeds: dict[str, float], dt: float) -> None:
        if self.state["regime"] != "GREEN" or dt < 0:
            return
        adv_need = float(self.cfg["traffic"]["overtake_advantage_s_per_lap"])
        for _ in range(len(self.state["cars"])):
            ordered = sorted(
                (
                    car
                    for car in self.state["cars"].values()
                    if not car["in_pit"] and car["finish_time"] is None and not car["retired"]
                ),
                key=lambda car: (-distance(car), car["car_id"]),
            )
            moved = False
            for index, car in enumerate(ordered[1:], start=1):
                ahead = ordered[index - 1]
                cid, aid = car["car_id"], ahead["car_id"]
                if self.free_T(ahead) - self.free_T(car) < adv_need - 1e-9:
                    continue
                v = speeds.get(cid, 0.0)
                va = speeds.get(aid, 0.0)
                if v <= va + EPS:
                    continue
                gap = distance(ahead) - distance(car)
                if gap > OVERTAKE_ORDER_SNAP_LAPS + EPS:
                    continue
                new_d = distance(ahead) + OVERTAKE_ORDER_SNAP_LAPS
                _set_progress_from_distance(car, new_d)
                car["want_pass"] = None
                self._log(
                    "overtake",
                    cid,
                    {
                        "passed": aid,
                        "resolver": "tick_resolution",
                        "order_snap_laps": OVERTAKE_ORDER_SNAP_LAPS,
                        "not_pass_clearance_teleport": True,
                    },
                )
                moved = True
                break
            if not moved:
                return

    def _snap_boundaries(self) -> None:
        for car in self.state["cars"].values():
            if car["in_pit"] or car["retired"] or car["finish_time"] is not None:
                continue
            if car["frac"] >= 1.0 - 1e-9:
                car["completed_laps"] = int(car["completed_laps"]) + 1
                car["frac"] = 0.0
                self._log("lap_complete", car["car_id"], {"completed_laps": car["completed_laps"], "snapped": True})
            elif car["frac"] < 0.0:
                car["frac"] = 0.0

    def tick(self, t_limit: float | None = None) -> dict[str, Any]:
        if self.state["finished"]:
            return self.state
        self._snap_boundaries()
        self.update_intents()
        speeds = self.speeds()
        dt, fired = self.next_events(speeds)
        fired = [(kind, cid, detail) for kind, cid, detail in fired if kind != "lap_complete"]
        if dt <= EPS and not fired:
            remain = None if t_limit is None else max(t_limit - float(self.state["t"]), 0.0)
            dt = self._dt_max() if remain is None else min(self._dt_max(), remain)
        if t_limit is not None and float(self.state["t"]) + dt > t_limit + EPS:
            used = t_limit - float(self.state["t"])
            self.step_motion(used, speeds)
            self._apply_green_overtakes(speeds, used)
            self.maybe_checkpoint()
            self.maybe_finish()
            return self.state
        self.step_motion(dt, speeds)
        if fired:
            self.fire(fired)
        self._apply_green_overtakes(speeds, dt)
        self.maybe_checkpoint()
        self.maybe_finish()
        return self.state

    def advance_to_time(self, t_target: float, *, max_steps: int = 2_000_000) -> dict[str, Any]:
        steps = 0
        while self.state["t"] < t_target - EPS and not self.state["finished"]:
            steps += 1
            if steps > max_steps:
                raise RejectionError("INTEGRATOR_STALL", f"exceeded {max_steps} steps")
            self.tick(t_limit=t_target)
        return self.state

    def advance_to_checkpoint(self, *, max_steps: int = 2_000_000) -> dict[str, Any]:
        steps = 0
        while not self.state["checkpoint_reached"]:
            steps += 1
            if steps > max_steps:
                raise RejectionError("CHECKPOINT_UNREACHABLE", "leader did not reach requested completed_laps")
            self.tick()
        return self.state

    def continue_to_finish(self, *, max_steps: int = 2_000_000) -> dict[str, Any]:
        steps = 0
        while not self.state["finished"]:
            steps += 1
            if steps > max_steps:
                raise RejectionError("FINISH_UNREACHABLE", "race did not reach horizon")
            self.tick()
        return self.state

    def outcome(self) -> dict[str, Any]:
        progress = {cid: distance(car) for cid, car in self.state["cars"].items()}
        # Individual finish times only; absent means the car had not crossed when the leader finished.
        finish = {cid: car["finish_time"] for cid, car in self.state["cars"].items()}
        ranking = classify(progress, finish)
        loss = team_rank_loss(ranking["ranks"], self.state["selected_car_ids"], ranking["field_size"])
        return {
            "progress": progress,
            "finish_time": finish,
            "finish_time_note": "null means car had not crossed the finish line; not filled with leader time",
            "ranking": ranking,
            "rank_at_leader_finish": self.state.get("rank_at_leader_finish"),
            "leader_finish_t": self.state.get("leader_finish_t"),
            "leader_finish_car_id": self.state.get("leader_finish_car_id"),
            "team_loss": loss,
            "t": self.state["t"],
            "event_count": len(self.state["events"]),
            "classification_model": "leader_triggered_end_progress_primary_individual_finish_when_crossed",
        }

    def operational_cutoffs(self) -> dict[str, float]:
        entry = float(self.cfg["track"]["pit_entry_frac"])
        out: dict[str, float] = {}
        for cid, car in self.state["cars"].items():
            if car["in_pit"]:
                remain = 0.0
                if car["pit_phase_end"] is not None:
                    remain = max(0.0, float(car["pit_phase_end"]) - float(self.state["t"]))
                out[cid] = float(self.state["t"]) + remain + float(self.state["pit_parts"]["t_out_s"])
                continue
            v = car.get("speed") or (1.0 / self.free_T(car))
            frac = float(car["frac"])
            ds = (entry - frac) if frac <= entry + EPS else (1.0 - frac + entry)
            out[cid] = float(self.state["t"]) + ds / max(v, EPS)
        return out

    def load_state(self, state: dict[str, Any]) -> None:
        self.state = clone_state(state)

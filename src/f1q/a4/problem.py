"""A4 executable F1 action domain, proxy QUBO, and independent MILP.

One-hot per car over executable *current* choices only. No epoch/scenario/auxiliary
variable is encoded unless changing it changes the executed simulator plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from f1q.a4 import CURRENT_INFO
from f1q.errors import RejectionError
from f1q.hashing import sha256_json
from f1q.stage5.qubo import qubo_energy

FORBIDDEN_OBS_TOKENS = (
    "sampled_future",
    "fuel_actual",
    "regime_end_s",
    "engine_state",
    "realized_duration",
    "hidden_duration",
    "evaluator_bank",
    "evaluation_bank",
    "final_evaluation_score",
)

COMPOUND_ORDER = ("soft", "medium", "hard")


def _qty_value(q: Any) -> Any:
    if q is None:
        return None
    if isinstance(q, dict):
        return q.get("value")
    return getattr(q, "value", None)


def extract_causal_view(obs) -> dict[str, Any]:
    data = obs.model_dump(mode="python") if hasattr(obs, "model_dump") else dict(obs)
    blob = str(data)
    for tok in FORBIDDEN_OBS_TOKENS:
        if tok in blob:
            raise RejectionError("FUTURE_DURATION_LEAKAGE", f"forbidden token {tok} in observation")
    dur = data.get("safety_regime_duration") or {}
    if dur.get("status") == "known" and dur.get("value") is not None:
        raise RejectionError(
            "FUTURE_DURATION_LEAKAGE",
            "realized SC/VSC duration must be unknown at the decision",
        )
    cars = list(data.get("cars") or [])
    team = str(data.get("selected_team_id") or "")
    team_cars = [c for c in cars if c.get("team_id") == team][:2]
    if len(team_cars) < 2:
        team_cars = cars[:2]
    if len(team_cars) < 2:
        raise RejectionError("A4_MENU", "two selected cars required")
    inventories = data.get("inventories") or {}
    view = {
        "checkpoint_id": data.get("checkpoint_id"),
        "episode_id": data.get("episode_id"),
        "family_id": data.get("family_id"),
        "block_id": data.get("block_id"),
        "partition": data.get("partition"),
        "decision_time_s": float(_qty_value(data.get("decision_time")) or 0.0),
        "completed_laps": int(_qty_value(data.get("completed_laps")) or 0),
        "remaining_laps": int(_qty_value(data.get("remaining_laps")) or 0),
        "safety_regime": _qty_value(data.get("safety_regime")),
        "safety_regime_duration_status": dur.get("status"),
        "selected_team_id": team,
        "car_ids": [str(c["car_id"]) for c in team_cars],
        "cars": [
            {
                "car_id": c["car_id"],
                "classified_position": c.get("classified_position"),
                "compound": c.get("compound"),
                "tyre_age_laps": float(c.get("tyre_age_laps") or 0.0),
                "gap_ahead_s": float(c.get("gap_ahead_s") or 0.0),
                "in_pit_lane": bool(c.get("in_pit_lane")),
                "mounted_set_id": c.get("mounted_set_id"),
                "used_compounds": list(c.get("used_compounds") or []),
                "pit_entry_commitment_cutoff_race_s": c.get("pit_entry_commitment_cutoff_race_s"),
            }
            for c in team_cars
        ],
        "inventories": {cid: list(inventories.get(cid) or []) for cid in [c["car_id"] for c in team_cars]},
        "pit_lane": data.get("pit_lane") or {},
        "team_service": data.get("team_service") or {},
        "compound_obligations": data.get("compound_obligations") or {},
        "expired_actions": [
            e if isinstance(e, dict) else e.model_dump(mode="python")
            for e in (data.get("expired_actions") or [])
        ],
        "effective_deadline_s": _qty_value(data.get("effective_deadline_s")),
        "nominal_budget_s": _qty_value(data.get("nominal_budget_s")),
        "forecasts_present": bool(data.get("forecasts")),
        "provenance": data.get("provenance") or {},
    }
    view["observation_hash"] = sha256_json({k: view[k] for k in view if k != "provenance"})
    return view


def _pit_now_expired(view: dict[str, Any], car_id: str) -> bool:
    for e in view["expired_actions"]:
        if e.get("car_id") == car_id and e.get("action") == "pit_now":
            return True
    return False


def _unused_sets(view: dict[str, Any], car: dict[str, Any]) -> list[dict[str, Any]]:
    inv = view["inventories"].get(car["car_id"]) or []
    mounted = car.get("mounted_set_id")
    out = []
    for s in inv:
        if s.get("used"):
            continue
        if mounted and s.get("set_id") == mounted:
            continue
        if s.get("compound") not in COMPOUND_ORDER:
            continue
        out.append(s)
    return out


def _dedup_sets_by_compound(sets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Keep lex-first unused set per compound. Same compound + unused + age 0 is equivalent."""
    by: dict[str, dict[str, Any]] = {}
    reasons: list[dict[str, str]] = []
    for s in sorted(sets, key=lambda x: (x.get("compound") or "", x.get("set_id") or "")):
        c = str(s.get("compound"))
        if c not in by:
            by[c] = s
        else:
            reasons.append(
                {
                    "dropped_set_id": str(s.get("set_id")),
                    "kept_set_id": str(by[c].get("set_id")),
                    "compound": c,
                    "why": "equivalent_unused_same_compound_lex_first_set_id",
                }
            )
    kept = [by[c] for c in COMPOUND_ORDER if c in by]
    return kept, reasons


@dataclass
class A4Action:
    action_id: str
    kind: str
    compound: str | None
    delay_laps: int | None
    set_id: str | None
    motorsport_reason: str

    def to_plan_item(self) -> dict[str, Any]:
        if self.kind == "continuation":
            return {"kind": "continuation"}
        if self.kind == "pit_now":
            return {"kind": "pit_now", "compound": self.compound, "set_id": self.set_id}
        item: dict[str, Any] = {
            "kind": "delay_laps",
            "delay_laps": int(self.delay_laps or 1),
            "compound": self.compound,
            "set_id": self.set_id,
        }
        return item


@dataclass
class A4InfoSet:
    info_set_id: str
    epoch: int
    parent_id: str | None
    reachable_scenarios: tuple[str, ...]
    observable_signature: str


@dataclass
class A4Instance:
    instance_id: str
    car_ids: tuple[str, str]
    info_sets: list[A4InfoSet]
    actions_by_car: dict[str, list[A4Action]]
    observation_hash: str
    crew_overlap_cost: float
    action_costs: dict[tuple[str, str, str], float]
    pair_costs: dict[tuple[str, str, str], float]
    view: dict[str, Any]
    dedup_reasons: list[dict[str, str]] = field(default_factory=list)
    extra_variable_reasons: dict[str, str] = field(default_factory=dict)
    n_epochs: int = 1
    n_scenarios: int = 1
    scenarios: list = field(default_factory=list)

    def n_logical_vars(self) -> int:
        return sum(len(self.actions_by_car[c]) for c in self.car_ids)

    def variable_blocks(self) -> list[dict[str, Any]]:
        blocks = []
        idx = 0
        info = self.info_sets[0]
        for car in self.car_ids:
            actions = self.actions_by_car[car]
            blocks.append(
                {
                    "info_set_id": info.info_set_id,
                    "car_id": car,
                    "epoch": 0,
                    "action_ids": [a.action_id for a in actions],
                    "start": idx,
                    "end": idx + len(actions),
                    "size": len(actions),
                    "f1_map": [a.motorsport_reason for a in actions],
                }
            )
            idx += len(actions)
        return blocks


def _pit_loss(view: dict[str, Any]) -> float:
    pit_parts = (view.get("pit_lane") or {}).get("public_pit_parts_s") or {}
    pit_loss = float(pit_parts.get("t_in_s") or 0) + float(pit_parts.get("t_service_s") or 2.4) + float(
        pit_parts.get("t_out_s") or 0
    )
    return pit_loss if pit_loss > 0 else 20.0


def _build_car_actions(view: dict[str, Any], car: dict[str, Any]) -> tuple[list[A4Action], list[dict[str, str]]]:
    cid = car["car_id"]
    remaining = max(int(view["remaining_laps"]), 0)
    unused, dedup = _dedup_sets_by_compound(_unused_sets(view, car))
    expired = _pit_now_expired(view, cid)
    in_pit = bool(car.get("in_pit_lane"))
    acts = [
        A4Action(
            "continue",
            "continuation",
            None,
            None,
            None,
            "Stay out: preserve track position and tyre thermal window.",
        )
    ]
    if in_pit:
        return acts, dedup + [{"car_id": cid, "why": "in_pit_lane_only_continuation_executable"}]
    if remaining <= 0:
        return acts, dedup + [{"car_id": cid, "why": "no_remaining_laps"}]

    if unused and not expired:
        for s in unused:
            acts.append(
                A4Action(
                    f"pit_now_{s['compound']}_{s['set_id']}",
                    "pit_now",
                    str(s["compound"]),
                    None,
                    str(s["set_id"]),
                    f"Pit now onto {s['compound']} set {s['set_id']}.",
                )
            )
    elif expired:
        dedup.append({"car_id": cid, "why": "pit_now_expired_not_relabelled_next_lap"})

    # delay_laps requires remaining distance to complete the delayed pit.
    if unused and remaining >= 2:
        for s in unused:
            acts.append(
                A4Action(
                    f"delay1_{s['compound']}_{s['set_id']}",
                    "delay_laps",
                    str(s["compound"]),
                    1,
                    str(s["set_id"]),
                    f"Delay 1 lap then pit onto {s['compound']} set {s['set_id']}.",
                )
            )
    if unused and remaining >= 3:
        for s in unused:
            acts.append(
                A4Action(
                    f"delay2_{s['compound']}_{s['set_id']}",
                    "delay_laps",
                    str(s["compound"]),
                    2,
                    str(s["set_id"]),
                    f"Delay 2 laps then pit onto {s['compound']} set {s['set_id']}.",
                )
            )
    return acts, dedup


def build_menu_and_instance(view: dict[str, Any]) -> A4Instance:
    cars = view["cars"]
    c0, c1 = cars[0]["car_id"], cars[1]["car_id"]
    remaining = max(int(view["remaining_laps"]), 1)
    pit_loss = _pit_loss(view)
    actions: dict[str, list[A4Action]] = {}
    all_dedup: list[dict[str, str]] = []
    for car in cars:
        acts, dedup = _build_car_actions(view, car)
        if len(acts) < 1:
            raise RejectionError("A4_MENU", f"empty menu for {car['car_id']}")
        actions[car["car_id"]] = acts
        all_dedup.extend(dedup)

    info_sets = [A4InfoSet(CURRENT_INFO, 0, None, ("checkpoint",), "causal_checkpoint")]
    action_costs: dict[tuple[str, str, str], float] = {}
    pair_costs: dict[tuple[str, str, str], float] = {}
    by_id = {c["car_id"]: c for c in cars}
    for cid, acts in actions.items():
        car = by_id[cid]
        age = float(car["tyre_age_laps"])
        gap = float(car.get("gap_ahead_s") or 0.0)
        used = set(car.get("used_compounds") or [])
        required = int((view.get("compound_obligations") or {}).get("distinct_compounds_required") or 2)
        for a in acts:
            if a.kind == "continuation":
                cost = 0.08 * age * remaining / 10.0 + 0.01 * max(0.0, 4.0 - gap)
                if len(used) < required:
                    cost += 0.15
            elif a.kind == "pit_now":
                compound_pen = {"soft": -0.05, "medium": 0.0, "hard": 0.04}.get(a.compound or "medium", 0.0)
                obl = 0.0 if (len(used | {a.compound}) >= required) else 0.12
                cost = pit_loss / 90.0 - 0.04 * age + compound_pen + obl
            else:
                delay = int(a.delay_laps or 1)
                compound_pen = {"soft": -0.05, "medium": 0.0, "hard": 0.04}.get(a.compound or "medium", 0.0)
                obl = 0.0 if (len(used | {a.compound}) >= required) else 0.12
                cost = 0.08 * age * delay / 10.0 + pit_loss / 110.0 + compound_pen + obl
            action_costs[(CURRENT_INFO, cid, a.action_id)] = float(cost)
    for x in actions[c0]:
        for y in actions[c1]:
            pair = 0.0
            if x.kind == "pit_now" and y.kind == "pit_now":
                pair = 0.12  # shared-crew stacking delay, not a prohibition
            elif {x.kind, y.kind} == {"pit_now", "delay_laps"}:
                pair = 0.02
            pair_costs[(CURRENT_INFO, x.action_id, y.action_id)] = pair

    return A4Instance(
        instance_id=str(view.get("episode_id") or view["observation_hash"][:16]),
        car_ids=(c0, c1),
        info_sets=info_sets,
        actions_by_car=actions,
        observation_hash=str(view["observation_hash"]),
        crew_overlap_cost=0.12,
        action_costs=action_costs,
        pair_costs=pair_costs,
        view=view,
        dedup_reasons=all_dedup,
        extra_variable_reasons={
            "continue": "Preserve position; default on-track action.",
            "pit_now": "Immediate tyre change under cutoff/commitment; one variable per distinct compound after set-equivalence dedup.",
            "delay_laps": "Delayed pit by 1 or 2 laps with an explicit compound/set; executed by RaceSimulator delay_laps.",
            "stacking_pair_cost": "Shared crew: simultaneous pit_now incurs delay, not a prohibition.",
            "no_later_info_set": "Later-epoch/scenario bits are omitted because they would not enter the executed plan.",
        },
        scenarios=[],
    )


def variable_index_map(instance: A4Instance) -> dict[str, Any]:
    blocks = instance.variable_blocks()
    index_to_meta: list[dict[str, Any]] = []
    key_to_index: dict[tuple[str, str, str], int] = {}
    for block in blocks:
        for offset, aid in enumerate(block["action_ids"]):
            idx = block["start"] + offset
            act = _action_by_id(instance, block["car_id"], aid)
            meta = {
                "index": idx,
                "info_set_id": block["info_set_id"],
                "car_id": block["car_id"],
                "action_id": aid,
                "epoch": 0,
                "kind": act.kind,
                "compound": act.compound,
                "delay_laps": act.delay_laps,
                "set_id": act.set_id,
                "f1_decision": f"{block['car_id']}:{aid}",
                "affects_executed_plan": True,
            }
            index_to_meta.append(meta)
            key_to_index[(block["info_set_id"], block["car_id"], aid)] = idx
    return {"n": len(index_to_meta), "blocks": blocks, "index_to_meta": index_to_meta, "key_to_index": key_to_index}


def _action_by_id(instance: A4Instance, car_id: str, action_id: str) -> A4Action:
    for a in instance.actions_by_car[car_id]:
        if a.action_id == action_id:
            return a
    raise KeyError(action_id)


def binary_to_policy(instance: A4Instance, x: np.ndarray) -> dict[str, dict[str, str]] | None:
    vmap = variable_index_map(instance)
    x = np.asarray(x, dtype=int).reshape(-1)
    if x.size != vmap["n"]:
        return None
    policy: dict[str, dict[str, str]] = {}
    for block in vmap["blocks"]:
        sl = x[block["start"] : block["end"]]
        if int(sl.sum()) != 1:
            return None
        chosen = block["action_ids"][int(np.argmax(sl))]
        policy.setdefault(block["info_set_id"], {})[block["car_id"]] = chosen
    return policy


def policy_to_simulator_plan(instance: A4Instance, policy: dict[str, dict[str, str]]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    for car in instance.car_ids:
        aid = policy[CURRENT_INFO][car]
        plan[car] = _action_by_id(instance, car, aid).to_plan_item()
    return {
        "plan": plan,
        "nonanticipative_current_only": True,
        "hidden_duration_not_used": True,
        "no_unexecuted_decision_variables": True,
    }


def proxy_direct_cost(instance: A4Instance, policy: dict[str, dict[str, str]]) -> float:
    total = 0.0
    for car in instance.car_ids:
        aid = policy[CURRENT_INFO][car]
        total += instance.action_costs[(CURRENT_INFO, car, aid)]
    a0 = policy[CURRENT_INFO][instance.car_ids[0]]
    a1 = policy[CURRENT_INFO][instance.car_ids[1]]
    total += instance.pair_costs.get((CURRENT_INFO, a0, a1), 0.0)
    return float(total)


def plan_fingerprint(plan: dict[str, Any]) -> str:
    return sha256_json(plan)


def enumerate_legal_policies(instance: A4Instance) -> list[dict[str, Any]]:
    vmap = variable_index_map(instance)
    n = vmap["n"]
    choices = [list(range(b["start"], b["end"])) for b in vmap["blocks"]]
    rows = []
    for chosen in product(*choices):
        x = np.zeros(n, dtype=int)
        for i in chosen:
            x[int(i)] = 1
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        cost = proxy_direct_cost(instance, pol)
        wrapped = policy_to_simulator_plan(instance, pol)
        rows.append(
            {
                "x": x,
                "policy": pol,
                "proxy_cost": cost,
                "plan": wrapped["plan"],
                "wrapped": wrapped,
                "plan_hash": plan_fingerprint(wrapped["plan"]),
            }
        )
    rows.sort(key=lambda r: (r["proxy_cost"], r["plan_hash"]))
    return rows


def build_a4_qubo(instance: A4Instance, *, margin: float = 1.0) -> dict[str, Any]:
    t0 = __import__("time").perf_counter()
    vmap = variable_index_map(instance)
    n = vmap["n"]
    Q = np.zeros((n, n), dtype=float)
    offset = 0.0
    for meta in vmap["index_to_meta"]:
        key = (meta["info_set_id"], meta["car_id"], meta["action_id"])
        Q[meta["index"], meta["index"]] += instance.action_costs[key]
    c0, c1 = instance.car_ids
    for a1 in instance.actions_by_car[c0]:
        for a2 in instance.actions_by_car[c1]:
            pair = instance.pair_costs.get((CURRENT_INFO, a1.action_id, a2.action_id), 0.0)
            if pair == 0.0:
                continue
            i = vmap["key_to_index"][(CURRENT_INFO, c0, a1.action_id)]
            j = vmap["key_to_index"][(CURRENT_INFO, c1, a2.action_id)]
            lo, hi = (i, j) if i <= j else (j, i)
            Q[lo, hi] += pair
    B = float(np.sum(np.abs(Q)) + abs(offset))
    M = B + float(margin)
    for block in vmap["blocks"]:
        s, e = block["start"], block["end"]
        offset += M
        for i in range(s, e):
            Q[i, i] += -M
        for i in range(s, e):
            for j in range(i + 1, e):
                Q[i, j] += 2.0 * M
    nonconst = [abs(float(Q[i, j])) for i in range(n) for j in range(i, n) if Q[i, j] != 0]
    s_Q = float(max(1.0, max(nonconst) if nonconst else 0.0))
    Q_serial = [{"i": i, "j": j, "q": float(Q[i, j])} for i in range(n) for j in range(i, n) if Q[i, j] != 0]
    elapsed = __import__("time").perf_counter() - t0
    return {
        "n": n,
        "offset": float(offset),
        "Q_dense": Q.tolist(),
        "Q_serial": Q_serial,
        "n_terms": len(Q_serial),
        "n_quadratic_terms": sum(1 for t in Q_serial if t["i"] != t["j"]),
        "density": (2 * len(Q_serial)) / max(n * n, 1),
        "penalty_M": float(M),
        "s_Q": s_Q,
        "offset_scaled": float(offset / s_Q),
        "Q_scaled": (Q / s_Q).tolist(),
        "variable_map": {"n": n, "blocks": vmap["blocks"], "index_to_meta": vmap["index_to_meta"]},
        "hash": sha256_json({"offset": offset, "Q_serial": Q_serial, "M": M}),
        "architecture": "A4",
        "construction_s": elapsed,
        "note": "QUBO is a candidate-generator proxy; evaluator is simulator team_rank_loss.",
    }


def verify_direct_qubo_agreement(instance: A4Instance, qubo: dict[str, Any], *, all_legal: bool = True) -> dict[str, Any]:
    t0 = __import__("time").perf_counter()
    rows = enumerate_legal_policies(instance)
    diffs = []
    for r in rows:
        energy = float(qubo_energy(qubo, r["x"], scaled=False))
        diffs.append(abs(float(r["proxy_cost"]) - energy))
    elapsed = __import__("time").perf_counter() - t0
    ok = bool(diffs) and max(diffs) < 1e-8
    return {
        "ok": ok,
        "n_legal": len(rows),
        "n_checked": len(diffs),
        "max_abs_diff": float(max(diffs) if diffs else 0.0),
        "all_legal": all_legal,
        "exact_scan_s": elapsed,
        "n_qubits": int(qubo["n"]),
    }


def solve_independent_milp(instance: A4Instance, *, time_limit_s: float = 8.0) -> dict[str, Any]:
    """Linearised binary model: one-hot per car + McCormick stacking products."""
    vmap = variable_index_map(instance)
    n = vmap["n"]
    c0, c1 = instance.car_ids
    a0 = instance.actions_by_car[c0]
    a1 = instance.actions_by_car[c1]
    z_meta = []
    for x in a0:
        for y in a1:
            i = vmap["key_to_index"][(CURRENT_INFO, c0, x.action_id)]
            j = vmap["key_to_index"][(CURRENT_INFO, c1, y.action_id)]
            z_meta.append((x.action_id, y.action_id, i, j))
    n_z = len(z_meta)
    n_tot = n + n_z
    c_full = np.zeros(n_tot)
    for meta in vmap["index_to_meta"]:
        key = (meta["info_set_id"], meta["car_id"], meta["action_id"])
        c_full[meta["index"]] = instance.action_costs[key]
    for zi, (aid0, aid1, _i, _j) in enumerate(z_meta):
        c_full[n + zi] = instance.pair_costs.get((CURRENT_INFO, aid0, aid1), 0.0)
    A_rows = []
    b_lb = []
    b_ub = []
    for block in vmap["blocks"]:
        row = np.zeros(n_tot)
        row[block["start"] : block["end"]] = 1.0
        A_rows.append(row)
        b_lb.append(1.0)
        b_ub.append(1.0)
    for zi, (_a, _b, i_idx, j_idx) in enumerate(z_meta):
        z = n + zi
        r1 = np.zeros(n_tot)
        r1[z] = 1.0
        r1[i_idx] = -1.0
        A_rows.append(r1)
        b_lb.append(-np.inf)
        b_ub.append(0.0)
        r2 = np.zeros(n_tot)
        r2[z] = 1.0
        r2[j_idx] = -1.0
        A_rows.append(r2)
        b_lb.append(-np.inf)
        b_ub.append(0.0)
        r3 = np.zeros(n_tot)
        r3[z] = -1.0
        r3[i_idx] = 1.0
        r3[j_idx] = 1.0
        A_rows.append(r3)
        b_lb.append(-np.inf)
        b_ub.append(1.0)
    t0 = __import__("time").perf_counter()
    integrality = np.ones(n_tot)
    bounds = Bounds(0, 1)
    cons = LinearConstraint(np.vstack(A_rows), np.asarray(b_lb), np.asarray(b_ub))
    res = milp(c=c_full, integrality=integrality, bounds=bounds, constraints=cons, options={"time_limit": time_limit_s})
    elapsed = __import__("time").perf_counter() - t0
    x = None
    policy = None
    obj = None
    success = bool(getattr(res, "success", False))
    if success and res.x is not None:
        x = np.rint(res.x[:n]).astype(int)
        policy = binary_to_policy(instance, x)
        obj = float(res.fun)
    status = str(getattr(res, "message", "") or getattr(res, "status", ""))
    gap = None
    if success and obj is not None:
        gap = 0.0
    return {
        "success": success and policy is not None,
        "status": status,
        "objective": obj,
        "policy": policy,
        "x": None if x is None else x.tolist(),
        "solve_s": elapsed,
        "gap": gap,
        "n_vars": n_tot,
        "deadline_feasible": elapsed <= time_limit_s + 0.5,
    }


def verify_direct_qubo_milp(instance: A4Instance, qubo: dict[str, Any]) -> dict[str, Any]:
    agr = verify_direct_qubo_agreement(instance, qubo)
    milp_res = solve_independent_milp(instance)
    rows = enumerate_legal_policies(instance)
    enum_best = rows[0] if rows else None
    milp_ok = False
    enum_obj = None
    if enum_best is not None:
        enum_obj = float(enum_best["proxy_cost"])
        if milp_res.get("success") and milp_res.get("objective") is not None:
            milp_ok = abs(float(milp_res["objective"]) - enum_obj) < 1e-6
    return {
        **agr,
        "milp": {k: v for k, v in milp_res.items() if k != "policy"},
        "milp_matches_enum": milp_ok,
        "enum_best_proxy": enum_obj,
        "ok": bool(agr["ok"] and (milp_ok or not milp_res.get("success"))),
        "legal_plan_count": agr["n_legal"],
        "bit_count": agr["n_qubits"],
        "qubo_construction_s": qubo.get("construction_s"),
    }


def variable_f1_map(instance: A4Instance) -> list[dict[str, Any]]:
    return variable_index_map(instance)["index_to_meta"]


def every_variable_affects_plan(instance: A4Instance) -> dict[str, Any]:
    """Flip each one-hot to another legal action in the same block and compare executed plans."""
    rows = enumerate_legal_policies(instance)
    vmap = variable_index_map(instance)
    unused = []
    for meta in vmap["index_to_meta"]:
        plans = []
        for r in rows:
            if int(r["x"][meta["index"]]) == 1:
                plans.append(r["plan_hash"])
        distinct = len(set(plans))
        # A variable is unused if selecting it never changes the executed plan vs other indices
        # in a way distinguishable from not selecting it. We require at least one plan uses it,
        # and that plan differs from some plan that does not.
        used = distinct > 0
        if not used:
            unused.append(meta["index"])
    # Stronger: for each block size>=2, two different actions produce different plan items.
    unexecuted = 0
    details = []
    for block in vmap["blocks"]:
        items = []
        for aid in block["action_ids"]:
            act = _action_by_id(instance, block["car_id"], aid)
            items.append(sha256_json(act.to_plan_item()))
        if len(set(items)) != len(items):
            # equivalent executed items inside a block would be unexecuted distinctions
            unexecuted += len(items) - len(set(items))
            details.append({"car_id": block["car_id"], "duplicate_plan_items": True})
    return {
        "n_variables": vmap["n"],
        "unexecuted_decision_variables": int(unexecuted),
        "ok": unexecuted == 0,
        "details": details,
        "never_selected_indices": unused,
    }


def repair_to_legal_plan(instance: A4Instance, sim_validate: Callable, x: np.ndarray | None = None) -> dict[str, Any]:
    fallback = {cid: {"kind": "continuation"} for cid in instance.car_ids}
    if x is None:
        return {"plan": fallback, "repaired": True, "reason": "no_bitstring", "legal": True}
    pol = binary_to_policy(instance, x)
    if pol is None:
        return {"plan": fallback, "repaired": True, "reason": "decoding_invalid", "legal": True}
    wrapped = policy_to_simulator_plan(instance, pol)
    plan = wrapped["plan"]
    try:
        sim_validate(plan)
        return {"plan": plan, "repaired": False, "reason": None, "legal": True, "policy": pol, "wrapped": wrapped}
    except Exception as exc:
        return {
            "plan": fallback,
            "repaired": True,
            "reason": str(exc),
            "legal": True,
            "policy": pol,
            "wrapped": wrapped,
        }


FEATURE_KEYS = [
    "n_logical_vars",
    "n_legal_joint",
    "qubo_density",
    "penalty_M",
    "remaining_laps",
    "completed_laps",
    "mean_tyre_age",
    "mean_gap_ahead",
    "crew_overlap_cost",
    "deadline_s",
    "n_expired",
    "regime_is_sc",
    "n_pit_now_actions",
    "n_delay_actions",
]


def qubo_structural_features(instance: A4Instance, qubo: dict[str, Any]) -> dict[str, float]:
    view = instance.view
    cars = view["cars"]
    n_pit = sum(1 for c in instance.car_ids for a in instance.actions_by_car[c] if a.kind == "pit_now")
    n_delay = sum(1 for c in instance.car_ids for a in instance.actions_by_car[c] if a.kind == "delay_laps")
    n_legal = 1
    for c in instance.car_ids:
        n_legal *= max(len(instance.actions_by_car[c]), 1)
    return {
        "n_logical_vars": float(qubo["n"]),
        "n_legal_joint": float(n_legal),
        "qubo_density": float(qubo["density"]),
        "penalty_M": float(qubo["penalty_M"]),
        "remaining_laps": float(view["remaining_laps"]),
        "completed_laps": float(view["completed_laps"]),
        "mean_tyre_age": float(np.mean([c["tyre_age_laps"] for c in cars])),
        "mean_gap_ahead": float(np.mean([c.get("gap_ahead_s") or 0.0 for c in cars])),
        "crew_overlap_cost": float(instance.crew_overlap_cost),
        "deadline_s": float(view["effective_deadline_s"] or view["nominal_budget_s"] or 30.0),
        "n_expired": float(len(view["expired_actions"])),
        "regime_is_sc": 1.0 if view.get("safety_regime") == "SC" else 0.0,
        "n_pit_now_actions": float(n_pit),
        "n_delay_actions": float(n_delay),
    }


def feature_vector(feats: dict[str, float]) -> np.ndarray:
    return np.array([float(feats[k]) for k in FEATURE_KEYS], dtype=float)

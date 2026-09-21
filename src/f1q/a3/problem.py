"""A3 rolling-horizon F1 subproblem: causal observation → menu → QUBO → decode.

This is a pre-final-test protocol amendment architecture. A2 models/evidence
are not transferable confirmations of A3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from f1q.causal import DecisionObservation
from f1q.errors import RejectionError
from f1q.hashing import sha256_json
from f1q.stage5.qubo import qubo_energy

A3_VERSION = "0.7.0"
CURRENT_INFO = "a3.root"
LATER_INFO = "a3.later_observable"
FORECAST_SHORT = "forecast_short"
FORECAST_LONG = "forecast_long"

# Predeclared forecast masses (solver-visible; NOT realized hidden duration).
DEFAULT_FORECAST = {FORECAST_SHORT: 0.45, FORECAST_LONG: 0.55}

FORBIDDEN_OBS_TOKENS = (
    "sampled_future",
    "fuel_actual",
    "regime_end_s",
    "engine_state",
    "realized_duration",
    "hidden_duration",
)


def _qty_value(q: Any) -> Any:
    if q is None:
        return None
    if isinstance(q, dict):
        return q.get("value")
    return getattr(q, "value", None)


def extract_causal_view(obs: DecisionObservation) -> dict[str, Any]:
    """Project DecisionObservation to solver-visible fields only."""
    data = obs.model_dump(mode="python")
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
        "inventories": {cid: data.get("inventories", {}).get(cid, []) for cid in [c["car_id"] for c in team_cars]},
        "pit_lane": data.get("pit_lane") or {},
        "team_service": data.get("team_service") or {},
        "expired_actions": [
            e if isinstance(e, dict) else e.model_dump(mode="python")
            for e in (data.get("expired_actions") or [])
        ],
        "effective_deadline_s": _qty_value(data.get("effective_deadline_s")),
        "nominal_budget_s": _qty_value(data.get("nominal_budget_s")),
        "forecasts_present": bool(data.get("forecasts")),
        "provenance": data.get("provenance") or {},
    }
    view["observation_hash"] = sha256_json(
        {k: view[k] for k in view if k not in {"provenance"}}
    )
    return view


def _unused_sets(view: dict[str, Any], car_id: str, mounted: str | None) -> list[dict[str, Any]]:
    inv = view["inventories"].get(car_id) or []
    out = []
    for s in inv:
        if s.get("used"):
            continue
        if mounted and s.get("set_id") == mounted:
            continue
        out.append(s)
    return out


def _pit_now_expired(view: dict[str, Any], car_id: str) -> bool:
    for e in view["expired_actions"]:
        if e.get("car_id") == car_id and e.get("action") == "pit_now":
            return True
    return False


def _preferred_set(sets: list[dict[str, Any]]) -> dict[str, Any] | None:
    med = [s for s in sets if s.get("compound") == "medium"]
    if med:
        return med[0]
    return sets[0] if sets else None


@dataclass
class A3Action:
    action_id: str
    kind: str
    compound: str | None
    delay_laps: int | None
    set_id: str | None
    motorsport_reason: str


@dataclass
class A3InfoSet:
    info_set_id: str
    epoch: int
    parent_id: str | None
    reachable_scenarios: tuple[str, ...]
    observable_signature: str


@dataclass
class A3Scenario:
    scenario_id: str
    probability: float


@dataclass
class A3Instance:
    """Duck-typed for C0/C1 reuse (variable_blocks / n_logical_vars)."""

    instance_id: str
    car_ids: tuple[str, str]
    info_sets: list[A3InfoSet]
    actions_by_car: dict[str, list[A3Action]]
    n_epochs: int
    n_scenarios: int
    scenarios: list[A3Scenario]
    observation_hash: str
    crew_overlap_cost: float
    action_costs: dict[tuple[str, str, str], float]
    pair_costs: dict[tuple[str, str, str], float]
    scenario_leaf_costs: dict[str, float]
    view: dict[str, Any]
    extra_variable_reasons: dict[str, str] = field(default_factory=dict)

    def n_logical_vars(self) -> int:
        n = 0
        for _info in self.info_sets:
            for car in self.car_ids:
                n += len(self.actions_by_car[car])
        return n

    def variable_blocks(self) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        idx = 0
        for info in self.info_sets:
            for car in self.car_ids:
                actions = self.actions_by_car[car]
                blocks.append(
                    {
                        "info_set_id": info.info_set_id,
                        "car_id": car,
                        "epoch": info.epoch,
                        "action_ids": [a.action_id for a in actions],
                        "start": idx,
                        "end": idx + len(actions),
                        "size": len(actions),
                    }
                )
                idx += len(actions)
        return blocks


def build_menu_and_instance(view: dict[str, Any], *, forecast: dict[str, float] | None = None) -> A3Instance:
    """Bounded two-car rolling-horizon menu. Every extra variable has an F1 reason."""
    cars = view["cars"]
    if len(cars) < 2:
        raise RejectionError("A3_MENU", "two selected cars required")
    c0, c1 = cars[0]["car_id"], cars[1]["car_id"]
    remaining = max(int(view["remaining_laps"]), 1)
    pit_parts = (view.get("pit_lane") or {}).get("public_pit_parts_s") or {}
    pit_loss = float(pit_parts.get("t_in_s") or 0) + float(pit_parts.get("t_service_s") or 2.4) + float(
        pit_parts.get("t_out_s") or 0
    )
    if pit_loss <= 0:
        pit_loss = 20.0

    actions: dict[str, list[A3Action]] = {}
    for car in cars:
        cid = car["car_id"]
        unused = _unused_sets(view, cid, car.get("mounted_set_id"))
        pref = _preferred_set(unused)
        acts = [
            A3Action(
                "continue",
                "continuation",
                None,
                None,
                None,
                "Stay out: preserve track position and tyre thermal window.",
            )
        ]
        expired = _pit_now_expired(view, cid) or bool(car.get("in_pit_lane"))
        if pref is not None and not expired:
            acts.append(
                A3Action(
                    f"pit_now_{pref['compound']}",
                    "pit_now",
                    str(pref["compound"]),
                    None,
                    str(pref["set_id"]),
                    "Pit now: undercut/overcut and compound obligation; missed if cutoff expired.",
                )
            )
        else:
            # Keep a two-action block so C1 mixers have size≥2; second action is delay if legal.
            acts.append(
                A3Action(
                    "delay_1_same",
                    "delay_laps",
                    str(car.get("compound") or "medium"),
                    1,
                    pref["set_id"] if pref else None,
                    "Bounded one-lap offset: wait for a later pit window (traffic/crew).",
                )
            )
        if len(acts) == 2 and pref is not None and not expired:
            # Optional delay alternative only when pit_now exists — still 2 actions (continue vs pit).
            pass
        actions[cid] = acts[:2]

    # Two info sets: current (nonanticipative) + later observable continuation.
    # Later is keyed by a future *observable* (still out), not hidden duration.
    info_sets = [
        A3InfoSet(CURRENT_INFO, 0, None, (FORECAST_SHORT, FORECAST_LONG), "causal_checkpoint"),
        A3InfoSet(LATER_INFO, 1, CURRENT_INFO, (FORECAST_SHORT, FORECAST_LONG), "later_still_out_observable"),
    ]
    fc = forecast or DEFAULT_FORECAST
    scenarios = [
        A3Scenario(FORECAST_SHORT, float(fc[FORECAST_SHORT])),
        A3Scenario(FORECAST_LONG, float(fc[FORECAST_LONG])),
    ]

    action_costs: dict[tuple[str, str, str], float] = {}
    pair_costs: dict[tuple[str, str, str], float] = {}
    by_id = {c["car_id"]: c for c in cars}
    for info in info_sets:
        epoch_scale = 1.0 if info.epoch == 0 else 0.35
        for cid, acts in actions.items():
            car = by_id[cid]
            age = float(car["tyre_age_laps"])
            gap = float(car.get("gap_ahead_s") or 0.0)
            for a in acts:
                if a.kind == "continuation":
                    cost = epoch_scale * (0.08 * age * remaining / 10.0 + 0.01 * max(0.0, 4.0 - gap))
                elif a.kind == "pit_now":
                    compound_pen = {"soft": -0.05, "medium": 0.0, "hard": 0.04}.get(a.compound or "medium", 0.0)
                    cost = epoch_scale * (pit_loss / 90.0 - 0.04 * age + compound_pen)
                else:
                    cost = epoch_scale * (0.08 * age * remaining / 10.0 + 0.02)
                action_costs[(info.info_set_id, cid, a.action_id)] = float(cost)
        a0 = actions[c0]
        a1 = actions[c1]
        for x in a0:
            for y in a1:
                pair = 0.0
                if x.kind == "pit_now" and y.kind == "pit_now" and info.epoch == 0:
                    pair = 0.12  # shared-crew stacking delay (F1 two-car pit conflict)
                pair_costs[(info.info_set_id, x.action_id, y.action_id)] = pair

    inst = A3Instance(
        instance_id=str(view.get("episode_id") or view["observation_hash"][:16]),
        car_ids=(c0, c1),
        info_sets=info_sets,
        actions_by_car=actions,
        n_epochs=2,
        n_scenarios=2,
        scenarios=scenarios,
        observation_hash=str(view["observation_hash"]),
        crew_overlap_cost=0.12,
        action_costs=action_costs,
        pair_costs=pair_costs,
        scenario_leaf_costs={FORECAST_SHORT: 0.0, FORECAST_LONG: 0.0},
        view=view,
        extra_variable_reasons={
            "continue": "Preserve position; default on-track action.",
            "pit_now": "Immediate tyre change under cutoff/commitment.",
            "later_info_set": "Scenario-contingent completion if still out; not hidden duration.",
            "stacking_pair_cost": "Shared crew: simultaneous pit_now incurs delay, not a prohibition.",
            "not_enlarged_to_break_enumeration": True,
        },
    )
    return inst


def variable_index_map(instance: A3Instance) -> dict[str, Any]:
    blocks = instance.variable_blocks()
    index_to_meta: list[dict[str, Any]] = []
    key_to_index: dict[tuple[str, str, str], int] = {}
    for block in blocks:
        for offset, aid in enumerate(block["action_ids"]):
            idx = block["start"] + offset
            meta = {
                "index": idx,
                "info_set_id": block["info_set_id"],
                "car_id": block["car_id"],
                "action_id": aid,
                "epoch": block["epoch"],
            }
            index_to_meta.append(meta)
            key_to_index[(block["info_set_id"], block["car_id"], aid)] = idx
    return {"n": len(index_to_meta), "blocks": blocks, "index_to_meta": index_to_meta, "key_to_index": key_to_index}


def binary_to_policy(instance: A3Instance, x: np.ndarray) -> dict[str, dict[str, str]] | None:
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


def proxy_direct_cost(instance: A3Instance, policy: dict[str, dict[str, str]]) -> float:
    total = 0.0
    for sc in instance.scenarios:
        mass = sc.probability
        for info in instance.info_sets:
            if sc.scenario_id not in info.reachable_scenarios:
                continue
            for car in instance.car_ids:
                aid = policy[info.info_set_id][car]
                total += mass * instance.action_costs[(info.info_set_id, car, aid)]
            a0 = policy[info.info_set_id][instance.car_ids[0]]
            a1 = policy[info.info_set_id][instance.car_ids[1]]
            total += mass * instance.pair_costs.get((info.info_set_id, a0, a1), 0.0)
    return float(total)


def build_a3_qubo(instance: A3Instance, *, margin: float = 1.0) -> dict[str, Any]:
    vmap = variable_index_map(instance)
    n = vmap["n"]
    Q = np.zeros((n, n), dtype=float)
    offset = 0.0
    for sc in instance.scenarios:
        offset += sc.probability * instance.scenario_leaf_costs.get(sc.scenario_id, 0.0)
    for meta in vmap["index_to_meta"]:
        key = (meta["info_set_id"], meta["car_id"], meta["action_id"])
        Q[meta["index"], meta["index"]] += instance.action_costs[key]
    c0, c1 = instance.car_ids
    for info in instance.info_sets:
        mass = sum(sc.probability for sc in instance.scenarios if sc.scenario_id in info.reachable_scenarios)
        for a1 in instance.actions_by_car[c0]:
            for a2 in instance.actions_by_car[c1]:
                pair = instance.pair_costs.get((info.info_set_id, a1.action_id, a2.action_id), 0.0)
                if pair == 0.0:
                    continue
                i = vmap["key_to_index"][(info.info_set_id, c0, a1.action_id)]
                j = vmap["key_to_index"][(info.info_set_id, c1, a2.action_id)]
                lo, hi = (i, j) if i <= j else (j, i)
                Q[lo, hi] += mass * pair
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
        "architecture": "A3",
        "note": "QUBO is a candidate-generator proxy; evaluator is simulator team_rank_loss.",
    }


def verify_direct_cost_qubo_agreement(instance: A3Instance, qubo: dict[str, Any], *, n_samples: int = 8) -> dict[str, Any]:
    vmap = variable_index_map(instance)
    n = vmap["n"]
    diffs = []
    rng = np.random.default_rng(0)
    # Enumerate a few legal one-hot assignments.
    from itertools import product

    block_choices = [list(range(b["start"], b["end"])) for b in vmap["blocks"]]
    legal_idx = list(product(*block_choices))
    take = legal_idx[:n_samples] if len(legal_idx) <= n_samples else [legal_idx[i] for i in rng.choice(len(legal_idx), size=n_samples, replace=False)]
    for chosen in take:
        x = np.zeros(n, dtype=int)
        for i in chosen:
            x[int(i)] = 1
        pol = binary_to_policy(instance, x)
        assert pol is not None
        direct = proxy_direct_cost(instance, pol)
        energy = float(qubo_energy(qubo, x, scaled=False))
        diffs.append(abs(direct - energy))
    ok = bool(diffs) and max(diffs) < 1e-8
    return {"ok": ok, "n_checked": len(diffs), "max_abs_diff": float(max(diffs) if diffs else 0.0)}


def _action_by_id(instance: A3Instance, car_id: str, action_id: str) -> A3Action:
    for a in instance.actions_by_car[car_id]:
        if a.action_id == action_id:
            return a
    raise KeyError(action_id)


def policy_to_simulator_plan(instance: A3Instance, policy: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Apply CURRENT-epoch actions only. Later info-set is recorded as completion, not hidden-duration peek."""
    plan: dict[str, Any] = {}
    for car in instance.car_ids:
        aid = policy[CURRENT_INFO][car]
        act = _action_by_id(instance, car, aid)
        if act.kind == "continuation":
            plan[car] = {"kind": "continuation"}
        elif act.kind == "pit_now":
            plan[car] = {"kind": "pit_now", "compound": act.compound, "set_id": act.set_id}
        else:
            item: dict[str, Any] = {"kind": "delay_laps", "delay_laps": int(act.delay_laps or 1)}
            if act.compound and act.set_id:
                item["compound"] = act.compound
                item["set_id"] = act.set_id
            plan[car] = item
    later = {car: policy[LATER_INFO][car] for car in instance.car_ids}
    return {
        "plan": plan,
        "contingent_completion": later,
        "nonanticipative_current_only": True,
        "hidden_duration_not_used": True,
    }


def repair_to_legal_plan(instance: A3Instance, sim_validate, x: np.ndarray | None = None) -> dict[str, Any]:
    """Deterministic full-policy completion/repair: fallback continue both cars if illegal."""
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


def qubo_structural_features(instance: A3Instance, qubo: dict[str, Any]) -> dict[str, float]:
    view = instance.view
    cars = view["cars"]
    feats = {
        "n_logical_vars": float(qubo["n"]),
        "n_info_sets": float(len(instance.info_sets)),
        "n_scenarios": float(instance.n_scenarios),
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
    }
    return feats


FEATURE_KEYS = [
    "n_logical_vars",
    "n_info_sets",
    "n_scenarios",
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
]


def feature_vector(feats: dict[str, float]) -> np.ndarray:
    return np.array([float(feats[k]) for k in FEATURE_KEYS], dtype=float)

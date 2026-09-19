"""Deterministic two-car legal action dictionaries from solver-visible observations only."""

from __future__ import annotations

from typing import Any, Literal

from f1q.errors import SchemaError
from f1q.formulation.boundaries import SpyMapping, reject_private_payload
from f1q.formulation.public_config import PublicPhysicsConfig
from f1q.formulation.versions import (
    ACTION_MODEL_VERSION,
    DOWNSTREAM_POLICY_ID,
    DOWNSTREAM_POLICY_VERSION,
)
from f1q.hashing import sha256_json
from f1q.schemas import StrictModel, reject_non_finite

ActionKind = Literal["pit_now", "delay_laps", "continuation"]


class CarAction(StrictModel):
    action_id: str
    car_id: str
    kind: ActionKind
    compound: str | None = None
    set_id: str | None = None
    delay_laps: int | None = None
    downstream_policy_id: str = DOWNSTREAM_POLICY_ID
    downstream_policy_version: str = DOWNSTREAM_POLICY_VERSION
    commitment: dict[str, Any]
    description: str
    observable_admission_facts: dict[str, Any]
    exclusion_reason: str | None = None
    admitted: bool = True


def _qty_value(q: Any) -> Any:
    if isinstance(q, dict) and "value" in q:
        return q["value"]
    return q


def _obs_dict(observation: Any) -> dict[str, Any]:
    if hasattr(observation, "model_dump"):
        data = observation.model_dump(mode="python")
    else:
        data = dict(observation)
    reject_private_payload(data)
    reject_non_finite(data)
    return SpyMapping(data)


def _selected_car_ids(obs: dict[str, Any], public: PublicPhysicsConfig) -> list[str]:
    del public  # physics not needed for selection
    team = obs["selected_team_id"]
    cars = [c for c in obs["cars"] if c.get("team_id") == team]
    # Prefer provenance / ordered team cars as they appear in observation.
    ordered = sorted(cars, key=lambda c: str(c["car_id"]))
    if len(ordered) < 2:
        raise SchemaError("observation must contain exactly two selected-team cars")
    # Development fixtures use two selected cars; take the two team cars with lowest classified_position then id.
    ordered.sort(key=lambda c: (c.get("classified_position") is None, c.get("classified_position") or 999, c["car_id"]))
    return [ordered[0]["car_id"], ordered[1]["car_id"]]


def _car_row(obs: dict[str, Any], car_id: str) -> dict[str, Any]:
    for row in obs["cars"]:
        if row["car_id"] == car_id:
            return row
    raise SchemaError(f"missing car {car_id}")


def _inventory(obs: dict[str, Any], car_id: str) -> list[dict[str, Any]]:
    inv = obs.get("inventories") or {}
    rows = inv.get(car_id)
    if rows is None:
        raise SchemaError(f"missing inventory for {car_id}")
    return list(rows)


def _compounds_used(car: dict[str, Any], inventory: list[dict[str, Any]]) -> set[str]:
    used = {car["compound"]}
    used.update(car.get("used_compounds") or [])
    for item in inventory:
        if item.get("used"):
            used.add(item["compound"])
    return set(used)


def _obligation_feasible_after(
    *,
    car: dict[str, Any],
    inventory: list[dict[str, Any]],
    after_compound: str | None,
    remaining_laps: float,
    required: int,
    delay: int = 0,
) -> bool:
    used = _compounds_used(car, inventory)
    if after_compound is not None:
        used = set(used)
        used.add(after_compound)
    if len(used) >= required:
        return True
    # Remaining unused sets after consuming the planned mount.
    unused = [s for s in inventory if not s.get("used") and s.get("set_id") != car.get("mounted_set_id")]
    if after_compound is not None:
        # One set is consumed by the planned stop; remove one matching unused of that compound.
        removed = False
        kept = []
        for s in unused:
            if not removed and s["compound"] == after_compound:
                removed = True
                continue
            kept.append(s)
        unused = kept
    # Downstream policy can schedule one further obligation stop within remaining horizon after delay.
    horizon_after = float(remaining_laps) - float(delay)
    if horizon_after < 1.0 - 1e-12:
        return False
    for s in unused:
        if s["compound"] not in used:
            return True
    return False


def _candidate_pit_sets(car: dict[str, Any], inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mounted = car.get("mounted_set_id")
    out = []
    for item in inventory:
        if item.get("used"):
            continue
        if item.get("set_id") == mounted:
            continue
        if item.get("compound") not in {"soft", "medium", "hard"}:
            continue
        out.append(item)
    out.sort(key=lambda s: (s["compound"], s["set_id"]))
    return out


def _missed_pit_entry(car: dict[str, Any], obs: dict[str, Any]) -> bool:
    for exp in obs.get("expired_actions") or []:
        if exp.get("car_id") == car["car_id"] and exp.get("action") == "pit_now":
            return True
    # Observable frac past pit entry without being in pit: use service_state / frac when available.
    if car.get("in_pit_lane"):
        return False
    frac = car.get("frac")
    # Pit entry is configured at 0.95 in public track geometry; frac past entry and still on track.
    if frac is not None and float(frac) >= 0.95 - 1e-12:
        return True
    return False


def generate_car_actions(
    observation: Any,
    public: PublicPhysicsConfig,
    *,
    car_id: str,
    include_rejected: bool = True,
) -> list[CarAction]:
    obs = _obs_dict(observation)
    car = _car_row(obs, car_id)
    inventory = _inventory(obs, car_id)
    remaining = float(_qty_value(obs["remaining_laps"]))
    required = int(public.distinct_compounds_required)
    actions: list[CarAction] = []
    rejected: list[CarAction] = []

    def admit(action: CarAction) -> None:
        actions.append(action)

    def reject(action: CarAction, reason: str) -> None:
        action.admitted = False
        action.exclusion_reason = reason
        if include_rejected:
            rejected.append(action)

    # Finished / in-pit cars: only continuation if already done, otherwise reject pits.
    finished = car.get("classified_position") is not None and remaining <= 0
    in_pit = bool(car.get("in_pit_lane"))

    # continuation
    cont_id = f"{car_id}|continuation|{DOWNSTREAM_POLICY_ID}@{DOWNSTREAM_POLICY_VERSION}"
    cont_ok = _obligation_feasible_after(
        car=car,
        inventory=inventory,
        after_compound=None,
        remaining_laps=remaining,
        required=required,
        delay=0,
    )
    # Same-compound continuation is legal only if obligation already met OR downstream can still stop.
    cont = CarAction(
        action_id=cont_id,
        car_id=car_id,
        kind="continuation",
        commitment={"expires": "decision_window", "kind": "soft_continuation"},
        description=f"{car_id} continuation under {DOWNSTREAM_POLICY_ID}",
        observable_admission_facts={
            "compound": car["compound"],
            "tyre_age_laps": car["tyre_age_laps"],
            "remaining_laps": remaining,
            "used_compounds": sorted(_compounds_used(car, inventory)),
            "obligation_required": required,
            "in_pit_lane": in_pit,
        },
    )
    if finished:
        reject(cont, "car_finished")
    elif in_pit:
        # Already in pit service: continuation is the only legal external plan (no new pit instruction).
        admit(cont)
    elif not cont_ok:
        reject(cont, "downstream_obligation_infeasible")
    else:
        admit(cont)

    missed = _missed_pit_entry(car, obs)
    for item in _candidate_pit_sets(car, inventory):
        compound = item["compound"]
        set_id = item["set_id"]
        # pit_now
        pit_id = f"{car_id}|pit_now|{compound}|{set_id}"
        pit = CarAction(
            action_id=pit_id,
            car_id=car_id,
            kind="pit_now",
            compound=compound,
            set_id=set_id,
            commitment={"expires": "pit_entry_this_lap", "kind": "hard_entry"},
            description=f"{car_id} pit_now onto {compound} set {set_id}",
            observable_admission_facts={
                "compound": compound,
                "set_id": set_id,
                "set_used": False,
                "mounted_set_id": car.get("mounted_set_id"),
                "missed_pit_entry": missed,
            },
        )
        if in_pit:
            reject(pit, "already_in_pit_lane")
        elif missed:
            reject(pit, "expired_pit_now_missed_entry")
        elif remaining < 1.0 - 1e-12:
            reject(pit, "insufficient_horizon")
        elif not _obligation_feasible_after(
            car=car,
            inventory=inventory,
            after_compound=compound,
            remaining_laps=remaining,
            required=required,
            delay=0,
        ):
            reject(pit, "downstream_obligation_infeasible")
        else:
            admit(pit)

        for delay in (1, 2):
            did = f"{car_id}|delay_laps|{delay}|{compound}|{set_id}"
            delayed = CarAction(
                action_id=did,
                car_id=car_id,
                kind="delay_laps",
                compound=compound,
                set_id=set_id,
                delay_laps=delay,
                commitment={"expires": f"after_{delay}_completed_laps", "kind": "delayed_entry"},
                description=f"{car_id} delay {delay} lap(s) then pit onto {compound} set {set_id}",
                observable_admission_facts={
                    "delay_laps": delay,
                    "compound": compound,
                    "set_id": set_id,
                    "remaining_laps": remaining,
                },
            )
            if in_pit:
                reject(delayed, "already_in_pit_lane")
            elif remaining < float(delay) + 1.0 - 1e-12:
                reject(delayed, "insufficient_horizon_for_delay")
            elif not _obligation_feasible_after(
                car=car,
                inventory=inventory,
                after_compound=compound,
                remaining_laps=remaining,
                required=required,
                delay=delay,
            ):
                reject(delayed, "downstream_obligation_infeasible")
            else:
                admit(delayed)

    actions.sort(key=lambda a: a.action_id)
    rejected.sort(key=lambda a: a.action_id)
    return actions + rejected


def equivalence_key(action: CarAction) -> tuple[Any, ...]:
    """Semantic reduction key independent of objective values."""
    return (action.kind, action.delay_laps, action.compound)


def reduce_action_menu(
    actions: list[CarAction],
    *,
    policy: str = "kind_delay_compound_lex_set",
) -> dict[str, Any]:
    admitted = [a for a in actions if a.admitted]
    if policy != "kind_delay_compound_lex_set":
        raise SchemaError(f"unsupported reduction policy {policy}")
    groups: dict[tuple[Any, ...], list[CarAction]] = {}
    for action in admitted:
        groups.setdefault(equivalence_key(action), []).append(action)
    retained: list[CarAction] = []
    member_map: dict[str, str] = {}
    degeneracy: dict[str, int] = {}
    for key, members in sorted(groups.items(), key=lambda kv: kv[0]):
        members_sorted = sorted(members, key=lambda a: (a.set_id or "", a.action_id))
        rep = members_sorted[0]
        retained.append(rep)
        degeneracy[rep.action_id] = len(members_sorted)
        for m in members_sorted:
            member_map[m.action_id] = rep.action_id
    retained.sort(key=lambda a: a.action_id)
    return {
        "policy": policy,
        "full_count": len(admitted),
        "reduced_count": len(retained),
        "member_to_representative": member_map,
        "degeneracy": degeneracy,
        "retained_action_ids": [a.action_id for a in retained],
        "retained_actions": retained,
    }


def build_joint_plan(action_a: CarAction, action_b: CarAction, selected_car_ids: list[str]) -> dict[str, Any]:
    if len(selected_car_ids) != 2:
        raise SchemaError("joint plan requires exactly two selected cars")
    if {action_a.car_id, action_b.car_id} != set(selected_car_ids):
        raise SchemaError("joint plan must cover exactly both selected cars")
    if action_a.car_id == action_b.car_id:
        raise SchemaError("partial/same-car joint plan rejected")

    def to_sim(action: CarAction) -> dict[str, Any]:
        if action.kind == "continuation":
            return {"kind": "continuation"}
        if action.kind == "pit_now":
            return {"kind": "pit_now", "compound": action.compound, "set_id": action.set_id}
        return {
            "kind": "delay_laps",
            "delay_laps": action.delay_laps,
            "compound": action.compound,
            "set_id": action.set_id,
        }

    return {
        action_a.car_id: to_sim(action_a),
        action_b.car_id: to_sim(action_b),
        "_meta": {
            "complete_joint": True,
            "action_ids": {action_a.car_id: action_a.action_id, action_b.car_id: action_b.action_id},
            "selected_car_ids": list(selected_car_ids),
        },
    }


def simulator_plan_payload(joint: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in joint.items() if not k.startswith("_")}


def generate_action_model(
    observation: Any,
    public: PublicPhysicsConfig,
    *,
    selected_car_ids: list[str] | None = None,
    reduce: bool = True,
) -> dict[str, Any]:
    obs = _obs_dict(observation)
    if selected_car_ids is None:
        # Prefer explicit two-car team ordering from observation cars of selected team.
        selected_car_ids = _selected_car_ids(obs, public)
    if len(selected_car_ids) != 2:
        raise SchemaError("Stage 4 requires exactly two selected_car_ids")
    per_car: dict[str, list[CarAction]] = {}
    excluded: list[dict[str, Any]] = []
    for cid in selected_car_ids:
        all_actions = generate_car_actions(observation, public, car_id=cid, include_rejected=True)
        admitted = [a for a in all_actions if a.admitted]
        per_car[cid] = admitted
        for a in all_actions:
            if not a.admitted:
                excluded.append(
                    {
                        "action_id": a.action_id,
                        "car_id": a.car_id,
                        "reason": a.exclusion_reason,
                    }
                )
    reductions = {}
    menus = {}
    for cid, actions in per_car.items():
        red = reduce_action_menu(actions) if reduce else {
            "policy": "none_full_menu",
            "full_count": len(actions),
            "reduced_count": len(actions),
            "member_to_representative": {a.action_id: a.action_id for a in actions},
            "degeneracy": {a.action_id: 1 for a in actions},
            "retained_action_ids": [a.action_id for a in actions],
            "retained_actions": actions,
        }
        reductions[cid] = {k: v for k, v in red.items() if k != "retained_actions"}
        menus[cid] = [a.model_dump(mode="python") for a in red["retained_actions"]]
    payload = {
        "action_model_version": ACTION_MODEL_VERSION,
        "selected_car_ids": list(selected_car_ids),
        "menus": menus,
        "full_counts": {cid: reductions[cid]["full_count"] for cid in selected_car_ids},
        "reduced_counts": {cid: reductions[cid]["reduced_count"] for cid in selected_car_ids},
        "reduction": reductions,
        "excluded_actions": excluded,
        "observation_hash": sha256_json(dict(obs)),
        "evidence_class": "development",
        "not_experimental": True,
        "not_calibrated_f1": True,
        "not_physical_qpu": True,
    }
    payload["action_dictionary_hash"] = sha256_json(
        {"menus": menus, "selected_car_ids": selected_car_ids, "excluded": excluded}
    )
    return payload

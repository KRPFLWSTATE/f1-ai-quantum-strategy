"""A2 deterministic scenario-tree policy model (non-anticipative by construction)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from f1q.hashing import sha256_json

ACTION_KINDS = ("pit_now", "continue")
COMPOUNDS = ("soft", "medium", "hard")


@dataclass(frozen=True)
class Action:
    action_id: str
    kind: str
    compound: str | None
    set_id: str | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "compound": self.compound,
            "set_id": self.set_id,
            "description": self.description,
        }


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    probability: float
    sc_duration_laps: int
    restart_mode: str  # "rolling" | "standing" | "none"
    observable_at_epoch: tuple[str, ...]  # what becomes visible by epoch index

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "probability": self.probability,
            "sc_duration_laps": self.sc_duration_laps,
            "restart_mode": self.restart_mode,
            "observable_at_epoch": list(self.observable_at_epoch),
        }


@dataclass(frozen=True)
class InfoSet:
    info_set_id: str
    epoch: int
    observable_signature: str
    parent_id: str | None
    reachable_scenarios: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "info_set_id": self.info_set_id,
            "epoch": self.epoch,
            "observable_signature": self.observable_signature,
            "parent_id": self.parent_id,
            "reachable_scenarios": list(self.reachable_scenarios),
        }


@dataclass
class InventoryState:
    soft: int
    medium: int
    hard: int
    compounds_used: frozenset[str]
    required_compounds: int

    def copy(self) -> InventoryState:
        return InventoryState(
            soft=self.soft,
            medium=self.medium,
            hard=self.hard,
            compounds_used=self.compounds_used,
            required_compounds=self.required_compounds,
        )

    def apply(self, action: Action) -> InventoryState | None:
        inv = self.copy()
        if action.kind == "continue":
            return inv
        if action.compound is None:
            return None
        key = action.compound
        stock = getattr(inv, key)
        if stock <= 0:
            return None
        setattr(inv, key, stock - 1)
        inv.compounds_used = frozenset(set(inv.compounds_used) | {key})
        return inv

    def obligation_ok(self, terminal: bool) -> bool:
        if not terminal:
            return True
        return len(self.compounds_used) >= self.required_compounds


@dataclass
class A2Instance:
    instance_id: str
    rung: str
    family_id: str
    n_epochs: int
    scenarios: list[Scenario]
    info_sets: list[InfoSet]
    actions_by_car: dict[str, list[Action]]  # car_id -> menu (same menu all info sets for simplicity)
    car_ids: tuple[str, str]
    initial_inventory: dict[str, InventoryState]
    crew_overlap_cost: float
    deadline_s: float
    base_loss: dict[str, float]  # (info_set, car, action_id) keyed later via tables
    action_costs: dict[tuple[str, str, str], float]  # (info_set_id, car_id, action_id) -> cost
    pair_costs: dict[tuple[str, str, str], float]  # (info_set_id, a1, a2) -> extra joint cost
    scenario_leaf_costs: dict[str, float]
    seed: int
    meta: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        probs = [s.probability for s in self.scenarios]
        if abs(sum(probs) - 1.0) > 1e-9:
            errors.append(f"scenario probabilities sum to {sum(probs)}, not 1")
        if any(p < 0 for p in probs):
            errors.append("negative scenario probability")
        ids = [i.info_set_id for i in self.info_sets]
        if len(ids) != len(set(ids)):
            errors.append("duplicate info_set_id")
        for info in self.info_sets:
            if info.epoch < 0 or info.epoch >= self.n_epochs:
                errors.append(f"info set {info.info_set_id} epoch out of range")
            for sid in info.reachable_scenarios:
                if sid not in {s.scenario_id for s in self.scenarios}:
                    errors.append(f"unknown scenario {sid} in {info.info_set_id}")
        for car in self.car_ids:
            if car not in self.actions_by_car or not self.actions_by_car[car]:
                errors.append(f"missing actions for {car}")
            if car not in self.initial_inventory:
                errors.append(f"missing inventory for {car}")
        return errors

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "rung": self.rung,
            "family_id": self.family_id,
            "n_epochs": self.n_epochs,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "info_sets": [i.to_dict() for i in self.info_sets],
            "car_ids": list(self.car_ids),
            "actions_by_car": {
                c: [a.to_dict() for a in acts] for c, acts in self.actions_by_car.items()
            },
            "initial_inventory": {
                c: {
                    "soft": inv.soft,
                    "medium": inv.medium,
                    "hard": inv.hard,
                    "compounds_used": sorted(inv.compounds_used),
                    "required_compounds": inv.required_compounds,
                }
                for c, inv in self.initial_inventory.items()
            },
            "crew_overlap_cost": self.crew_overlap_cost,
            "deadline_s": self.deadline_s,
            "n_logical_vars": self.n_logical_vars(),
            "n_info_sets": len(self.info_sets),
            "n_scenarios": len(self.scenarios),
            "seed": self.seed,
            "meta": self.meta,
            "instance_hash": self.instance_hash(),
        }

    def instance_hash(self) -> str:
        payload = {
            "instance_id": self.instance_id,
            "rung": self.rung,
            "family_id": self.family_id,
            "n_epochs": self.n_epochs,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "info_sets": [i.to_dict() for i in self.info_sets],
            "actions": {c: [a.to_dict() for a in acts] for c, acts in self.actions_by_car.items()},
            "crew_overlap_cost": self.crew_overlap_cost,
            "action_costs": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sorted(self.action_costs.items())},
            "pair_costs": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sorted(self.pair_costs.items())},
            "scenario_leaf_costs": self.scenario_leaf_costs,
            "seed": self.seed,
        }
        return sha256_json(payload)


def _default_actions(n_actions: int) -> list[Action]:
    """Admitted Stage-4-lineage actions: pit_now with compound/set, or continue."""
    actions: list[Action] = []
    if n_actions >= 1:
        actions.append(
            Action("continue", "continue", None, None, "remain on track / no pit this epoch")
        )
    compounds = ["soft", "medium", "hard"]
    for i in range(1, n_actions):
        comp = compounds[(i - 1) % len(compounds)]
        actions.append(
            Action(
                f"pit_now_{comp}",
                "pit_now",
                comp,
                f"set_{comp}_{i}",
                f"pit now mount {comp}",
            )
        )
    return actions


def build_a2_instance(
    *,
    instance_id: str,
    family_id: str,
    rung: str,
    n_scenarios: int,
    n_epochs: int,
    n_actions: int,
    seed: int,
    crew_overlap_cost: float = 0.15,
    deadline_s: float = 2.0,
) -> A2Instance:
    """Build a deterministic A2 instance. Decisions are per info-set (non-anticipative)."""
    rng = np.random.default_rng(seed)
    car_ids = ("car_a", "car_b")
    # Scenario probabilities (Dirichlet-like via normalised exponentials)
    raw = rng.random(n_scenarios) + 0.05
    probs = raw / raw.sum()
    scenarios: list[Scenario] = []
    # circuit_unit: share one duration class so epoch-1 has a single info set (≤8–12 qubits).
    # tiny+: allow distinct durations for genuine branching.
    shared_duration = int(rng.integers(1, 5)) if rung == "circuit_unit" else None
    for i in range(n_scenarios):
        duration = int(shared_duration if shared_duration is not None else rng.integers(1, 5))
        restart = ("rolling", "standing", "none")[int(rng.integers(0, 3))]
        # Observable signature grows with epoch: duration class visible from epoch 1
        obs = tuple(
            f"dur:{duration}" if e >= 1 else "root" for e in range(n_epochs)
        )
        scenarios.append(
            Scenario(
                scenario_id=f"s{i}",
                probability=float(probs[i]),
                sc_duration_laps=duration,
                restart_mode=restart,
                observable_at_epoch=obs,
            )
        )

    # Build info sets: at epoch 0 always one root; later epochs partition by observable signature
    info_sets: list[InfoSet] = []
    # epoch 0
    info_sets.append(
        InfoSet(
            info_set_id="I0_root",
            epoch=0,
            observable_signature="root",
            parent_id=None,
            reachable_scenarios=tuple(s.scenario_id for s in scenarios),
        )
    )
    for epoch in range(1, n_epochs):
        buckets: dict[str, list[str]] = {}
        for s in scenarios:
            # Observable: duration class (and restart if epoch>=2 for richer trees)
            if epoch == 1:
                sig = f"dur:{s.sc_duration_laps}"
            else:
                sig = f"dur:{s.sc_duration_laps}|rst:{s.restart_mode}"
            buckets.setdefault(sig, []).append(s.scenario_id)
        for sig, sc_ids in sorted(buckets.items()):
            info_sets.append(
                InfoSet(
                    info_set_id=f"I{epoch}_{sig}",
                    epoch=epoch,
                    observable_signature=sig,
                    parent_id="I0_root" if epoch == 1 else None,
                    reachable_scenarios=tuple(sc_ids),
                )
            )

    menu = _default_actions(n_actions)
    actions_by_car = {c: list(menu) for c in car_ids}
    # Inventory: enough sets for pit actions; obligation may bind on tiny
    initial_inventory = {
        c: InventoryState(
            soft=2,
            medium=2,
            hard=1,
            compounds_used=frozenset({"medium"}),
            required_compounds=1,  # medium already used; continue-only remains legal
        )
        for c in car_ids
    }

    action_costs: dict[tuple[str, str, str], float] = {}
    pair_costs: dict[tuple[str, str, str], float] = {}
    for info in info_sets:
        for car in car_ids:
            for a in actions_by_car[car]:
                base = float(rng.normal(1.0, 0.35))
                if a.kind == "pit_now":
                    base += 0.4 + 0.05 * info.epoch
                action_costs[(info.info_set_id, car, a.action_id)] = base
        for a1 in actions_by_car[car_ids[0]]:
            for a2 in actions_by_car[car_ids[1]]:
                joint = 0.0
                if a1.kind == "pit_now" and a2.kind == "pit_now":
                    joint = crew_overlap_cost  # finite cost, not hard prohibition
                pair_costs[(info.info_set_id, a1.action_id, a2.action_id)] = joint

    scenario_leaf_costs = {
        s.scenario_id: float(0.1 * s.sc_duration_laps + (0.2 if s.restart_mode == "standing" else 0.0))
        for s in scenarios
    }

    inst = A2Instance(
        instance_id=instance_id,
        rung=rung,
        family_id=family_id,
        n_epochs=n_epochs,
        scenarios=scenarios,
        info_sets=info_sets,
        actions_by_car=actions_by_car,
        car_ids=car_ids,
        initial_inventory=initial_inventory,
        crew_overlap_cost=crew_overlap_cost,
        deadline_s=deadline_s,
        base_loss={},
        action_costs=action_costs,
        pair_costs=pair_costs,
        scenario_leaf_costs=scenario_leaf_costs,
        seed=seed,
        meta={"n_actions": n_actions, "builder": "stage5.model.build_a2_instance"},
    )
    errs = inst.validate()
    if errs:
        raise ValueError(f"invalid A2 instance: {errs}")
    return inst


def info_set_for_scenario(instance: A2Instance, epoch: int, scenario_id: str) -> InfoSet:
    for info in instance.info_sets:
        if info.epoch == epoch and scenario_id in info.reachable_scenarios:
            return info
    raise KeyError(f"no info set for epoch={epoch} scenario={scenario_id}")


def policy_selects(
    policy: dict[str, dict[str, str]], info_set_id: str, car_id: str
) -> str:
    return policy[info_set_id][car_id]


def empty_policy_template(instance: A2Instance) -> dict[str, dict[str, str]]:
    return {info.info_set_id: {car: "" for car in instance.car_ids} for info in instance.info_sets}


def iter_action_choices(instance: A2Instance) -> Iterable[tuple[str, str, list[str]]]:
    for info in instance.info_sets:
        for car in instance.car_ids:
            yield info.info_set_id, car, [a.action_id for a in instance.actions_by_car[car]]

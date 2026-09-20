"""A2 deterministic scenario-tree policy model (non-anticipative by construction).

Corrected builder: family factors drive mechanisms; action costs have documented
Stage-3/4 lineage; scenario probabilities are deterministic_synthetic (not claimed
AI-trained).

Causal duration scope (restricted synthetic surrogate — preserved for Phase 5 evidence):
the training model ASSUMES SC/VSC duration is fully revealed at the second decision
epoch (epoch 1 observables are ``dur:<laps>``). Epoch 0 is a shared ``root`` info set
only. This is a **synthetic commitment-epoch revealed-duration surrogate**, not a
demonstration of event-timed, on-track causal validity or Stage-3 pit-entry deadline
integration. Checking that epoch 0 equals ``root`` does **not** prove causal validity
at subsequent decisions under a live simulator. Operational Phase 6 race-decision
pilots require explicit causal simulator integration as a prerequisite. This
surrogate does **not** demonstrate actual F1 operational value.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from f1q.hashing import sha256_json

# Documented assumption retained so training evidence stays valid without regenerating
# the generator. Do not silently widen revelation timing without a new authorised run.
CAUSAL_DURATION_MODEL = "restricted_synthetic_revealed_at_epoch_1"
CAUSAL_DURATION_ASSUMPTION = (
    "SC/VSC duration is fully placed into epoch-1 observables; epoch 0 is root-only. "
    "Synthetic commitment-epoch check — not event-timed on-track causal validation."
)


def _stable_unit_jitter(*parts: Any) -> float:
    """Deterministic [-0.01, 0.01] jitter without Python hash()."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF - 0.5) * 0.02

ACTION_KINDS = ("pit_now", "continue")
COMPOUNDS = ("soft", "medium", "hard")


def parse_family_factors(family_id: str) -> dict[str, str]:
    """Parse fam.green_pit_{low|high}.tyre_{near_linear|nonlinear}.traffic_{sparse|dense}."""
    parts = family_id.split(".")
    if len(parts) != 4 or parts[0] != "fam":
        raise ValueError(f"unrecognised family_id: {family_id}")
    pit = parts[1].removeprefix("green_pit_")
    tyre = parts[2].removeprefix("tyre_")
    traffic = parts[3].removeprefix("traffic_")
    if pit not in ("low", "high") or tyre not in ("near_linear", "nonlinear") or traffic not in (
        "sparse",
        "dense",
    ):
        raise ValueError(f"unrecognised family factors in {family_id}")
    return {"green_pit_loss": pit, "tyre_degradation": tyre, "traffic": traffic}


def family_mechanism_params(factors: dict[str, str]) -> dict[str, float]:
    """Map Stage-2 family factors to mechanism coefficients (synthetic, not F1-calibrated).

    Lineage: green_pit_loss ↔ Stage-2/3 pit-loss factor; tyre_degradation ↔ wear model
    class; traffic ↔ interaction/overlap intensity. Values are development synthetics
    with documented factor→coefficient maps — not scraped timing data.
    """
    pit_base = 0.35 if factors["green_pit_loss"] == "low" else 0.85
    tyre_scale = 0.12 if factors["tyre_degradation"] == "near_linear" else 0.28
    tyre_quad = 0.0 if factors["tyre_degradation"] == "near_linear" else 0.08
    traffic_scale = 0.05 if factors["traffic"] == "sparse" else 0.22
    crew_scale = 0.10 if factors["traffic"] == "sparse" else 0.25
    return {
        "pit_base_loss": pit_base,
        "tyre_linear": tyre_scale,
        "tyre_quadratic": tyre_quad,
        "traffic_interaction": traffic_scale,
        "crew_overlap_scale": crew_scale,
        "continue_base": 0.15 + 0.05 * (1 if factors["traffic"] == "dense" else 0),
    }


@dataclass(frozen=True)
class Action:
    action_id: str
    kind: str
    compound: str | None
    set_id: str | None
    description: str
    commitment_expires_epoch: int | None = None  # deadline: invalid if chosen after expiry

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "compound": self.compound,
            "set_id": self.set_id,
            "description": self.description,
            "commitment_expires_epoch": self.commitment_expires_epoch,
        }


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    probability: float
    sc_duration_laps: int
    restart_mode: str  # "rolling" | "standing" | "none"
    observable_at_epoch: tuple[str, ...]

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
    history_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "info_set_id": self.info_set_id,
            "epoch": self.epoch,
            "observable_signature": self.observable_signature,
            "parent_id": self.parent_id,
            "reachable_scenarios": list(self.reachable_scenarios),
            "history_signature": self.history_signature,
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
    actions_by_car: dict[str, list[Action]]
    car_ids: tuple[str, str]
    initial_inventory: dict[str, InventoryState]
    crew_overlap_cost: float
    deadline_s: float
    base_loss: dict[str, float]
    action_costs: dict[tuple[str, str, str], float]
    pair_costs: dict[tuple[str, str, str], float]
    scenario_leaf_costs: dict[str, float]
    seed: int
    meta: dict[str, Any] = field(default_factory=dict)
    cost_lineage: dict[str, Any] = field(default_factory=dict)

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
        parent_ok = True
        for info in self.info_sets:
            if info.epoch < 0 or info.epoch >= self.n_epochs:
                errors.append(f"info set {info.info_set_id} epoch out of range")
            for sid in info.reachable_scenarios:
                if sid not in {s.scenario_id for s in self.scenarios}:
                    errors.append(f"unknown scenario {sid} in {info.info_set_id}")
            if info.epoch == 0 and info.parent_id is not None:
                errors.append(f"root {info.info_set_id} must have parent_id=None")
                parent_ok = False
            if info.epoch > 0 and info.parent_id is None:
                errors.append(f"non-root {info.info_set_id} missing parent")
                parent_ok = False
            if info.parent_id is not None and info.parent_id not in ids:
                errors.append(f"parent {info.parent_id} missing for {info.info_set_id}")
                parent_ok = False
        if parent_ok:
            # Reachable scenarios of child ⊆ parent
            by_id = {i.info_set_id: i for i in self.info_sets}
            for info in self.info_sets:
                if info.parent_id is None:
                    continue
                parent = by_id[info.parent_id]
                if not set(info.reachable_scenarios).issubset(set(parent.reachable_scenarios)):
                    errors.append(f"child scenarios not subset of parent for {info.info_set_id}")
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
            "cost_lineage": self.cost_lineage,
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
            "cost_lineage": self.cost_lineage,
        }
        return sha256_json(payload)


def _default_actions(n_actions: int, *, binding_deadline: bool = False) -> list[Action]:
    actions: list[Action] = []
    if n_actions >= 1:
        actions.append(
            Action("continue", "continue", None, None, "remain on track / no pit this epoch")
        )
    compounds = ["soft", "medium", "hard"]
    for i in range(1, n_actions):
        comp = compounds[(i - 1) % len(compounds)]
        # Pit commitment expires after epoch 0 when binding_deadline microcase
        expires = 0 if binding_deadline and i == 1 else None
        actions.append(
            Action(
                f"pit_now_{comp}",
                "pit_now",
                comp,
                f"set_{comp}_{i}",
                f"pit now mount {comp}",
                commitment_expires_epoch=expires,
            )
        )
    return actions


def _synthetic_probs(rng: np.random.Generator, n: int) -> np.ndarray:
    """Deterministic synthetic probabilities — NOT a trained AI probability model."""
    raw = rng.random(n) + 0.05
    return raw / raw.sum()


def build_a2_instance(
    *,
    instance_id: str,
    family_id: str,
    rung: str,
    n_scenarios: int,
    n_epochs: int,
    n_actions: int,
    seed: int,
    crew_overlap_cost: float | None = None,
    deadline_s: float = 2.0,
    microcase: str | None = None,
) -> A2Instance:
    """Build a deterministic A2 instance with family-driven mechanisms.

    microcase options (for adversarial/acceptance tests):
      - binding_inventory
      - binding_compound
      - binding_deadline
      - force_branching
      - None → seed-derived defaults
    """
    rng = np.random.default_rng(seed)
    factors = parse_family_factors(family_id)
    mech = family_mechanism_params(factors)
    if crew_overlap_cost is None:
        crew_overlap_cost = float(mech["crew_overlap_scale"])

    # Microcase selection from seed when not explicit
    if microcase is None:
        roll = int(seed) % 17
        if roll == 0:
            microcase = "binding_inventory"
        elif roll == 1:
            microcase = "binding_compound"
        elif roll == 2:
            microcase = "binding_deadline"
        elif roll == 3:
            microcase = "force_branching"
        else:
            microcase = "standard"

    car_ids = ("car_a", "car_b")
    probs = _synthetic_probs(rng, n_scenarios)

    # Branching: circuit_unit shares duration unless force_branching / tiny+
    force_branch = microcase == "force_branching" or rung != "circuit_unit"
    shared_duration = None if force_branch else int(rng.integers(1, 5))

    scenarios: list[Scenario] = []
    for i in range(n_scenarios):
        if shared_duration is not None:
            duration = int(shared_duration)
        else:
            # Ensure at least two distinct durations when branching intended
            if force_branch and n_scenarios >= 2:
                duration = 1 + (i % min(n_scenarios, 4))
            else:
                duration = int(rng.integers(1, 5))
        restart = ("rolling", "standing", "none")[int(rng.integers(0, 3))]
        # Restricted synthetic revealed-duration surrogate (CAUSAL_DURATION_MODEL):
        # epoch 0 = shared "root"; full sampled duration is placed into epoch-1+
        # observables. This ASSUMES duration is fully revealed by the second decision
        # epoch. It is NOT event-timed / on-track causal validation and does NOT
        # substitute for Stage-3 pit-entry deadline checks under the live simulator.
        obs = tuple("root" if e == 0 else f"dur:{duration}" for e in range(n_epochs))
        # Duration is intentionally absent from epoch-0; present from epoch 1 by assumption.
        scenarios.append(
            Scenario(
                scenario_id=f"s{i}",
                probability=float(probs[i]),
                sc_duration_laps=duration,
                restart_mode=restart,
                observable_at_epoch=obs,
            )
        )

    # Info sets with valid parent/history chain
    info_sets: list[InfoSet] = []
    root = InfoSet(
        info_set_id="I0_root",
        epoch=0,
        observable_signature="root",
        parent_id=None,
        reachable_scenarios=tuple(s.scenario_id for s in scenarios),
        history_signature="root",
    )
    info_sets.append(root)
    parents_by_epoch: dict[int, list[InfoSet]] = {0: [root]}

    for epoch in range(1, n_epochs):
        buckets: dict[tuple[str, str], list[str]] = {}
        # Partition each parent by newly revealed observables
        for parent in parents_by_epoch[epoch - 1]:
            for sid in parent.reachable_scenarios:
                s = next(sc for sc in scenarios if sc.scenario_id == sid)
                if epoch == 1:
                    sig = f"dur:{s.sc_duration_laps}"
                else:
                    sig = f"dur:{s.sc_duration_laps}|rst:{s.restart_mode}"
                key = (parent.info_set_id, sig)
                buckets.setdefault(key, []).append(sid)
        epoch_nodes: list[InfoSet] = []
        for (parent_id, sig), sc_ids in sorted(buckets.items()):
            node = InfoSet(
                info_set_id=f"I{epoch}_{sig}_from_{parent_id}",
                epoch=epoch,
                observable_signature=sig,
                parent_id=parent_id,
                reachable_scenarios=tuple(sc_ids),
                history_signature=f"{parent_id}>{sig}",
            )
            epoch_nodes.append(node)
            info_sets.append(node)
        parents_by_epoch[epoch] = epoch_nodes

    binding_deadline = microcase == "binding_deadline"
    menu = _default_actions(n_actions, binding_deadline=binding_deadline)
    actions_by_car = {c: list(menu) for c in car_ids}

    # Inventory / compound binding microcases
    if microcase == "binding_inventory":
        initial_inventory = {
            c: InventoryState(
                soft=1 if c == "car_a" else 2,
                medium=0,
                hard=0,
                compounds_used=frozenset(),
                required_compounds=0,
            )
            for c in car_ids
        }
    elif microcase == "binding_compound":
        # Require an additional compound beyond the initial set; with small menus
        # require ≥1 compound used (continue-only illegal). With ≥3 actions, require 2.
        req = 2 if n_actions >= 3 else 1
        initial_inventory = {
            c: InventoryState(
                soft=2,
                medium=2,
                hard=1,
                compounds_used=frozenset(),
                required_compounds=req,
            )
            for c in car_ids
        }
    else:
        initial_inventory = {
            c: InventoryState(
                soft=2,
                medium=2,
                hard=1,
                compounds_used=frozenset({"medium"}),
                required_compounds=1,
            )
            for c in car_ids
        }

    # Action costs from family mechanisms + Stage-3/4-style lineage (not independent noise)
    action_costs: dict[tuple[str, str, str], float] = {}
    pair_costs: dict[tuple[str, str, str], float] = {}
    lineage_rows: list[dict[str, Any]] = []
    for info in info_sets:
        for car in car_ids:
            for a in actions_by_car[car]:
                if a.kind == "continue":
                    cost = float(mech["continue_base"] + mech["tyre_linear"] * (info.epoch + 1))
                    if mech["tyre_quadratic"] > 0:
                        cost += mech["tyre_quadratic"] * (info.epoch + 1) ** 2
                    formula = "continue_base + tyre_linear*(epoch+1) [+ tyre_quad*(epoch+1)^2]"
                else:
                    cost = float(
                        mech["pit_base_loss"]
                        + mech["traffic_interaction"] * (0.5 if info.epoch == 0 else 1.0)
                        + 0.02 * info.epoch
                    )
                    formula = "pit_base_loss + traffic_interaction*epoch_factor + 0.02*epoch"
                # Tiny deterministic jitter from seed+ids (reproducible), not independent random costs
                jitter = _stable_unit_jitter(info.info_set_id, car, a.action_id, seed)
                cost = cost + jitter
                action_costs[(info.info_set_id, car, a.action_id)] = cost
                lineage_rows.append(
                    {
                        "key": f"{info.info_set_id}|{car}|{a.action_id}",
                        "formula": formula,
                        "family_factors": factors,
                        "mechanism": mech,
                        "cost": cost,
                    }
                )
        for a1 in actions_by_car[car_ids[0]]:
            for a2 in actions_by_car[car_ids[1]]:
                joint = 0.0
                if a1.kind == "pit_now" and a2.kind == "pit_now":
                    joint = float(crew_overlap_cost)  # finite cost, not hard rule
                pair_costs[(info.info_set_id, a1.action_id, a2.action_id)] = joint

    # Leaf costs use duration — under the restricted surrogate, epoch-0 decisions
    # cannot observe duration; epoch-1+ decisions may (by construction).
    scenario_leaf_costs = {
        s.scenario_id: float(
            0.1 * s.sc_duration_laps
            + (0.2 if s.restart_mode == "standing" else 0.0)
            + mech["traffic_interaction"] * 0.1
        )
        for s in scenarios
    }

    n_branching_epochs = sum(1 for e, nodes in parents_by_epoch.items() if e > 0 and len(nodes) > 1)

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
        crew_overlap_cost=float(crew_overlap_cost),
        deadline_s=deadline_s,
        base_loss={},
        action_costs=action_costs,
        pair_costs=pair_costs,
        scenario_leaf_costs=scenario_leaf_costs,
        seed=seed,
        meta={
            "n_actions": n_actions,
            "builder": "stage5.model.build_a2_instance",
            "builder_version": "corrected.v1",
            "microcase": microcase,
            "scenario_probability_model": "deterministic_synthetic",
            "scenario_probability_claim": "NOT_AI_TRAINED",
            "n_branching_epochs": n_branching_epochs,
            "family_factors": factors,
            "mechanism_params": mech,
            "causal_duration_model": CAUSAL_DURATION_MODEL,
            "causal_duration_assumption": CAUSAL_DURATION_ASSUMPTION,
            "causal_event_timed_on_track_validated": False,
            "causal_pit_entry_deadline_validated": False,
        },
        cost_lineage={
            "source": "family_mechanism_params + Stage-2 factor map",
            "not_f1_calibrated": True,
            "n_rows": len(lineage_rows),
            "sample_rows": lineage_rows[:6],
        },
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


def policy_selects(policy: dict[str, dict[str, str]], info_set_id: str, car_id: str) -> str:
    return policy[info_set_id][car_id]


def empty_policy_template(instance: A2Instance) -> dict[str, dict[str, str]]:
    return {info.info_set_id: {car: "" for car in instance.car_ids} for info in instance.info_sets}


def iter_action_choices(instance: A2Instance) -> Iterable[tuple[str, str, list[str]]]:
    for info in instance.info_sets:
        for car in instance.car_ids:
            yield info.info_set_id, car, [a.action_id for a in instance.actions_by_car[car]]


def decisions_cannot_see_hidden_duration(instance: A2Instance) -> bool:
    """Synthetic commitment-epoch check: epoch-0 must be root-only (no ``dur:``).

    Passing this check only validates the restricted revealed-duration surrogate
    (duration fully exposed at epoch 1 by construction). It does **not** prove
    event-timed, on-track causal validity or live pit-entry deadline behaviour.
    """
    for info in instance.info_sets:
        if info.epoch == 0:
            if "dur:" in info.observable_signature:
                return False
            # All scenarios share the root — duration not partitioned yet
            if set(info.reachable_scenarios) != {s.scenario_id for s in instance.scenarios}:
                return False
    for s in instance.scenarios:
        if s.observable_at_epoch[0] != "root":
            return False
    return True

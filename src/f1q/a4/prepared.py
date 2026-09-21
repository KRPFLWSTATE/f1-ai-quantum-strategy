"""One immutable PreparedCase per (partition, block_id, regime)."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from f1q import INTERFACE_VERSION, SIMULATOR_VERSION, __version__ as PACKAGE_VERSION
from f1q.a4.contracts import StructuralError
from f1q.a4.loop import family_spec
from f1q.a4.problem import (
    build_a4_qubo,
    build_menu_and_instance,
    enumerate_legal_policies,
    extract_causal_view,
    qubo_structural_features,
    verify_direct_qubo_milp,
)
from f1q.hashing import sha256_json
from f1q.simulator.deadline import effective_deadline
from f1q.simulator.interface import RaceSimulator

_PREPARE_COUNTERS: dict[str, int] = {
    "checkpoint_init": 0,
    "menu_qubo": 0,
    "enumeration": 0,
    "formulation_verify": 0,
}


def reset_prepare_counters() -> None:
    for k in _PREPARE_COUNTERS:
        _PREPARE_COUNTERS[k] = 0


def prepare_counters() -> dict[str, int]:
    return dict(_PREPARE_COUNTERS)


@dataclass
class PreparedCase:
    split: str
    block_id: str
    family_id: str
    regime: str
    seed: int
    case_id: str
    spec: dict[str, Any]
    spec_hash: str
    checkpoint_blob: dict[str, Any]
    checkpoint_hash: str
    observation_hash: str
    view: dict[str, Any]
    decision_time_race_s: float
    pit_cutoffs_race_s: list[float]
    communication_margin_s: float
    instance: Any
    legal_table: list[dict[str, Any]]
    qubo: dict[str, Any]
    formulation: dict[str, Any]
    features: dict[str, float]
    simulator_version: str
    interface_version: str
    package_version: str
    timings: dict[str, float] = field(default_factory=dict)

    def window_for_budget(self, nominal_budget_s: float) -> dict[str, Any]:
        return effective_deadline(
            decision_time_race_s=self.decision_time_race_s,
            nominal_budget_s=float(nominal_budget_s),
            team_pit_entry_cutoffs_race_s=list(self.pit_cutoffs_race_s),
            communication_margin_s=self.communication_margin_s,
        )

    def spec_with_budget(self, nominal_budget_s: float) -> dict[str, Any]:
        spec = copy.deepcopy(self.spec)
        spec.setdefault("deadline_interface", {})["primary_nominal_budget_s"] = float(nominal_budget_s)
        return spec

    def remaining_for_budget(self, nominal_budget_s: float) -> float:
        w = self.window_for_budget(nominal_budget_s)
        return max(0.0, float(w["remaining_window_s"]))


def prepare_case(
    *,
    family_id: str,
    block_id: str,
    regime: str,
    partition: str,
    index: int,
    seed: int,
    spec: dict[str, Any] | None = None,
) -> PreparedCase:
    t0 = time.perf_counter()
    if str(partition) in {"finaltest", "final_test"}:
        raise StructuralError("FINAL_TEST_BOUNDARY", "refusing to prepare a final-test spec", path="prepare_case")
    spec = family_spec(
            family_id=family_id,
            block_id=block_id,
            regime=regime,
            partition=partition,
            index=index,
            seed=seed,
        ) if spec is None else spec
    sim = RaceSimulator()
    _PREPARE_COUNTERS["checkpoint_init"] += 1
    sim.initialize(copy.deepcopy(spec))
    sim.advance_to_checkpoint()
    blob = sim.serialize()
    obs = sim.observe()
    view = extract_causal_view(obs)
    t_menu = time.perf_counter()
    _PREPARE_COUNTERS["menu_qubo"] += 1
    inst = build_menu_and_instance(view)
    qubo = build_a4_qubo(inst)
    _PREPARE_COUNTERS["formulation_verify"] += 1
    agree = verify_direct_qubo_milp(inst, qubo)
    if not agree.get("ok"):
        raise StructuralError("FORMULATION", "direct/QUBO/MILP verification failed", path="prepare_case.formulation")
    _PREPARE_COUNTERS["enumeration"] += 1
    legal = enumerate_legal_policies(inst)
    feats = qubo_structural_features(inst, qubo)
    menu_s = time.perf_counter() - t_menu
    eng = sim.engine
    assert eng is not None
    cutoffs = eng.operational_cutoffs()
    team_cut = [float(cutoffs[cid]) for cid in eng.state["selected_car_ids"]]
    spec_hash = sha256_json({k: spec[k] for k in spec if k not in {"stream_key_ids"}})
    legal_ser = list(legal)
    case_id = f"{partition}:{block_id}:{regime}"
    return PreparedCase(
        split=str(partition),
        block_id=block_id,
        family_id=family_id,
        regime=regime,
        seed=int(seed),
        case_id=case_id,
        spec=spec,
        spec_hash=spec_hash,
        checkpoint_blob=blob,
        checkpoint_hash=str(view["observation_hash"]),
        observation_hash=str(view["observation_hash"]),
        view=view,
        decision_time_race_s=float(view["decision_time_race_s"]),
        pit_cutoffs_race_s=team_cut,
        communication_margin_s=float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
        instance=inst,
        legal_table=legal_ser,
        qubo=qubo,
        formulation=agree,
        features=feats,
        simulator_version=SIMULATOR_VERSION,
        interface_version=INTERFACE_VERSION,
        package_version=PACKAGE_VERSION,
        timings={"prepare_s": time.perf_counter() - t0, "menu_qubo_enum_verify_s": menu_s},
    )


def validate_plan_fn(sim: RaceSimulator) -> Callable:
    def _validate(plan: dict[str, Any]) -> None:
        sim.validate_plan(plan)

    return _validate

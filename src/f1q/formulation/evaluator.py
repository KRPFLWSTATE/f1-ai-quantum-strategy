"""Simulator evaluator adapter — separate implementation from the proxy compiler.

Evaluates complete joint plans on cloned simulator checkpoints and reports modelled
outcome/classification quantities. Must not share scoring code with the compiler.
"""

from __future__ import annotations

from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload
from f1q.simulator.interface import RaceSimulator

# Architectural separation marker: evaluator imports simulator; compiler must not.
EVALUATOR_IMPLEMENTATION = "simulator_clone_continue_to_finish"
COMPILER_IMPLEMENTATION = "analytical_remaining_time_proxy"


def evaluate_joint_plan_on_checkpoint(
    *,
    cfg: dict[str, Any],
    spec: dict[str, Any],
    action_a: CarAction | dict[str, Any],
    action_b: CarAction | dict[str, Any],
) -> dict[str, Any]:
    """Modelled development diagnostic — not race truth."""
    if isinstance(action_a, dict):
        action_a = CarAction.model_validate(action_a)
    if isinstance(action_b, dict):
        action_b = CarAction.model_validate(action_b)
    selected = list(spec["selected_car_ids"])
    joint = build_joint_plan(action_a, action_b, selected)
    plan = simulator_plan_payload(joint)
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.advance_to_checkpoint()
    legality = {"ok": False}
    try:
        legality = sim.validate_plan(plan)
        clone = sim.clone()
        clone.apply_plan(plan)
        _, outcome = clone.continue_to_finish()
        ranks = {cid: outcome["ranking"]["ranks"][cid] for cid in selected}
        field_size = int(outcome["ranking"]["field_size"])
        r1 = ranks[selected[0]]
        r2 = ranks[selected[1]]
        L = (r1 + r2 - 2) / (2 * (field_size - 1))
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "not_race_truth": True,
            "modelled_development_diagnostic": True,
            "legal": True,
            "legality": legality,
            "leader_finish_classification": outcome["ranking"],
            "selected_team_ranks": ranks,
            "team_rank_loss_L": float(L),
            "finish_t": float(outcome["t"]),
            "action_ids": joint["_meta"]["action_ids"],
        }
    except Exception as exc:
        return {
            "implementation": EVALUATOR_IMPLEMENTATION,
            "not_race_truth": True,
            "modelled_development_diagnostic": True,
            "legal": False,
            "error": f"{type(exc).__name__}: {exc}",
            "action_ids": {
                action_a.car_id: action_a.action_id,
                action_b.car_id: action_b.action_id,
            },
        }


def assert_compiler_evaluator_separation() -> dict[str, Any]:
    import ast
    import f1q.formulation.compiler as compiler_mod
    import f1q.formulation.evaluator as evaluator_mod

    compiler_file = getattr(compiler_mod, "__file__", "")
    evaluator_file = getattr(evaluator_mod, "__file__", "")
    with open(compiler_file, encoding="utf-8") as handle:
        compiler_src = handle.read()
    with open(evaluator_file, encoding="utf-8") as handle:
        evaluator_src = handle.read()
    tree = ast.parse(compiler_src)
    banned_names = {"continue_to_finish", "RaceSimulator"}
    banned_modules = {"f1q.formulation.evaluator", "f1q.simulator.engine", "f1q.simulator.interface"}
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in banned_modules or alias.name.startswith("f1q.simulator"):
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in banned_modules or mod.startswith("f1q.simulator"):
                hits.append(f"from {mod}")
        elif isinstance(node, ast.Name) and node.id in banned_names:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in banned_names:
            hits.append(node.attr)
    return {
        "ok": len(hits) == 0 and compiler_file != evaluator_file,
        "compiler_banned_hits": hits,
        "compiler_implementation": COMPILER_IMPLEMENTATION,
        "evaluator_implementation": EVALUATOR_IMPLEMENTATION,
        "same_file": compiler_file == evaluator_file,
        "evaluator_uses_simulator": "RaceSimulator" in evaluator_src,
    }

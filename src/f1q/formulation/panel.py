"""Bounded development-only evaluator separation panel."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.formulation.actions import CarAction
from f1q.formulation.compiler import score_joint_direct
from f1q.formulation.evaluator import evaluate_joint_plan_on_checkpoint
from f1q.formulation.instance import build_instance_record
from f1q.hashing import sha256_json


def select_panel_specs(
    specs: list[dict[str, Any]], *, per_family: int = 1
) -> tuple[list[dict[str, Any]], str]:
    """Deterministic selection spanning all eight families and both SC/VSC where available.

    Selection is hashed before any evaluator outcomes are computed.
    """
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        by_fam.setdefault(spec["family_id"], []).append(spec)
    selected: list[dict[str, Any]] = []
    for index, family_id in enumerate(sorted(by_fam)):
        want = "SC" if index % 2 == 0 else "VSC"
        pool = [s for s in by_fam[family_id] if s["checkpoint_request"]["requested_regime"] == want]
        if not pool:
            pool = list(by_fam[family_id])
        pool.sort(key=lambda s: hashlib.sha256(s["episode_id"].encode("utf-8")).hexdigest())
        selected.extend(pool[:per_family])
    selection_ids = [s["episode_id"] for s in selected]
    return selected, sha256_json({"episode_ids": selection_ids, "policy": "family_hash_sc_vsc_alt"})


def run_evaluator_panel(
    *,
    root,
    cfg: dict[str, Any],
    specs: list[dict[str, Any]],
    joint_plan_cap: int = 6,
) -> dict[str, Any]:
    selected, selection_hash = select_panel_specs(specs)
    # Record selection before outcomes.
    panel = {
        "selection_hash": selection_hash,
        "episode_ids": [s["episode_id"] for s in selected],
        "joint_plan_cap": joint_plan_cap,
        "cases": [],
        "selection_recorded_before_outcomes": True,
        "modelled_development_diagnostic": True,
        "not_race_truth": True,
        "weights_not_tuned_from_panel": True,
    }
    for spec in selected:
        inst = build_instance_record(cfg=cfg, spec=spec, verify_energies=False, cross_check_simulator=False)
        costs = inst["costs"]
        enum = inst["enumeration"]
        selected_cars = inst["selected_car_ids"]
        menus = inst["action_model"]["menus"]
        a_actions = [CarAction.model_validate(a) for a in menus[selected_cars[0]]]
        b_actions = [CarAction.model_validate(b) for b in menus[selected_cars[1]]]
        # Plans: exact optimum, greedy, and up to cap deterministic comparison pairs.
        plans = []
        for m in enum["minimisers"][:1]:
            plans.append(("exact_proxy_optimum", a_actions[m["i"]], b_actions[m["j"]], m["value"]))
        g = inst["heuristics"]["greedy_local"]["incumbent"]
        if g is not None:
            plans.append(("greedy_incumbent", a_actions[g["i"]], b_actions[g["j"]], g["value"]))
        # Deterministic comparison: first/last of each menu
        if a_actions and b_actions:
            plans.append(("comparison_first_first", a_actions[0], b_actions[0], score_joint_direct(costs, index_a=0, index_b=0)))
            if len(a_actions) > 1 and len(b_actions) > 1:
                plans.append(
                    (
                        "comparison_last_last",
                        a_actions[-1],
                        b_actions[-1],
                        score_joint_direct(costs, index_a=len(a_actions) - 1, index_b=len(b_actions) - 1),
                    )
                )
        plans = plans[:joint_plan_cap]
        case = {
            "episode_id": spec["episode_id"],
            "family_id": spec["family_id"],
            "regime": spec["checkpoint_request"]["requested_regime"],
            "record_hash": inst["record_hash"],
            "proxy_optimum": enum["exact_proxy_minimum"],
            "evaluations": [],
        }
        proxy_ranks = []
        eval_ranks = []
        for label, a, b, proxy_val in plans:
            ev = evaluate_joint_plan_on_checkpoint(cfg=cfg, spec=spec, action_a=a, action_b=b)
            case["evaluations"].append(
                {
                    "label": label,
                    "proxy_value": proxy_val,
                    "evaluator": ev,
                }
            )
            proxy_ranks.append((proxy_val, label))
            if ev.get("legal") and "team_rank_loss_L" in ev:
                eval_ranks.append((float(ev["team_rank_loss_L"]), label))
        # Descriptive disagreement: compare order by proxy vs by L
        proxy_order = [lab for _, lab in sorted(proxy_ranks)]
        eval_order = [lab for _, lab in sorted(eval_ranks)] if eval_ranks else []
        case["proxy_order"] = proxy_order
        case["evaluator_L_order"] = eval_order
        case["rank_agreement"] = proxy_order == eval_order if eval_order else None
        panel["cases"].append(case)
    panel["n_cases"] = len(panel["cases"])
    panel["panel_hash"] = sha256_json({"selection": selection_hash, "n": panel["n_cases"]})
    return panel

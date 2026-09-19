"""Bounded development-only evaluator separation panel (Stage 4.1 tie-aware)."""

from __future__ import annotations

import hashlib
from typing import Any

from f1q.formulation.actions import CarAction
from f1q.formulation.compiler import score_joint_direct
from f1q.formulation.evaluator import evaluate_joint_plan_on_checkpoint
from f1q.formulation.instance import build_instance_record
from f1q.formulation.versions import EVALUATOR_RANK_TOLERANCE, TOLERANCE_S
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


def _pair_key(a: CarAction, b: CarAction) -> tuple[str, str]:
    return (a.action_id, b.action_id)


def kendall_tau_b(ranks_x: list[float], ranks_y: list[float]) -> dict[str, Any]:
    """Pairwise concordant/discordant/tied counts and Kendall tau-b."""
    n = len(ranks_x)
    if n != len(ranks_y) or n < 2:
        return {
            "n": n,
            "concordant": 0,
            "discordant": 0,
            "tied_x": 0,
            "tied_y": 0,
            "tied_both": 0,
            "tau_b": None,
        }
    import math

    conc = disc = tx = ty = tb = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = ranks_x[j] - ranks_x[i]
            dy = ranks_y[j] - ranks_y[i]
            if abs(dx) <= EVALUATOR_RANK_TOLERANCE and abs(dy) <= EVALUATOR_RANK_TOLERANCE:
                tb += 1
            elif abs(dx) <= EVALUATOR_RANK_TOLERANCE:
                tx += 1
            elif abs(dy) <= EVALUATOR_RANK_TOLERANCE:
                ty += 1
            elif dx * dy > 0:
                conc += 1
            else:
                disc += 1
    # Kendall tau-b: (C-D) / sqrt((n0-n1)(n0-n2)); n1/n2 count all pairs tied on x/y.
    n0 = n * (n - 1) / 2.0
    n1 = tx + tb
    n2 = ty + tb
    denom = math.sqrt(max(0.0, (n0 - n1) * (n0 - n2)))
    tau = ((conc - disc) / denom) if denom > 0 else None
    return {
        "n": n,
        "concordant": conc,
        "discordant": disc,
        "tied_x": tx,
        "tied_y": ty,
        "tied_both": tb,
        "tau_b": tau,
    }


def classify_order_relation(
    proxy_vals: list[float],
    eval_vals: list[float],
    *,
    proxy_tol: float = TOLERANCE_S,
    eval_tol: float = EVALUATOR_RANK_TOLERANCE,
) -> dict[str, Any]:
    kt = kendall_tau_b(proxy_vals, eval_vals)
    if kt["discordant"] == 0 and kt["concordant"] >= 0:
        relation = "agreement"
        if kt["tied_x"] or kt["tied_y"] or kt["tied_both"]:
            relation = "agreement_with_ties"
    elif kt["discordant"] > 0:
        relation = "reversal"
    else:
        relation = "tie_loss_of_discrimination"
    return {"relation": relation, **kt}


def run_evaluator_panel(
    *,
    root,
    cfg: dict[str, Any],
    specs: list[dict[str, Any]],
    joint_plan_cap: int = 6,
) -> dict[str, Any]:
    selected, selection_hash = select_panel_specs(specs)
    panel = {
        "selection_hash": selection_hash,
        "episode_ids": [s["episode_id"] for s in selected],
        "joint_plan_cap": joint_plan_cap,
        "cases": [],
        "selection_recorded_before_outcomes": True,
        "modelled_development_diagnostic": True,
        "not_race_truth": True,
        "weights_not_tuned_from_panel": True,
        "tie_aware": True,
        "deduplicates_identical_joint_action_ids": True,
    }
    for spec in selected:
        inst = build_instance_record(cfg=cfg, spec=spec, verify_energies=False, cross_check_simulator=False)
        costs = inst["costs"]
        enum = inst["enumeration"]
        selected_cars = inst["selected_car_ids"]
        menus = inst["action_model"]["menus"]
        a_actions = [CarAction.model_validate(a) for a in menus[selected_cars[0]]]
        b_actions = [CarAction.model_validate(b) for b in menus[selected_cars[1]]]
        candidates: list[tuple[str, CarAction, CarAction, float]] = []
        for m in enum["minimisers"][:1]:
            candidates.append(("exact_proxy_optimum", a_actions[m["i"]], b_actions[m["j"]], m["value"]))
        g = inst["heuristics"]["greedy_local"]["incumbent"]
        if g is not None:
            candidates.append(("greedy_incumbent", a_actions[g["i"]], b_actions[g["j"]], g["value"]))
        if a_actions and b_actions:
            candidates.append(
                ("comparison_first_first", a_actions[0], b_actions[0], score_joint_direct(costs, index_a=0, index_b=0))
            )
            if len(a_actions) > 1 and len(b_actions) > 1:
                candidates.append(
                    (
                        "comparison_last_last",
                        a_actions[-1],
                        b_actions[-1],
                        score_joint_direct(costs, index_a=len(a_actions) - 1, index_b=len(b_actions) - 1),
                    )
                )

        # Deduplicate identical joint action IDs; retain provenance labels.
        unique: list[dict[str, Any]] = []
        by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for label, a, b, proxy_val in candidates:
            key = _pair_key(a, b)
            if key in by_pair:
                by_pair[key]["provenance_labels"].append(label)
                continue
            entry = {
                "provenance_labels": [label],
                "action_a": a,
                "action_b": b,
                "proxy_value": proxy_val,
                "pair_key": list(key),
            }
            by_pair[key] = entry
            unique.append(entry)
        unique = unique[:joint_plan_cap]

        case = {
            "episode_id": spec["episode_id"],
            "family_id": spec["family_id"],
            "regime": spec["checkpoint_request"]["requested_regime"],
            "record_hash": inst["record_hash"],
            "proxy_optimum": enum["exact_proxy_minimum"],
            "evaluations": [],
            "dedup_notes": {
                "raw_candidates": len(candidates),
                "unique_joint_plans": len(unique),
                "duplicate_exact_greedy": any(
                    len(e["provenance_labels"]) > 1 and "exact_proxy_optimum" in e["provenance_labels"] and "greedy_incumbent" in e["provenance_labels"]
                    for e in unique
                ),
            },
        }
        proxy_vals: list[float] = []
        eval_vals: list[float] = []
        for entry in unique:
            a = entry["action_a"]
            b = entry["action_b"]
            ev = evaluate_joint_plan_on_checkpoint(cfg=cfg, spec=spec, action_a=a, action_b=b)
            case["evaluations"].append(
                {
                    "provenance_labels": entry["provenance_labels"],
                    "pair_key": entry["pair_key"],
                    "proxy_value": entry["proxy_value"],
                    "evaluator": ev,
                }
            )
            proxy_vals.append(float(entry["proxy_value"]))
            if ev.get("semantic_legal") and "team_rank_loss_L" in ev:
                eval_vals.append(float(ev["team_rank_loss_L"]))
            else:
                eval_vals.append(float("nan"))

        # Drop NaN evaluator entries for ranking comparison.
        paired = [(p, e) for p, e in zip(proxy_vals, eval_vals) if e == e]
        if len(paired) >= 2:
            p_only = [p for p, _ in paired]
            e_only = [e for _, e in paired]
            # Identify proxy ties / evaluator ties
            proxy_ties = sum(
                1
                for i in range(len(p_only))
                for j in range(i + 1, len(p_only))
                if abs(p_only[i] - p_only[j]) <= TOLERANCE_S
            )
            eval_ties = sum(
                1
                for i in range(len(e_only))
                for j in range(i + 1, len(e_only))
                if abs(e_only[i] - e_only[j]) <= EVALUATOR_RANK_TOLERANCE
            )
            relation = classify_order_relation(p_only, e_only)
            case["proxy_ties_pairs"] = proxy_ties
            case["evaluator_ties_pairs"] = eval_ties
            case["tie_aware_comparison"] = relation
            case["rank_agreement"] = relation["relation"] in {"agreement", "agreement_with_ties"}
        else:
            case["tie_aware_comparison"] = None
            case["rank_agreement"] = None
        panel["cases"].append(case)
    panel["n_cases"] = len(panel["cases"])
    panel["n_agree"] = sum(1 for c in panel["cases"] if c.get("rank_agreement") is True)
    panel["n_disagree_reversal"] = sum(
        1 for c in panel["cases"] if (c.get("tie_aware_comparison") or {}).get("relation") == "reversal"
    )
    panel["n_tie_loss"] = sum(
        1
        for c in panel["cases"]
        if (c.get("tie_aware_comparison") or {}).get("relation") == "tie_loss_of_discrimination"
    )
    panel["panel_hash"] = sha256_json({"selection": selection_hash, "n": panel["n_cases"]})
    return panel

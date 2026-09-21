"""Precision targets and study sizing (Gate F inputs) with executed stratified bootstrap."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from f1q.stage6.config import Phase6Config


def _round_up_multiple_of_8(n: float, floor: int, cap: int) -> dict[str, Any]:
    raw = int(math.ceil(n))
    bal = int(math.ceil(raw / 8.0) * 8)
    bal = max(floor, bal)
    capped = min(cap, bal)
    return {
        "raw": raw,
        "rounded_family_balance": bal,
        "after_floor_cap": capped,
        "exceeds_max": bal > cap,
    }


def mechanism_precision_targets_predeclared(cfg: Phase6Config) -> dict[str, Any]:
    """Justify mechanism/boundary precision targets BEFORE examining calibration outcomes."""
    return {
        "declared_before_calibration_outcomes": True,
        "mechanism_endpoints": {
            "exact_ideal_legal_probability": {
                "target": "report exact value; no sampling precision target",
                "justification": "statevector ideal distribution is deterministic given params",
            },
            "best_of_pool_normalised_regret": {
                "target_halfwidth_per_block_mean": 0.05,
                "units": "normalised_regret_on_A2_proxy_loss",
                "interpretation": (
                    "Block-mean best-of-pool normalised regret vs exact classical; "
                    "saturated-at-zero is informative of exact-incumbent dominance, not superiority."
                ),
                "justification": (
                    "Mechanism boundary endpoint on synthetic A2 loss; looser than operational "
                    "h=0.01 because estimand is circuit-sample regret not race-outcome delta"
                ),
            },
            "strict_improvement_vs_exact": {
                "target": "point estimate with declared tolerance",
                "tolerance": cfg.improvement_tol,
                "justification": "When exact incumbent dominates, estimand is structurally zero",
            },
        },
        "operational_endpoints": {
            "status": "NOT_ELIGIBLE",
            "reason": "Causal operational evaluator not integrated; dossier δ/h sizing NOT_APPLICABLE",
        },
        "do_not_transfer_operational_margin_to_circuit_probs": True,
    }


def size_operational_if_eligible(
    cfg: Phase6Config,
    *,
    paired_block_sd: float | None,
    eligible: bool,
    eligibility_reasons: list[str],
) -> dict[str, Any]:
    if not eligible:
        return {
            "status": "NOT_APPLICABLE",
            "reasons": eligibility_reasons,
            "delta": cfg.superiority_delta,
            "h": cfg.precision_halfwidth,
            "formula_power": "n=((1.96+0.84)*s/delta)^2",
            "formula_precision": "n=(1.96*s/h)^2",
            "note": "Do not use zero variance to assert an 80-block superiority study is powered",
        }
    assert paired_block_sd is not None
    s = float(paired_block_sd)
    n_power = ((1.96 + 0.84) * s / cfg.superiority_delta) ** 2
    n_prec = (1.96 * s / cfg.precision_halfwidth) ** 2
    larger = max(n_power, n_prec)
    rounded = _round_up_multiple_of_8(larger, cfg.test_block_floor, cfg.test_block_max)
    return {
        "status": "ESTIMABLE",
        "s": s,
        "n_power_raw": n_power,
        "n_precision_raw": n_prec,
        "n_selected_raw": larger,
        **rounded,
        "delta": cfg.superiority_delta,
        "h": cfg.precision_halfwidth,
        "uncertainty_in_s": "pilot_only_3_blocks_per_family_high_uncertainty",
    }


def stratified_block_bootstrap(
    block_effects: list[dict[str, Any]],
    *,
    n_boot: int = 2000,
    seed: int = 20260921,
    equal_family_weight: bool = True,
) -> dict[str, Any]:
    """Seeded stratified block bootstrap with equal family weight.

    ``block_effects`` entries: {block_id, family_id, effect} where effect is the
    within-block aggregate (e.g. mean of SC/VSC for a fixed arm).
    """
    if not block_effects:
        return {
            "status": "EMPTY",
            "n_blocks": 0,
            "n_boot": n_boot,
            "seed": seed,
        }
    by_fam: dict[str, list[float]] = {}
    for row in block_effects:
        by_fam.setdefault(row["family_id"], []).append(float(row["effect"]))
    families = sorted(by_fam.keys())
    rng = np.random.default_rng(seed)
    boots: list[float] = []
    for _ in range(n_boot):
        fam_means = []
        for fam in families:
            vals = np.asarray(by_fam[fam], dtype=float)
            draw = rng.choice(vals, size=len(vals), replace=True)
            fam_means.append(float(np.mean(draw)))
        if equal_family_weight:
            boots.append(float(np.mean(fam_means)))
        else:
            # fallback: weight by block count
            weights = [len(by_fam[f]) for f in families]
            boots.append(float(np.average(fam_means, weights=weights)))
    arr = np.asarray(boots, dtype=float)
    point = float(np.mean([float(r["effect"]) for r in block_effects]))
    if equal_family_weight:
        point = float(np.mean([float(np.mean(by_fam[f])) for f in families]))
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return {
        "status": "EXECUTED",
        "n_blocks": len(block_effects),
        "n_families": len(families),
        "blocks_per_family": {f: len(by_fam[f]) for f in families},
        "n_boot": n_boot,
        "seed": seed,
        "equal_family_weight": equal_family_weight,
        "pairing_preserved": True,
        "point_estimate": point,
        "bootstrap_mean": float(np.mean(arr)),
        "bootstrap_std": float(np.std(arr, ddof=1)),
        "ci95": [float(lo), float(hi)],
        "halfwidth_ci95": float((hi - lo) / 2.0),
        "missing_excluded_handling": "blocks_without_effect_omitted_before_call",
    }


def build_block_effects_from_summaries(
    summaries: list[dict[str, Any]],
    *,
    arm_key: str = "C1_p1:learned",
) -> list[dict[str, Any]]:
    """Average SC/VSC within parent block for one arm; preserve pairing."""
    by_block: dict[str, dict[str, Any]] = {}
    for s in summaries:
        regs = s.get("mean_regret_by_arm") or {}
        val = regs.get(arm_key)
        if val is None and regs:
            # Prefer any C1_p1 learned-like key
            for k, v in regs.items():
                if "C1_p1" in k and "learned" in k:
                    val = v
                    arm_key = k
                    break
            if val is None:
                val = next(iter(regs.values()))
        if val is None:
            continue
        bid = s["block_id"]
        slot = by_block.setdefault(
            bid,
            {"block_id": bid, "family_id": s["family_id"], "vals": [], "arm_key": arm_key},
        )
        slot["vals"].append(float(val))
    out = []
    for bid, slot in sorted(by_block.items()):
        out.append(
            {
                "block_id": bid,
                "family_id": slot["family_id"],
                "effect": float(np.mean(slot["vals"])),
                "n_checkpoints": len(slot["vals"]),
                "arm_key": slot["arm_key"],
            }
        )
    return out


def recommend_independent_blocks_for_precision(
    *,
    observed_halfwidth: float,
    target_halfwidth: float,
    n_blocks_observed: int,
    floor: int,
    cap: int,
) -> dict[str, Any]:
    """Scale observed bootstrap halfwidth ~ 1/sqrt(n) to meet target (mechanism only)."""
    if observed_halfwidth <= 0:
        return {
            "status": "DEGENERATE_ZERO_OBSERVED_HALFWIDTH",
            "note": (
                "Zero observed variance does not imply population homogeneity or justify "
                "an 80-block superiority study. For saturated-at-zero regret, precision "
                "target is met vacuously for that estimand; recommended count remains a "
                "protocol design choice, not a powered superiority sample size."
            ),
            "suggested_held_out_mechanism_blocks": floor,
            "justification": "protocol_floor_not_variance_powered_superiority",
            "target_halfwidth": target_halfwidth,
            "observed_halfwidth": observed_halfwidth,
            "n_blocks_observed": n_blocks_observed,
        }
    # hw_obs ≈ c/sqrt(n_obs) ⇒ n_need ≈ n_obs * (hw_obs/target)^2
    n_need = n_blocks_observed * (observed_halfwidth / target_halfwidth) ** 2
    rounded = _round_up_multiple_of_8(n_need, floor, cap)
    return {
        "status": "DERIVED_FROM_PILOT_BOOTSTRAP",
        "target_halfwidth": target_halfwidth,
        "observed_halfwidth": observed_halfwidth,
        "n_blocks_observed": n_blocks_observed,
        "n_need_raw": float(n_need),
        **rounded,
        "suggested_held_out_mechanism_blocks": rounded["after_floor_cap"],
        "limitation": "Only 3 calibration blocks/family — high uncertainty in s and halfwidth",
    }


def size_from_pilot_summaries(cfg: Phase6Config, pilot_receipt: dict[str, Any]) -> dict[str, Any]:
    """Post-pilot sizing with executed stratified bootstrap (not a string placeholder)."""
    summaries = pilot_receipt.get("summaries") or []
    block_effects = build_block_effects_from_summaries(summaries)
    boot = stratified_block_bootstrap(block_effects, n_boot=2000, seed=20260921)

    headroom_zero = pilot_receipt.get("development_headroom") == "ZERO"
    op_eligible = False
    reasons = [
        "CAUSAL_OPERATIONAL_READINESS=false",
        "operational independent evaluator campaign not available in Phase 6",
    ]
    if headroom_zero:
        reasons.append("DEVELOPMENT_HEADROOM=ZERO on calibration cases with exact incumbent")
        reasons.append("headroom gate blocks H1 superiority before test access")

    operational = size_operational_if_eligible(
        cfg, paired_block_sd=None, eligible=op_eligible, eligibility_reasons=reasons
    )

    targets = mechanism_precision_targets_predeclared(cfg)
    target_hw = float(
        targets["mechanism_endpoints"]["best_of_pool_normalised_regret"]["target_halfwidth_per_block_mean"]
    )
    rec = recommend_independent_blocks_for_precision(
        observed_halfwidth=float(boot.get("halfwidth_ci95") or 0.0),
        target_halfwidth=target_hw,
        n_blocks_observed=int(boot.get("n_blocks") or 0),
        floor=cfg.test_block_floor,
        cap=cfg.test_block_max,
    )

    # Endpoint saturation diagnostic
    effects = [float(r["effect"]) for r in block_effects]
    saturated_zero = bool(effects) and all(abs(e) <= 1e-12 for e in effects)

    mech = {
        "n_blocks_observed": len(block_effects),
        "blocks_per_family_nominal": 3,
        "limitation": "Only 3 calibration blocks/family — pilot uncertainty is large",
        "block_effects": block_effects,
        "stratified_bootstrap": boot,
        "precision_targets": targets,
        "independent_block_recommendation": rec,
        "endpoint_saturation": {
            "best_of_pool_regret_identically_zero": saturated_zero,
            "note": (
                "If saturated at zero under exact incumbent, the endpoint is informative of "
                "zero proxy headroom; do not swap endpoints post-calibration."
            ),
        },
    }

    mc = {
        "status": "NOT_ESTIMABLE_FOR_OPERATIONAL_WORLDS",
        "reason": (
            "Eligible simulator-outcome pilot requires operational evaluator with separate "
            "train/online/final random banks and event-keyed CRN; unavailable/unaffordable here. "
            "Do not substitute surrogate A2 objective variation for simulated race-outcome uncertainty."
        ),
        "dossier_world_candidates": cfg.mc_world_candidates,
        "preflight": "blocked",
    }

    return {
        "mechanism": mech,
        "operational_superiority_sizing": operational,
        "monte_carlo_operational": mc,
        "headroom_gate": {
            "DEVELOPMENT_HEADROOM": pilot_receipt.get("development_headroom"),
            "SUPERIORITY_PATH_AVAILABLE": False,
            "do_not_power_impossible_superiority": True,
            "do_not_use_zero_variance_for_80_block_floor": True,
        },
        "proposed_phase7_test_blocks_if_mechanism_only": {
            "note": "Mechanism/boundary study — not H1 superiority",
            "calibration_reuse_forbidden_as_final_test": True,
            "independent_unit": "block",
            "suggested_held_out_mechanism_blocks_if_amended": rec.get(
                "suggested_held_out_mechanism_blocks", cfg.test_block_floor
            ),
            "not_80_cases_without_pairing_disclosure": True,
            "requires_dated_amendment_before_final_test_access": True,
            "derivation": rec.get("status"),
        },
        "precision_analysis_executed": boot.get("status") == "EXECUTED",
    }

"""Precision targets and study sizing (Gate F inputs) — declared before outcome peeking where required."""

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


def size_from_pilot_summaries(cfg: Phase6Config, pilot_receipt: dict[str, Any]) -> dict[str, Any]:
    """Post-pilot sizing. Operational path remains NOT_APPLICABLE under zero headroom / causal gap."""
    summaries = pilot_receipt.get("summaries") or []
    # Block-level paired structure: average SC/VSC within block for a representative arm
    by_block: dict[str, list[float]] = {}
    for s in summaries:
        regs = s.get("mean_regret_by_arm") or {}
        # Use learned C1_p1 if present else first arm
        val = regs.get("C1_p1:learned")
        if val is None and regs:
            val = next(iter(regs.values()))
        if val is None:
            continue
        by_block.setdefault(s["block_id"], []).append(float(val))
    block_means = [float(np.mean(v)) for v in by_block.values() if v]
    s_mech = float(np.std(block_means, ddof=1)) if len(block_means) > 1 else 0.0

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

    # Mechanism precision for actual endpoints (not operational δ)
    mech = {
        "n_blocks_observed": len(block_means),
        "blocks_per_family_nominal": 3,
        "limitation": "Only 3 calibration blocks/family — pilot uncertainty is large",
        "block_mean_sd_mechanism_regret": s_mech,
        "stratified_bootstrap": "preserve SC/VSC pairing and policy seeds within blocks; equal family weight",
        "precision_targets": mechanism_precision_targets_predeclared(cfg),
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
            "suggested_held_out_mechanism_blocks_if_amended": 80,
            "requires_dated_amendment_before_final_test_access": True,
        },
    }

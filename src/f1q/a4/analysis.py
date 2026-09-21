"""Calibration q, bootstrap, Gate E/F, Stage 7 sizing. Recomputed, not trusted booleans."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from f1q.a4.contracts import PRIMARY_BUDGET_S, StructuralError
from f1q.hashing import sha256_json


def finite_sample_q(residuals: list[float], *, p: float = 0.95) -> dict[str, Any]:
    """One-sided conformal/order-statistic rule: index ceil((n+1)*p) clipped to n.

    For n=24, p=0.95 this is the **maximum** residual, not a NumPy interpolated percentile.
    """
    vals = [float(x) for x in residuals]
    n = len(vals)
    if n == 0:
        raise StructuralError("CALIBRATION", "no block residuals for q")
    k = min(n, int(math.ceil((n + 1) * float(p))))
    ordered = sorted(vals)
    q = ordered[k - 1]
    return {
        "n": n,
        "p": float(p),
        "index_one_based": k,
        "formula": "ceil((n+1)*p) clipped to n",
        "q": q,
        "is_maximum": k == n,
        "ordered": ordered,
        "not_numpy_interpolated_percentile": True,
        "consequence_n24_p95": "for n=24 this is the maximum residual",
    }


def mc_allowance(paired_diffs: list[float], *, z: float = 1.96) -> dict[str, Any]:
    arr = np.asarray(paired_diffs, dtype=float)
    if arr.size == 0:
        return {"allowance": 0.0, "n": 0, "std": None, "halfwidth": None}
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    hw = z * std / math.sqrt(arr.size)
    return {"allowance": hw, "n": int(arr.size), "std": std, "halfwidth": hw, "rule": "z*s/sqrt(n) from paired per-world losses"}


def stratified_block_bootstrap(
    block_effects: list[float],
    *,
    n_boot: int = 2000,
    seed: int = 20260921,
) -> dict[str, Any]:
    rng = np.random.default_rng(int(seed))
    arr = np.asarray(block_effects, dtype=float)
    n = arr.size
    if n == 0:
        return {"mean": None, "ci95": None, "n_boot": n_boot, "seed": seed, "n_blocks": 0}
    means = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, size=n)
        means.append(float(arr[idx].mean()))
    lo, hi = float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))
    return {
        "mean": float(arr.mean()),
        "ci95": [lo, hi],
        "n_boot": int(n_boot),
        "seed": int(seed),
        "n_blocks": n,
        "block_effects": [float(x) for x in arr],
        "independent_unit": "parent_block",
    }


def stage7_block_sizing(
    block_effects: list[float],
    *,
    floor: int = 80,
    ceiling: int = 160,
    target_halfwidth: float = 0.01,
) -> dict[str, Any]:
    arr = np.asarray(block_effects, dtype=float)
    n = max(arr.size, 1)
    s = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    # n ≈ (1.96 s / hw)^2
    if s <= 0 or target_halfwidth <= 0:
        required = floor
    else:
        required = int(math.ceil((1.96 * s / target_halfwidth) ** 2))
    rounded = int(8 * math.ceil(required / 8.0))  # family-balance rounding
    recommended = min(ceiling, max(floor, rounded))
    exceeds = required > ceiling
    return {
        "s": s,
        "n_observed_blocks": int(arr.size),
        "required_raw": required,
        "family_balance_rounded": rounded,
        "floor": floor,
        "ceiling": ceiling,
        "recommended_blocks": recommended,
        "exceeds_ceiling": exceeds,
        "analysis_classification": "estimation_only" if exceeds else "powered_boundary_candidate",
        "simulated_planned_block_analysis": True,
        "not_a_powered_superiority_design_if_exceeds_160": exceeds,
    }


def choose_mc_world_target(halfwidths_2048: list[float]) -> dict[str, Any]:
    arr = np.asarray(halfwidths_2048, dtype=float)
    if arr.size == 0:
        return {"target": 2048, "reason": "no_diagnostics", "frac_le_0_02": None}
    frac = float(np.mean(arr <= 0.02))
    p90 = float(np.quantile(arr, 0.90))
    if frac >= 0.90:
        target = 2048
        reason = "95pct_halfwidth_<=0.02_at_>=90pct_checkpoints"
    elif p90 <= 0.04:
        target = 8192
        reason = "extrapolated_need_8192"
    else:
        target = 32768
        reason = "extrapolated_need_32768"
    return {
        "target": target,
        "frac_le_0_02": frac,
        "p90_halfwidth": p90,
        "reason": reason,
        "candidates": [2048, 8192, 32768],
        "phase6_did_not_execute_all_three": True,
    }


def derive_gate_e(
    *,
    proxy_headroom_zero: bool,
    quantum_incremental_evaluated_cases: int,
    n_matched_k: int,
    boundary_question_survives: bool,
    mechanism_distinguishable: bool,
) -> dict[str, Any]:
    superiority = False
    superiority_reason = "PROXY_HEADROOM_ZERO" if proxy_headroom_zero else "not_claimed"
    if quantum_incremental_evaluated_cases <= 0 or n_matched_k <= 0:
        gate = "FAIL_NO_SURVIVING_QUESTION"
        boundary = False
        reason = "treatment did not reach the evaluated K-set"
    elif not mechanism_distinguishable and not boundary_question_survives:
        gate = "FAIL_NO_SURVIVING_QUESTION"
        boundary = False
        reason = "quantum treatment structurally or empirically indistinguishable; no boundary contribution"
    elif boundary_question_survives:
        gate = "PASS_BOUNDARY_MECHANISM"
        boundary = True
        reason = "matched-K experiment supports a nontrivial boundary/mechanism question; superiority path closed"
    else:
        gate = "FAIL_NO_SURVIVING_QUESTION"
        boundary = False
        reason = "no surviving justified boundary question"
    return {
        "GATE_E_SCIENTIFIC_VALUE": gate,
        "SUPERIORITY_PATH_AVAILABLE": superiority,
        "BOUNDARY_MECHANISM_PATH_AVAILABLE": boundary,
        "reason": reason,
        "superiority_reason": superiority_reason,
        "proxy_headroom_zero": proxy_headroom_zero,
        "quantum_incremental_evaluated_cases": quantum_incremental_evaluated_cases,
        "n_matched_k": n_matched_k,
    }


def derive_gate_f(
    *,
    n_calib_parents: int,
    q_record: dict[str, Any] | None,
    sizing: dict[str, Any] | None,
    admission_ok: bool,
    resources_fit: bool,
    precision_met: bool,
) -> dict[str, Any]:
    ok = (
        n_calib_parents == 24
        and q_record is not None
        and sizing is not None
        and admission_ok
        and resources_fit
    )
    if not ok:
        status = "FAIL"
        ready = False
        reason = "missing calibration parents, q, sizing, admission, or resource fit"
    elif not precision_met:
        status = "FAIL"
        ready = False
        reason = "precision target not met; Stage 7 estimation-only or not ready"
    else:
        status = "PASS_BOUNDARY_RESOURCES"
        ready = True
        reason = "local precision and resources support a Stage 7 boundary design; not authorised"
    return {
        "GATE_F_LOCAL_PRECISION_AND_RESOURCES": status,
        "PHASE_7_BOUNDARY_STUDY_READY": ready,
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "PHASE_7_AUTHORISED": False,
        "reason": reason,
        "n_calib_parents": n_calib_parents,
    }


def claims_ledger(*, gate_e: dict[str, Any], gate_f: dict[str, Any], proxy_headroom: str) -> dict[str, Any]:
    allowed = [
        "local_simulator_mechanism_description",
        "engineering_repair_and_admission_measurement",
        "development_calibration_block_effects_labelled_as_such",
    ]
    prohibited = [
        "quantum_advantage",
        "F1_calibration",
        "hardware_readiness",
        "scientific_novelty_unverified",
        "IBM_or_device_noise",
        "provider_latency",
        "certified_quantum_optimum",
        "final_test_confirmation",
        "superiority_with_zero_proxy_headroom",
    ]
    if gate_e.get("GATE_E_SCIENTIFIC_VALUE") == "PASS_BOUNDARY_MECHANISM":
        allowed.append("boundary_mechanism_question_for_future_phase7_design")
    return {
        "allowed": allowed,
        "prohibited": prohibited,
        "not_yet_literature_verified": ["novelty_status"],
        "proxy_headroom": proxy_headroom,
        "hash": sha256_json({"allowed": allowed, "prohibited": prohibited, "e": gate_e, "f": gate_f}),
    }

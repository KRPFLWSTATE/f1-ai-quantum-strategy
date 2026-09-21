"""Separate frozen scenario latency from measured local compute time.

Scenario latency advances the simulated race and is keyed by case/option/budget/seed.
Isolated local compute latency is reported separately and is never called provider latency.
"""

from __future__ import annotations

from typing import Any

from f1q.hashing import sha256_json


def modelled_algorithm_latency_s(
    *,
    prepare_s: float,
    n_qubits: int,
    n_legal: int,
    family: str | None,
    p_depth: int,
    pool_draws: int,
    n_plans: int,
    n_planning_worlds: int,
    n_evaluation_worlds: int,
) -> dict[str, float]:
    """Deterministic modelled component times. No component is hard-coded to zero."""
    obs_s = max(1e-6, 0.05 * float(prepare_s))
    feature_s = max(1e-6, 0.02 * float(prepare_s))
    encoding_s = max(1e-6, 0.25 * float(prepare_s))
    incumbent_s = max(1e-6, 1e-4 * max(n_legal, 1))
    donor_infer_s = max(1e-6, 5e-4)
    if family == "C0":
        circuit_s = max(1e-5, 2e-7 * (1 << min(int(n_qubits), 20)) * max(int(p_depth), 1))
    elif family == "C1":
        circuit_s = max(1e-5, 5e-6 * max(n_legal, 1) * max(int(p_depth), 1))
    else:
        circuit_s = 1e-5
    decode_s = max(1e-6, 2e-7 * int(pool_draws))
    validation_s = max(1e-6, 2e-5 * max(n_plans, 1))
    fallback_s = 1e-5
    planning_s = max(1e-6, 8e-4 * max(n_plans, 1) * max(n_planning_worlds, 1))
    evaluation_s = max(1e-6, 8e-4 * max(n_evaluation_worlds, 1))
    serial = (
        obs_s
        + feature_s
        + encoding_s
        + incumbent_s
        + donor_infer_s
        + circuit_s
        + decode_s
        + validation_s
        + fallback_s
        + planning_s
        + evaluation_s
    )
    # Overlap: circuit/decode cannot overlap encoding; planning/eval sequential after decode.
    overlapped = (
        max(obs_s, feature_s)
        + encoding_s
        + max(incumbent_s, donor_infer_s)
        + circuit_s
        + decode_s
        + validation_s
        + planning_s
        + evaluation_s
        + fallback_s
    )
    return {
        "observation_state_s": obs_s,
        "features_s": feature_s,
        "encoding_s": encoding_s,
        "incumbent_search_s": incumbent_s,
        "donor_inference_s": donor_infer_s,
        "circuit_sim_s": circuit_s,
        "candidate_decoding_s": decode_s,
        "downstream_scoring_s": planning_s,
        "validation_s": validation_s,
        "fallback_s": fallback_s,
        "evaluation_s": evaluation_s,
        "serial_sum_s": serial,
        "overlapped_critical_path_s": overlapped,
        "never_divide_paired_turnaround_by_two": True,
    }


def frozen_scenario_latency_s(
    *,
    case_hash: str,
    option: str,
    budget_s: float,
    seed: int,
    modelled_s: float,
) -> float:
    """Reproducible scenario delay. Not this-execution wall time. Not provider latency."""
    digest = sha256_json(
        {
            "case_hash": case_hash,
            "option": option,
            "budget_s": float(budget_s),
            "seed": int(seed),
            "kind": "a4.frozen_scenario_latency.v1",
        }
    )
    u = int(digest[:8], 16) / 0xFFFFFFFF
    # Small keyed modulation around the model so two executions of the same key match.
    return float(modelled_s) * (0.97 + 0.06 * u)


def reconcile_timing(components: dict[str, float], *, atol: float = 1e-6) -> dict[str, Any]:
    serial_keys = [
        "observation_state_s",
        "features_s",
        "encoding_s",
        "incumbent_search_s",
        "donor_inference_s",
        "circuit_sim_s",
        "candidate_decoding_s",
        "downstream_scoring_s",
        "validation_s",
        "fallback_s",
        "evaluation_s",
    ]
    serial = sum(float(components.get(k) or 0.0) for k in serial_keys)
    claimed = float(components.get("serial_sum_s") or serial)
    overlap = float(components.get("overlapped_critical_path_s") or claimed)
    ok = abs(serial - claimed) <= atol + 1e-9 * max(1.0, abs(claimed))
    if overlap > serial + atol:
        ok = False
    zeros = [k for k in serial_keys if float(components.get(k) or 0.0) == 0.0]
    return {
        "ok": ok and not zeros,
        "recomputed_serial_s": serial,
        "claimed_serial_s": claimed,
        "overlapped_critical_path_s": overlap,
        "hardcoded_zero_components": zeros,
        "never_divide_paired_turnaround_by_two": True,
        "not_provider_latency": True,
    }

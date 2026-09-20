"""Efficient ideal statevector helpers with cached diagonals."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from f1q.stage5.circuits_c0 import apply_diag_phase, apply_rx_mixer, plus_state
from f1q.stage5.circuits_c1 import apply_c1_mixer, prepare_one_hot_uniform
from f1q.stage5.model import A2Instance
from f1q.stage5.qubo import qubo_energy


def cost_diags_from_qubo(qubo: dict[str, Any], *, scaled: bool = True) -> np.ndarray:
    n = int(qubo["n"])
    dim = 1 << n
    diags = np.empty(dim, dtype=float)
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    offset = float(qubo["offset_scaled"] if scaled else qubo["offset"])
    # Fast enumerate
    for b in range(dim):
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=float)
        e = offset
        for i in range(n):
            if x[i] == 0:
                continue
            e += Q[i, i]
            for j in range(i + 1, n):
                if x[j]:
                    e += Q[i, j]
        diags[b] = e
    return diags


def simulate_c0_cached(diags: np.ndarray, n: int, gammas: list[float], betas: list[float]) -> dict[str, Any]:
    state = plus_state(n)
    for g, b in zip(gammas, betas):
        state = apply_diag_phase(state, diags, float(g))
        state = apply_rx_mixer(state, n, float(b))
    probs = np.abs(state) ** 2
    return {
        "family": "C0",
        "p": len(gammas),
        "n": n,
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(probs, diags)),
        "param_count": 2 * len(gammas),
    }


def simulate_c1_cached(
    instance: A2Instance,
    diags: np.ndarray,
    init_state: np.ndarray,
    gammas: list[float],
    betas: list[float],
) -> dict[str, Any]:
    state = init_state.copy()
    for g, b in zip(gammas, betas):
        state = apply_diag_phase(state, diags, float(g))
        state = apply_c1_mixer(state, instance, float(b))
    probs = np.abs(state) ** 2
    return {
        "family": "C1",
        "p": len(gammas),
        "n": int(np.log2(diags.size)),
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(probs, diags)),
        "param_count": 2 * len(gammas),
    }

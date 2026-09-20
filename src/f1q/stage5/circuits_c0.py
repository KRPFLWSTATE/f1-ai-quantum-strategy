"""C0 transverse-X mixer QAOA and shared circuit utilities (local Qiskit only)."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.qubo import qubo_energy


def cost_unitary_diags(qubo: dict[str, Any], *, scaled: bool = True) -> np.ndarray:
    """Diagonal of cost Hamiltonian in computational basis (length 2^n)."""
    n = int(qubo["n"])
    dim = 1 << n
    diags = np.zeros(dim, dtype=float)
    for b in range(dim):
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=float)
        diags[b] = qubo_energy(qubo, x, scaled=scaled)
    return diags


def apply_diag_phase(state: np.ndarray, diags: np.ndarray, gamma: float) -> np.ndarray:
    return state * np.exp(-1j * gamma * diags)


def apply_rx_mixer(state: np.ndarray, n: int, beta: float) -> np.ndarray:
    """Tensor-product RX(2β) on each qubit (transverse-X mixer)."""
    # RX(θ) = [[cos(θ/2), -i sin(θ/2)], [-i sin(θ/2), cos(θ/2)]] with θ=2β
    c = np.cos(beta)
    s = np.sin(beta)
    out = state.astype(complex).copy()
    for q in range(n):
        step = 1 << q
        # Pair amplitudes differing at bit q
        new = out.copy()
        for b in range(1 << n):
            if (b & step) == 0:
                i0 = b
                i1 = b | step
                a0, a1 = out[i0], out[i1]
                new[i0] = c * a0 - 1j * s * a1
                new[i1] = -1j * s * a0 + c * a1
        out = new
    return out


def plus_state(n: int) -> np.ndarray:
    dim = 1 << n
    return np.ones(dim, dtype=complex) / np.sqrt(dim)


def simulate_c0(
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    scaled: bool = True,
) -> dict[str, Any]:
    n = int(qubo["n"])
    assert len(gammas) == len(betas)
    p = len(gammas)
    diags = cost_unitary_diags(qubo, scaled=scaled)
    state = plus_state(n)
    for layer in range(p):
        state = apply_diag_phase(state, diags, float(gammas[layer]))
        state = apply_rx_mixer(state, n, float(betas[layer]))
    probs = np.abs(state) ** 2
    norm = float(np.sum(probs))
    exp = float(np.dot(probs, diags))
    return {
        "family": "C0",
        "p": p,
        "n": n,
        "state": state,
        "probs": probs,
        "norm": norm,
        "expectation_scaled": exp,
        "param_count": 2 * p,
        "init": "plus",
    }


def c0_param_count(p: int) -> int:
    return 2 * p

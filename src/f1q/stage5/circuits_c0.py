"""C0 transverse-X mixer QAOA with actual inspectable Qiskit circuits."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.qubo import qubo_energy


def cost_unitary_diags(qubo: dict[str, Any], *, scaled: bool = True) -> np.ndarray:
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
    c = np.cos(beta)
    s = np.sin(beta)
    out = state.astype(complex).copy()
    for q in range(n):
        step = 1 << q
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
    return {
        "family": "C0",
        "p": p,
        "n": n,
        "state": state,
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(probs, diags)),
        "param_count": 2 * p,
        "init": "plus",
    }


def build_c0_qiskit_circuit(
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    scaled: bool = True,
):
    """Actual C0 circuit: H^n init, QUBO cost as Phase/CPhase (RZ/RZZ-equiv), RX mixer."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import PhaseGate, CPhaseGate

    n = int(qubo["n"])
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    offset = float(qubo["offset_scaled"] if scaled else qubo["offset"])
    qc = QuantumCircuit(n, name="C0_actual")
    # Init |+>^n
    for q in range(n):
        qc.h(q)
    n_cost_1q = 0
    n_cost_2q = 0
    for g, b in zip(gammas, betas):
        g = float(g)
        # Global phase from offset ignored for observables
        _ = offset
        for i in range(n):
            if Q[i, i] != 0.0:
                # PhaseGate(θ)|1> = e^{iθ}|1>; want e^{-i g Q_ii} on |1>
                qc.append(PhaseGate(-g * float(Q[i, i])), [i])
                n_cost_1q += 1
            for j in range(i + 1, n):
                if Q[i, j] != 0.0:
                    qc.append(CPhaseGate(-g * float(Q[i, j])), [i, j])
                    n_cost_2q += 1
        for q in range(n):
            qc.rx(2.0 * float(b), q)
    return {
        "circuit": qc,
        "n": n,
        "cost_1q_gates": n_cost_1q,
        "cost_2q_gates": n_cost_2q,
        "mixer_1q_gates": n * len(betas),
        "has_quadratic_interactions": int(qubo.get("n_quadratic_terms", 0)) > 0,
        "init": "H^n",
        "mixer": "transverse_X_RX",
        "cost_encoding": "Phase_and_CPhase_from_actual_QUBO",
    }


def c0_param_count(p: int) -> int:
    return 2 * p

"""C1 one-hot XY-exchange mixer QAOA for A2 action blocks."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.circuits_c0 import apply_diag_phase, cost_unitary_diags
from f1q.stage5.encode import binary_to_policy, variable_index_map
from f1q.stage5.model import A2Instance


def one_hot_feasible_mask(instance: A2Instance) -> np.ndarray:
    n = instance.n_logical_vars()
    dim = 1 << n
    mask = np.zeros(dim, dtype=bool)
    for b in range(dim):
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        mask[b] = binary_to_policy(instance, x) is not None
    return mask


def prepare_one_hot_uniform(instance: A2Instance) -> np.ndarray:
    """Uniform superposition over one-hot-feasible bitstrings (prep counted in resources).

    Init is NOT a global-phase eigenvector of the cost diagonal restricted to feasible
    subspace in general — first cost parameter remains effective.
    """
    mask = one_hot_feasible_mask(instance)
    idx = np.flatnonzero(mask)
    state = np.zeros(mask.size, dtype=complex)
    if idx.size == 0:
        return state
    state[idx] = 1.0 / np.sqrt(idx.size)
    return state


def _xy_exchange(state: np.ndarray, i: int, j: int, beta: float) -> np.ndarray:
    """Partial swap / XY exchange on qubits i,j: rotates |10> ↔ |01>."""
    # On subspace span{|01>,|10>}: RY-like exchange
    c = np.cos(beta)
    s = np.sin(beta)
    n = int(np.log2(state.size))
    bit_i = 1 << i
    bit_j = 1 << j
    out = state.copy()
    seen = set()
    for b in range(1 << n):
        bi = (b & bit_i) != 0
        bj = (b & bit_j) != 0
        if bi == bj:
            continue
        # partner flips both bits
        partner = b ^ bit_i ^ bit_j
        if b in seen or partner in seen:
            continue
        seen.add(b)
        seen.add(partner)
        # Order: lower index as |01> style — use bit_i set as first
        if bi and not bj:
            a10, a01 = state[b], state[partner]
            out[b] = c * a10 - 1j * s * a01
            out[partner] = -1j * s * a10 + c * a01
        else:
            a01, a10 = state[b], state[partner]
            out[b] = c * a01 - 1j * s * a10
            out[partner] = -1j * s * a01 + c * a10
    return out


def apply_c1_mixer(state: np.ndarray, instance: A2Instance, beta: float) -> np.ndarray:
    """Within each action block, connected-ring XY exchanges (exactly one excitation preserved)."""
    vmap = variable_index_map(instance)
    out = state
    for block in vmap["blocks"]:
        idxs = list(range(block["start"], block["end"]))
        if len(idxs) < 2:
            continue
        # Ring: (0,1), (1,2), ..., (k-1,0)
        for a, b in zip(idxs, idxs[1:] + idxs[:1]):
            out = _xy_exchange(out, a, b, beta)
    return out


def simulate_c1(
    instance: A2Instance,
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    scaled: bool = True,
) -> dict[str, Any]:
    n = int(qubo["n"])
    p = len(gammas)
    diags = cost_unitary_diags(qubo, scaled=scaled)
    state = prepare_one_hot_uniform(instance)
    prep_qubits = n
    prep_two_qubit_gates_est = sum(max(0, b["size"] - 1) for b in variable_index_map(instance)["blocks"])
    for layer in range(p):
        state = apply_diag_phase(state, diags, float(gammas[layer]))
        state = apply_c1_mixer(state, instance, float(betas[layer]))
    probs = np.abs(state) ** 2
    mask = one_hot_feasible_mask(instance)
    # Amplitude outside one-hot blocks (should stay ~0)
    outside = float(np.sum(probs[~mask]))
    return {
        "family": "C1",
        "p": p,
        "n": n,
        "state": state,
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(probs, diags)),
        "param_count": 2 * p,
        "init": "one_hot_uniform",
        "amp_outside_one_hot": outside,
        "prep": {
            "counted": True,
            "logical_qubits": prep_qubits,
            "estimated_2q_gates": prep_two_qubit_gates_est,
        },
    }


def feasible_graph_edges(instance: A2Instance) -> list[tuple[int, int]]:
    """Edges of one-hot feasible graph under single within-block exchanges."""
    mask = one_hot_feasible_mask(instance)
    feasible = np.flatnonzero(mask)
    edges = []
    vmap = variable_index_map(instance)
    for b in feasible:
        for block in vmap["blocks"]:
            idxs = list(range(block["start"], block["end"]))
            bits_on = [q for q in idxs if (b >> q) & 1]
            if len(bits_on) != 1:
                continue
            on = bits_on[0]
            for q in idxs:
                if q == on:
                    continue
                # exchange on↔q
                nb = b ^ (1 << on) ^ (1 << q)
                if mask[nb] and b < nb:
                    edges.append((int(b), int(nb)))
    return edges

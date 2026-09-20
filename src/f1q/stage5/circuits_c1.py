"""C1 one-hot XY-exchange mixer QAOA with actual inspectable circuits and graph proofs."""

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
    mask = one_hot_feasible_mask(instance)
    idx = np.flatnonzero(mask)
    state = np.zeros(mask.size, dtype=complex)
    if idx.size == 0:
        return state
    state[idx] = 1.0 / np.sqrt(idx.size)
    return state


def scheduled_ring_edges(instance: A2Instance) -> list[tuple[int, int]]:
    """Actual scheduled within-block ring-exchange qubit pairs."""
    edges: list[tuple[int, int]] = []
    vmap = variable_index_map(instance)
    for block in vmap["blocks"]:
        idxs = list(range(block["start"], block["end"]))
        if len(idxs) < 2:
            continue
        for a, b in zip(idxs, idxs[1:] + idxs[:1]):
            edges.append((int(a), int(b)))
    return edges


def _xy_exchange(state: np.ndarray, i: int, j: int, beta: float) -> np.ndarray:
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
        partner = b ^ bit_i ^ bit_j
        if b in seen or partner in seen:
            continue
        seen.add(b)
        seen.add(partner)
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
    out = state
    for a, b in scheduled_ring_edges(instance):
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
    """Edges induced by ACTUAL scheduled ring exchanges on one-hot feasible bitstrings."""
    mask = one_hot_feasible_mask(instance)
    feasible = np.flatnonzero(mask)
    edges = []
    ring = scheduled_ring_edges(instance)
    for b in feasible:
        for qi, qj in ring:
            bi = (int(b) >> qi) & 1
            bj = (int(b) >> qj) & 1
            if bi == bj:
                continue
            nb = int(b) ^ (1 << qi) ^ (1 << qj)
            if mask[nb] and int(b) < nb:
                edges.append((int(b), nb))
    return edges


def connected_components_of_transition_graph(instance: A2Instance) -> dict[str, Any]:
    """Connected components of the ACTUAL transition graph (not merely nonempty edge list)."""
    mask = one_hot_feasible_mask(instance)
    nodes = [int(x) for x in np.flatnonzero(mask)]
    adj: dict[int, set[int]] = {n: set() for n in nodes}
    for u, v in feasible_graph_edges(instance):
        adj[u].add(v)
        adj[v].add(u)
    seen: set[int] = set()
    comps: list[list[int]] = []
    for n0 in nodes:
        if n0 in seen:
            continue
        stack = [n0]
        comp = []
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            comp.append(u)
            stack.extend(adj[u] - seen)
        comps.append(sorted(comp))
    # Per action-block: one-hot states within a block of size k form a complete graph under ring
    # if ring connects all qubits — ring on k>=2 is connected ⇒ one component per block subspace product
    return {
        "n_nodes": len(nodes),
        "n_edges": len(feasible_graph_edges(instance)),
        "n_components": len(comps),
        "component_sizes": [len(c) for c in comps],
        "is_connected": len(comps) <= 1,
        "proof": "BFS_connected_components_on_actual_scheduled_ring_transition_graph",
    }


def broken_schedule_disconnects(instance: A2Instance) -> dict[str, Any]:
    """Adversarial: intentionally broken schedule (drop ring edges) must fail connectivity."""
    mask = one_hot_feasible_mask(instance)
    nodes = [int(x) for x in np.flatnonzero(mask)]
    # Use only first edge of each block — typically disconnects k>2 rings
    vmap = variable_index_map(instance)
    broken_edges: list[tuple[int, int]] = []
    for block in vmap["blocks"]:
        idxs = list(range(block["start"], block["end"]))
        if len(idxs) >= 2:
            broken_edges.append((idxs[0], idxs[1]))  # omit closing ring edge and others
    adj: dict[int, set[int]] = {n: set() for n in nodes}
    for b in nodes:
        for qi, qj in broken_edges:
            bi = (b >> qi) & 1
            bj = (b >> qj) & 1
            if bi == bj:
                continue
            nb = b ^ (1 << qi) ^ (1 << qj)
            if mask[nb]:
                adj[b].add(nb)
    seen: set[int] = set()
    n_comps = 0
    for n0 in nodes:
        if n0 in seen:
            continue
        n_comps += 1
        stack = [n0]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(adj[u] - seen)
    # For block size 2, single edge still connects; for size>=3 broken should disconnect product space
    max_block = max((b["size"] for b in vmap["blocks"]), default=0)
    expect_fail = max_block >= 3
    return {
        "n_components_broken": n_comps,
        "max_block_size": max_block,
        "expect_disconnected_when_block_ge_3": expect_fail,
        "fails_as_intended": (n_comps > 1) if expect_fail else True,
    }


def append_one_hot_uniform_prep(qc, idxs: list[int]) -> tuple[int, int]:
    """Append W-state / uniform Hamming-weight-1 prep on ``idxs`` (all-positive amplitudes).

    Matches ``prepare_one_hot_uniform`` on a single block under little-endian indexing
    (bit ``i`` of the amplitude index = qubit ``i``), up to a single global phase.

    Construction: excite the highest-index qubit, then cascade CRY+CX downward so each
    computational one-hot basis state receives amplitude ``1/sqrt(k)`` with relative
    phase ``+1``. The prior RY+CZ+X+CX+X sequence produced ``(|01>-|10>)/sqrt(2)`` for
    ``k=2`` and incorrect probabilities for ``k>=3`` — not a global-phase difference.
    """
    k = len(idxs)
    if k == 0:
        return 0, 0
    if k == 1:
        qc.x(idxs[0])
        return 1, 0
    prep_1q = 1
    prep_2q = 0
    qc.x(idxs[k - 1])
    for i in range(k - 1, 0, -1):
        theta = 2.0 * np.arccos(np.sqrt(1.0 / (i + 1)))
        qc.cry(float(theta), idxs[i], idxs[i - 1])
        qc.cx(idxs[i - 1], idxs[i])
        prep_2q += 2  # CRY (controlled) + CX
    return prep_1q, prep_2q


def append_deliberately_wrong_phase_prep(qc, idxs: list[int]) -> None:
    """Negative-control prep: uniform one-hot magnitudes with a wrong relative phase.

    For ``k>=2``, applies the repaired W prep then a Z on the first qubit so the
    relative phase between one-hot basis states is no longer all ``+1``.
    """
    append_one_hot_uniform_prep(qc, idxs)
    if len(idxs) >= 2:
        qc.z(idxs[0])


def build_c1_qiskit_circuit(
    instance: A2Instance,
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    scaled: bool = True,
    wrong_prep_phase: bool = False,
):
    """Actual C1 circuit: validated one-hot prep + QUBO Phase/CPhase + XY ring (RXX+RYY equiv).

    Bit ordering (declared, fixed): little-endian — amplitude index bit ``i`` is qubit
    ``i``, identical to NumPy ``prepare_one_hot_uniform`` / ``simulate_c1``.
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import PhaseGate, CPhaseGate

    n = int(qubo["n"])
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    qc = QuantumCircuit(n, name="C1_actual")
    prep_1q = 0
    prep_2q = 0
    vmap = variable_index_map(instance)
    for block in vmap["blocks"]:
        idxs = list(range(block["start"], block["end"]))
        if not idxs:
            continue
        if wrong_prep_phase:
            append_deliberately_wrong_phase_prep(qc, idxs)
            k = len(idxs)
            prep_1q += 1 + (1 if k >= 2 else 0)  # X (+ Z for negative control)
            prep_2q += 2 * max(0, k - 1)
        else:
            p1, p2 = append_one_hot_uniform_prep(qc, idxs)
            prep_1q += p1
            prep_2q += p2
    n_cost_1q = 0
    n_cost_2q = 0
    n_mixer_2q = 0
    for g, b in zip(gammas, betas):
        g = float(g)
        for i in range(n):
            if Q[i, i] != 0.0:
                qc.append(PhaseGate(-g * float(Q[i, i])), [i])
                n_cost_1q += 1
            for j in range(i + 1, n):
                if Q[i, j] != 0.0:
                    qc.append(CPhaseGate(-g * float(Q[i, j])), [i, j])
                    n_cost_2q += 1
        for qi, qj in scheduled_ring_edges(instance):
            # XY exchange = exp(-i β/2 (XX+YY)) ≡ RXX(β) RYY(β)
            qc.rxx(float(b), qi, qj)
            qc.ryy(float(b), qi, qj)
            n_mixer_2q += 2
    return {
        "circuit": qc,
        "n": n,
        "prep_1q_gates": prep_1q,
        "prep_2q_gates": prep_2q,
        "cost_1q_gates": n_cost_1q,
        "cost_2q_gates": n_cost_2q,
        "mixer_2q_gates": n_mixer_2q,
        "ring_edges": scheduled_ring_edges(instance),
        "init": "validated_one_hot_prep_w_cascade",
        "bit_order": "little_endian_bit_i_equals_qubit_i",
        "mixer": "XY_ring_RXX_RYY",
        "cost_encoding": "Phase_and_CPhase_from_actual_QUBO",
        "wrong_prep_phase": bool(wrong_prep_phase),
    }

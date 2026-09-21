"""A4 C0/C1 simulation with vectorised mixers.

C1 is simulated in the one-hot legal subspace (mixer-invariant). C0 uses the
full 2^n space. Synthetic local ideal simulation only.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.a4.problem import A4Instance, enumerate_legal_policies, variable_index_map
from f1q.stage5.circuits_c0 import apply_diag_phase, plus_state
from f1q.stage5.qubo import qubo_energy


_DIAG_CACHE: dict[tuple[str, bool], np.ndarray] = {}


def cost_diags_vectorized(qubo: dict[str, Any], *, scaled: bool = True) -> np.ndarray:
    key = (str(qubo.get("hash")), bool(scaled))
    cached = _DIAG_CACHE.get(key)
    if cached is not None:
        return cached
    n = int(qubo["n"])
    dim = 1 << n
    Q = np.asarray(qubo["Q_scaled"] if scaled else qubo["Q_dense"], dtype=float)
    offset = float(qubo["offset_scaled"] if scaled else qubo["offset"])
    idx = np.arange(dim, dtype=np.uint64)
    diags = np.full(dim, offset, dtype=float)
    bits = []
    for i in range(n):
        bits.append(((idx >> i) & 1).astype(np.float64))
    for i in range(n):
        diags += bits[i] * Q[i, i]
        for j in range(i + 1, n):
            qij = Q[i, j]
            if qij != 0.0:
                diags += bits[i] * bits[j] * qij
    _DIAG_CACHE[key] = diags
    return diags


def apply_rx_mixer_np(state: np.ndarray, n: int, beta: float) -> np.ndarray:
    c = np.cos(beta)
    s = np.sin(beta)
    out = np.asarray(state, dtype=complex).copy()
    for q in range(n):
        shape = (1 << (n - q - 1), 2, 1 << q)
        x = out.reshape(shape)
        a0 = x[:, 0, :].copy()
        a1 = x[:, 1, :].copy()
        x[:, 0, :] = c * a0 - 1j * s * a1
        x[:, 1, :] = -1j * s * a0 + c * a1
        out = x.reshape(-1)
    return out


def simulate_c0(qubo: dict[str, Any], gammas: list[float], betas: list[float], *, scaled: bool = True) -> dict[str, Any]:
    n = int(qubo["n"])
    diags = cost_diags_vectorized(qubo, scaled=scaled)
    state = plus_state(n)
    for g, b in zip(gammas, betas):
        state = apply_diag_phase(state, diags, float(g))
        state = apply_rx_mixer_np(state, n, float(b))
    probs = np.abs(state) ** 2
    return {
        "family": "C0",
        "p": len(gammas),
        "n": n,
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(probs, diags)),
        "param_count": 2 * len(gammas),
        "init": "plus",
    }


def _bitstring(x: np.ndarray) -> int:
    b = 0
    for i, bit in enumerate(np.asarray(x, dtype=int)):
        if bit:
            b |= 1 << int(i)
    return b


def _c1_subspace_mixer(state: np.ndarray, rows: list[dict[str, Any]], instance: A4Instance, beta: float) -> np.ndarray:
    """XY ring mixer inside each one-hot block, acting on the legal subspace."""
    c = np.cos(beta)
    s = np.sin(beta)
    vmap = variable_index_map(instance)
    state = np.asarray(state, dtype=complex).copy()
    for block in vmap["blocks"]:
        idxs = list(range(block["start"], block["end"]))
        if len(idxs) < 2:
            continue
        ring = list(zip(idxs, idxs[1:] + idxs[:1]))
        groups: dict[tuple[int, ...], list[int]] = {}
        for li, r in enumerate(rows):
            x = np.asarray(r["x"], dtype=int)
            key = tuple(int(x[i]) for i in range(x.size) if not (block["start"] <= i < block["end"]))
            groups.setdefault(key, []).append(li)
        for members in groups.values():
            by_action = {}
            for li in members:
                x = np.asarray(rows[li]["x"], dtype=int)
                sl = x[block["start"] : block["end"]]
                by_action[int(np.argmax(sl))] = li
            for a, b in ring:
                ia = a - block["start"]
                ib = b - block["start"]
                if ia not in by_action or ib not in by_action:
                    continue
                i0, i1 = by_action[ia], by_action[ib]
                a10, a01 = state[i0], state[i1]
                state[i0] = c * a10 - 1j * s * a01
                state[i1] = -1j * s * a10 + c * a01
    return state


def simulate_c1(
    instance: A4Instance,
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    scaled: bool = True,
) -> dict[str, Any]:
    """C1 on the one-hot subspace (XY mixer preserves it). Equivalent to full-space C1."""
    n = int(qubo["n"])
    rows = enumerate_legal_policies(instance)
    n_legal = len(rows)
    sub_diags = np.array(
        [float(qubo_energy(qubo, r["x"], scaled=scaled)) for r in rows],
        dtype=float,
    )
    state = np.zeros(max(n_legal, 1), dtype=complex)
    if n_legal:
        state[:] = 1.0 / np.sqrt(n_legal)
    for g, b in zip(gammas, betas):
        state = state * np.exp(-1j * float(g) * sub_diags)
        state = _c1_subspace_mixer(state, rows, instance, float(b))
    sub_probs = np.abs(state) ** 2
    dim = 1 << n
    probs = np.zeros(dim, dtype=float)
    legal_idx = []
    for i, r in enumerate(rows):
        b = _bitstring(r["x"])
        legal_idx.append(b)
        probs[b] = float(sub_probs[i]) if n_legal else 0.0
    s = float(probs.sum())
    if s > 0:
        probs = probs / s
    outside = 0.0
    return {
        "family": "C1",
        "p": len(gammas),
        "n": n,
        "probs": probs,
        "norm": float(np.sum(probs)),
        "expectation_scaled": float(np.dot(sub_probs, sub_diags)) if n_legal else 0.0,
        "param_count": 2 * len(gammas),
        "init": "one_hot_uniform",
        "amp_outside_one_hot": outside,
        "n_legal": n_legal,
    }


def c0_objective(qubo: dict[str, Any], params: np.ndarray) -> float:
    p = params.size // 2
    gammas = params[:p].tolist()
    betas = params[p:].tolist()
    return float(simulate_c0(qubo, gammas, betas, scaled=True)["expectation_scaled"])


def c1_objective(instance: A4Instance, qubo: dict[str, Any], params: np.ndarray) -> float:
    p = params.size // 2
    gammas = params[:p].tolist()
    betas = params[p:].tolist()
    return float(simulate_c1(instance, qubo, gammas, betas, scaled=True)["expectation_scaled"])

"""QUBO construction, penalty proofs, Ising conversion, decoding, and s_Q scaling."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.formulation.compiler import score_joint_direct
from f1q.formulation.versions import QUBO_SPEC_VERSION, TOLERANCE_S
from f1q.hashing import sha256_json


def build_variable_map(action_ids_1: list[str], action_ids_2: list[str]) -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    for a in action_ids_1:
        variables.append({"index": len(variables), "car_slot": 1, "action_id": a})
    for b in action_ids_2:
        variables.append({"index": len(variables), "car_slot": 2, "action_id": b})
    return {
        "order": [v["action_id"] for v in variables],
        "variables": variables,
        "k1": len(action_ids_1),
        "k2": len(action_ids_2),
        "n": len(variables),
    }


def _expand_one_hot_penalty(k: int, M: float) -> tuple[float, list[float], list[list[float]]]:
    """Expand M*(sum x_i - 1)^2 = M*(sum_i x_i^2 + 2 sum_{i<j} x_i x_j - 2 sum_i x_i + 1).

    With binary x^2=x: constant M, linear (M-2M)= -M on each diag contribution handled as
    diagonal += M + (-2M) = -M, and upper 2M.
    """
    const = float(M)
    linear = [-float(M) for _ in range(k)]  # after x^2=x absorbed into diag below
    # Better explicit: M*(s^2 - 2s + 1) with s=sum x, x^2=x =>
    # diag gets M each, off +2M, linear -2M each, const M.
    # Combined diagonal coefficient for x_i: M - 2M = -M
    diag = [-float(M) for _ in range(k)]
    upper = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i + 1, k):
            upper[i][j] = 2.0 * float(M)
    del linear
    return const, diag, upper


def compute_penalty_bound(
    *,
    u1c: list[float],
    u2c: list[float],
    v: list[list[float]],
    margin: float = 1.0,
) -> dict[str, Any]:
    """B = sum |unpenalised nonconstant coeffs|; v_min=1 for one-hot; M > B/v_min."""
    coeffs: list[float] = []
    coeffs.extend(u1c)
    coeffs.extend(u2c)
    for row in v:
        coeffs.extend(row)
    B = float(sum(abs(c) for c in coeffs))
    # One-hot: any infeasible assignment has integer violation; expanded P >= 1 * M after scaling?
    # For one-hot, minimum positive penalty of (sum x - 1)^2 over binary non-exactly-one is 1
    # (zero selected => const contribution handled; one-hot violation examples: empty or double).
    # With our expansion, empty string yields P=M (from constant alone with all x=0: E has +M).
    # Two selected: (2-1)^2*M=M. So v_min = 1 when measuring the multiplier of M, i.e. P/M.
    v_min = 1.0
    if B == 0.0:
        M = float(margin)  # strictly positive
    else:
        M = float(B) / float(v_min) + float(margin)
    if not (M > (B / v_min if v_min else 0.0)):
        raise AssertionError("penalty M must be strictly greater than B/v_min")
    return {
        "B": B,
        "v_min": v_min,
        "margin": float(margin),
        "M": M,
        "rule": "M = B/v_min + margin (strict), v_min=1 for one-hot binary violation measure",
    }


def build_qubo(costs: dict[str, Any], *, margin: float = 1.0, M_override: float | None = None) -> dict[str, Any]:
    """E_Q(x) = offset + sum_{i<=j} Q[i,j] x_i x_j with upper-triangular + diagonal serialisation."""
    car1, car2 = costs["selected_car_ids"]
    ids1 = costs["action_ids"][car1]
    ids2 = costs["action_ids"][car2]
    varmap = build_variable_map(ids1, ids2)
    k1, k2, n = varmap["k1"], varmap["k2"], varmap["n"]
    if n == 0 or k1 == 0 or k2 == 0:
        return {
            "qubo_spec_version": QUBO_SPEC_VERSION,
            "convention": "E_Q(x)=offset + sum_{i<=j} Q[i,j] x_i x_j ; x in {0,1}; upper+diag",
            "offset": 0.0,
            "Q_dense": [],
            "Q_serial": [],
            "variable_map": varmap,
            "penalty": {"B": 0.0, "v_min": 1.0, "margin": margin, "M": margin, "M_used": margin, "failure_code": "EMPTY_MENU"},
            "largest_nonconstant_qubo_coeff": 0.0,
            "decision_objective_note": "empty menu",
            "hash": sha256_json({"empty": True}),
            "failure_code": "EMPTY_MENU",
        }
    u1c = list(costs["u1_centered"])
    u2c = list(costs["u2_centered"])
    v = [list(row) for row in costs["v"]]
    proof = compute_penalty_bound(u1c=u1c, u2c=u2c, v=v, margin=margin)
    M = float(M_override) if M_override is not None else float(proof["M"])
    Q = np.zeros((n, n), dtype=float)
    offset = float(costs["C_centered"])

    # Centred unaries on diagonal (binary).
    for i, coeff in enumerate(u1c):
        Q[i, i] += float(coeff)
    for j, coeff in enumerate(u2c):
        Q[k1 + j, k1 + j] += float(coeff)

    # Cross-car pair terms (upper triangle i<j).
    for i in range(k1):
        for j in range(k2):
            Q[i, k1 + j] += float(v[i][j])

    # One-hot penalties for each car block.
    for start, k in ((0, k1), (k1, k2)):
        const, diag, upper = _expand_one_hot_penalty(k, M)
        offset += const
        for i in range(k):
            Q[start + i, start + i] += diag[i]
            for j in range(i + 1, k):
                Q[start + i, start + j] += upper[i][j]

    # Serialise strictly upper-triangular plus diagonal.
    serial: list[dict[str, float | int]] = []
    for i in range(n):
        if abs(Q[i, i]) > 0.0:
            serial.append({"i": i, "j": i, "q": float(Q[i, i])})
        for j in range(i + 1, n):
            if abs(Q[i, j]) > 0.0:
                serial.append({"i": i, "j": j, "q": float(Q[i, j])})

    largest_nonconst = 0.0
    for i in range(n):
        largest_nonconst = max(largest_nonconst, abs(float(Q[i, i])))
        for j in range(i + 1, n):
            largest_nonconst = max(largest_nonconst, abs(float(Q[i, j])))

    return {
        "qubo_spec_version": QUBO_SPEC_VERSION,
        "convention": "E_Q(x)=offset + sum_{i<=j} Q[i,j] x_i x_j ; x in {0,1}; upper+diag",
        "offset": float(offset),
        "Q_dense": Q.tolist(),
        "Q_serial": serial,
        "variable_map": varmap,
        "penalty": {**proof, "M_used": M, "M_override": M_override},
        "largest_nonconstant_qubo_coeff": float(largest_nonconst),
        "decision_objective_note": "physical seconds require restoring C_centered via direct scorer; do not drop offset",
        "hash": sha256_json({"offset": offset, "Q_serial": serial, "order": varmap["order"]}),
    }


def energy_qubo(qubo: dict[str, Any], bits: list[int] | np.ndarray) -> float:
    x = np.asarray(bits, dtype=float)
    Q = np.asarray(qubo["Q_dense"], dtype=float)
    # offset + x^T Q_upper_and_diag x with Q stored full upper incl diag (lower zero)
    return float(qubo["offset"] + x @ Q @ x)


def is_feasible(bits: list[int] | np.ndarray, k1: int, k2: int) -> bool:
    x = list(int(b) for b in bits)
    return sum(x[:k1]) == 1 and sum(x[k1:]) == 1


def hard_penalty_value(bits: list[int] | np.ndarray, k1: int, k2: int, M: float) -> float:
    x = list(int(b) for b in bits)
    s1 = sum(x[:k1])
    s2 = sum(x[k1:])
    return float(M) * ((s1 - 1) ** 2 + (s2 - 1) ** 2)


def verify_penalty_proof(qubo: dict[str, Any], costs: dict[str, Any], *, tol: float = TOLERANCE_S) -> dict[str, Any]:
    k1 = qubo["variable_map"]["k1"]
    k2 = qubo["variable_map"]["k2"]
    n = qubo["variable_map"]["n"]
    M = float(qubo["penalty"]["M_used"])
    B = float(qubo["penalty"]["B"])
    v_min = float(qubo["penalty"]["v_min"])
    feasible_energies = []
    infeasible_penalties = []
    best_feasible = None
    # Exhaustive on small n only.
    if n > 20:
        return {"ok": False, "reason": "n_too_large_for_exhaustive", "n": n}
    for mask in range(1 << n):
        bits = [(mask >> i) & 1 for i in range(n)]
        P = hard_penalty_value(bits, k1, k2, M)
        # Unpenalised energy relative to centred physical on legal pairs only for feasible.
        if is_feasible(bits, k1, k2):
            if abs(P) > tol:
                return {"ok": False, "reason": "feasible_nonzero_penalty", "bits": bits, "P": P}
            i = bits[:k1].index(1)
            j = bits[k1:].index(1)
            phys = score_joint_direct(costs, index_a=i, index_b=j, centred=True)
            eq = energy_qubo(qubo, bits)
            # Penalised energy should equal physical centred (P=0).
            if abs(eq - phys) > 1e-6:
                return {"ok": False, "reason": "feasible_energy_mismatch", "eq": eq, "phys": phys, "bits": bits}
            feasible_energies.append(eq)
            if best_feasible is None or eq < best_feasible:
                best_feasible = eq
        else:
            # Measure dimensionless violation: P/M
            viol = ((sum(bits[:k1]) - 1) ** 2 + (sum(bits[k1:]) - 1) ** 2)
            if viol < v_min - 1e-15:
                return {"ok": False, "reason": "infeasible_below_vmin", "bits": bits, "viol": viol}
            infeasible_penalties.append(P)
            if best_feasible is not None:
                # Will check after loop once best known; collect all.
                pass
    if not feasible_energies:
        return {"ok": False, "reason": "no_feasible_state"}
    best_feasible = min(feasible_energies)
    # No infeasible state may beat best feasible.
    for mask in range(1 << n):
        bits = [(mask >> i) & 1 for i in range(n)]
        if is_feasible(bits, k1, k2):
            continue
        eq = energy_qubo(qubo, bits)
        if eq + tol < best_feasible:
            return {"ok": False, "reason": "infeasible_beats_feasible", "bits": bits, "eq": eq, "best_feasible": best_feasible}
    return {
        "ok": True,
        "feasible_count": len(feasible_energies),
        "best_feasible_energy": best_feasible,
        "B": B,
        "v_min": v_min,
        "M": M,
        "M_gt_B_over_vmin": M > B / v_min,
        "all_feasible_P_zero": True,
        "all_infeasible_P_ge_M": True,
    }


def qubo_to_ising(qubo: dict[str, Any]) -> dict[str, Any]:
    """x=(1-Z)/2 with Z in {+1,-1}; bit 1 -> Z=-1, bit 0 -> Z=+1."""
    Q = np.asarray(qubo["Q_dense"], dtype=float)
    n = Q.shape[0]
    offset = float(qubo["offset"])
    h = np.zeros(n)
    J = np.zeros((n, n))
    const = offset
    # E = offset + sum_i Q_ii x_i + sum_{i<j} Q_ij x_i x_j
    # x=(1-Z)/2
    for i in range(n):
        qii = Q[i, i]
        # Q_ii * (1-Z_i)/2 = Q_ii/2 - (Q_ii/2) Z_i
        const += qii / 2.0
        h[i] += -qii / 2.0
    for i in range(n):
        for j in range(i + 1, n):
            qij = Q[i, j]
            # qij * (1-Zi)/2 * (1-Zj)/2 = qij/4 * (1 - Zi - Zj + Zi Zj)
            const += qij / 4.0
            h[i] += -qij / 4.0
            h[j] += -qij / 4.0
            J[i, j] += qij / 4.0
    s_Q = max(1.0, float(np.max(np.abs(h))) if n else 1.0, float(np.max(np.abs(J))) if n else 1.0)
    return {
        "convention": "x=(1-Z)/2 ; Z=+1 for bit0, Z=-1 for bit1",
        "constant": float(const),
        "h": h.tolist(),
        "J_upper": [[float(J[i, j]) for j in range(n)] for i in range(n)],
        "variable_order": list(qubo["variable_map"]["order"]),
        "s_Q": float(s_Q),
        "s_Q_definition": "max(1, max|h_i|, max|J_ij|) excluding constant, including penalties",
        "hash": sha256_json({"constant": const, "h": h.tolist(), "J": J.tolist()}),
    }


def energy_ising(ising: dict[str, Any], bits: list[int] | np.ndarray) -> float:
    x = [int(b) for b in bits]
    z = [1 - 2 * b for b in x]  # bit0->+1, bit1->-1
    n = len(z)
    e = float(ising["constant"])
    h = ising["h"]
    J = ising["J_upper"]
    for i in range(n):
        e += float(h[i]) * z[i]
        for j in range(i + 1, n):
            e += float(J[i][j]) * z[i] * z[j]
    return float(e)


def decode_bits(qubo: dict[str, Any], bits: list[int], *, tol: float = TOLERANCE_S) -> dict[str, Any]:
    k1 = qubo["variable_map"]["k1"]
    k2 = qubo["variable_map"]["k2"]
    order = qubo["variable_map"]["order"]
    if len(bits) != len(order):
        return {"feasible": False, "reason": "length_mismatch"}
    if not is_feasible(bits, k1, k2):
        reasons = []
        if sum(bits[:k1]) != 1:
            reasons.append("car1_one_hot_violated")
        if sum(bits[k1:]) != 1:
            reasons.append("car2_one_hot_violated")
        return {"feasible": False, "reason": ";".join(reasons), "bits": bits}
    i = bits[:k1].index(1)
    j = bits[k1:].index(1)
    return {
        "feasible": True,
        "action_id_1": order[i],
        "action_id_2": order[k1 + j],
        "indices": {"i": i, "j": j},
        "energy": energy_qubo(qubo, bits),
        "tol": tol,
    }


def scale_ising(ising: dict[str, Any]) -> dict[str, Any]:
    s = float(ising["s_Q"])
    h = [float(v) / s for v in ising["h"]]
    J = [[float(v) / s for v in row] for row in ising["J_upper"]]
    const = float(ising["constant"]) / s
    return {**ising, "scaled": True, "s_Q": s, "h": h, "J_upper": J, "constant": const}

"""Ideal simulators, actual-circuit Qiskit cross-checks, and resource estimates."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit, simulate_c0
from f1q.stage5.circuits_c1 import build_c1_qiskit_circuit, simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.heuristic import greedy_safe_fallback
from f1q.stage5.metrics import evaluate_distribution_metrics
from f1q.stage5.model import A2Instance
from f1q.stage5.qubo import qubo_energy


def estimate_statevector_memory_bytes(n_qubits: int, *, complex_bytes: int = 16) -> int:
    return (1 << n_qubits) * complex_bytes


def statevector_feasible(n_qubits: int, *, max_bytes: int = 2_000_000_000) -> bool:
    return estimate_statevector_memory_bytes(n_qubits) <= max_bytes and n_qubits <= 20


def sample_metrics(
    instance: A2Instance,
    qubo: dict[str, Any],
    probs: np.ndarray,
    *,
    exact_cost: float | None,
    f_max: float | None = None,
    pool_size: int = 64,
    seed: int = 0,
) -> dict[str, Any]:
    if f_max is None and exact_cost is not None:
        en = enumerate_legal_policies(instance)
        f_max = en.get("f_max")
    fb = greedy_safe_fallback(instance)
    weak = float(fb["cost"]) if fb.get("feasible") else None
    return evaluate_distribution_metrics(
        instance,
        probs,
        exact_cost=exact_cost,
        f_max=f_max,
        weak_incumbent_cost=weak,
        pool_size=pool_size,
        seed=seed,
    )


def qiskit_statevector_crosscheck_c0(qubo: dict[str, Any], gammas: list[float], betas: list[float]) -> dict[str, Any]:
    """Independent Qiskit Statevector cross-check on the ACTUAL C0 circuit."""
    from qiskit.quantum_info import Statevector

    n = int(qubo["n"])
    if n > 12:
        return {"ok": False, "reason": "n_too_large_for_crosscheck"}
    ours = simulate_c0(qubo, gammas, betas, scaled=True)
    built = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)
    qc = built["circuit"]
    state = Statevector.from_instruction(qc)
    q_probs = np.asarray(state.probabilities())
    ours_p = ours["probs"]

    def rev_bits(p: np.ndarray) -> np.ndarray:
        out = np.zeros_like(p)
        for i, v in enumerate(p):
            rb = int(f"{i:0{n}b}"[::-1], 2)
            out[rb] = v
        return out

    diffs = [
        float(np.max(np.abs(ours_p - q_probs))),
        float(np.max(np.abs(ours_p - q_probs[::-1]))),
        float(np.max(np.abs(ours_p - rev_bits(q_probs)))),
    ]
    best = min(diffs)
    return {
        "ok": best < 1e-6,
        "max_prob_diff": best,
        "n": n,
        "method": "qiskit.Statevector.from_instruction(actual_C0_circuit)",
        "cost_2q_gates": built["cost_2q_gates"],
        "has_quadratic": built["has_quadratic_interactions"],
    }


def _global_phase_aligned_amp_diff(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Max |a - e^{iφ} b| after choosing one global phase; also return |⟨a|b⟩| fidelity."""
    a = np.asarray(a, dtype=complex)
    b = np.asarray(b, dtype=complex)
    ov = np.vdot(a, b)
    fid = float(abs(ov))
    if fid < 1e-15:
        return float(np.max(np.abs(a - b))), fid
    phase = ov / abs(ov)
    return float(np.max(np.abs(a - b * np.conj(phase)))), fid


def qiskit_statevector_crosscheck_c1(
    instance: A2Instance,
    qubo: dict[str, Any],
    gammas: list[float],
    betas: list[float],
    *,
    amp_tol: float = 1e-8,
    prob_tol: float = 1e-8,
    exp_tol: float = 1e-8,
    wrong_prep_phase: bool = False,
) -> dict[str, Any]:
    """Independent Qiskit Statevector cross-check on the ACTUAL C1 circuit.

    Evolves ``Statevector.from_instruction(build_c1_qiskit_circuit(...))`` only.
    Does **not** hand-initialise a NumPy one-hot state and does **not** call
    ``apply_c1_mixer`` on the independent path.

    Bit order is fixed little-endian (bit i = qubit i), matching NumPy ``simulate_c1``.
    Equivalence is up to one global phase on amplitudes; probabilities and scaled
    objective expectation must agree without reordering.
    """
    from qiskit.quantum_info import Statevector

    from f1q.stage5.circuits_c0 import cost_unitary_diags

    n = int(qubo["n"])
    if n > 12:
        return {"ok": False, "reason": "n_too_large_for_crosscheck", "n": n}
    ours = simulate_c1(instance, qubo, gammas, betas, scaled=True)
    built = build_c1_qiskit_circuit(
        instance, qubo, gammas, betas, scaled=True, wrong_prep_phase=wrong_prep_phase
    )
    qc = built["circuit"]
    q_state = np.asarray(Statevector.from_instruction(qc).data, dtype=complex)
    q_probs = np.abs(q_state) ** 2
    amp_diff, fidelity = _global_phase_aligned_amp_diff(ours["state"], q_state)
    prob_diff = float(np.max(np.abs(ours["probs"] - q_probs)))
    diags = cost_unitary_diags(qubo, scaled=True)
    exp_ours = float(ours["expectation_scaled"])
    exp_q = float(np.dot(q_probs, diags))
    exp_diff = float(abs(exp_ours - exp_q))
    mask = np.abs(ours["state"]) > 1e-12
    # One-hot preservation on the actual circuit output
    from f1q.stage5.circuits_c1 import one_hot_feasible_mask

    oh_mask = one_hot_feasible_mask(instance)
    amp_outside = float(np.sum(q_probs[~oh_mask]))
    if wrong_prep_phase:
        # Magnitudes may still match; relative-phase defect must fail amplitude alignment
        ok = not (amp_diff < amp_tol and fidelity > 1.0 - 1e-9)
        expect_reject = True
    else:
        ok = (
            amp_diff < amp_tol
            and prob_diff < prob_tol
            and exp_diff < exp_tol
            and amp_outside <= 1e-8
            and fidelity > 1.0 - 1e-9
        )
        expect_reject = False
    return {
        "ok": bool(ok),
        "expect_reject": expect_reject,
        "wrong_prep_phase": bool(wrong_prep_phase),
        "max_amp_diff_global_phase": amp_diff,
        "state_fidelity_abs_inner": fidelity,
        "max_prob_diff": prob_diff,
        "expectation_diff": exp_diff,
        "expectation_ours": exp_ours,
        "expectation_qiskit": exp_q,
        "amp_outside_one_hot_qiskit": amp_outside,
        "amp_outside_one_hot_numpy": float(ours["amp_outside_one_hot"]),
        "n": n,
        "p": len(gammas),
        "amp_tol": amp_tol,
        "prob_tol": prob_tol,
        "exp_tol": exp_tol,
        "bit_order": "little_endian_bit_i_equals_qubit_i",
        "method": "qiskit.Statevector.from_instruction(actual_C1_circuit)",
        "prep_1q_gates": built["prep_1q_gates"],
        "prep_2q_gates": built["prep_2q_gates"],
        "cost_2q_gates": built["cost_2q_gates"],
        "mixer_2q_gates": built["mixer_2q_gates"],
        "support_size_numpy": int(np.count_nonzero(mask)),
    }


def circuit_resource_estimate(
    instance: A2Instance,
    family: str,
    p: int,
    *,
    transpiler_seed: int = 17,
    opt_level: int = 1,
) -> dict[str, Any]:
    n = instance.n_logical_vars()
    mem = estimate_statevector_memory_bytes(n)
    return {
        "family": family,
        "p": p,
        "logical_qubits": n,
        "ancillas": 0,
        "statevector_memory_bytes_complex128": mem,
        "ideal_statevector_feasible": statevector_feasible(n),
        "transpiler_seed": transpiler_seed,
        "opt_level": opt_level,
        "target": "generic_local_basis_rz_sx_x_cx",
    }


def transpile_actual_circuit(
    instance: A2Instance,
    qubo: dict[str, Any],
    family: str,
    p: int,
    *,
    seed: int = 17,
    opt_level: int = 1,
) -> dict[str, Any]:
    """Transpile ACTUAL C0/C1 circuits (not proxies)."""
    from qiskit import transpile

    gammas = [0.3] * p
    betas = [0.2] * p
    if family == "C0":
        built = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)
    else:
        built = build_c1_qiskit_circuit(instance, qubo, gammas, betas, scaled=True)
    qc = built["circuit"]
    tqc = transpile(
        qc,
        basis_gates=["rz", "sx", "x", "cx"],
        optimization_level=opt_level,
        seed_transpiler=seed,
    )
    counts = tqc.count_ops()
    cx = int(counts.get("cx", 0))
    logical_2q = int(built.get("cost_2q_gates", 0)) + int(built.get("mixer_2q_gates", 0)) + int(
        built.get("prep_2q_gates", 0)
    )
    # No coupling map / device routing is used — excess CX vs logical 2q count is
    # native-basis decomposition (e.g. RXX/RYY/CRY/CPhase → CX), not SWAP routing.
    native_decomp_cx_excess = max(0, cx - logical_2q)
    return {
        "family": family,
        "p": p,
        "depth": int(tqc.depth()),
        "ops": {k: int(v) for k, v in counts.items()},
        "n_1q": int(sum(v for k, v in counts.items() if k != "cx")),
        "n_2q_cx": cx,
        "logical_2q_est": logical_2q,
        "native_basis_decomposition_cx_excess": native_decomp_cx_excess,
        "swap_routing_overhead_cx": 0,
        "routing_used": False,
        "coupling_map": None,
        # Retained key name for readers of older rows; value is decomposition excess, NOT routing.
        "swap_routing_overhead_cx_proxy": native_decomp_cx_excess,
        "swap_routing_overhead_cx_proxy_meaning": (
            "DEPRECATED_ALIAS_of_native_basis_decomposition_cx_excess;"
            "no_coupling_map_or_SWAP_routing_was_applied"
        ),
        "cost_interaction_gates": int(built.get("cost_2q_gates", 0)),
        "mixer_gates": int(built.get("mixer_2q_gates", 0) or built.get("mixer_1q_gates", 0)),
        "prep_gates": int(built.get("prep_1q_gates", 0)) + int(built.get("prep_2q_gates", 0)),
        "prep_1q_gates": int(built.get("prep_1q_gates", 0)),
        "prep_2q_gates": int(built.get("prep_2q_gates", 0)),
        "seed": seed,
        "opt_level": opt_level,
        "basis_gates": ["rz", "sx", "x", "cx"],
        "target_assumptions": "all-to-all_generic_local_no_device_coupling_map",
        "proxy": False,
        "actual_circuit": True,
        "has_quadratic_cost_terms": int(qubo.get("n_quadratic_terms", 0)) > 0,
        "cost_2q_on_circuit": int(built.get("cost_2q_gates", 0)),
        "c0_nonzero_2q_when_quadratic": (
            family != "C0"
            or int(qubo.get("n_quadratic_terms", 0)) == 0
            or int(built.get("cost_2q_gates", 0)) > 0
        ),
    }


# Back-compat name used by older call sites
def transpile_resource_qiskit(n: int, family: str, p: int, *, seed: int = 17, opt_level: int = 1) -> dict[str, Any]:
    del n
    return {
        "deprecated": True,
        "note": "Use transpile_actual_circuit with real instance/qubo",
        "family": family,
        "p": p,
        "seed": seed,
        "opt_level": opt_level,
    }

"""Gate-channel noisy simulation panel (synthetic depolarizing ≠ measured IBM noise).

Withdraws the superseded Phase 6 probability-perturbation panel as evidence of
gate-level noise resilience. This module applies documented 1q/2q depolarizing
channels to native-basis instructions of the actual C0/C1 circuits via
qiskit.quantum_info DensityMatrix evolution (no Aer required; no Gaussian jitter).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Kraus, Statevector

from f1q.hashing import sha256_json
from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit, simulate_c0
from f1q.stage5.circuits_c1 import build_c1_qiskit_circuit, simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import compute_features
from f1q.stage6.config import Phase6Config
from f1q.stage6.metrics_pilot import exact_distribution_metrics, pool_sample_metrics


ProgressFn = Callable[[str], None]

# Supersession record for historical Phase 6 noisy evidence
HISTORICAL_NOISY_PANEL_CLASS = (
    "WITHDRAWN_AS_GATE_LEVEL_NOISE_EVIDENCE:"
    "probability_mix_toward_uniform_plus_gaussian_jitter_not_gate_channels"
)


_PAULI_1Q = (
    np.eye(2, dtype=complex),
    np.array([[0, 1], [1, 0]], dtype=complex),
    np.array([[0, -1j], [1j, 0]], dtype=complex),
    np.array([[1, 0], [0, -1]], dtype=complex),
)

DEPOLARIZING_MIXTURE_CONVENTION = (
    "Dimension-independent Qiskit/Nielsen-Chuang mixture: "
    "E_p(rho)=(1-p) rho + p I/d, d=2**n, 0<=p<=1. "
    "Equivalent Pauli Kraus: identity probability 1-p*(d**2-1)/d**2; "
    "each non-identity Pauli probability p/d**2. "
    "p=1 yields I/2 (1q) and I/4 (2q). Synthetic; not IBM-calibrated noise."
)


def _n_qubit_paulis(n_qubits: int) -> list[np.ndarray]:
    ops = [np.array([[1.0 + 0.0j]], dtype=complex)]
    for _ in range(n_qubits):
        ops = [np.kron(P, Q) for P in ops for Q in _PAULI_1Q]
    return ops


def depolarizing_closed_form(rho: np.ndarray, p: float) -> np.ndarray:
    """Closed form E_p(rho)=(1-p) rho + p I/d for a density matrix."""
    if p < 0.0 or p > 1.0:
        raise ValueError("p must be in [0,1]")
    rho = np.asarray(rho, dtype=complex)
    d = int(rho.shape[0])
    return (1.0 - p) * rho + p * np.eye(d, dtype=complex) / d


def depolarizing_kraus(n_qubits: int, p: float) -> Kraus:
    """General n-qubit depolarizing Kraus operators for the mixture convention."""
    if n_qubits < 1:
        raise ValueError("n_qubits must be >= 1")
    if p < 0.0 or p > 1.0:
        raise ValueError("p must be in [0,1]")
    d = 2**n_qubits
    d2 = d * d
    paulis = _n_qubit_paulis(n_qubits)
    assert len(paulis) == d2
    p_id = 1.0 - p * (d2 - 1) / d2
    p_ni = p / d2
    kraus = [np.sqrt(max(0.0, p_id)) * paulis[0]]
    for op in paulis[1:]:
        kraus.append(np.sqrt(p_ni) * op)
    return Kraus(kraus)


def depolarizing_kraus_1q(p: float) -> Kraus:
    """One-qubit depolarizing: E_p(rho)=(1-p)rho + p I/2."""
    return depolarizing_kraus(1, p)


def depolarizing_kraus_2q(p: float) -> Kraus:
    """Two-qubit depolarizing: E_p(rho)=(1-p)rho + p I/4.

    Identity probability 1-15p/16; each of 15 non-identity Paulis p/16.
    This supersedes the previous total-nonidentity-error convention
    (identity 1-p, each non-identity p/15) that disagreed with the 1q mixture parameter.
    """
    return depolarizing_kraus(2, p)


def _gate_qubit_count(instr) -> int:
    return len(instr.qubits)


def simulate_circuit_with_depolarizing(
    qc: QuantumCircuit,
    *,
    p1: float,
    p2: float,
    include_prep_and_mixer: bool = True,
) -> dict[str, Any]:
    """Evolve DensityMatrix through each native instruction + depolarizing channels.

    Channels are applied after every 1q / 2q gate instruction (including H, RX,
    Phase, CPhase, CRY, CX used in C0/C1 prep+cost+mixer). Measurement-free.
    """
    n = qc.num_qubits
    if n > 10:
        raise ValueError(f"refusing density-matrix noise for n={n}>10")
    # Circuits start from |0>^n and include their own prep/mixer/cost.
    dm_data = np.zeros((2**n, 2**n), dtype=complex)
    dm_data[0, 0] = 1.0
    dm = DensityMatrix(dm_data, dims=2**n)

    k1 = depolarizing_kraus_1q(p1) if p1 > 0 else None
    k2 = depolarizing_kraus_2q(p2) if p2 > 0 else None
    n_1q = n_2q = 0
    for item in qc.data:
        instr = item.operation
        qargs = [qc.find_bit(q).index for q in item.qubits]
        name = instr.name
        if name in ("barrier", "measure", "snapshot"):
            continue
        # Apply unitary / instruction
        dm = dm.evolve(instr, qargs=qargs)
        nq = len(qargs)
        if not include_prep_and_mixer:
            continue
        if nq == 1 and k1 is not None:
            dm = dm.evolve(k1, qargs=qargs)
            n_1q += 1
        elif nq == 2 and k2 is not None:
            dm = dm.evolve(k2, qargs=qargs)
            n_2q += 1
        elif nq > 2:
            # Decompose not performed here; fail closed for unhandled multi-qubit
            raise ValueError(f"unhandled {nq}-qubit instruction {name}")

    probs = np.asarray(dm.probabilities(), dtype=float)
    # Numerical cleanup
    probs = np.clip(probs, 0.0, None)
    s = float(probs.sum())
    if s <= 0:
        raise RuntimeError("non-positive probability mass after noise")
    probs = probs / s
    return {
        "probs": probs,
        "norm": float(probs.sum()),
        "n_1q_channels_applied": n_1q,
        "n_2q_channels_applied": n_2q,
        "p1": p1,
        "p2": p2,
        "method": "qiskit.quantum_info.DensityMatrix_gate_depolarizing",
        "synthetic_not_ibm": True,
        "include_prep_and_mixer": include_prep_and_mixer,
    }


def verify_analytical_channel_behaviour() -> dict[str, Any]:
    """Simple analytical checks: identity channel; pure X-error bias; normalisation."""
    checks = []
    # 1) Zero noise on H|0> = |+>
    qc = QuantumCircuit(1)
    qc.h(0)
    ideal = np.abs(Statevector.from_instruction(qc).data) ** 2
    zn = simulate_circuit_with_depolarizing(qc, p1=0.0, p2=0.0)
    checks.append(
        {
            "name": "zero_noise_matches_statevector",
            "pass": bool(np.allclose(zn["probs"], ideal, atol=1e-10)),
            "max_abs_diff": float(np.max(np.abs(zn["probs"] - ideal))),
        }
    )
    # 2) Full 1q depolarizing p=1 on |0> → maximally mixed
    qc0 = QuantumCircuit(1)
    noisy = simulate_circuit_with_depolarizing(qc0, p1=1.0, p2=0.0)
    # |0> with no gates: no channels applied → still |0|. Apply explicit X then noise:
    qc1 = QuantumCircuit(1)
    qc1.x(0)
    noisy_x = simulate_circuit_with_depolarizing(qc1, p1=1.0, p2=0.0)
    checks.append(
        {
            "name": "p1_1_after_X_near_maximally_mixed",
            "pass": bool(np.allclose(noisy_x["probs"], [0.5, 0.5], atol=1e-8)),
            "probs": noisy_x["probs"].tolist(),
        }
    )
    # 3) Finite nonnegative normalised
    checks.append(
        {
            "name": "probs_finite_nonneg_norm",
            "pass": bool(
                np.all(np.isfinite(noisy_x["probs"]))
                and np.all(noisy_x["probs"] >= -1e-15)
                and abs(noisy_x["norm"] - 1.0) < 1e-10
            ),
        }
    )
    # Unused quiet
    _ = noisy
    return {"ok": all(c["pass"] for c in checks), "checks": checks}


def parse_noise_model(label: str) -> tuple[float, float]:
    # depolarizing_1q_1e-3_2q_1e-2
    p1, p2 = 1e-3, 1e-2
    try:
        parts = label.split("_")
        # [... 1q, 1e-3, 2q, 1e-2]
        i1 = parts.index("1q")
        i2 = parts.index("2q")
        p1 = float(parts[i1 + 1])
        p2 = float(parts[i2 + 1])
    except (ValueError, IndexError):
        pass
    return p1, p2


def run_noisy_panel(
    cfg: Phase6Config,
    *,
    assets: dict[str, Any],
    progress: ProgressFn,
) -> dict[str, Any]:
    """Gate-channel noisy panel on ≤noisy_max_qubits VSC-style cases (one/family)."""
    if not cfg.noisy_panel_enabled:
        return {"status": "DISABLED", "reason": "noisy_panel_enabled=false"}

    analytical = verify_analytical_channel_behaviour()
    if not analytical["ok"]:
        return {
            "status": "BLOCKED",
            "reason": "analytical_channel_self_check_failed",
            "analytical": analytical,
            "historical_panel_class": HISTORICAL_NOISY_PANEL_CLASS,
        }

    p1, p2 = parse_noise_model(cfg.noisy_noise_model)
    depth = 1 if cfg.noisy_depth_choice == "p1" else 2
    from f1q.generator.config import cartesian_family_ids

    fams = cartesian_family_ids()
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for fam in fams:
        progress(f"gate-noise panel {fam}")
        inst = build_a2_instance(
            instance_id=f"phase6.noisy.gate.{fam}",
            family_id=fam,
            rung="circuit_unit",
            seed=9000 + int(hashlib.sha256(fam.encode()).hexdigest()[:6], 16) % 1000,
            deadline_s=cfg.deadline_s,
            n_scenarios=2,
            n_epochs=2,
            n_actions=2,
            microcase="standard",
        )
        qubo = build_a2_qubo(inst)
        n = int(qubo["n"])
        if n > cfg.noisy_max_qubits:
            rows.append(
                {
                    "family_id": fam,
                    "status": "excluded",
                    "reason": f"n_qubits={n}>{cfg.noisy_max_qubits}",
                    "n_qubits": n,
                }
            )
            continue
        en = enumerate_legal_policies(inst)
        for family in ("C0", "C1"):
            fd = f"{family}_p{depth}"
            feats = compute_features(inst, qubo, family, depth)
            donors = assets["donors"][fd]["selected"]
            learned = assets["selectors"][fd].select(feats, donors)["selected_donor"]
            fixed = assets["fixed"][fd]
            for policy_name, donor in (("learned", learned), ("fixed", fixed)):
                params = np.asarray(donor["params"], dtype=float)
                gammas = params[:depth].tolist()
                betas = params[depth:].tolist()
                if family == "C0":
                    ideal = simulate_c0(qubo, gammas, betas, scaled=True)
                    built = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)
                else:
                    ideal = simulate_c1(inst, qubo, gammas, betas, scaled=True)
                    built = build_c1_qiskit_circuit(inst, qubo, gammas, betas, scaled=True)
                qc = built["circuit"]
                ideal_m = exact_distribution_metrics(
                    inst,
                    ideal["probs"],
                    exact_cost=en.get("f_star"),
                    f_max=en.get("f_max"),
                    weak_incumbent_cost=None,
                    improvement_tol=cfg.improvement_tol,
                )
                # Zero-noise density-matrix path vs independent ideal simulator
                zn = simulate_circuit_with_depolarizing(qc, p1=0.0, p2=0.0)
                zn_ok = bool(np.allclose(zn["probs"], ideal["probs"], atol=1e-5))
                # Exact noisy probabilities (infinite-shot / density matrix)
                noisy_exact = simulate_circuit_with_depolarizing(qc, p1=p1, p2=p2)
                nm = exact_distribution_metrics(
                    inst,
                    noisy_exact["probs"],
                    exact_cost=en.get("f_star"),
                    f_max=en.get("f_max"),
                    weak_incumbent_cost=None,
                    improvement_tol=cfg.improvement_tol,
                )
                # Finite-shot sampling from noisy exact probs
                shot_rows = []
                for s in range(cfg.noisy_seeds):
                    pool = pool_sample_metrics(
                        inst,
                        noisy_exact["probs"],
                        exact_cost=en.get("f_star"),
                        f_max=en.get("f_max"),
                        pool_size=cfg.noisy_shots,
                        seed=1000 + s,
                        distribution_id=f"noisy_gate_{fam}_{family}_p{depth}_{policy_name}",
                        circuit_id=family,
                        parameter_id=str(donor.get("params_hash")),
                    )
                    shot_rows.append(
                        {
                            "seed": s,
                            "actual_draws": pool["actual_draws"],
                            "shot_conservation_ok": pool["shot_conservation_ok"],
                            "n_legal": pool["n_legal_in_pool"],
                            "best_of_pool_normalised_regret": pool["best_of_pool_normalised_regret"],
                        }
                    )
                rows.append(
                    {
                        "status": "completed",
                        "family_id": fam,
                        "circuit_family": family,
                        "p": depth,
                        "policy": policy_name,
                        "n_qubits": n,
                        "params_hash": donor.get("params_hash"),
                        "ideal_legal_prob": ideal_m["complete_legal_policy_probability"],
                        "noisy_exact_legal_prob": nm["complete_legal_policy_probability"],
                        "noisy_exact_one_hot_prob": nm["one_hot_probability"],
                        "noisy_exact_optimal_mass": nm["optimal_sample_probability"],
                        "zero_noise_vs_ideal_ok": zn_ok,
                        "noise_model": cfg.noisy_noise_model,
                        "p1": p1,
                        "p2": p2,
                        "n_1q_channels": noisy_exact["n_1q_channels_applied"],
                        "n_2q_channels": noisy_exact["n_2q_channels_applied"],
                        "method": noisy_exact["method"],
                        "synthetic_noise_not_ibm": True,
                        "evidence_class": "synthetic_gate_depolarizing_sensitivity_model",
                        "finite_shot_pools": shot_rows,
                        "probs_finite_norm_ok": bool(
                            np.all(np.isfinite(noisy_exact["probs"]))
                            and abs(noisy_exact["norm"] - 1.0) < 1e-9
                        ),
                    }
                )
    completed = [r for r in rows if r.get("status") == "completed"]
    zn_pass = sum(1 for r in completed if r.get("zero_noise_vs_ideal_ok"))
    return {
        "status": "COMPLETED",
        "elapsed_s": time.perf_counter() - t0,
        "predeclared_depth": cfg.noisy_depth_choice,
        "noise_model": cfg.noisy_noise_model,
        "max_qubits": cfg.noisy_max_qubits,
        "n_rows": len(rows),
        "n_completed": len(completed),
        "zero_noise_pass": zn_pass,
        "zero_noise_total": len(completed),
        "analytical_self_check": analytical,
        "evidence_class": "synthetic_gate_depolarizing_sensitivity_model",
        "historical_panel_class": HISTORICAL_NOISY_PANEL_CLASS,
        "historical_panel_path": (
            "evidence/stage6/bd83cb22-6a38-4d21-9267-3253f52587d7/noisy_panel.json"
        ),
        "rows": rows,
        "panel_hash": sha256_json(
            [{k: v for k, v in r.items() if k != "finite_shot_pools"} for r in rows]
        ),
    }

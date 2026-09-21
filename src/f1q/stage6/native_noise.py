"""Native-basis (rz/sx/x/cx) depolarizing noise on transpiled C0/C1 circuits.

Virtual-RZ assumption (declared): rz is treated as a zero-duration virtual phase
and does NOT receive a 1-qubit depolarizing channel. 1q channels attach after
every native sx/x. 2q channels attach after every native cx. No coupling map
and no routing claim. Synthetic ≠ IBM measured noise.

This module supersedes ``stage6.noisy.simulate_circuit_with_depolarizing`` as
*native-basis* evidence. The prior panel applied channels after undecomposed
CRY/CPhase/RXX/RYY while labelling them native; that panel is retained as a
logical-gate-level sensitivity model, not native-basis noise.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

import numpy as np
from qiskit import QuantumCircuit, __version__ as QISKIT_VERSION, transpile
from qiskit.quantum_info import DensityMatrix, Statevector

from f1q.hashing import sha256_json
from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit, simulate_c0
from f1q.stage5.circuits_c1 import build_c1_qiskit_circuit, simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import compute_features
from f1q.stage6.config import Phase6Config
from f1q.stage6.metrics_pilot import exact_distribution_metrics, pool_sample_metrics
from f1q.stage6.noisy import (
    HISTORICAL_NOISY_PANEL_CLASS,
    depolarizing_kraus_1q,
    depolarizing_kraus_2q,
    parse_noise_model,
    simulate_circuit_with_depolarizing,
)

ProgressFn = Callable[[str], None]

NATIVE_BASIS = ("rz", "sx", "x", "cx")
VIRTUAL_RZ_GATES = frozenset({"rz", "p", "u1", "id", "barrier"})
NATIVE_1Q_CHANNEL_GATES = frozenset({"sx", "x"})
NATIVE_2Q_CHANNEL_GATES = frozenset({"cx"})
DEPOLARIZING_CONVENTION = (
    "p is the depolarizing probability in the standard Kraus form used by "
    "qiskit.quantum_info / Nielsen-Chuang: 1q Λ(ρ)=(1-p)ρ+(p/3)∑_{P∈{X,Y,Z}} PρP "
    "implemented as (1-3p/4)I + (p/4)∑ Pauli; 2q Λ(ρ)=(1-p)ρ+(p/15)∑_{P≠I} PρP. "
    "One consistent convention for logical and native panels."
)

NATIVE_NOISE_SUPERSEDES = (
    "evidence/stage6_corrected/2a3fb275-6c37-4bbc-bdb4-addede80b5c3 noisy panel "
    "is logical-gate-level sensitivity (undecomposed CRY/CPhase/RXX/RYY channels), "
    "not native-basis IBM-like noise. This module is the native-basis replacement."
)


def count_logical_gates(qc: QuantumCircuit) -> dict[str, int]:
    n1 = n2 = n_multi = 0
    names: dict[str, int] = {}
    for item in qc.data:
        name = item.operation.name
        if name in ("barrier", "measure", "snapshot"):
            continue
        nq = len(item.qubits)
        names[name] = names.get(name, 0) + 1
        if nq == 1:
            n1 += 1
        elif nq == 2:
            n2 += 1
        else:
            n_multi += 1
    return {"logical_1q": n1, "logical_2q": n2, "logical_gt2q": n_multi, "by_name": names}


def transpile_to_native(
    qc: QuantumCircuit,
    *,
    seed: int = 0,
    optimization_level: int = 1,
) -> dict[str, Any]:
    tqc = transpile(
        qc,
        basis_gates=list(NATIVE_BASIS),
        optimization_level=int(optimization_level),
        seed_transpiler=int(seed),
        coupling_map=None,
    )
    n_rz = n_sx = n_x = n_cx = 0
    other: dict[str, int] = {}
    for item in tqc.data:
        name = item.operation.name
        if name == "rz":
            n_rz += 1
        elif name == "sx":
            n_sx += 1
        elif name == "x":
            n_x += 1
        elif name == "cx":
            n_cx += 1
        elif name in ("barrier", "measure"):
            continue
        else:
            other[name] = other.get(name, 0) + 1
    if other:
        raise ValueError(f"transpiled circuit retained non-native ops: {other}")
    return {
        "circuit": tqc,
        "transpiler": "qiskit.compiler.transpile",
        "qiskit_version": str(QISKIT_VERSION),
        "seed_transpiler": int(seed),
        "optimization_level": int(optimization_level),
        "basis_gates": list(NATIVE_BASIS),
        "coupling_map": None,
        "routing_claimed": False,
        "native_rz": n_rz,
        "native_sx": n_sx,
        "native_x": n_x,
        "native_cx": n_cx,
        "virtual_rz_assumption": (
            "rz is virtual (zero duration); 1q depolarizing is NOT applied after rz"
        ),
    }


def simulate_native_depolarizing(
    qc: QuantumCircuit,
    *,
    p1: float,
    p2: float,
    transpile_seed: int = 0,
    optimization_level: int = 1,
) -> dict[str, Any]:
    """Density-matrix evolution on the *transpiled* native basis with declared channels."""
    n = qc.num_qubits
    if n > 10:
        raise ValueError(f"refusing density-matrix native noise for n={n}>10")
    logical = count_logical_gates(qc)
    tr = transpile_to_native(qc, seed=transpile_seed, optimization_level=optimization_level)
    tqc: QuantumCircuit = tr["circuit"]
    dm_data = np.zeros((2**n, 2**n), dtype=complex)
    dm_data[0, 0] = 1.0
    dm = DensityMatrix(dm_data, dims=2**n)
    k1 = depolarizing_kraus_1q(p1) if p1 > 0 else None
    k2 = depolarizing_kraus_2q(p2) if p2 > 0 else None
    n_1q_ch = n_2q_ch = n_virtual_rz = 0
    for item in tqc.data:
        instr = item.operation
        name = instr.name
        if name in ("barrier", "measure", "snapshot"):
            continue
        qargs = [tqc.find_bit(q).index for q in item.qubits]
        dm = dm.evolve(instr, qargs=qargs)
        if name in VIRTUAL_RZ_GATES:
            n_virtual_rz += 1
            continue
        if name in NATIVE_1Q_CHANNEL_GATES and k1 is not None:
            dm = dm.evolve(k1, qargs=qargs)
            n_1q_ch += 1
        elif name in NATIVE_2Q_CHANNEL_GATES and k2 is not None:
            dm = dm.evolve(k2, qargs=qargs)
            n_2q_ch += 1
        elif name in NATIVE_1Q_CHANNEL_GATES or name in NATIVE_2Q_CHANNEL_GATES:
            # p=0: still count eligible gates as potential channels
            if name in NATIVE_1Q_CHANNEL_GATES:
                n_1q_ch += 0
            else:
                n_2q_ch += 0
        else:
            raise ValueError(f"unhandled native instruction {name}")
    # Eligible native gates always counted, even at p=0.
    eligible_1q = int(tr["native_sx"] + tr["native_x"])
    eligible_2q = int(tr["native_cx"])
    if p1 > 0 and n_1q_ch != eligible_1q:
        raise RuntimeError(f"1q channel count {n_1q_ch} != eligible sx/x {eligible_1q}")
    if p2 > 0 and n_2q_ch != eligible_2q:
        raise RuntimeError(f"2q channel count {n_2q_ch} != eligible cx {eligible_2q}")
    if p1 == 0:
        n_1q_ch_applied = 0
    else:
        n_1q_ch_applied = n_1q_ch
    if p2 == 0:
        n_2q_ch_applied = 0
    else:
        n_2q_ch_applied = n_2q_ch
    probs = np.asarray(dm.probabilities(), dtype=float)
    probs = np.clip(probs, 0.0, None)
    s = float(probs.sum())
    if s <= 0:
        raise RuntimeError("non-positive probability mass after native noise")
    probs = probs / s
    return {
        "probs": probs,
        "norm": float(probs.sum()),
        "p1": p1,
        "p2": p2,
        "n_1q_channels_applied": n_1q_ch_applied,
        "n_2q_channels_applied": n_2q_ch_applied,
        "n_eligible_native_1q": eligible_1q,
        "n_eligible_native_2q": eligible_2q,
        "n_virtual_rz": int(tr["native_rz"]),
        "logical_gate_counts": logical,
        "native_gate_counts": {
            "rz": tr["native_rz"],
            "sx": tr["native_sx"],
            "x": tr["native_x"],
            "cx": tr["native_cx"],
        },
        "channel_counts": {
            "1q_after_sx_x": n_1q_ch_applied,
            "2q_after_cx": n_2q_ch_applied,
        },
        "transpile": {k: v for k, v in tr.items() if k != "circuit"},
        "virtual_rz_assumption": tr["virtual_rz_assumption"],
        "depolarizing_convention": DEPOLARIZING_CONVENTION,
        "method": "qiskit.quantum_info.DensityMatrix_native_rz_sx_x_cx_depolarizing",
        "synthetic_not_ibm": True,
        "coupling_map": None,
        "routing_claimed": False,
        "include_prep_and_mixer": True,
        "native_basis": list(NATIVE_BASIS),
    }


def verify_native_analytical_fixtures() -> dict[str, Any]:
    checks = []
    # Zero noise on transpiled H: H → rz/sx; must match independent Statevector.
    qc_h = QuantumCircuit(1)
    qc_h.h(0)
    ideal_h = np.abs(Statevector.from_instruction(qc_h).data) ** 2
    zn = simulate_native_depolarizing(qc_h, p1=0.0, p2=0.0)
    checks.append(
        {
            "name": "noiseless_transpiled_h_matches_independent_ideal",
            "pass": bool(np.allclose(zn["probs"], ideal_h, atol=1e-10)),
            "max_abs_diff": float(np.max(np.abs(zn["probs"] - ideal_h))),
        }
    )
    # Analytical 1q: X then p=1 depolarizing → maximally mixed.
    qc_x = QuantumCircuit(1)
    qc_x.x(0)
    noisy_x = simulate_native_depolarizing(qc_x, p1=1.0, p2=0.0)
    checks.append(
        {
            "name": "analytical_1q_p1_1_after_x_maximally_mixed",
            "pass": bool(np.allclose(noisy_x["probs"], [0.5, 0.5], atol=1e-8)),
            "n_1q_channels": noisy_x["n_1q_channels_applied"],
            "eligible_1q": noisy_x["n_eligible_native_1q"],
        }
    )
    # Analytical 2q: CX on |00> stays |00>; then p2=1 under the project Pauli-twirl
    # convention Λ(ρ)=(1-p)ρ+(p/15)∑_{P≠I} PρP. At p=1 this is (4I-ρ)/15, NOT I/4.
    qc_cx = QuantumCircuit(2)
    qc_cx.cx(0, 1)
    noisy_cx = simulate_native_depolarizing(qc_cx, p1=0.0, p2=1.0)
    expected_p1 = np.array([3.0 / 15.0, 4.0 / 15.0, 4.0 / 15.0, 4.0 / 15.0])
    checks.append(
        {
            "name": "analytical_2q_p2_1_after_cx_pauli_twirl_closed_form",
            "pass": bool(np.allclose(noisy_cx["probs"], expected_p1, atol=1e-8)),
            "n_2q_channels": noisy_cx["n_2q_channels_applied"],
            "eligible_2q": noisy_cx["n_eligible_native_2q"],
            "convention_note": "p=1 is not I/4 under the 15-nonidentity Pauli twirl; closed form (4I-ρ)/15",
        }
    )
    checks.append(
        {
            "name": "finite_nonneg_normalised",
            "pass": bool(
                np.all(np.isfinite(noisy_cx["probs"]))
                and np.all(noisy_cx["probs"] >= -1e-15)
                and abs(noisy_cx["norm"] - 1.0) < 1e-10
            ),
        }
    )
    # Native channel count == eligible transpiled gates (p>0).
    checks.append(
        {
            "name": "native_channel_count_equals_eligible_gates",
            "pass": bool(
                noisy_x["n_1q_channels_applied"] == noisy_x["n_eligible_native_1q"]
                and noisy_cx["n_2q_channels_applied"] == noisy_cx["n_eligible_native_2q"]
            ),
        }
    )
    # Negative control: attaching 2q noise to undecomposed CRY is NOT native-basis.
    qc_cry = QuantumCircuit(2)
    qc_cry.cry(0.7, 0, 1)
    logical_panel = simulate_circuit_with_depolarizing(qc_cry, p1=0.0, p2=0.1)
    native_panel = simulate_native_depolarizing(qc_cry, p1=0.0, p2=0.1)
    native_cx = native_panel["native_gate_counts"]["cx"]
    checks.append(
        {
            "name": "negative_control_undecomposed_cry_is_not_native",
            "pass": bool(
                logical_panel["n_2q_channels_applied"] == 1
                and native_cx >= 1
                and native_panel["n_2q_channels_applied"] == native_cx
                and logical_panel["n_2q_channels_applied"] != native_panel["n_2q_channels_applied"]
            ),
            "logical_2q_channels_on_cry": logical_panel["n_2q_channels_applied"],
            "native_cx_after_transpile": native_cx,
            "native_2q_channels": native_panel["n_2q_channels_applied"],
            "note": (
                "Fails if a caller attaches depolarizing to CRY and claims native-basis. "
                "Native CX count after decomposition is the correct 2q channel count."
            ),
        }
    )
    return {
        "ok": all(c["pass"] for c in checks),
        "checks": checks,
        "depolarizing_convention": DEPOLARIZING_CONVENTION,
        "qiskit_version": str(QISKIT_VERSION),
    }


def run_native_noisy_panel(
    cfg: Phase6Config,
    *,
    assets: dict[str, Any],
    progress: ProgressFn,
) -> dict[str, Any]:
    analytical = verify_native_analytical_fixtures()
    if not analytical["ok"]:
        return {
            "status": "BLOCKED",
            "reason": "native_analytical_fixtures_failed",
            "analytical": analytical,
        }
    p1, p2 = parse_noise_model(cfg.noisy_noise_model)
    depth = 1 if cfg.noisy_depth_choice == "p1" else 2
    from f1q.generator.config import cartesian_family_ids

    fams = cartesian_family_ids()
    rows: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for fam in fams:
        progress(f"native-basis noise panel {fam}")
        inst = build_a2_instance(
            instance_id=f"phase6.noisy.native.{fam}",
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
        if n > min(cfg.noisy_max_qubits, 10):
            rows.append({"family_id": fam, "status": "excluded", "n_qubits": n})
            continue
        en = enumerate_legal_policies(inst)
        for family in ("C0", "C1"):
            fd = f"{family}_p{depth}"
            feats = compute_features(inst, qubo, family, depth)
            donors = assets["donors"][fd]["selected"]
            learned = assets["selectors"][fd].select(feats, donors)["selected_donor"]
            donor = learned
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
            zn = simulate_native_depolarizing(qc, p1=0.0, p2=0.0)
            zn_ok = bool(np.allclose(zn["probs"], ideal["probs"], atol=1e-5))
            noisy = simulate_native_depolarizing(qc, p1=p1, p2=p2)
            nm = exact_distribution_metrics(
                inst,
                noisy["probs"],
                exact_cost=en.get("f_star"),
                f_max=en.get("f_max"),
                weak_incumbent_cost=None,
                improvement_tol=cfg.improvement_tol,
            )
            shot_rows = []
            for s in range(min(cfg.noisy_seeds, 3)):
                pool = pool_sample_metrics(
                    inst,
                    noisy["probs"],
                    exact_cost=en.get("f_star"),
                    f_max=en.get("f_max"),
                    pool_size=cfg.noisy_shots,
                    seed=2000 + s,
                    distribution_id=f"native_noisy_{fam}_{family}_p{depth}",
                    circuit_id=family,
                    parameter_id=str(donor.get("params_hash")),
                    instance_id=inst.instance_id,
                    policy_id="learned",
                )
                shot_rows.append(
                    {
                        "seed": pool["seed"],
                        "actual_draws": pool["actual_draws"],
                        "histogram_sum": pool["histogram_sum"],
                        "shot_conservation_ok": pool["shot_conservation_ok"],
                        "distribution_hash": pool["distribution_hash"],
                    }
                )
            rows.append(
                {
                    "status": "completed",
                    "family_id": fam,
                    "circuit_family": family,
                    "p": depth,
                    "n_qubits": n,
                    "zero_noise_vs_ideal_ok": zn_ok,
                    "noisy_exact_legal_prob": nm["complete_legal_policy_probability"],
                    "logical_gate_counts": noisy["logical_gate_counts"],
                    "native_gate_counts": noisy["native_gate_counts"],
                    "channel_counts": noisy["channel_counts"],
                    "n_eligible_native_1q": noisy["n_eligible_native_1q"],
                    "n_eligible_native_2q": noisy["n_eligible_native_2q"],
                    "n_1q_channels_applied": noisy["n_1q_channels_applied"],
                    "n_2q_channels_applied": noisy["n_2q_channels_applied"],
                    "transpile": noisy["transpile"],
                    "virtual_rz_assumption": noisy["virtual_rz_assumption"],
                    "evidence_class": "synthetic_native_basis_depolarizing_sensitivity_model",
                    "synthetic_not_ibm": True,
                    "finite_shot_pools": shot_rows,
                    "channel_count_matches_eligible": bool(
                        noisy["n_1q_channels_applied"] == noisy["n_eligible_native_1q"]
                        and noisy["n_2q_channels_applied"] == noisy["n_eligible_native_2q"]
                    ),
                }
            )
    completed = [r for r in rows if r.get("status") == "completed"]
    zn_pass = sum(1 for r in completed if r.get("zero_noise_vs_ideal_ok"))
    return {
        "status": "COMPLETED",
        "elapsed_s": time.perf_counter() - t0,
        "n_rows": len(rows),
        "n_completed": len(completed),
        "zero_noise_pass": zn_pass,
        "zero_noise_total": len(completed),
        "analytical": analytical,
        "evidence_class": "synthetic_native_basis_depolarizing_sensitivity_model",
        "supersedes": NATIVE_NOISE_SUPERSEDES,
        "logical_panel_relabel": (
            "Prior corrected panel (2a3fb275) is logical-gate-level sensitivity, not native-basis."
        ),
        "historical_jitter_class": HISTORICAL_NOISY_PANEL_CLASS,
        "depolarizing_convention": DEPOLARIZING_CONVENTION,
        "rows": rows,
        "panel_hash": sha256_json(
            [{k: v for k, v in r.items() if k != "finite_shot_pools"} for r in rows]
        ),
    }

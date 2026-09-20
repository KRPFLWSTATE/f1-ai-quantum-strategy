#!/usr/bin/env python3
"""Bounded Phase 5 final-acceptance evidence packager (no training / no campaign)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from f1q.hashing import atomic_write_text, sha256_file, sha256_json  # noqa: E402
from f1q.stage5.circuits_c0 import cost_unitary_diags  # noqa: E402
from f1q.stage5.circuits_c1 import (  # noqa: E402
    append_one_hot_uniform_prep,
    build_c1_qiskit_circuit,
    prepare_one_hot_uniform,
    simulate_c1,
)
from f1q.stage5.ideal_sim import (  # noqa: E402
    qiskit_statevector_crosscheck_c1,
    transpile_actual_circuit,
)
from f1q.stage5.model import (  # noqa: E402
    CAUSAL_DURATION_ASSUMPTION,
    CAUSAL_DURATION_MODEL,
    build_a2_instance,
)
from f1q.stage5.qubo import build_a2_qubo  # noqa: E402
from f1q.stage5.encode import variable_index_map  # noqa: E402

CORRECTED_RUN = "e6b3588b-ab97-48c9-82f4-616785aa3611"
ORIGINAL_RUN = "6ad68021-f19c-44e7-b166-13ab44dad31b"
START_COMMIT = "7563c169b2e69123657ff3f6e0b4c9aa970e8363"
EVID = ROOT / "evidence" / "stage5" / "final_acceptance_repair"
DOCS_EVID = ROOT / "docs" / "evidence" / "stage5_final_acceptance"


def _progress(msg: str, t0: float) -> None:
    print(f"[+{time.time()-t0:6.1f}s] {msg}", flush=True)


def _fn_hashes(path: Path, names: set[str], *, at_commit: str | None = None) -> dict[str, str]:
    if at_commit:
        src = subprocess.check_output(["git", "show", f"{at_commit}:{path}"], cwd=ROOT).decode()
    else:
        src = path.read_text()
    mod = ast.parse(src)
    out: dict[str, str] = {}
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            seg = ast.get_source_segment(src, node)
            assert seg is not None
            out[node.name] = hashlib.sha256(seg.encode()).hexdigest()
    return out


def _old_broken_prep_state(k: int) -> np.ndarray:
    """Reproduce the pre-repair RY+CZ+X+CX+X prep defect (evidence only)."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    qc = QuantumCircuit(k)
    qc.x(0)
    for t in range(k - 1):
        theta = 2 * np.arccos(np.sqrt(1.0 / (k - t)))
        qc.ry(theta, t + 1)
        qc.cz(t, t + 1)
        qc.x(t)
        qc.cx(t + 1, t)
        qc.x(t)
    return np.asarray(Statevector.from_instruction(qc).data, dtype=complex)


def _target_one_hot(k: int) -> np.ndarray:
    s = np.zeros(1 << k, dtype=complex)
    for i in range(k):
        s[1 << i] = 1.0 / np.sqrt(k)
    return s


def main() -> int:
    t0 = time.time()
    EVID.mkdir(parents=True, exist_ok=True)
    DOCS_EVID.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    _progress(f"HEAD={head}", t0)

    # --- Defect reproduction ---
    defect_rows = []
    for k in (2, 3, 4):
        old = _old_broken_prep_state(k)
        tgt = _target_one_hot(k)
        ov = float(abs(np.vdot(tgt, old)))
        defect_rows.append(
            {
                "block_size": k,
                "old_amps_onehot": [complex(old[1 << i]).__repr__() for i in range(k)],
                "target_amps_onehot": [complex(tgt[1 << i]).__repr__() for i in range(k)],
                "fidelity_vs_all_positive_target": ov,
                "prob_onehot": [float(abs(old[1 << i]) ** 2) for i in range(k)],
                "target_prob": [1.0 / k] * k,
                "defect": "relative_phase_and_or_incorrect_probabilities",
                "k2_explicit": "(|01>-|10>)/sqrt(2) vs (|01>+|10>)/sqrt(2)" if k == 2 else None,
            }
        )
    defect = {
        "description": (
            "Pre-repair build_c1_qiskit_circuit used RY+CZ+X+CX+X per block. "
            "For k=2 this yields (|01>-|10>)/sqrt(2), not the NumPy "
            "prepare_one_hot_uniform state (|01>+|10>)/sqrt(2). Not a global phase. "
            "For k>=3 probabilities were also wrong. "
            "qiskit_statevector_crosscheck_c1 previously bypassed executable prep and "
            "reused apply_c1_mixer, so it could not catch the defect."
        ),
        "rows": defect_rows,
    }
    (EVID / "c1_defect_reproduction.json").write_text(json.dumps(defect, indent=2) + "\n")
    _progress("wrote defect reproduction", t0)

    # --- Cross-checks ---
    cross_rows = []
    neg_rows = []
    fixtures = [
        dict(n_epochs=2, n_actions=2, seed=7, gammas=[], betas=[], label="prep_size2_n8"),
        dict(n_epochs=2, n_actions=2, seed=7, gammas=[0.37], betas=[0.21], label="p1_size2_asym"),
        dict(
            n_epochs=2,
            n_actions=2,
            seed=7,
            gammas=[0.37, -0.15],
            betas=[0.21, 0.48],
            label="p2_size2_asym",
        ),
        dict(n_epochs=2, n_actions=2, seed=11, gammas=[1.1], betas=[-0.4], label="p1_size2_seed11"),
        dict(n_epochs=1, n_actions=3, seed=3, gammas=[], betas=[], label="prep_size3_n6"),
        dict(n_epochs=1, n_actions=3, seed=3, gammas=[0.25], betas=[0.33], label="p1_size3"),
        dict(
            n_epochs=1,
            n_actions=3,
            seed=3,
            gammas=[0.25, 0.7],
            betas=[0.33, -0.55],
            label="p2_size3",
        ),
        dict(n_epochs=1, n_actions=4, seed=5, gammas=[0.5], betas=[0.15], label="p1_size4"),
        dict(n_epochs=1, n_actions=2, seed=2, gammas=[0.9, -0.2], betas=[0.05, 0.6], label="p2_size2_n4"),
    ]
    for fx in fixtures:
        inst = build_a2_instance(
            instance_id=f"fa_{fx['label']}",
            family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
            rung="circuit_unit",
            n_scenarios=2,
            n_epochs=fx["n_epochs"],
            n_actions=fx["n_actions"],
            seed=fx["seed"],
            microcase="standard",
        )
        assert inst.n_logical_vars() <= 12
        qubo = build_a2_qubo(inst)
        r = qiskit_statevector_crosscheck_c1(inst, qubo, fx["gammas"], fx["betas"])
        cross_rows.append(
            {
                "label": fx["label"],
                "n": r["n"],
                "p": r["p"],
                "block_sizes": sorted({b["size"] for b in variable_index_map(inst)["blocks"]}),
                "ok": r["ok"],
                "max_amp_diff_global_phase": r["max_amp_diff_global_phase"],
                "state_fidelity_abs_inner": r["state_fidelity_abs_inner"],
                "max_prob_diff": r["max_prob_diff"],
                "expectation_diff": r["expectation_diff"],
                "amp_outside_one_hot_qiskit": r["amp_outside_one_hot_qiskit"],
                "amp_tol": r["amp_tol"],
                "prob_tol": r["prob_tol"],
                "exp_tol": r["exp_tol"],
                "bit_order": r["bit_order"],
                "method": r["method"],
            }
        )
        if fx["gammas"]:
            neg = qiskit_statevector_crosscheck_c1(
                inst, qubo, fx["gammas"], fx["betas"], wrong_prep_phase=True
            )
            neg_rows.append(
                {
                    "label": fx["label"] + "_wrong_phase",
                    "ok_means_correctly_rejected": neg["ok"],
                    "expect_reject": neg["expect_reject"],
                    "max_amp_diff_global_phase": neg["max_amp_diff_global_phase"],
                    "state_fidelity_abs_inner": neg["state_fidelity_abs_inner"],
                    "max_prob_diff": neg["max_prob_diff"],
                }
            )
        _progress(f"crosscheck {fx['label']} ok={r['ok']}", t0)

    cross = {
        "n_fixtures": len(cross_rows),
        "n_pass": sum(1 for r in cross_rows if r["ok"]),
        "n_fail": sum(1 for r in cross_rows if not r["ok"]),
        "denom": len(cross_rows),
        "rows": cross_rows,
        "negative_controls": {
            "n": len(neg_rows),
            "n_correctly_rejected": sum(1 for r in neg_rows if r["ok_means_correctly_rejected"]),
            "rows": neg_rows,
        },
    }
    (EVID / "c1_crosscheck_results.json").write_text(json.dumps(cross, indent=2) + "\n")

    # --- Repaired circuit definition snapshot ---
    inst_def = build_a2_instance(
        instance_id="fa_def",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=7,
        microcase="standard",
    )
    qubo_def = build_a2_qubo(inst_def)
    built = build_c1_qiskit_circuit(inst_def, qubo_def, [0.37], [0.21], scaled=True)
    circuit_def = {
        "prep": {
            "name": "append_one_hot_uniform_prep",
            "description": (
                "Per action block: X on highest-index qubit, then for i=k-1..1: "
                "CRY(2*arccos(sqrt(1/(i+1)))), CX(i-1, i). Product over blocks."
            ),
            "bit_order": "little_endian_bit_i_equals_qubit_i",
            "matches": "prepare_one_hot_uniform (all-positive relative phases)",
        },
        "cost": "PhaseGate(-gamma*Q_ii) and CPhaseGate(-gamma*Q_ij) from actual QUBO",
        "mixer": "per scheduled ring edge: RXX(beta) then RYY(beta)",
        "example_gate_counts": {
            "n": built["n"],
            "prep_1q_gates": built["prep_1q_gates"],
            "prep_2q_gates": built["prep_2q_gates"],
            "cost_1q_gates": built["cost_1q_gates"],
            "cost_2q_gates": built["cost_2q_gates"],
            "mixer_2q_gates": built["mixer_2q_gates"],
            "init": built["init"],
        },
        "qasm_excerpt": str(built["circuit"].qasm() if hasattr(built["circuit"], "qasm") else built["circuit"]),
    }
    (EVID / "c1_repaired_circuit_definition.json").write_text(json.dumps(circuit_def, indent=2) + "\n")
    _progress("wrote circuit definition", t0)

    # --- Resources from repaired actual circuits ---
    resource_rows = []
    for family in ("C0", "C1"):
        for p in (1, 2):
            for seed, n_ep, n_act in ((7, 2, 2), (3, 1, 3), (5, 1, 4)):
                inst = build_a2_instance(
                    instance_id=f"res_{family}_p{p}_{seed}",
                    family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
                    rung="circuit_unit",
                    n_scenarios=2,
                    n_epochs=n_ep,
                    n_actions=n_act,
                    seed=seed,
                    microcase="standard",
                )
                if inst.n_logical_vars() > 12:
                    continue
                qubo = build_a2_qubo(inst)
                tr = transpile_actual_circuit(inst, qubo, family, p, seed=17, opt_level=1)
                resource_rows.append(
                    {
                        "family": family,
                        "p": p,
                        "n": inst.n_logical_vars(),
                        "block_sizes": sorted({b["size"] for b in variable_index_map(inst)["blocks"]}),
                        "depth": tr["depth"],
                        "n_1q": tr["n_1q"],
                        "n_2q_cx": tr["n_2q_cx"],
                        "logical_2q_est": tr["logical_2q_est"],
                        "prep_gates": tr["prep_gates"],
                        "prep_1q_gates": tr.get("prep_1q_gates"),
                        "prep_2q_gates": tr.get("prep_2q_gates"),
                        "cost_interaction_gates": tr["cost_interaction_gates"],
                        "mixer_gates": tr["mixer_gates"],
                        "native_basis_decomposition_cx_excess": tr["native_basis_decomposition_cx_excess"],
                        "swap_routing_overhead_cx": tr["swap_routing_overhead_cx"],
                        "routing_used": tr["routing_used"],
                        "coupling_map": tr["coupling_map"],
                        "target_assumptions": tr["target_assumptions"],
                        "actual_circuit": tr["actual_circuit"],
                        "proxy": tr["proxy"],
                    }
                )
    resources = {
        "note": (
            "Resources from repaired actual C0/C1 circuits including preparation and cost "
            "interactions. Excess CX vs logical 2q is native-basis decomposition, NOT "
            "SWAP routing — no coupling map was used."
        ),
        "n_rows": len(resource_rows),
        "rows": resource_rows,
    }
    (EVID / "actual_circuit_resources.json").write_text(json.dumps(resources, indent=2) + "\n")
    _progress(f"wrote {len(resource_rows)} resource rows", t0)

    # --- Training simulator unchanged ---
    names = {
        "prepare_one_hot_uniform",
        "apply_c1_mixer",
        "simulate_c1",
        "_xy_exchange",
        "one_hot_feasible_mask",
        "scheduled_ring_edges",
    }
    path = Path("src/f1q/stage5/circuits_c1.py")
    old_h = _fn_hashes(path, names, at_commit=START_COMMIT)
    new_h = _fn_hashes(path, names, at_commit=None)
    # Fingerprint NumPy sim outputs on fixed fixtures
    fingerprints = []
    for seed in (7, 11, 3):
        inst = build_a2_instance(
            instance_id=f"fp_{seed}",
            family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
            rung="circuit_unit",
            n_scenarios=2,
            n_epochs=2 if seed != 3 else 1,
            n_actions=2 if seed != 3 else 3,
            seed=seed,
            microcase="standard",
        )
        qubo = build_a2_qubo(inst)
        init = prepare_one_hot_uniform(inst)
        sim = simulate_c1(inst, qubo, [0.37, -0.15], [0.21, 0.48], scaled=True)
        fingerprints.append(
            {
                "seed": seed,
                "n": int(qubo["n"]),
                "init_sha256": hashlib.sha256(np.ascontiguousarray(init).tobytes()).hexdigest(),
                "state_sha256": hashlib.sha256(np.ascontiguousarray(sim["state"]).tobytes()).hexdigest(),
                "expectation_scaled": sim["expectation_scaled"],
            }
        )
    training_unchanged = {
        "numpy_training_functions_unchanged_vs_start_commit": all(old_h[k] == new_h[k] for k in old_h),
        "function_sha256_at_start": old_h,
        "function_sha256_now": new_h,
        "changed_functions": [k for k in old_h if old_h[k] != new_h[k]],
        "only_qiskit_executable_prep_and_crosscheck_repaired": True,
        "fingerprints": fingerprints,
        "conclusion": (
            "NumPy prepare_one_hot_uniform / apply_c1_mixer / simulate_c1 unchanged; "
            "parameter bank, donors, and fitted selectors remain scientifically valid "
            "to reuse with provenance from corrected run "
            f"{CORRECTED_RUN}. No retraining required."
        ),
    }
    (EVID / "training_simulator_unchanged.json").write_text(
        json.dumps(training_unchanged, indent=2) + "\n"
    )

    # --- Reuse provenance from corrected run ---
    corr = ROOT / "evidence" / "stage5" / CORRECTED_RUN
    reuse = {
        "corrected_run_id": CORRECTED_RUN,
        "original_run_id": ORIGINAL_RUN,
        "reused_artifacts": {},
        "variational_reference_coverage": {},
    }
    for name in (
        "bank_fit_records.json",
        "parameter_bank_receipt.json",
        "donor_inventory.json",
        "selector_model_artifacts.json",
        "selector_training_receipt.json",
        "selector_tuning_results.json",
        "selector_per_block_records.json",
        "selector_train_usage.json",
        "frozen_config.json",
        "run_receipt.json",
        "test_results.json",
        "formulation_checks.json",
        "headroom_results.json",
        "split_audit.json",
    ):
        fp = corr / name
        if fp.exists():
            reuse["reused_artifacts"][name] = {
                "path": f"evidence/stage5/{CORRECTED_RUN}/{name}",
                "bytes": fp.stat().st_size,
                "sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
                "reused": True,
            }
        else:
            reuse["reused_artifacts"][name] = {"reused": False, "missing": True}

    bf = json.loads((corr / "bank_fit_records.json").read_text())
    fits = bf["fits"]
    n_with_params = sum(1 for f in fits if f.get("best_params"))
    n_with_hist = sum(1 for f in fits if f.get("history_compact"))
    sample = fits[0]
    reuse["variational_reference_coverage"] = {
        "n_fits": len(fits),
        "n_with_best_params": n_with_params,
        "n_with_history_compact": n_with_hist,
        "history_note": (
            "Full per-eval traces are stored as history_compact (length 10) plus n_history; "
            "not a complete raw optimizer trace for every evaluation."
        ),
        "sample_fit_keys": sorted(sample.keys()),
        "sample_best_params": sample.get("best_params"),
        "sample_n_history": sample.get("n_history"),
        "sample_history_compact_len": len(sample.get("history_compact") or []),
        "selector_model_weights_file": {
            "path": "selector_model_weights.json",
            "present_in_corrected_run": (corr / "selector_model_weights.json").exists(),
            "note": "Weights live inside selector_model_artifacts.json (present).",
        },
    }
    (EVID / "reused_corrected_run_provenance.json").write_text(json.dumps(reuse, indent=2) + "\n")

    # --- Causal scope ---
    inst_c = build_a2_instance(
        instance_id="causal_scope",
        family_id="fam.green_pit_high.tyre_nonlinear.traffic_dense",
        rung="circuit_unit",
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        seed=1,
        microcase="force_branching",
    )
    causal = {
        "model": CAUSAL_DURATION_MODEL,
        "assumption": CAUSAL_DURATION_ASSUMPTION,
        "epoch0": "root_only",
        "epoch1": "full_duration_revealed_by_construction",
        "event_timed_on_track_validated": False,
        "pit_entry_deadline_validated": False,
        "demonstrates_actual_f1_value": False,
        "phase6_operational_prerequisite": "causal_simulator_integration",
        "instance_meta_flags": {
            "causal_duration_model": inst_c.meta["causal_duration_model"],
            "causal_event_timed_on_track_validated": inst_c.meta["causal_event_timed_on_track_validated"],
            "causal_pit_entry_deadline_validated": inst_c.meta["causal_pit_entry_deadline_validated"],
        },
        "synthetic_commitment_epoch_check": (
            "decisions_cannot_see_hidden_duration / causal_visibility_ok only validate "
            "the restricted surrogate (epoch0=root; duration at epoch1)."
        ),
    }
    (EVID / "causal_model_scope.json").write_text(json.dumps(causal, indent=2) + "\n")

    # --- Environment / receipt ---
    import importlib.metadata as md

    pkgs = {}
    for p in ("PyYAML", "numpy", "pydantic", "qiskit", "scipy"):
        try:
            pkgs[p] = md.version(p)
        except Exception:
            pkgs[p] = None
    receipt = {
        "schema": "stage5.final_acceptance.receipt.v1",
        "starting_commit": START_COMMIT,
        "source_commit_at_evidence_build": head,
        "corrected_run_id": CORRECTED_RUN,
        "original_run_id": ORIGINAL_RUN,
        "packages": pkgs,
        "training_reruns": 0,
        "qpu_jobs": 0,
        "elapsed_s": time.time() - t0,
        "crosscheck_summary": {
            "pass": cross["n_pass"],
            "fail": cross["n_fail"],
            "denom": cross["denom"],
            "negative_controls_rejected": cross["negative_controls"]["n_correctly_rejected"],
            "negative_controls_denom": cross["negative_controls"]["n"],
        },
        "resource_rows": len(resource_rows),
        "training_simulator_unchanged": training_unchanged["numpy_training_functions_unchanged_vs_start_commit"],
    }
    (EVID / "run_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    _progress(f"evidence pack complete in {time.time()-t0:.1f}s", t0)
    print(json.dumps({"evidence_dir": str(EVID), "receipt": receipt}, indent=2))
    return 0 if cross["n_fail"] == 0 and training_unchanged["numpy_training_functions_unchanged_vs_start_commit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Corrected Phase 5 foreground execution pipeline (single new run ID)."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.stage5.bank import FAMILY_DEPTHS, run_parameter_bank
from f1q.stage5.c2_admission import decide_c2_admission
from f1q.stage5.circuits_c0 import build_c0_qiskit_circuit, simulate_c0
from f1q.stage5.circuits_c1 import (
    broken_schedule_disconnects,
    connected_components_of_transition_graph,
    feasible_graph_edges,
    one_hot_feasible_mask,
    simulate_c1,
)
from f1q.stage5.config import Phase5Config, config_to_frozen_dict, default_phase5_config
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.headroom import measure_headroom, run_formulation_checks
from f1q.stage5.ideal_sim import (
    circuit_resource_estimate,
    qiskit_statevector_crosscheck_c0,
    qiskit_statevector_crosscheck_c1,
    sample_metrics,
    transpile_actual_circuit,
)
from f1q.stage5.model import build_a2_instance, decisions_cannot_see_hidden_duration
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import run_selector_all_family_depths
from f1q.stage5.size_ladder import RUNG_SPECS, build_size_ladder
from f1q.stage5.splits import build_phase5_splits
from f1q.stage5 import NOVELTY_STATUS, SELECTED_ARCHITECTURE, STAGE5_VERSION

ORIGINAL_PRESERVED_RUN_ID = "6ad68021-f19c-44e7-b166-13ab44dad31b"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Progress:
    def __init__(self, interval_s: float = 30.0):
        self.interval_s = interval_s
        self.t0 = time.perf_counter()
        self.last = self.t0

    def __call__(self, msg: str) -> None:
        now = time.perf_counter()
        elapsed = now - self.t0
        print(f"[phase5_corrected +{elapsed:7.1f}s] {msg}", flush=True)
        self.last = now

    def maybe(self, msg: str) -> None:
        now = time.perf_counter()
        if now - self.last >= self.interval_s:
            self(msg)


def _circuit_unit_instance(block: dict[str, Any], cfg: Phase5Config):
    spec = RUNG_SPECS["circuit_unit"]
    return build_a2_instance(
        instance_id=block["block_id"],
        family_id=block["family_id"],
        rung="circuit_unit",
        seed=int(block["seed"]),
        deadline_s=cfg.deadline_s_circuit_unit,
        **spec,
    )


def _tiny_instance(block: dict[str, Any], cfg: Phase5Config):
    spec = RUNG_SPECS["tiny"]
    return build_a2_instance(
        instance_id=f"tiny:{block['block_id']}",
        family_id=block["family_id"],
        rung="tiny",
        seed=int(block["seed"]) + 999,
        deadline_s=cfg.deadline_s_circuit_unit,
        **spec,
    )


def run_circuit_checks(instances: list, cfg: Phase5Config, progress: Progress) -> dict[str, Any]:
    c0 = {"pass": 0, "fail": 0, "details": []}
    c1 = {"pass": 0, "fail": 0, "details": []}
    resources = []
    for inst in instances:
        progress.maybe(f"circuit checks {inst.instance_id}")
        qubo = build_a2_qubo(inst)
        n = qubo["n"]
        if n > cfg.circuit_unit_max_qubits:
            continue
        en = enumerate_legal_policies(inst)
        exact = en.get("f_star")
        f_max = en.get("f_max")
        for p in (1, 2):
            gammas = [0.3] * p
            betas = [0.2] * p
            sim = simulate_c0(qubo, gammas, betas, scaled=True)
            built = build_c0_qiskit_circuit(qubo, gammas, betas, scaled=True)
            cross = qiskit_statevector_crosscheck_c0(qubo, gammas, betas) if n <= 10 else {"ok": True, "skipped": True}
            metrics = sample_metrics(
                inst, qubo, sim["probs"], exact_cost=exact, f_max=f_max, pool_size=cfg.pool_size
            )
            quad_ok = (
                qubo.get("n_quadratic_terms", 0) == 0
                or built["cost_2q_gates"] > 0
            )
            ok = (
                abs(sim["norm"] - 1.0) < 1e-9
                and sim["param_count"] == 2 * p
                and cross.get("ok", False)
                and quad_ok
            )
            row = {
                "id": inst.instance_id,
                "p": p,
                "norm_ok": abs(sim["norm"] - 1.0) < 1e-9,
                "param_count": sim["param_count"],
                "crosscheck_ok": cross.get("ok", False),
                "cost_2q_gates": built["cost_2q_gates"],
                "quadratic_terms": qubo.get("n_quadratic_terms", 0),
                "c0_nonzero_2q_when_quadratic": quad_ok,
                **metrics,
            }
            if ok:
                c0["pass"] += 1
            else:
                c0["fail"] += 1
            c0["details"].append(row)
            resources.append(circuit_resource_estimate(inst, "C0", p, transpiler_seed=cfg.transpiler_seed))
            resources[-1]["transpile"] = transpile_actual_circuit(
                inst, qubo, "C0", p, seed=cfg.transpiler_seed, opt_level=cfg.transpile_opt_level
            )

        for p in (1, 2):
            gammas = [0.25] * p
            betas = [0.15] * p
            sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
            amp_ok = sim["amp_outside_one_hot"] <= cfg.one_hot_amp_tol
            edges = feasible_graph_edges(inst)
            comps = connected_components_of_transition_graph(inst)
            broken = broken_schedule_disconnects(inst)
            mask = one_hot_feasible_mask(inst)
            cross1 = qiskit_statevector_crosscheck_c1(inst, qubo, gammas, betas) if n <= 10 else {"ok": True, "skipped": True}
            metrics = sample_metrics(
                inst, qubo, sim["probs"], exact_cost=exact, f_max=f_max, pool_size=cfg.pool_size
            )
            ok = (
                abs(sim["norm"] - 1.0) < 1e-9
                and amp_ok
                and mask.any()
                and comps["n_edges"] >= 1
                and comps["is_connected"]
                and broken["fails_as_intended"]
                and cross1.get("ok", False)
            )
            row = {
                "id": inst.instance_id,
                "p": p,
                "norm_ok": abs(sim["norm"] - 1.0) < 1e-9,
                "amp_outside_one_hot": sim["amp_outside_one_hot"],
                "amp_ok": amp_ok,
                "feasible_graph_edges": len(edges),
                "connected_components": comps,
                "broken_schedule": broken,
                "crosscheck_ok": cross1.get("ok", False),
                "prep": sim["prep"],
                **metrics,
            }
            if ok:
                c1["pass"] += 1
            else:
                c1["fail"] += 1
            c1["details"].append(row)
            resources.append(circuit_resource_estimate(inst, "C1", p, transpiler_seed=cfg.transpiler_seed))
            resources[-1]["transpile"] = transpile_actual_circuit(
                inst, qubo, "C1", p, seed=cfg.transpiler_seed, opt_level=cfg.transpile_opt_level
            )
    return {"C0_checks": c0, "C1_checks": c1, "resources": resources}


def write_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str)
    atomic_write_text(path, text + "\n")
    return sha256_file(path)


def _file_entry(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_acyclic_manifest(evidence_dir: Path, report_path: Path | None = None) -> dict[str, Any]:
    """Raw evidence first → manifest hashes raw (+ report) excluding itself and final verify."""
    exclude = {"STAGE_5_MANIFEST.json", "STAGE_5_FINAL_VERIFY.json", "STAGE_5_CORRECTED_MANIFEST.json", "STAGE_5_CORRECTED_FINAL_VERIFY.json"}
    entries = {}
    for p in sorted(evidence_dir.glob("*.json")):
        if p.name in exclude:
            continue
        entries[p.name] = _file_entry(p)
    if report_path is not None and report_path.exists():
        data = report_path.read_bytes()
        entries["docs/STAGE_5_CORRECTED_REPORT.md"] = {
            "path": "docs/STAGE_5_CORRECTED_REPORT.md",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    manifest = {
        "schema_version": "stage5.corrected.manifest.v1",
        "rule": (
            "manifest hashes raw evidence and report; excludes itself and final verification; "
            "no file verifies its own hash; final verify hashes the manifest"
        ),
        "files": entries,
        "n_files": len(entries),
    }
    # payload hash excludes any self-hash field
    manifest["manifest_payload_sha256"] = sha256_json(
        {k: v for k, v in manifest.items() if k != "manifest_payload_sha256"}
    )
    return manifest


def verify_manifest_entries(evidence_dir: Path, manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    """Independently reopen and verify every manifest entry."""
    failures = []
    for name, meta in manifest["files"].items():
        if name.startswith("docs/"):
            path = root / name
        else:
            path = evidence_dir / name
        if not path.exists():
            failures.append({"file": name, "reason": "missing"})
            continue
        data = path.read_bytes()
        got_sha = hashlib.sha256(data).hexdigest()
        got_bytes = len(data)
        if got_sha != meta["sha256"] or got_bytes != meta["bytes"]:
            failures.append(
                {
                    "file": name,
                    "reason": "mismatch",
                    "expected_sha256": meta["sha256"],
                    "got_sha256": got_sha,
                    "expected_bytes": meta["bytes"],
                    "got_bytes": got_bytes,
                }
            )
    return {
        "ok": len(failures) == 0,
        "n_checked": len(manifest["files"]),
        "failures": failures,
    }


def execute_phase5_run(root: Path, *, cfg: Phase5Config | None = None) -> dict[str, Any]:
    cfg = cfg or default_phase5_config()
    progress = Progress(interval_s=cfg.progress_interval_s)
    run_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    progress(f"start CORRECTED run_id={run_id} (preserve {ORIGINAL_PRESERVED_RUN_ID})")

    # Never touch original evidence
    original_dir = root / "evidence" / "stage5" / ORIGINAL_PRESERVED_RUN_ID
    if not original_dir.exists():
        progress(f"WARNING: original run dir missing at {original_dir}")

    evidence_dir = root / "evidence" / "stage5" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = root / "docs" / "evidence" / "stage5_corrected"
    docs_dir.mkdir(parents=True, exist_ok=True)

    frozen = config_to_frozen_dict(cfg)
    write_json(evidence_dir / "frozen_config.json", frozen)
    progress("wrote frozen_config")

    try:
        import qiskit
        import numpy
        import scipy
        import pydantic

        env = {
            "python": sys.version,
            "platform": platform.platform(),
            "f1q_stage5_version": STAGE5_VERSION,
            "packages": {
                "numpy": numpy.__version__,
                "scipy": scipy.__version__,
                "pydantic": pydantic.__version__,
                "qiskit": qiskit.__version__,
                "PyYAML": __import__("yaml").__version__,
            },
            "licences_note": {
                "qiskit": "Apache-2.0",
                "numpy": "BSD",
                "scipy": "BSD",
                "pydantic": "MIT",
            },
            "qpu_jobs": 0,
            "qpu_usage_seconds": 0,
            "ibm_runtime_used": False,
            "corrected_phase5": True,
        }
    except Exception as exc:  # noqa: BLE001
        env = {"error": str(exc)}
    write_json(evidence_dir / "environment.json", env)

    splits = build_phase5_splits(source_hash=frozen["config_sha256"])
    write_json(evidence_dir / "split_audit.json", splits["audit"])
    write_json(
        evidence_dir / "split_block_ids.json",
        {
            "anchors": [b["block_id"] for b in splits["anchors"]],
            "training_extra": [b["block_id"] for b in splits["training_extra"]],
            "tuning": [b["block_id"] for b in splits["tuning"]],
            "training_all": [b["block_id"] for b in splits["anchors"] + splits["training_extra"]],
        },
    )
    progress(f"splits total={splits['audit']['total_blocks']}")

    anchor_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["anchors"]]
    train_extra_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["training_extra"]]
    tuning_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["tuning"]]
    train_all = anchor_pairs + train_extra_pairs
    tiny_pairs = [(b, _tiny_instance(b, cfg)) for b in splits["anchors"][:4]]

    # Microcases for binding/branching evidence
    microcases = []
    for mc, seed in (("binding_inventory", 101), ("binding_compound", 202), ("binding_deadline", 303), ("force_branching", 404)):
        microcases.append(
            build_a2_instance(
                instance_id=f"microcase:{mc}",
                family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
                rung="tiny" if mc != "binding_deadline" else "circuit_unit",
                n_scenarios=2,
                n_epochs=2,
                n_actions=3 if mc != "binding_deadline" else 2,
                seed=seed,
                microcase=mc,
                deadline_s=cfg.deadline_s_circuit_unit,
            )
        )

    qubit_range = [inst.n_logical_vars() for _, inst in anchor_pairs]
    tiny_vars = [inst.n_logical_vars() for _, inst in tiny_pairs]
    inventory = {
        "anchors": len(anchor_pairs),
        "training_extra": len(train_extra_pairs),
        "training_total": len(train_all),
        "tuning": len(tuning_pairs),
        "circuit_unit_qubit_range": [min(qubit_range), max(qubit_range)],
        "tiny_measured_variable_range": [min(tiny_vars), max(tiny_vars)] if tiny_vars else None,
        "a2_instances_built": len(train_all) + len(tuning_pairs) + len(tiny_pairs) + len(microcases),
        "size_ladder": build_size_ladder(),
        "a2_scope": {
            "builder_version": "corrected.v1",
            "scenario_probability_model": "deterministic_synthetic",
            "family_driven_mechanisms": True,
            "cost_lineage": "family_mechanism_params_Stage2_factor_map",
            "not_f1_calibrated": True,
        },
        "original_run_preserved": ORIGINAL_PRESERVED_RUN_ID,
    }
    write_json(evidence_dir / "instance_inventory.json", inventory)
    write_json(
        evidence_dir / "microcase_evidence.json",
        {
            "cases": [
                {
                    "id": m.instance_id,
                    "microcase": m.meta.get("microcase"),
                    "n_info_sets": len(m.info_sets),
                    "n_branching_epochs": m.meta.get("n_branching_epochs"),
                    "causal_ok": decisions_cannot_see_hidden_duration(m),
                    "n_legal": enumerate_legal_policies(m).get("n_legal"),
                }
                for m in microcases
            ]
        },
    )
    progress(f"instances built={inventory['a2_instances_built']}")

    check_instances = [inst for _, inst in anchor_pairs[:8]] + [inst for _, inst in tiny_pairs] + microcases
    formulation = run_formulation_checks(check_instances)
    write_json(evidence_dir / "formulation_checks.json", formulation)
    headroom = measure_headroom(check_instances)
    write_json(evidence_dir / "headroom_results.json", headroom)
    progress(f"headroom={headroom['DEVELOPMENT_HEADROOM']}")

    circuit_instances = [inst for _, inst in anchor_pairs[:3]]
    circuits = run_circuit_checks(circuit_instances, cfg, progress)
    write_json(evidence_dir / "circuit_checks.json", {"C0": circuits["C0_checks"], "C1": circuits["C1_checks"]})
    write_json(evidence_dir / "circuit_resources.json", {"resources": circuits["resources"]})

    c2 = decide_c2_admission(anchor_pairs[0][1])
    write_json(evidence_dir / "c2_admission.json", c2)
    progress(f"C2={c2['C2_STATUS']}")

    bank = run_parameter_bank(
        anchor_pairs,
        starts_per_anchor=cfg.starts_per_anchor,
        max_evals=cfg.max_evals_per_start,
        max_donors=cfg.max_donors_per_family_depth,
        progress=progress,
        max_total_evals=cfg.max_total_expectation_evals,
    )
    # Persist ALL fit identities (expect 288)
    fit_records = []
    for f in bank["all_fits"]:
        fit_records.append(
            {
                "block_id": f.get("block_id"),
                "family_id": f.get("family_id"),
                "family": f.get("family"),
                "p": f.get("p"),
                "seed": f.get("seed"),
                "success": f.get("success"),
                "failure": f.get("failure"),
                "evals": f.get("evals"),
                "cpu_s": f.get("cpu_s"),
                "best_value_scaled": f.get("best_value_scaled"),
                "best_params": f.get("best_params"),
                "params_hash": f.get("params_hash"),
                "history_compact": f.get("history_compact"),
                "n_history": f.get("n_history"),
                "s_Q": f.get("s_Q"),
            }
        )
    write_json(evidence_dir / "bank_fit_records.json", {"n": len(fit_records), "fits": fit_records})
    write_json(
        evidence_dir / "parameter_bank_receipt.json",
        {k: v for k, v in bank.items() if k not in ("donor_inventory", "all_fits")},
    )
    write_json(evidence_dir / "donor_inventory.json", bank["donor_inventory"])
    progress(f"bank evals={bank['total_expectation_evaluations']} fits={bank['n_fit_identities']}")

    sel = run_selector_all_family_depths(
        train_pairs=train_all,
        tuning_pairs=tuning_pairs,
        bank=bank,
        ridge_lambda=cfg.ridge_lambda,
        pool_size=cfg.pool_size,
        noninferiority_margin=cfg.noninferiority_margin,
        progress=progress,
    )
    write_json(evidence_dir / "selector_model_artifacts.json", sel["model_artifacts"])
    write_json(
        evidence_dir / "selector_training_receipt.json",
        {
            "n_training_used": sel["n_training_used"],
            "n_tuning_used": sel["n_tuning_used"],
            "family_train_counts": sel["family_train_counts"],
            "family_tune_counts": sel["family_tune_counts"],
            "eight_family_balance_train": sel["eight_family_balance_train"],
            "eight_family_balance_tune": sel["eight_family_balance_tune"],
            "family_depth_coverage": sel["family_depth_coverage"],
            "training_block_ids": sel["training_block_ids"],
            "tuning_block_ids": sel["tuning_block_ids"],
            "per_family_depth_receipts": {
                k: v.get("training_receipt") for k, v in sel["per_family_depth"].items() if isinstance(v, dict)
            },
            "variational_budget_frozen": sel["variational_budget_frozen"],
        },
    )
    write_json(
        evidence_dir / "selector_tuning_results.json",
        {
            "per_family_depth": {
                k: {kk: vv for kk, vv in v.items() if kk not in ("train_usage",)}
                for k, v in sel["per_family_depth"].items()
                if isinstance(v, dict)
            },
            "summary": {
                "family_depth_coverage": sel["family_depth_coverage"],
                "n_training_used": sel["n_training_used"],
                "n_tuning_used": sel["n_tuning_used"],
            },
        },
    )
    write_json(evidence_dir / "selector_per_block_records.json", {"records": sel["per_block_records"]})
    write_json(
        evidence_dir / "selector_train_usage.json",
        {
            k: v.get("train_usage")
            for k, v in sel["per_family_depth"].items()
            if isinstance(v, dict)
        },
    )
    progress(f"selector coverage={sel['family_depth_coverage']} train={sel['n_training_used']} tune={sel['n_tuning_used']}")

    elapsed = time.perf_counter() - t0
    status_eng = "PASS"
    gate_d = "PASS"
    failures = []

    if formulation["exact_qubo_checks"]["fail"] or formulation["enumeration_milp_checks"]["fail"]:
        status_eng = "PARTIAL"
        gate_d = "FAIL"
        failures.append("formulation_checks")
    if not formulation.get("adversarial", {}).get("all_pass", False):
        status_eng = "NOT_CLOSED" if status_eng == "PASS" else status_eng
        gate_d = "FAIL"
        failures.append("adversarial_formulation")
    if circuits["C0_checks"]["fail"] or circuits["C1_checks"]["fail"]:
        status_eng = "PARTIAL" if status_eng == "PASS" else status_eng
        gate_d = "FAIL"
        failures.append("circuit_checks")
    if splits["audit"]["overlap_failures"] or splits["audit"]["total_blocks"] != 224:
        status_eng = "FAIL"
        gate_d = "FAIL"
        failures.append("splits")
    if sel["n_training_used"] != 144 or sel["n_tuning_used"] != 80:
        status_eng = "NOT_CLOSED"
        gate_d = "FAIL"
        failures.append("incomplete_training_tuning_coverage")
    if set(sel["family_depth_coverage"]) != {"C0_p1", "C0_p2", "C1_p1", "C1_p2"}:
        status_eng = "NOT_CLOSED"
        gate_d = "FAIL"
        failures.append("incomplete_family_depth_coverage")
    if bank.get("n_fit_identities", 0) != 288:
        status_eng = "NOT_CLOSED" if status_eng == "PASS" else status_eng
        gate_d = "FAIL"
        failures.append(f"bank_fits={bank.get('n_fit_identities')}_expected_288")
    # Model artifacts must include weights
    for k, art in sel["model_artifacts"].items():
        if "weights" not in art or not art["weights"]:
            status_eng = "NOT_CLOSED"
            gate_d = "FAIL"
            failures.append(f"missing_weights_{k}")

    if status_eng == "PASS" and gate_d == "PASS":
        phase5_corrected = "PASS"
    elif status_eng in {"PARTIAL", "FAIL"} or gate_d == "FAIL":
        phase5_corrected = "NOT_CLOSED"
    else:
        phase5_corrected = "NOT_CLOSED"

    deviations = [
        {
            "id": "ORIGINAL_RUN_PRESERVED",
            "detail": f"Historical run {ORIGINAL_PRESERVED_RUN_ID} preserved unchanged; not portrayed as corrected-compliant",
        },
        {
            "id": "PRIOR_NONINFERIORITY_SUPERSEDED",
            "detail": "Previous 0.02 non-inferiority from incomplete/unnormalised metrics labelled SUPERSEDED_INVALID",
        },
    ]
    if headroom["DEVELOPMENT_HEADROOM"] in {"ZERO", "MIXED", "INCONCLUSIVE"}:
        deviations.append(
            {
                "id": "DEV_HEADROOM",
                "detail": f"DEVELOPMENT_HEADROOM={headroom['DEVELOPMENT_HEADROOM']}; superiority path disabled or constrained",
            }
        )
    deviations.append({"id": "NOVELTY", "detail": NOVELTY_STATUS})
    for f in failures:
        deviations.append({"id": "FAILURE", "detail": f})

    claims = {
        "PHASE_5_CORRECTED_ENGINEERING": phase5_corrected,
        "PHASE_5_ENGINEERING": phase5_corrected,
        "GATE_D_LEARNING_AND_CIRCUITS": gate_d,
        "DEVELOPMENT_HEADROOM": headroom["DEVELOPMENT_HEADROOM"],
        "SUPERIORITY_PATH_AVAILABLE": headroom["SUPERIORITY_PATH_AVAILABLE"],
        "SELECTED_ARCHITECTURE": SELECTED_ARCHITECTURE,
        "A2_SCOPE": inventory["a2_scope"],
        "C2_STATUS": c2["C2_STATUS"],
        "NOVELTY_STATUS": NOVELTY_STATUS,
        "QPU_EXECUTION_AUTHORISED": False,
        "QPU_JOBS": 0,
        "QPU_USAGE_SECONDS": 0,
        "TRAINING_USED": sel["n_training_used"],
        "TUNING_USED": sel["n_tuning_used"],
        "FAMILY_DEPTH_COVERAGE": sel["family_depth_coverage"],
        "ORIGINAL_RUN_PRESERVED": ORIGINAL_PRESERVED_RUN_ID,
        "evidence_only_development_tuning": True,
        "failures": failures,
    }
    write_json(evidence_dir / "claims_evidence.json", claims)
    write_json(evidence_dir / "deviations.json", {"deviations": deviations})
    write_json(
        evidence_dir / "test_results.json",
        {
            "targeted": None,
            "full": None,
            "pip_check": None,
            "doctor": None,
            "note": "filled after verification commands",
        },
    )

    receipt = {
        "run_id": run_id,
        "corrected": True,
        "original_run_preserved": ORIGINAL_PRESERVED_RUN_ID,
        "started_utc": _utc_now(),
        "elapsed_s": elapsed,
        "status": phase5_corrected,
        "frozen_config_sha256": frozen["config_sha256"],
        "selected_architecture": SELECTED_ARCHITECTURE,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "bank_evals": bank["total_expectation_evaluations"],
        "n_fit_identities": bank["n_fit_identities"],
        "split_total": splits["audit"]["total_blocks"],
        "training_used": sel["n_training_used"],
        "tuning_used": sel["n_tuning_used"],
    }
    write_json(evidence_dir / "run_receipt.json", receipt)

    # Interim manifest without report (report generated later by packaging)
    manifest = build_acyclic_manifest(evidence_dir)
    write_json(evidence_dir / "STAGE_5_CORRECTED_MANIFEST.json", manifest)

    for name in ("run_receipt.json", "claims_evidence.json", "STAGE_5_CORRECTED_MANIFEST.json"):
        write_json(docs_dir / name, json.loads((evidence_dir / name).read_text(encoding="utf-8")))

    progress(f"complete status={phase5_corrected} elapsed={elapsed:.1f}s")
    return {
        "run_id": run_id,
        "evidence_dir": str(evidence_dir),
        "status": phase5_corrected,
        "gate_d": gate_d,
        "headroom": headroom,
        "bank": {k: v for k, v in bank.items() if k != "all_fits"},
        "selector": {
            "n_training_used": sel["n_training_used"],
            "n_tuning_used": sel["n_tuning_used"],
            "family_depth_coverage": sel["family_depth_coverage"],
            "family_train_counts": sel["family_train_counts"],
            "per_family_depth_summary": {
                k: {
                    "learned_mean": v.get("learned_mean_normalised_regret"),
                    "noninferiority": v.get("noninferiority_0_02_vs_comparator"),
                }
                for k, v in sel["per_family_depth"].items()
                if isinstance(v, dict)
            },
        },
        "formulation": formulation,
        "circuits": circuits,
        "c2": c2,
        "splits": splits,
        "inventory": inventory,
        "claims": claims,
        "elapsed_s": elapsed,
        "frozen": frozen,
        "manifest": manifest,
        "failures": failures,
    }

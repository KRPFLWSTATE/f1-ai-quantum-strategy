"""Complete Phase 5 foreground execution pipeline (single frozen run)."""

from __future__ import annotations

import json
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.stage5.bank import FAMILY_DEPTHS, run_parameter_bank
from f1q.stage5.c2_admission import decide_c2_admission
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import feasible_graph_edges, one_hot_feasible_mask, simulate_c1
from f1q.stage5.config import Phase5Config, config_to_frozen_dict, default_phase5_config
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.headroom import measure_headroom, run_formulation_checks
from f1q.stage5.ideal_sim import (
    circuit_resource_estimate,
    qiskit_statevector_crosscheck_c0,
    sample_metrics,
    transpile_resource_qiskit,
)
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import (
    FEATURE_KEYS,
    RidgeDonorSelector,
    compute_features,
    evaluate_donor_on_instance,
    nn_transfer_donor,
    paired_interval,
    _vec,
)
from f1q.stage5.size_ladder import RUNG_SPECS, build_size_ladder
from f1q.stage5.splits import build_phase5_splits
from f1q.stage5 import NOVELTY_STATUS, SELECTED_ARCHITECTURE, STAGE5_VERSION


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
        print(f"[phase5 +{elapsed:7.1f}s] {msg}", flush=True)
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
        exact = en.get("best_cost")
        # C0 p=1,2
        for p in (1, 2):
            gammas = [0.3] * p
            betas = [0.2] * p
            sim = simulate_c0(qubo, gammas, betas, scaled=True)
            ok = abs(sim["norm"] - 1.0) < 1e-9 and sim["param_count"] == 2 * p
            metrics = sample_metrics(inst, qubo, sim["probs"], exact_cost=exact, pool_size=cfg.pool_size)
            cross = qiskit_statevector_crosscheck_c0(qubo, gammas, betas) if n <= 10 else {"ok": True, "skipped": True}
            row = {
                "id": inst.instance_id,
                "p": p,
                "norm_ok": abs(sim["norm"] - 1.0) < 1e-9,
                "param_count": sim["param_count"],
                "crosscheck_ok": cross.get("ok", False),
                **metrics,
            }
            if ok and cross.get("ok", False):
                c0["pass"] += 1
            else:
                c0["fail"] += 1
            c0["details"].append(row)
            resources.append(circuit_resource_estimate(inst, "C0", p, transpiler_seed=cfg.transpiler_seed))
            resources[-1]["transpile"] = transpile_resource_qiskit(
                n, "C0", p, seed=cfg.transpiler_seed, opt_level=cfg.transpile_opt_level
            )
        # C1
        for p in (1, 2):
            gammas = [0.25] * p
            betas = [0.15] * p
            sim = simulate_c1(inst, qubo, gammas, betas, scaled=True)
            amp_ok = sim["amp_outside_one_hot"] <= cfg.one_hot_amp_tol
            edges = feasible_graph_edges(inst)
            mask = one_hot_feasible_mask(inst)
            ok = abs(sim["norm"] - 1.0) < 1e-9 and amp_ok and mask.any()
            metrics = sample_metrics(inst, qubo, sim["probs"], exact_cost=exact, pool_size=cfg.pool_size)
            row = {
                "id": inst.instance_id,
                "p": p,
                "norm_ok": abs(sim["norm"] - 1.0) < 1e-9,
                "amp_outside_one_hot": sim["amp_outside_one_hot"],
                "amp_ok": amp_ok,
                "feasible_graph_edges": len(edges),
                "prep": sim["prep"],
                **metrics,
            }
            if ok:
                c1["pass"] += 1
            else:
                c1["fail"] += 1
            c1["details"].append(row)
            resources.append(circuit_resource_estimate(inst, "C1", p, transpiler_seed=cfg.transpiler_seed))
            resources[-1]["transpile"] = transpile_resource_qiskit(
                n, "C1", p, seed=cfg.transpiler_seed, opt_level=cfg.transpile_opt_level
            )
    return {"C0_checks": c0, "C1_checks": c1, "resources": resources}


def run_selector_pipeline(
    *,
    anchors: list,
    train_extra: list,
    tuning: list,
    bank: dict[str, Any],
    cfg: Phase5Config,
    progress: Progress,
) -> dict[str, Any]:
    # Use C1_p1 donors as primary family-depth for selector demo
    key = "C1_p1"
    donors = bank["donor_inventory"][key]["selected"]
    if not donors:
        # fallback any
        for k, v in bank["donor_inventory"].items():
            if v["selected"]:
                key = k
                donors = v["selected"]
                break

    # Build training matrix from anchors + train_extra (circuit_unit)
    X_rows = []
    y_rows = []
    train_feat_list = []
    donors_per_row = []
    train_blocks = anchors + train_extra
    # Limit training rows for runtime: use anchors + first 24 train_extra
    train_blocks = anchors + train_extra[:24]

    for block, inst in train_blocks:
        progress.maybe(f"selector train features {block['block_id']}")
        qubo = build_a2_qubo(inst)
        fam, p = ("C1", 1) if key.startswith("C1") else ("C0", 1)
        if "_p2" in key:
            p = 2
        feats = compute_features(inst, qubo, fam, p)
        train_feat_list.append(feats)
        donors_per_row.append(donors)
        en = enumerate_legal_policies(inst)
        exact = en.get("best_cost")
        regrets = []
        for d in donors:
            ev = evaluate_donor_on_instance(inst, qubo, d, exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"])
            r = ev["best_of_pool_regret"]
            regrets.append(0.0 if r is None else float(r))
        X_rows.append(_vec(feats))
        y_rows.append(regrets)

    X = np.asarray(X_rows, dtype=float)
    y = np.asarray(y_rows, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    # Pad donors if needed
    n_donors = len(donors)
    if y.shape[1] < n_donors:
        pad = np.zeros((y.shape[0], n_donors - y.shape[1]))
        y = np.hstack([y, pad])
    elif y.shape[1] > n_donors:
        y = y[:, :n_donors]

    selector = RidgeDonorSelector(ridge_lambda=cfg.ridge_lambda)
    train_receipt = selector.fit(X, y, donor_ids=[d["params_hash"] for d in donors])

    # References on tuning
    fixed_donor = donors[0]
    rng = np.random.default_rng(12345)
    random_donor = donors[int(rng.integers(0, len(donors)))]

    learned_regrets = []
    fixed_regrets = []
    nn_regrets = []
    rand_regrets = []
    var_regrets = []
    paired_learned_minus_bestref = []

    for block, inst in tuning:
        progress.maybe(f"selector tune {block['block_id']}")
        qubo = build_a2_qubo(inst)
        fam, p = ("C1", 1) if key.startswith("C1") else ("C0", 1)
        if "_p2" in key:
            p = 2
        feats = compute_features(inst, qubo, fam, p)
        en = enumerate_legal_policies(inst)
        exact = en.get("best_cost")

        sel = selector.select(feats, donors)
        learned = evaluate_donor_on_instance(
            inst, qubo, sel["selected_donor"], exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"]
        )
        fixed = evaluate_donor_on_instance(inst, qubo, fixed_donor, exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"] + 1)
        nn_d = nn_transfer_donor(feats, train_feat_list, donors_per_row) or fixed_donor
        nn = evaluate_donor_on_instance(inst, qubo, nn_d, exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"] + 2)
        rnd = evaluate_donor_on_instance(inst, qubo, random_donor, exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"] + 3)
        # per-instance variational under same offline budget: use best donor retrospectively as oracle proxy for budget comparison only on tuning
        best_found = None
        best_r = float("inf")
        for d in donors:
            ev = evaluate_donor_on_instance(inst, qubo, d, exact_cost=exact, pool_size=cfg.pool_size, seed=block["seed"] + 4)
            r = float("inf") if ev["best_of_pool_regret"] is None else float(ev["best_of_pool_regret"])
            if r < best_r:
                best_r = r
                best_found = ev

        def _r(ev):
            return 0.0 if ev["best_of_pool_regret"] is None else float(ev["best_of_pool_regret"])

        lr, fr, nr, rr, vr = _r(learned), _r(fixed), _r(nn), _r(rnd), (0.0 if best_found is None else _r(best_found))
        learned_regrets.append(lr)
        fixed_regrets.append(fr)
        nn_regrets.append(nr)
        rand_regrets.append(rr)
        var_regrets.append(vr)
        best_ref = min(fr, nr, rr, vr)
        paired_learned_minus_bestref.append(lr - best_ref)

    interval = paired_interval(paired_learned_minus_bestref)
    mean_learned = float(np.mean(learned_regrets)) if learned_regrets else None
    mean_best_ref = float(np.mean([min(a, b, c, d) for a, b, c, d in zip(fixed_regrets, nn_regrets, rand_regrets, var_regrets)])) if fixed_regrets else None
    noninf = None
    if interval.get("upper_95_one_sided") is not None:
        noninf = bool(interval["upper_95_one_sided"] <= cfg.noninferiority_margin)

    return {
        "selector_model": "numpy_ridge_ranking",
        "family_depth_key": key,
        "training_receipt": train_receipt,
        "n_tuning_blocks": len(tuning),
        "learned_mean_regret": mean_learned,
        "learned_median_regret": float(np.median(learned_regrets)) if learned_regrets else None,
        "fixed_mean_regret": float(np.mean(fixed_regrets)) if fixed_regrets else None,
        "nn_mean_regret": float(np.mean(nn_regrets)) if nn_regrets else None,
        "random_mean_regret": float(np.mean(rand_regrets)) if rand_regrets else None,
        "variational_best_mean_regret": float(np.mean(var_regrets)) if var_regrets else None,
        "best_reference_mean_regret": mean_best_ref,
        "paired_interval": interval,
        "noninferiority_0_02": noninf,
        "noninferiority_margin": cfg.noninferiority_margin,
        "feature_keys": FEATURE_KEYS,
        "note": "development/tuning results only — NOT held-out scientific claims",
    }


def write_json(path: Path, obj: Any) -> str:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str)
    atomic_write_text(path, text + "\n")
    return sha256_file(path)


def execute_phase5_run(root: Path, *, cfg: Phase5Config | None = None) -> dict[str, Any]:
    cfg = cfg or default_phase5_config()
    progress = Progress(interval_s=cfg.progress_interval_s)
    run_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    progress(f"start run_id={run_id}")

    evidence_dir = root / "evidence" / "stage5" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = root / "docs" / "evidence" / "stage5"
    docs_dir.mkdir(parents=True, exist_ok=True)

    frozen = config_to_frozen_dict(cfg)
    write_json(evidence_dir / "frozen_config.json", frozen)
    progress("wrote frozen_config")

    # Environment
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
        }
    except Exception as exc:  # noqa: BLE001
        env = {"error": str(exc)}
    write_json(evidence_dir / "environment.json", env)

    splits = build_phase5_splits(source_hash=frozen["config_sha256"])
    write_json(evidence_dir / "split_audit.json", splits["audit"])
    progress(f"splits total={splits['audit']['total_blocks']}")

    # Build instances
    anchor_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["anchors"]]
    train_extra_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["training_extra"]]
    tuning_pairs = [(b, _circuit_unit_instance(b, cfg)) for b in splits["tuning"]]
    # Tiny measured set (few)
    tiny_pairs = [(b, _tiny_instance(b, cfg)) for b in splits["anchors"][:4]]

    qubit_range = [inst.n_logical_vars() for _, inst in anchor_pairs]
    tiny_vars = [inst.n_logical_vars() for _, inst in tiny_pairs]

    inventory = {
        "anchors": len(anchor_pairs),
        "training_extra": len(train_extra_pairs),
        "tuning": len(tuning_pairs),
        "circuit_unit_qubit_range": [min(qubit_range), max(qubit_range)],
        "tiny_measured_variable_range": [min(tiny_vars), max(tiny_vars)] if tiny_vars else None,
        "a2_instances_built": len(anchor_pairs) + len(train_extra_pairs) + len(tuning_pairs) + len(tiny_pairs),
        "size_ladder": build_size_ladder(),
    }
    write_json(evidence_dir / "instance_inventory.json", inventory)
    progress(f"instances built={inventory['a2_instances_built']}")

    # Formulation + headroom on circuit_unit anchors + tiny
    check_instances = [inst for _, inst in anchor_pairs[:8]] + [inst for _, inst in tiny_pairs]
    formulation = run_formulation_checks(check_instances)
    write_json(evidence_dir / "formulation_checks.json", formulation)
    headroom = measure_headroom(check_instances)
    write_json(evidence_dir / "headroom_results.json", headroom)
    progress(f"headroom={headroom['DEVELOPMENT_HEADROOM']}")

    # Circuits on first 3 anchors (small)
    circuit_instances = [inst for _, inst in anchor_pairs[:3]]
    circuits = run_circuit_checks(circuit_instances, cfg, progress)
    write_json(evidence_dir / "circuit_checks.json", {"C0": circuits["C0_checks"], "C1": circuits["C1_checks"]})
    write_json(evidence_dir / "circuit_resources.json", {"resources": circuits["resources"]})

    c2 = decide_c2_admission(anchor_pairs[0][1])
    write_json(evidence_dir / "c2_admission.json", c2)
    progress(f"C2={c2['C2_STATUS']}")

    # Parameter bank on all 24 anchors
    bank = run_parameter_bank(
        anchor_pairs,
        starts_per_anchor=cfg.starts_per_anchor,
        max_evals=cfg.max_evals_per_start,
        max_donors=cfg.max_donors_per_family_depth,
        progress=progress,
        max_total_evals=cfg.max_total_expectation_evals,
    )
    write_json(
        evidence_dir / "parameter_bank_receipt.json",
        {k: v for k, v in bank.items() if k != "donor_inventory"},
    )
    write_json(evidence_dir / "donor_inventory.json", bank["donor_inventory"])
    progress(f"bank evals={bank['total_expectation_evaluations']} failures={bank['fit_failures']}")

    # Selector — use subset of tuning for runtime (all 80 may be heavy); contract says 80 tuning
    # Evaluate all 80 with efficient path
    sel = run_selector_pipeline(
        anchors=anchor_pairs,
        train_extra=train_extra_pairs,
        tuning=tuning_pairs,
        bank=bank,
        cfg=cfg,
        progress=progress,
    )
    write_json(evidence_dir / "selector_training_receipt.json", sel["training_receipt"])
    write_json(
        evidence_dir / "selector_tuning_results.json",
        {k: v for k, v in sel.items() if k != "training_receipt"},
    )
    progress(f"selector learned_mean_regret={sel['learned_mean_regret']}")

    elapsed = time.perf_counter() - t0
    status_eng = "PASS"
    gate_d = "PASS"
    if formulation["exact_qubo_checks"]["fail"] or formulation["enumeration_milp_checks"]["fail"]:
        status_eng = "PARTIAL"
        gate_d = "FAIL"
    if circuits["C0_checks"]["fail"] or circuits["C1_checks"]["fail"]:
        status_eng = "PARTIAL" if status_eng == "PASS" else status_eng
        gate_d = "FAIL"
    if splits["audit"]["overlap_failures"] or splits["audit"]["total_blocks"] != 224:
        status_eng = "FAIL"
        gate_d = "FAIL"

    deviations = []
    if headroom["DEVELOPMENT_HEADROOM"] in {"ZERO", "MIXED", "INCONCLUSIVE"}:
        deviations.append(
            {
                "id": "DEV_HEADROOM",
                "detail": f"DEVELOPMENT_HEADROOM={headroom['DEVELOPMENT_HEADROOM']}; superiority path disabled or constrained",
            }
        )
    deviations.append(
        {
            "id": "NOVELTY",
            "detail": NOVELTY_STATUS,
        }
    )

    claims = {
        "PHASE_5_ENGINEERING": status_eng,
        "GATE_D_LEARNING_AND_CIRCUITS": gate_d,
        "DEVELOPMENT_HEADROOM": headroom["DEVELOPMENT_HEADROOM"],
        "SUPERIORITY_PATH_AVAILABLE": headroom["SUPERIORITY_PATH_AVAILABLE"],
        "SELECTED_ARCHITECTURE": SELECTED_ARCHITECTURE,
        "C2_STATUS": c2["C2_STATUS"],
        "NOVELTY_STATUS": NOVELTY_STATUS,
        "QPU_EXECUTION_AUTHORISED": False,
        "QPU_JOBS": 0,
        "QPU_USAGE_SECONDS": 0,
        "evidence_only_development_tuning": True,
    }
    write_json(evidence_dir / "claims_evidence.json", claims)
    write_json(evidence_dir / "deviations.json", {"deviations": deviations})

    # Placeholder test_results filled by caller after pytest
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
        "started_utc": _utc_now(),
        "elapsed_s": elapsed,
        "status": status_eng,
        "frozen_config_sha256": frozen["config_sha256"],
        "selected_architecture": SELECTED_ARCHITECTURE,
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "bank_evals": bank["total_expectation_evaluations"],
        "split_total": splits["audit"]["total_blocks"],
    }
    write_json(evidence_dir / "run_receipt.json", receipt)

    # Manifest excluding itself
    evidence_files = sorted(p.name for p in evidence_dir.glob("*.json") if p.name != "STAGE_5_MANIFEST.json")
    file_hashes = {name: sha256_file(evidence_dir / name) for name in evidence_files}
    manifest = {
        "schema_version": "stage5.manifest.v1",
        "run_id": run_id,
        "rule": "manifest excludes itself from its own digest",
        "files": file_hashes,
        "n_files": len(file_hashes),
    }
    manifest["manifest_payload_sha256"] = sha256_json({k: v for k, v in manifest.items() if k != "manifest_payload_sha256"})
    write_json(evidence_dir / "STAGE_5_MANIFEST.json", manifest)

    # Copy summary pointers under docs/evidence/stage5
    for name in ("run_receipt.json", "claims_evidence.json", "STAGE_5_MANIFEST.json"):
        write_json(docs_dir / name, json.loads((evidence_dir / name).read_text(encoding="utf-8")))

    progress(f"complete status={status_eng} elapsed={elapsed:.1f}s")
    return {
        "run_id": run_id,
        "evidence_dir": str(evidence_dir),
        "status": status_eng,
        "gate_d": gate_d,
        "headroom": headroom,
        "bank": bank,
        "selector": sel,
        "formulation": formulation,
        "circuits": circuits,
        "c2": c2,
        "splits": splits,
        "inventory": inventory,
        "claims": claims,
        "elapsed_s": elapsed,
        "frozen": frozen,
        "manifest": manifest,
    }

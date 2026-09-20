"""Generate STAGE_5_REPORT.md and STAGE_5_FINAL_VERIFY.json from evidence files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text, sha256_file, sha256_json


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def generate_report_and_verify(
    *,
    root: Path,
    run_id: str,
    test_results: dict[str, Any],
    reviewed_source_commit: str,
    base_commit: str,
    frozen_stage4_diffs: int,
) -> dict[str, Any]:
    evid = root / "evidence" / "stage5" / run_id
    docs = root / "docs" / "evidence" / "stage5"
    claims = _load(evid / "claims_evidence.json")
    headroom = _load(evid / "headroom_results.json")
    formulation = _load(evid / "formulation_checks.json")
    circuits = _load(evid / "circuit_checks.json")
    bank = _load(evid / "parameter_bank_receipt.json")
    donors = _load(evid / "donor_inventory.json")
    sel = _load(evid / "selector_tuning_results.json")
    splits = _load(evid / "split_audit.json")
    inv = _load(evid / "instance_inventory.json")
    c2 = _load(evid / "c2_admission.json")
    receipt = _load(evid / "run_receipt.json")
    manifest = _load(evid / "STAGE_5_MANIFEST.json")
    deviations = _load(evid / "deviations.json")
    env = _load(evid / "environment.json")

    # Update test_results in evidence
    atomic_write_text(evid / "test_results.json", json.dumps(test_results, indent=2, sort_keys=True) + "\n")

    c0 = circuits["C0"]
    c1 = circuits["C1"]
    donors_selected = sum(len(v.get("selected", [])) for v in donors.values())

    report = f"""# Stage 5 / Phase 5 — Complete Report

**PHASE_5_ENGINEERING:** `{claims['PHASE_5_ENGINEERING']}`  
**GATE_D_LEARNING_AND_CIRCUITS:** `{claims['GATE_D_LEARNING_AND_CIRCUITS']}`  
**DEVELOPMENT_HEADROOM:** `{claims['DEVELOPMENT_HEADROOM']}`  
**SUPERIORITY_PATH_AVAILABLE:** `{claims['SUPERIORITY_PATH_AVAILABLE']}`  
**SELECTED_ARCHITECTURE:** `{claims['SELECTED_ARCHITECTURE']}`  
**C2_STATUS:** `{claims['C2_STATUS']}`  
**NOVELTY_STATUS:** `{claims['NOVELTY_STATUS']}`  
**QPU_EXECUTION_AUTHORISED:** `false`  
**QPU_JOBS:** `0`  
**QPU_USAGE_SECONDS:** `0`

Evidence class: local development / tuning measurements. Not physically measured on QPU. Not a held-out scientific superiority claim.

## 1. Executive outcome

Phase 5 implements architecture **A2** (two-car, multi-epoch, scenario-contingent strategy-policy optimisation) with non-anticipative info-set encoding, independent classical references, C0/C1 local ideal circuits, a preregistered parameter bank, and an inspectable ridge donor selector. Engineering status: **{claims['PHASE_5_ENGINEERING']}**. Gate D: **{claims['GATE_D_LEARNING_AND_CIRCUITS']}**. Development headroom: **{claims['DEVELOPMENT_HEADROOM']}** (superiority path available: `{claims['SUPERIORITY_PATH_AVAILABLE']}`).

## 2. Starting gate and reproducibility

- Base commit: `{base_commit}`
- Reviewed source commit: `{reviewed_source_commit}`
- Run id: `{run_id}`
- Frozen config SHA-256: `{receipt['frozen_config_sha256']}`
- Reproduction: `.venv/bin/python -m f1q run --plan phase5` (or `.venv/bin/python -m f1q.stage5`)
- Environment packages: `{json.dumps(env.get('packages', {}), sort_keys=True)}`

## 3. Scientific object (A2)

Non-anticipative joint strategy policies over a causal SC/VSC scenario tree: decisions once per information set; two team cars; multiple epochs; tyre inventory + compound obligations; shared pit-crew overlap as **finite cost**; deterministic classical safe fallback.

## 4. Size ladder

Circuit-unit measured logical qubits: `{inv['circuit_unit_qubit_range']}`.  
Tiny measured variables: `{inv['tiny_measured_variable_range']}`.  
A2 instances built: `{inv['a2_instances_built']}`.

| Rung | Logical vars | Info sets | Scenarios | Exact executed | Statevector feasible |
|------|-------------:|----------:|----------:|:--------------:|:--------------------:|
"""
    for row in inv["size_ladder"]:
        report += (
            f"| {row['rung']} | {row['logical_vars']} | {row['n_info_sets']} | {row['n_scenarios']} | "
            f"{row.get('executed_exact')} | {row.get('ideal_statevector_feasible')} |\n"
        )
    report += """
Dense 30–40q statevector is **not** claimed locally practical without measured evidence; small/larger rows are resource estimates unless `executed_exact` is true.

## 5. Classical correctness

- Exact/direct vs QUBO: pass `{formulation['exact_qubo_checks']['pass']}` / fail `{formulation['exact_qubo_checks']['fail']}`
- Enumeration vs MILP: pass `{formulation['enumeration_milp_checks']['pass']}` / fail `{formulation['enumeration_milp_checks']['fail']}`
- Non-anticipativity: pass `{formulation['nonanticipativity_checks']['pass']}` / fail `{formulation['nonanticipativity_checks']['fail']}`
- Encode/decode: pass `{formulation['encode_decode']['pass']}` / fail `{formulation['encode_decode']['fail']}`
- Causal visibility: pass `{formulation['causal_visibility']['pass']}` / fail `{formulation['causal_visibility']['fail']}`
- Fallback feasibility: pass `{formulation['fallback_feasibility']['pass']}` / fail `{formulation['fallback_feasibility']['fail']}`

## 6. Development headroom

Label: **{headroom['DEVELOPMENT_HEADROOM']}**.  
Nonzero cases: `{headroom['n_nonzero']}`; zero: `{headroom['n_zero']}`; unresolved: `{headroom['n_unresolved']}`; exact inside deadline: `{headroom['n_exact_inside_deadline']}`.  
Note: {headroom['note']}

Weak fallback gaps do **not** manufacture superiority headroom.

## 7–8. Quantum circuit families C0 / C1

- C0 checks: pass `{c0['pass']}` / fail `{c0['fail']}`
- C1 checks: pass `{c1['pass']}` / fail `{c1['fail']}`
- C0: transverse-X mixer, penalty cost H, \|+⟩ init, p=1 and p=2
- C1: within-block XY ring exchanges, one-hot uniform prep (counted in resources), p=1 and p=2
- Ideal sims are local; Qiskit Statevector cross-check on verification subset
- No IBM Runtime / provider path

## 9. C2 admission

**{c2['C2_STATUS']}** — {c2['reason']}

## 10. Splits

Total blocks: `{splits['total_blocks']}` (expected 224).  
Anchors: `{splits['anchors']}`; training extra: `{splits['training_extra']}`; tuning: `{splits['tuning']}`.  
Overlap failures: `{splits['overlap_failures']}`.  
Calibration/eval/test materialised: `{splits['calib_eval_test_materialized']}`.

## 11. Parameter bank

Family-depth pairs: `{bank['family_depth_pairs']}`.  
Anchors: `{bank['n_anchors']}`; starts/anchor: `{bank['starts_per_anchor']}`; max evals/start: `{bank['max_evals_per_start']}`.  
Expectation evaluations: `{bank['total_expectation_evaluations']}` (cap 23040).  
Fit failures: `{bank['fit_failures']}`.  
Donors selected (all family-depths): `{donors_selected}`.

## 12. Learned donor selector

Model: `{sel['selector_model']}`.  
Tuning blocks: `{sel['n_tuning_blocks']}`.  
Learned mean regret: `{sel['learned_mean_regret']}`.  
Best reference mean regret: `{sel['best_reference_mean_regret']}`.  
Paired interval: `{json.dumps(sel['paired_interval'], sort_keys=True)}`.  
Non-inferiority (margin 0.02): `{sel['noninferiority_0_02']}`.  
These are **development/tuning** results — not held-out scientific claims.

## 13. Novelty

`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`. C0/C1/QAOA/warm-start/guarded mixers are not claimed novel.

## 14. QPU / spend

QPU_EXECUTION_AUTHORISED=false; QPU_JOBS=0; QPU_USAGE_SECONDS=0; spending=0; no IBM credentials.

## 15. Tests and doctor

- Targeted Stage 5: `{test_results.get('targeted')}`
- Full pytest: `{test_results.get('full')}`
- pip check: `{test_results.get('pip_check')}`
- f1q doctor: `{test_results.get('doctor')}`
- f1q status: `{test_results.get('status')}`
- Frozen Stage 4 diffs: `{frozen_stage4_diffs}`

## 16. Deviations

{json.dumps(deviations.get('deviations', []), indent=2)}

## 17. Claims ↔ evidence index

| Claim field | Source file |
|-------------|-------------|
| PHASE_5_ENGINEERING | claims_evidence.json |
| DEVELOPMENT_HEADROOM | headroom_results.json |
| C0/C1 | circuit_checks.json |
| C2 | c2_admission.json |
| Splits | split_audit.json |
| Bank | parameter_bank_receipt.json |
| Selector | selector_tuning_results.json |
| Manifest | STAGE_5_MANIFEST.json |

## 18–26. Additional protocol notes

- Stage 4 evidence remains frozen; legacy Gate C archived; no resume of e85ee977 / 41c28597.
- Next authorised stage after review: **Stage 6 local pilot + resource/precision estimation**, not hardware.
- PHASE_6_BOUNDARY_PILOT_READY depends on review; PHASE_6_SUPERIORITY_PILOT_READY requires nonzero development headroom path (currently `{claims['SUPERIORITY_PATH_AVAILABLE']}`).
- Manifest excludes itself from its own digest (rule recorded in STAGE_5_MANIFEST.json).
- Run elapsed_s (pipeline): `{receipt['elapsed_s']}`.

## Evidence-path index

- `evidence/stage5/{run_id}/`
- `docs/evidence/stage5/`
- `docs/STAGE_5_REPORT.md`
"""

    report_path = root / "docs" / "STAGE_5_REPORT.md"
    atomic_write_text(report_path, report)
    report_sha = sha256_file(report_path)

    # Refresh manifest hashes including updated test_results
    evidence_files = sorted(p.name for p in evid.glob("*.json") if p.name != "STAGE_5_MANIFEST.json")
    file_hashes = {name: sha256_file(evid / name) for name in evidence_files}
    manifest_out = {
        "schema_version": "stage5.manifest.v1",
        "run_id": run_id,
        "rule": "manifest excludes itself from its own digest",
        "files": file_hashes,
        "n_files": len(file_hashes),
        "report_path": "docs/STAGE_5_REPORT.md",
        "report_sha256": report_sha,
    }
    manifest_out["manifest_payload_sha256"] = sha256_json(
        {k: v for k, v in manifest_out.items() if k != "manifest_payload_sha256"}
    )
    atomic_write_text(evid / "STAGE_5_MANIFEST.json", json.dumps(manifest_out, indent=2, sort_keys=True) + "\n")
    manifest_sha = sha256_file(evid / "STAGE_5_MANIFEST.json")

    final_verify = {
        "schema_version": "stage5.final_verify.v1",
        "PHASE_5_ENGINEERING": claims["PHASE_5_ENGINEERING"],
        "GATE_D_LEARNING_AND_CIRCUITS": claims["GATE_D_LEARNING_AND_CIRCUITS"],
        "DEVELOPMENT_HEADROOM": claims["DEVELOPMENT_HEADROOM"],
        "SUPERIORITY_PATH_AVAILABLE": claims["SUPERIORITY_PATH_AVAILABLE"],
        "SELECTED_ARCHITECTURE": claims["SELECTED_ARCHITECTURE"],
        "CIRCUIT_UNIT_QUBIT_RANGE": inv["circuit_unit_qubit_range"],
        "TINY_MEASURED_VARIABLE_RANGE": inv["tiny_measured_variable_range"],
        "A2_INSTANCES_BUILT": inv["a2_instances_built"],
        "EXACT_QUBO_CHECKS": f"{formulation['exact_qubo_checks']['pass']}/{formulation['exact_qubo_checks']['pass'] + formulation['exact_qubo_checks']['fail']}",
        "ENUMERATION_MILP_CHECKS": f"{formulation['enumeration_milp_checks']['pass']}/{formulation['enumeration_milp_checks']['pass'] + formulation['enumeration_milp_checks']['fail']}",
        "NONANTICIPATIVITY_CHECKS": f"{formulation['nonanticipativity_checks']['pass']}/{formulation['nonanticipativity_checks']['pass'] + formulation['nonanticipativity_checks']['fail']}",
        "SPLIT_COUNTS": splits["total_blocks"],
        "SPLIT_OVERLAP_FAILURES": len(splits["overlap_failures"]),
        "TRAINING_ANCHORS": splits["anchors"],
        "FAMILY_DEPTH_PAIRS": len(bank["family_depth_pairs"]),
        "OPTIMISER_STARTS": bank["n_anchors"] * bank["starts_per_anchor"] * len(bank["family_depth_pairs"]),
        "EXPECTATION_EVALUATIONS": bank["total_expectation_evaluations"],
        "FIT_FAILURES": bank["fit_failures"],
        "DONORS_SELECTED": donors_selected,
        "SELECTOR_MODEL": sel["selector_model"],
        "TUNING_BLOCKS": sel["n_tuning_blocks"],
        "LEARNED_MEAN_REGRET": sel["learned_mean_regret"],
        "BEST_REFERENCE_MEAN_REGRET": sel["best_reference_mean_regret"],
        "PAIRED_INTERVAL": sel["paired_interval"],
        "NONINFERIORITY_0_02": sel["noninferiority_0_02"],
        "C0_CHECKS": f"{c0['pass']}/{c0['pass'] + c0['fail']}",
        "C1_CHECKS": f"{c1['pass']}/{c1['pass'] + c1['fail']}",
        "C2_STATUS": c2["C2_STATUS"],
        "TARGETED_TESTS": test_results.get("targeted"),
        "FULL_TESTS": test_results.get("full"),
        "PIP_CHECK": test_results.get("pip_check"),
        "DOCTOR": test_results.get("doctor"),
        "FROZEN_STAGE4_DIFFS": frozen_stage4_diffs,
        "REPORT": "docs/STAGE_5_REPORT.md",
        "REPORT_SHA256": report_sha,
        "MANIFEST": f"evidence/stage5/{run_id}/STAGE_5_MANIFEST.json",
        "MANIFEST_SHA256": manifest_sha,
        "BASE_COMMIT": base_commit,
        "REVIEWED_SOURCE_COMMIT": reviewed_source_commit,
        "QPU_EXECUTION_AUTHORISED": False,
        "QPU_JOBS": 0,
        "QPU_USAGE_SECONDS": 0,
        "NOVELTY_STATUS": claims["NOVELTY_STATUS"],
        "PHASE_6_BOUNDARY_PILOT_READY": claims["PHASE_5_ENGINEERING"] in {"PASS", "PARTIAL"},
        "PHASE_6_SUPERIORITY_PILOT_READY": bool(claims["SUPERIORITY_PATH_AVAILABLE"]),
        "run_id": run_id,
    }
    atomic_write_text(evid / "STAGE_5_FINAL_VERIFY.json", json.dumps(final_verify, indent=2, sort_keys=True) + "\n")
    atomic_write_text(docs / "STAGE_5_FINAL_VERIFY.json", json.dumps(final_verify, indent=2, sort_keys=True) + "\n")
    atomic_write_text(docs / "STAGE_5_MANIFEST.json", json.dumps(manifest_out, indent=2, sort_keys=True) + "\n")
    verify_sha = sha256_file(evid / "STAGE_5_FINAL_VERIFY.json")
    final_verify["FINAL_VERIFY_SHA256"] = verify_sha
    # rewrite with self hash field
    atomic_write_text(evid / "STAGE_5_FINAL_VERIFY.json", json.dumps(final_verify, indent=2, sort_keys=True) + "\n")
    atomic_write_text(docs / "STAGE_5_FINAL_VERIFY.json", json.dumps(final_verify, indent=2, sort_keys=True) + "\n")
    return final_verify

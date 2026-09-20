"""Generate STAGE_5_CORRECTED_REPORT.md and acyclic final verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text, sha256_file, sha256_json
from f1q.stage5.run import build_acyclic_manifest, verify_manifest_entries


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(num: Any, den: Any) -> str:
    if den is None or den == 0:
        return f"{num}/{den}"
    return f"{num}/{den}"


def generate_corrected_report_and_verify(
    *,
    root: Path,
    run_id: str,
    test_results: dict[str, Any],
    corrected_source_commit: str,
    base_commit: str,
    frozen_stage4_diffs: int,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    evid = root / "evidence" / "stage5" / run_id
    docs = root / "docs" / "evidence" / "stage5_corrected"
    docs.mkdir(parents=True, exist_ok=True)

    claims = _load(evid / "claims_evidence.json")
    headroom = _load(evid / "headroom_results.json")
    formulation = _load(evid / "formulation_checks.json")
    circuits = _load(evid / "circuit_checks.json")
    bank = _load(evid / "parameter_bank_receipt.json")
    donors = _load(evid / "donor_inventory.json")
    sel = _load(evid / "selector_tuning_results.json")
    train_rcpt = _load(evid / "selector_training_receipt.json")
    splits = _load(evid / "split_audit.json")
    inv = _load(evid / "instance_inventory.json")
    c2 = _load(evid / "c2_admission.json")
    receipt = _load(evid / "run_receipt.json")
    deviations = _load(evid / "deviations.json")
    env = _load(evid / "environment.json")
    micro = _load(evid / "microcase_evidence.json")
    fit_rec = _load(evid / "bank_fit_records.json")
    model_art = _load(evid / "selector_model_artifacts.json")
    per_block = _load(evid / "selector_per_block_records.json")

    atomic_write_text(evid / "test_results.json", json.dumps(test_results, indent=2, sort_keys=True) + "\n")

    c0 = circuits["C0"]
    c1 = circuits["C1"]
    donors_selected = sum(len(v.get("selected", [])) for v in donors.values())
    per_fd = sel.get("per_family_depth", {})

    # Build tables from raw evidence
    fd_rows = []
    for key in sorted(per_fd.keys()):
        v = per_fd[key]
        fd_rows.append(
            f"| {key} | {v.get('n_training_blocks_used')} | {v.get('n_tuning_blocks_used')} | "
            f"{v.get('learned_mean_normalised_regret')} | {v.get('fixed_mean_normalised_regret')} | "
            f"{v.get('nn_mean_normalised_regret')} | {v.get('random_mean_normalised_regret')} | "
            f"{v.get('variational_mean_normalised_regret')} | {json.dumps(v.get('noninferiority_0_02_vs_comparator'))} |"
        )

    family_counts = train_rcpt.get("family_train_counts", {})
    fam_table = "\n".join(f"| {k} | {v} |" for k, v in sorted(family_counts.items()))

    weights_ok = all("weights" in a and a["weights"] for a in model_art.values())

    report = f"""# Stage 5 / Phase 5 — CORRECTED Closure Report

**PHASE_5_CORRECTED_ENGINEERING:** `{claims.get('PHASE_5_CORRECTED_ENGINEERING')}`  
**GATE_D_LEARNING_AND_CIRCUITS:** `{claims.get('GATE_D_LEARNING_AND_CIRCUITS')}`  
**DEVELOPMENT_HEADROOM:** `{claims.get('DEVELOPMENT_HEADROOM')}`  
**SUPERIORITY_PATH_AVAILABLE:** `{claims.get('SUPERIORITY_PATH_AVAILABLE')}`  
**SELECTED_ARCHITECTURE:** `{claims.get('SELECTED_ARCHITECTURE')}`  
**A2_SCOPE:** `{json.dumps(claims.get('A2_SCOPE'), sort_keys=True)}`  
**C2_STATUS:** `{claims.get('C2_STATUS')}`  
**NOVELTY_STATUS:** `{claims.get('NOVELTY_STATUS')}`  
**QPU_EXECUTION_AUTHORISED:** `false`  
**QPU_JOBS:** `0`  
**QPU_USAGE_SECONDS:** `0`  
**ORIGINAL_RUN_PRESERVED:** `{claims.get('ORIGINAL_RUN_PRESERVED')}`  
**CORRECTED_RUN_ID:** `{run_id}`

Evidence class: local development / tuning measurements. Not physically measured on QPU. Not a held-out scientific superiority claim.  
Historical Phase 5 run `6ad68021-f19c-44e7-b166-13ab44dad31b` is preserved unchanged and is **not** portrayed as corrected-compliant.

This report does **not** replace `docs/STAGE_5_REPORT.md` (historical).

## 1. Executive decision

Corrected Phase 5 engineering status: **{claims.get('PHASE_5_CORRECTED_ENGINEERING')}**.  
Gate D: **{claims.get('GATE_D_LEARNING_AND_CIRCUITS')}**.  
Development headroom on checked instances: **{claims.get('DEVELOPMENT_HEADROOM')}** (superiority path: `{claims.get('SUPERIORITY_PATH_AVAILABLE')}`).  
Failures recorded: `{claims.get('failures')}`.

## 2. Starting gate and reproducibility

- Base commit: `{base_commit}`
- Corrected source commit: `{corrected_source_commit}`
- Corrected run id: `{run_id}`
- Original preserved run: `{claims.get('ORIGINAL_RUN_PRESERVED')}`
- Frozen config SHA-256: `{receipt['frozen_config_sha256']}`
- Reproduction: `.venv/bin/python -m f1q run --plan phase5` (do not overwrite historical evidence)
- Packages: `{json.dumps(env.get('packages', {}), sort_keys=True)}`
- Pipeline elapsed_s: `{receipt.get('elapsed_s')}`
- Wall ELAPSED_SECONDS (packaging): `{elapsed_seconds}`

## 3. Scientific object (A2) — corrected scope

Non-anticipative joint strategy policies over a causal SC/VSC scenario tree.  
Family factors (`green_pit_*`, `tyre_*`, `traffic_*`) drive mechanism coefficients; action costs have documented lineage to Stage-2/3/4 factor maps (synthetic, **not F1-calibrated**).  
Scenario probabilities: **deterministic_synthetic** — **NOT** claimed AI-trained.  
SC/VSC duration revealed only through causally available observations (epoch 0 = `root` only).  
Crew overlap remains a **finite cost** (not a hard prohibition).  
Evidence: `instance_inventory.json` → `a2_scope`; `microcase_evidence.json`.

## 4. Size ladder

Circuit-unit qubits: `{inv['circuit_unit_qubit_range']}` (source: `instance_inventory.json`).  
Tiny variables: `{inv['tiny_measured_variable_range']}`.  
Instances built: `{inv['a2_instances_built']}`.

| Rung | Logical vars | Info sets | Scenarios | Exact executed | SV feasible |
|------|-------------:|----------:|----------:|:--------------:|:-----------:|
"""
    for row in inv["size_ladder"]:
        report += (
            f"| {row['rung']} | {row['logical_vars']} | {row['n_info_sets']} | {row['n_scenarios']} | "
            f"{row.get('executed_exact')} | {row.get('ideal_statevector_feasible')} |\n"
        )

    report += f"""
## 5. Classical correctness / formulation equivalence

- Exact/direct vs QUBO: pass `{formulation['exact_qubo_checks']['pass']}` / fail `{formulation['exact_qubo_checks']['fail']}` (denom `{formulation['exact_qubo_checks']['pass'] + formulation['exact_qubo_checks']['fail']}`) — `formulation_checks.json`
- Exhaustive microcase direct/QUBO: pass `{formulation['exhaustive_direct_qubo']['pass']}` / fail `{formulation['exhaustive_direct_qubo']['fail']}`
- Enumeration vs MILP: pass `{formulation['enumeration_milp_checks']['pass']}` / fail `{formulation['enumeration_milp_checks']['fail']}`
- s_Q excludes offset: pass `{formulation['s_Q_excludes_offset']['pass']}` / fail `{formulation['s_Q_excludes_offset']['fail']}`
- Causal visibility + no duration leak: pass `{formulation['causal_visibility']['pass']}` / fail `{formulation['causal_visibility']['fail']}`
- Hard constraints (inventory/compound/deadline): **acceptance filtering**, not QUBO penalties — applied to all samplers/comparators (`hard_constraint_encoding`)
- Adversarial suite all_pass: `{formulation.get('adversarial', {}).get('all_pass')}` — detail `{json.dumps(formulation.get('adversarial', {}), sort_keys=True)[:2000]}`

## 6. Development headroom (honest reassessment)

Label: **{headroom['DEVELOPMENT_HEADROOM']}**.  
Checked instances: `{headroom.get('n_instances_checked')}` (scope: checked only — not universal A2/F1).  
Nonzero `{headroom['n_nonzero']}` / zero `{headroom['n_zero']}` / unresolved `{headroom['n_unresolved']}` / exact-inside-deadline `{headroom['n_exact_inside_deadline']}`.  
Evidence: `headroom_results.json`.  
{headroom.get('note')}

## 7. Quantum circuit family C0

Actual QUBO cost as Phase/CPhase (RZ/RZZ-equivalent); transverse-X RX mixer; H^n init; p=1,2.  
Checks: pass `{c0['pass']}` / fail `{c0['fail']}` (denom `{c0['pass']+c0['fail']}`) — `circuit_checks.json`.  
C0 cannot report zero 2q when quadratic interactions exist (`c0_nonzero_2q_when_quadratic` in details).  
Transpile: **actual circuits** (`circuit_resources.json`, `proxy: false`).

## 8. Quantum circuit family C1

Validated one-hot prep; actual QUBO cost; XY ring (RXX+RYY); p=1,2.  
Checks: pass `{c1['pass']}` / fail `{c1['fail']}` — includes connected-components proof on **actual** transition graph and broken-schedule adversarial check.  
Evidence: `circuit_checks.json` → `connected_components`, `broken_schedule`.

## 9. C2 admission

**{c2['C2_STATUS']}** — {c2.get('reason')}  
Evidence: `c2_admission.json`.

## 10. Circuit resources

Documented target `rz/sx/x/cx`; seed from frozen config; opt level from frozen config.  
Resource rows: `{len(_load(evid / 'circuit_resources.json').get('resources', []))}`.  
Evidence: `circuit_resources.json`.

## 11. Splits and leakage controls

Total blocks `{splits['total_blocks']}` / expected 224.  
Anchors `{splits['anchors']}`; training extra `{splits['training_extra']}`; tuning `{splits['tuning']}`.  
Overlap failures `{splits['overlap_failures']}`. Calib/eval/test materialised: `{splits['calib_eval_test_materialized']}`.  
Evidence: `split_audit.json`, `split_block_ids.json`.

## 12. Complete training coverage

Training used: **{train_rcpt['n_training_used']}/144** (24 anchors + 120 extra).  
Tuning used: **{train_rcpt['n_tuning_used']}/80**.  
Eight-family balance (train): `{train_rcpt['eight_family_balance_train']}`; (tune): `{train_rcpt['eight_family_balance_tune']}`.

| Family | Training rows used |
|--------|-------------------:|
{fam_table}

Family-depth coverage: `{train_rcpt['family_depth_coverage']}` (must be all four).  
Evidence: `selector_training_receipt.json`, `selector_train_usage.json` (per-block `entered_feature_compute` / `entered_donor_eval`).

## 13. Parameter bank

Family-depth pairs: `{bank['family_depth_pairs']}`.  
Fit identities persisted: **{fit_rec['n']}** (expect 288 = 24×4×3).  
Expectation evaluations: `{bank['total_expectation_evaluations']}` / cap.  
Fit failures: `{bank['fit_failures']}`. Donors selected: `{donors_selected}`.  
Evidence: `bank_fit_records.json`, `parameter_bank_receipt.json`, `donor_inventory.json`.

## 14. Learned donor selector and genuine comparators

Model: NumPy ridge ranking with **persisted weights** (weights_ok=`{weights_ok}`).  
Angle banks remain separate by family and depth.  
Comparators (identified separately; no retrospective best-of as primary):
1. Frozen fixed donor (training-only selection)
2. Genuine nearest-neighbour transfer (fitted donor of nearest training instance)
3. Seeded random donor (identity+seed per block)
4. Learned ridge donor ranker
5. Genuine per-instance variational fit (fresh params; frozen budget starts=1, max_evals=40)

| Family-depth | Train N | Tune N | Learned mean | Fixed | NN | Random | Variational | Noninf@0.02 vs each |
|--------------|--------:|-------:|-------------:|------:|---:|-------:|------------:|---------------------|
{chr(10).join(fd_rows)}

Prior non-inferiority from the historical run is labelled **SUPERSEDED_INVALID**.  
Evidence: `selector_tuning_results.json`, `selector_per_block_records.json` (n={len(per_block.get('records', []))}), `selector_model_artifacts.json`.

### Normalised regret

Definition: `(f(a)-f*)/(f_max-f*)`. Zero range → feasible regret 0; all-infeasible pool → regret 1; never coerce missing to 0.  
Unnormalised gaps reported separately per block.  
Useful ≠ all legal: useful requires declared improvement vs weak incumbent (`USEFUL_IMPROVEMENT_FRAC=0.05` of range).

## 15. Microcases (binding / branching / causal)

{json.dumps(micro, indent=2)}

## 16. AI / classical / quantum role separation

AI: ridge donor ranking only on this stage (scenario probs are deterministic_synthetic).  
Classical: exact enumeration, MILP, heuristic fallback.  
Quantum: local ideal C0/C1 circuits only — no provider path.

## 17. Novelty

`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`.

## 18. QPU and spend

QPU_EXECUTION_AUTHORISED=false; QPU_JOBS=0; QPU_USAGE_SECONDS=0; spending=0; no IBM credentials.

## 19. Tests, doctor, freeze integrity

- Targeted Stage 5: `{test_results.get('targeted')}`
- Full pytest: `{test_results.get('full')}`
- pip check: `{test_results.get('pip_check')}`
- f1q doctor: `{test_results.get('doctor')}`
- Frozen Stage 4 path diffs: `{frozen_stage4_diffs}`

## 20. Evidence integrity (acyclic)

Raw evidence finalised → manifest hashes raw+report excluding itself and final verify → final verify hashes manifest.  
No file verifies its own hash. Historical mismatched evidence under `6ad68021-…` preserved unchanged.

## 21. Deviations

{json.dumps(deviations.get('deviations', []), indent=2)}

## 22. Negative results

- Development headroom on checked instances: {headroom['DEVELOPMENT_HEADROOM']}
- Superiority path available: {claims.get('SUPERIORITY_PATH_AVAILABLE')}
- C2 not admitted by protocol
- Prior incomplete-metric non-inferiority superseded

## 23. Claims status summary

Engineering PASS/NOT_CLOSED does not imply quantum advantage, F1 calibration, or held-out H1 success.

## 24. Stage 4 freeze

Stage 4 evidence frozen; legacy Gate C archived; no resume of e85ee977 / 41c28597; `formulation_gate_c_closure_check` not invoked. Diffs: `{frozen_stage4_diffs}`.

## 25. Stage 6 readiness

PHASE_6_READY: **false** until independent review. Next authorised stage: NONE — await independent review. Not hardware.

## 26. Evidence-path index

- `evidence/stage5/{run_id}/` (corrected)
- `evidence/stage5/6ad68021-f19c-44e7-b166-13ab44dad31b/` (preserved historical)
- `docs/evidence/stage5_corrected/`
- `docs/STAGE_5_CORRECTED_REPORT.md` (this file)
- `docs/STAGE_5_REPORT.md` (historical; not replaced)
"""

    report_path = root / "docs" / "STAGE_5_CORRECTED_REPORT.md"
    atomic_write_text(report_path, report)
    report_sha = sha256_file(report_path)

    # Rebuild acyclic manifest including report, excluding self + final verify
    manifest_out = build_acyclic_manifest(evid, report_path=report_path)
    manifest_out["run_id"] = run_id
    atomic_write_text(evid / "STAGE_5_CORRECTED_MANIFEST.json", json.dumps(manifest_out, indent=2, sort_keys=True) + "\n")
    manifest_sha = sha256_file(evid / "STAGE_5_CORRECTED_MANIFEST.json")
    verify = verify_manifest_entries(evid, manifest_out, root)

    final_verify = {
        "schema_version": "stage5.corrected.final_verify.v1",
        "PHASE_5_CORRECTED_ENGINEERING": claims.get("PHASE_5_CORRECTED_ENGINEERING"),
        "GATE_D_LEARNING_AND_CIRCUITS": claims.get("GATE_D_LEARNING_AND_CIRCUITS"),
        "DEVELOPMENT_HEADROOM": claims.get("DEVELOPMENT_HEADROOM"),
        "SUPERIORITY_PATH_AVAILABLE": claims.get("SUPERIORITY_PATH_AVAILABLE"),
        "CORRECTED_RUN_ID": run_id,
        "ORIGINAL_RUN_PRESERVED": claims.get("ORIGINAL_RUN_PRESERVED"),
        "A2_SCOPE": claims.get("A2_SCOPE"),
        "TRAINING_USED": claims.get("TRAINING_USED"),
        "TUNING_USED": claims.get("TUNING_USED"),
        "FAMILY_DEPTH_COVERAGE": claims.get("FAMILY_DEPTH_COVERAGE"),
        "NORMALISED_REGRET_IMPLEMENTED": True,
        "ALL_INFEASIBLE_REGRET": 1.0,
        "COMPARATORS": [
            "frozen_fixed_donor_training_only",
            "genuine_nearest_neighbour_transfer",
            "seeded_random_donor",
            "learned_ridge_donor_ranker",
            "genuine_per_instance_variational_fit",
        ],
        "MODEL_ARTIFACT": "selector_model_artifacts.json",
        "MODEL_WEIGHTS_PERSISTED": weights_ok,
        "FIT_RECORDS_PERSISTED": fit_rec["n"],
        "PER_BLOCK_RECORDS": len(per_block.get("records", [])),
        "C0_CHECKS": f"{c0['pass']}/{c0['pass']+c0['fail']}",
        "C1_CHECKS": f"{c1['pass']}/{c1['pass']+c1['fail']}",
        "ACTUAL_CIRCUITS_TRANSPILED": True,
        "FORMULATION_CHECKS": {
            "exact_qubo": f"{formulation['exact_qubo_checks']['pass']}/{formulation['exact_qubo_checks']['pass']+formulation['exact_qubo_checks']['fail']}",
            "enum_milp": f"{formulation['enumeration_milp_checks']['pass']}/{formulation['enumeration_milp_checks']['pass']+formulation['enumeration_milp_checks']['fail']}",
            "adversarial_all_pass": formulation.get("adversarial", {}).get("all_pass"),
        },
        "C2_STATUS": c2["C2_STATUS"],
        "TARGETED_TESTS": test_results.get("targeted"),
        "FULL_TESTS": test_results.get("full"),
        "MANIFEST_ENTRIES": manifest_out["n_files"],
        "MANIFEST_VERIFY": verify,
        "REPORT": "docs/STAGE_5_CORRECTED_REPORT.md",
        "REPORT_SHA256": report_sha,
        "MANIFEST": f"evidence/stage5/{run_id}/STAGE_5_CORRECTED_MANIFEST.json",
        "MANIFEST_SHA256": manifest_sha,
        "BASE_COMMIT": base_commit,
        "CORRECTED_SOURCE_COMMIT": corrected_source_commit,
        "FROZEN_STAGE4_DIFFS": frozen_stage4_diffs,
        "QPU_JOBS": 0,
        "QPU_USAGE_SECONDS": 0,
        "NOVELTY_STATUS": claims.get("NOVELTY_STATUS"),
        "PHASE_6_READY": False,
        "ELAPSED_SECONDS": elapsed_seconds,
        "note": "final_verify hashes the manifest; does not include its own content hash inside the hashed payload before write",
    }
    # Write final verify WITHOUT embedding its own SHA (acyclic: no file verifies itself)
    atomic_write_text(evid / "STAGE_5_CORRECTED_FINAL_VERIFY.json", json.dumps(final_verify, indent=2, sort_keys=True) + "\n")
    verify_sha = sha256_file(evid / "STAGE_5_CORRECTED_FINAL_VERIFY.json")

    for name in (
        "STAGE_5_CORRECTED_MANIFEST.json",
        "STAGE_5_CORRECTED_FINAL_VERIFY.json",
        "claims_evidence.json",
        "run_receipt.json",
    ):
        atomic_write_text(docs / name, (evid / name).read_text(encoding="utf-8"))

    out = dict(final_verify)
    out["FINAL_VERIFY_SHA256"] = verify_sha  # returned to caller; not stored inside the hashed file
    return out

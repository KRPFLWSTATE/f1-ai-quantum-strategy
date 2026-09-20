# Stage 5 / Phase 5 — CORRECTED Closure Report

**PHASE_5_CORRECTED_ENGINEERING:** `PASS`  
**GATE_D_LEARNING_AND_CIRCUITS:** `PASS`  
**DEVELOPMENT_HEADROOM:** `ZERO`  
**SUPERIORITY_PATH_AVAILABLE:** `False`  
**SELECTED_ARCHITECTURE:** `A2_multi_epoch_scenario_contingent_strategy_policy`  
**A2_SCOPE:** `{"builder_version": "corrected.v1", "cost_lineage": "family_mechanism_params_Stage2_factor_map", "family_driven_mechanisms": true, "not_f1_calibrated": true, "scenario_probability_model": "deterministic_synthetic"}`  
**C2_STATUS:** `NOT_ADMITTED_BY_PROTOCOL`  
**NOVELTY_STATUS:** `PROPOSED_NOT_LITERATURE_VERIFIED`  
**QPU_EXECUTION_AUTHORISED:** `false`  
**QPU_JOBS:** `0`  
**QPU_USAGE_SECONDS:** `0`  
**ORIGINAL_RUN_PRESERVED:** `6ad68021-f19c-44e7-b166-13ab44dad31b`  
**CORRECTED_RUN_ID:** `e6b3588b-ab97-48c9-82f4-616785aa3611`

Evidence class: local development / tuning measurements. Not physically measured on QPU. Not a held-out scientific superiority claim.  
Historical Phase 5 run `6ad68021-f19c-44e7-b166-13ab44dad31b` is preserved unchanged and is **not** portrayed as corrected-compliant.

This report does **not** replace `docs/STAGE_5_REPORT.md` (historical).

## 1. Executive decision

Corrected Phase 5 engineering status: **PASS**.  
Gate D: **PASS**.  
Development headroom on checked instances: **ZERO** (superiority path: `False`).  
Failures recorded: `[]`.

## 2. Starting gate and reproducibility

- Base commit: `d704f91f766b762a37a894dd2ef9b673bf484a06`
- Corrected source commit: `625916aa2fba9d28ae42ffa52ca8a79f6a52741b`
- Corrected run id: `e6b3588b-ab97-48c9-82f4-616785aa3611`
- Original preserved run: `6ad68021-f19c-44e7-b166-13ab44dad31b`
- Frozen config SHA-256: `67a864433b7134fc5f5534fcd71d518e4e5642ca438c2634ab21aef0e8cf9e75`
- Reproduction: `.venv/bin/python -m f1q run --plan phase5` (do not overwrite historical evidence)
- Packages: `{"PyYAML": "6.0.3", "numpy": "2.5.3", "pydantic": "2.13.5", "qiskit": "1.4.6", "scipy": "1.18.1"}`
- Pipeline elapsed_s: `112.82629874988925`
- Wall ELAPSED_SECONDS (packaging): `1973.5377049446106`

## 3. Scientific object (A2) — corrected scope

Non-anticipative joint strategy policies over a causal SC/VSC scenario tree.  
Family factors (`green_pit_*`, `tyre_*`, `traffic_*`) drive mechanism coefficients; action costs have documented lineage to Stage-2/3/4 factor maps (synthetic, **not F1-calibrated**).  
Scenario probabilities: **deterministic_synthetic** — **NOT** claimed AI-trained.  
SC/VSC duration revealed only through causally available observations (epoch 0 = `root` only).  
Crew overlap remains a **finite cost** (not a hard prohibition).  
Evidence: `instance_inventory.json` → `a2_scope`; `microcase_evidence.json`.

## 4. Size ladder

Circuit-unit qubits: `[8, 12]` (source: `instance_inventory.json`).  
Tiny variables: `[24, 24]`.  
Instances built: `232`.

| Rung | Logical vars | Info sets | Scenarios | Exact executed | SV feasible |
|------|-------------:|----------:|----------:|:--------------:|:-----------:|
| circuit_unit | 8 | 2 | 2 | True | True |
| tiny | 24 | 4 | 3 | False | False |
| small | 54 | 9 | 4 | False | False |
| larger | 120 | 15 | 8 | False | False |

## 5. Classical correctness / formulation equivalence

- Exact/direct vs QUBO: pass `16` / fail `0` (denom `16`) — `formulation_checks.json`
- Exhaustive microcase direct/QUBO: pass `16` / fail `0`
- Enumeration vs MILP: pass `16` / fail `0`
- s_Q excludes offset: pass `16` / fail `0`
- Causal visibility + no duration leak: pass `16` / fail `0`
- Hard constraints (inventory/compound/deadline): **acceptance filtering**, not QUBO penalties — applied to all samplers/comparators (`hard_constraint_encoding`)
- Adversarial suite all_pass: `True` — detail `{"all_infeasible_regret_is_1": {"pass": true, "regret": 1.0}, "all_pass": true, "binding_compound": {"n_legal": 4, "pass": true, "required_compounds": 2}, "binding_deadline": {"pass": true, "reason": "commitment expired pit_now_soft at epoch=1 (expires=0)"}, "binding_inventory": {"n_legal": 40, "one_hot_space": 729, "pass": true}, "genuine_branching": {"n_branching_epochs": 1, "n_info_sets": 3, "pass": true}, "missing_not_zero_regret": {"pass": true, "regret": 1.0}, "no_future_duration_leak": {"detail": "epoch0 observable is root only", "pass": true}, "zero_range_regret_is_0": {"pass": true, "regret": 0.0}}`

## 6. Development headroom (honest reassessment)

Label: **ZERO**.  
Checked instances: `16` (scope: checked only — not universal A2/F1).  
Nonzero `0` / zero `16` / unresolved `0` / exact-inside-deadline `16`.  
Evidence: `headroom_results.json`.  
When exact enumeration finishes inside the operational deadline it is an operational classical competitor; objective headroom vs that incumbent is zero. MILP runtime is included as a classical competitor when inside deadline. Weak fallback gaps are reported separately and do not manufacture superiority headroom.

## 7. Quantum circuit family C0

Actual QUBO cost as Phase/CPhase (RZ/RZZ-equivalent); transverse-X RX mixer; H^n init; p=1,2.  
Checks: pass `6` / fail `0` (denom `6`) — `circuit_checks.json`.  
C0 cannot report zero 2q when quadratic interactions exist (`c0_nonzero_2q_when_quadratic` in details).  
Transpile: **actual circuits** (`circuit_resources.json`, `proxy: false`).

## 8. Quantum circuit family C1

Validated one-hot prep; actual QUBO cost; XY ring (RXX+RYY); p=1,2.  
Checks: pass `6` / fail `0` — includes connected-components proof on **actual** transition graph and broken-schedule adversarial check.  
Evidence: `circuit_checks.json` → `connected_components`, `broken_schedule`.

## 9. C2 admission

**NOT_ADMITTED_BY_PROTOCOL** — A2 models shared pit-crew overlap as a finite cost and one-hot via C1 XY exchanges; no genuine joint hard constraint requires guarded paired moves beyond C1.  
Evidence: `c2_admission.json`.

## 10. Circuit resources

Documented target `rz/sx/x/cx`; seed from frozen config; opt level from frozen config.  
Resource rows: `12`.  
Evidence: `circuit_resources.json`.

## 11. Splits and leakage controls

Total blocks `224` / expected 224.  
Anchors `24`; training extra `120`; tuning `80`.  
Overlap failures `[]`. Calib/eval/test materialised: `False`.  
Evidence: `split_audit.json`, `split_block_ids.json`.

## 12. Complete training coverage

Training used: **144/144** (24 anchors + 120 extra).  
Tuning used: **80/80**.  
Eight-family balance (train): `True`; (tune): `True`.

| Family | Training rows used |
|--------|-------------------:|
| fam.green_pit_high.tyre_near_linear.traffic_dense | 18 |
| fam.green_pit_high.tyre_near_linear.traffic_sparse | 18 |
| fam.green_pit_high.tyre_nonlinear.traffic_dense | 18 |
| fam.green_pit_high.tyre_nonlinear.traffic_sparse | 18 |
| fam.green_pit_low.tyre_near_linear.traffic_dense | 18 |
| fam.green_pit_low.tyre_near_linear.traffic_sparse | 18 |
| fam.green_pit_low.tyre_nonlinear.traffic_dense | 18 |
| fam.green_pit_low.tyre_nonlinear.traffic_sparse | 18 |

Family-depth coverage: `['C0_p1', 'C0_p2', 'C1_p1', 'C1_p2']` (must be all four).  
Evidence: `selector_training_receipt.json`, `selector_train_usage.json` (per-block `entered_feature_compute` / `entered_donor_eval`).

## 13. Parameter bank

Family-depth pairs: `['C0_p1', 'C0_p2', 'C1_p1', 'C1_p2']`.  
Fit identities persisted: **288** (expect 288 = 24×4×3).  
Expectation evaluations: `23040` / cap.  
Fit failures: `0`. Donors selected: `32`.  
Evidence: `bank_fit_records.json`, `parameter_bank_receipt.json`, `donor_inventory.json`.

## 14. Learned donor selector and genuine comparators

Model: NumPy ridge ranking with **persisted weights** (weights_ok=`True`).  
Angle banks remain separate by family and depth.  
Comparators (identified separately; no retrospective best-of as primary):
1. Frozen fixed donor (training-only selection)
2. Genuine nearest-neighbour transfer (fitted donor of nearest training instance)
3. Seeded random donor (identity+seed per block)
4. Learned ridge donor ranker
5. Genuine per-instance variational fit (fresh params; frozen budget starts=1, max_evals=40)

| Family-depth | Train N | Tune N | Learned mean | Fixed | NN | Random | Variational | Noninf@0.02 vs each |
|--------------|--------:|-------:|-------------:|------:|---:|-------:|------------:|---------------------|
| C0_p1 | 144 | 80 | 0.024690591993408794 | 0.01328729129377792 | 0.028128845637228894 | 0.017553506378546375 | 0.03919697267516982 | {"fixed": false, "nn": true, "random": false, "variational": true} |
| C0_p2 | 144 | 80 | 0.02974811410646503 | 0.016144423792714614 | 0.022892615395555437 | 0.029325515542010804 | 0.052118454574730654 | {"fixed": false, "nn": false, "random": true, "variational": true} |
| C1_p1 | 144 | 80 | 0.004064032477563105 | 0.005373531846511724 | 0.006586653508873469 | 0.004115386859904439 | 0.024519757197898236 | {"fixed": true, "nn": true, "random": true, "variational": true} |
| C1_p2 | 144 | 80 | 0.002101692902788988 | 0.005353986361296359 | 0.006586653508873469 | 0.0014202714563373877 | 0.024545080909766925 | {"fixed": true, "nn": true, "random": true, "variational": true} |

Prior non-inferiority from the historical run is labelled **SUPERSEDED_INVALID**.  
Evidence: `selector_tuning_results.json`, `selector_per_block_records.json` (n=320), `selector_model_artifacts.json`.

### Normalised regret

Definition: `(f(a)-f*)/(f_max-f*)`. Zero range → feasible regret 0; all-infeasible pool → regret 1; never coerce missing to 0.  
Unnormalised gaps reported separately per block.  
Useful ≠ all legal: useful requires declared improvement vs weak incumbent (`USEFUL_IMPROVEMENT_FRAC=0.05` of range).

## 15. Microcases (binding / branching / causal)

{
  "cases": [
    {
      "causal_ok": true,
      "id": "microcase:binding_inventory",
      "microcase": "binding_inventory",
      "n_branching_epochs": 1,
      "n_info_sets": 3,
      "n_legal": 40
    },
    {
      "causal_ok": true,
      "id": "microcase:binding_compound",
      "microcase": "binding_compound",
      "n_branching_epochs": 1,
      "n_info_sets": 3,
      "n_legal": 4
    },
    {
      "causal_ok": true,
      "id": "microcase:binding_deadline",
      "microcase": "binding_deadline",
      "n_branching_epochs": 0,
      "n_info_sets": 2,
      "n_legal": 4
    },
    {
      "causal_ok": true,
      "id": "microcase:force_branching",
      "microcase": "force_branching",
      "n_branching_epochs": 1,
      "n_info_sets": 3,
      "n_legal": 729
    }
  ]
}

## 16. AI / classical / quantum role separation

AI: ridge donor ranking only on this stage (scenario probs are deterministic_synthetic).  
Classical: exact enumeration, MILP, heuristic fallback.  
Quantum: local ideal C0/C1 circuits only — no provider path.

## 17. Novelty

`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`.

## 18. QPU and spend

QPU_EXECUTION_AUTHORISED=false; QPU_JOBS=0; QPU_USAGE_SECONDS=0; spending=0; no IBM credentials.

## 19. Tests, doctor, freeze integrity

- Targeted Stage 5: `16 passed`
- Full pytest: `168 passed, 1 skipped`
- pip check: `No broken requirements found.`
- f1q doctor: `ok`
- Frozen Stage 4 path diffs: `0`

## 20. Evidence integrity (acyclic)

Raw evidence finalised → manifest hashes raw+report excluding itself and final verify → final verify hashes manifest.  
No file verifies its own hash. Historical mismatched evidence under `6ad68021-…` preserved unchanged.

## 21. Deviations

[
  {
    "detail": "Historical run 6ad68021-f19c-44e7-b166-13ab44dad31b preserved unchanged; not portrayed as corrected-compliant",
    "id": "ORIGINAL_RUN_PRESERVED"
  },
  {
    "detail": "Previous 0.02 non-inferiority from incomplete/unnormalised metrics labelled SUPERSEDED_INVALID",
    "id": "PRIOR_NONINFERIORITY_SUPERSEDED"
  },
  {
    "detail": "DEVELOPMENT_HEADROOM=ZERO; superiority path disabled or constrained",
    "id": "DEV_HEADROOM"
  },
  {
    "detail": "PROPOSED_NOT_LITERATURE_VERIFIED",
    "id": "NOVELTY"
  }
]

## 22. Negative results

- Development headroom on checked instances: ZERO
- Superiority path available: False
- C2 not admitted by protocol
- Prior incomplete-metric non-inferiority superseded

## 23. Claims status summary

Engineering PASS/NOT_CLOSED does not imply quantum advantage, F1 calibration, or held-out H1 success.

## 24. Stage 4 freeze

Stage 4 evidence frozen; legacy Gate C archived; no resume of e85ee977 / 41c28597; `formulation_gate_c_closure_check` not invoked. Diffs: `0`.

## 25. Stage 6 readiness

PHASE_6_READY: **false** until independent review. Next authorised stage: NONE — await independent review. Not hardware.

## 26. Evidence-path index

- `evidence/stage5/e6b3588b-ab97-48c9-82f4-616785aa3611/` (corrected)
- `evidence/stage5/6ad68021-f19c-44e7-b166-13ab44dad31b/` (preserved historical)
- `docs/evidence/stage5_corrected/`
- `docs/STAGE_5_CORRECTED_REPORT.md` (this file)
- `docs/STAGE_5_REPORT.md` (historical; not replaced)

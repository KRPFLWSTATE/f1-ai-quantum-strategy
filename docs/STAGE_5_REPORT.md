# Stage 5 / Phase 5 — Complete Report

**PHASE_5_ENGINEERING:** `PASS`  
**GATE_D_LEARNING_AND_CIRCUITS:** `PASS`  
**DEVELOPMENT_HEADROOM:** `ZERO`  
**SUPERIORITY_PATH_AVAILABLE:** `False`  
**SELECTED_ARCHITECTURE:** `A2_multi_epoch_scenario_contingent_strategy_policy`  
**C2_STATUS:** `NOT_ADMITTED_BY_PROTOCOL`  
**NOVELTY_STATUS:** `PROPOSED_NOT_LITERATURE_VERIFIED`  
**QPU_EXECUTION_AUTHORISED:** `false`  
**QPU_JOBS:** `0`  
**QPU_USAGE_SECONDS:** `0`

Evidence class: local development / tuning measurements. Not physically measured on QPU. Not a held-out scientific superiority claim.

## 1. Executive outcome

Phase 5 implements architecture **A2** with non-anticipative info-set encoding, independent classical references, C0/C1 local ideal circuits, a preregistered parameter bank, and an inspectable ridge donor selector. Engineering **PASS**. Gate D **PASS**. Development headroom **ZERO**; superiority path `False`.

## 2. Starting gate and reproducibility

- Base commit: `dff670739b6b89892cdbc57c6532dce2cf9cf440`
- Reviewed source commit: `dc8e77a9ffc25a3fca0b6a93b75679035c915f1a`
- Run id: `6ad68021-f19c-44e7-b166-13ab44dad31b`
- Frozen config SHA-256: `ebe74374e317ca0970d1c5fa134a005b12b7a09cd345b3ca75a2cbba07e8d4ba`
- Reproduction: `.venv/bin/python -m f1q run --plan phase5` (do not repeat as a second frozen scientific run)
- Packages: `{"PyYAML": "6.0.3", "numpy": "2.5.3", "pydantic": "2.13.5", "qiskit": "1.4.6", "scipy": "1.18.1"}`

## 3. Scientific object (A2)

Non-anticipative joint strategy policies over a causal SC/VSC scenario tree: decisions once per information set; two team cars; multiple epochs; tyre inventory + compound obligations; shared pit-crew overlap as finite cost; deterministic classical safe fallback. No scenario-copy padding variables.

## 4. Size ladder (measured / estimated)

Circuit-unit qubits: `[8, 8]`. Tiny variables: `[18, 24]`. Instances built: `228`.

| Rung | Logical vars | Info sets | Scenarios | Epochs | Exact executed | SV feasible (complex128) | Note |
|------|-------------:|----------:|----------:|-------:|:--------------:|:------------------------:|------|
| circuit_unit | 8 | 2 | 2 | 2 | True | True |  |
| tiny | 18 | 3 | 3 | 2 | False | True |  |
| small | 36 | 6 | 4 | 3 | False | False | resource_estimation_only_not_circuit_execution; dense statevector NOT claimed locally practical without measured evidence |
| larger | 136 | 17 | 8 | 4 | False | False | resource_estimation_only_not_circuit_execution; dense statevector NOT claimed locally practical without measured evidence |

Dense 30–40q statevector is **not** claimed locally practical without measured evidence. Resource estimation ≠ circuit execution.

## 5. Classical correctness

- Exact/direct vs QUBO: pass 12 / fail 0 (denom 12)
- Enumeration vs MILP: pass 12 / fail 0 (denom 12)
- Non-anticipativity: pass 12 / fail 0
- Encode/decode: pass 12 / fail 0
- Causal visibility: pass 12 / fail 0
- Inventory legality path: pass 12 / fail 0
- Fallback feasibility: pass 12 / fail 0

## 6. Development headroom

Label: **ZERO**. Nonzero `0`; zero `12`; unresolved `0`; exact inside deadline `12`.  
When exact enumeration finishes inside the operational deadline it is an operational classical competitor; objective headroom vs that incumbent is zero. Weak fallback gaps are reported separately and do not manufacture superiority headroom.

## 7. Quantum circuit family C0

Transverse-X mixer; penalty cost Hamiltonian; |+> init; p=1 and p=2. Checks pass 6 / fail 0 (denom 6). Includes norm, param count, Qiskit Statevector cross-check on verification subset, feasibility/regret metrics.

## 8. Quantum circuit family C1

Within-car/info-set XY ring exchanges; one-hot uniform prep counted in resources; p=1 and p=2. Checks pass 6 / fail 0. Outside one-hot amplitude within tolerance on verified instances; feasible-graph edges enumerated.

## 9. C2 admission

**NOT_ADMITTED_BY_PROTOCOL** — A2 models shared pit-crew overlap as a finite cost and one-hot via C1 XY exchanges; no genuine joint hard constraint requires guarded paired moves beyond C1.

## 10. Circuit resources

Documented local generic target `rz/sx/x/cx`; transpiler seed `17`; opt level `1`. Resource rows: 12.

## 11. Splits and leakage controls

Total blocks `224` / expected 224. Anchors `24`; training extra `120`; tuning `80`. Overlap failures `[]`. Calib/eval/test materialised: `False`. Forbidden features rejected by schema (`exact_optimum`, `hidden_tau`, etc.).

## 12. Parameter bank

Family-depth pairs `['C0_p1', 'C0_p2', 'C1_p1', 'C1_p2']`. Anchors `24`; starts/anchor `3`; max evals/start `80`. Expectation evaluations `23040` / cap 23040. Fit failures `0`. Donors selected (all family-depths) `32`. No unrecorded restarts; failed fits retained (count 0).

## 13. Learned donor selector

Model `numpy_ridge_ranking` (NumPy ridge ranking; does not average angle vectors). Tuning blocks `80`. Learned mean regret `0.0049519283907807025`; median `0.0`. Fixed `0.011048080216256157`; NN `0.009314780714386368`; random `0.024188757634146914`; variational-best `0.011652982540728146`. Best reference mean `0.0`. Paired interval `{"alpha": 0.05, "mean": 0.0049519283907807025, "n": 80, "se": 0.0033982830870130224, "upper_95_one_sided": 0.010541606651861917}`. Non-inferiority @0.02 `True`. **Development/tuning only — not held-out scientific claims.**

## 14. AI / classical / quantum role separation

AI supplies scenario probabilities in the generative instance builder and ranks donors; classical exact/MILP/heuristic own combinatorial references; quantum circuits sample/search encoded policies under local ideal simulation only.

## 15. Novelty

`NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED`. C0/C1/QAOA/warm-start/guarded mixers are not claimed novel.

## 16. QPU and spend

QPU_EXECUTION_AUTHORISED=false; QPU_JOBS=0; QPU_USAGE_SECONDS=0; spending=0; no IBM credentials; no provider package required for Phase 5.

## 17. Tests, doctor, freeze integrity

- Targeted Stage 5: `10 passed`
- Full pytest: `162 passed, 1 skipped` (163 collected; 162 passed + 1 skipped)
- pip check: `No broken requirements found.`
- f1q doctor: `ok`
- Frozen Stage 4 path diffs vs reviewed source: `0`

## 18. Deviations

[
  {
    "detail": "DEVELOPMENT_HEADROOM=ZERO; superiority path disabled or constrained",
    "id": "DEV_HEADROOM"
  },
  {
    "detail": "PROPOSED_NOT_LITERATURE_VERIFIED",
    "id": "NOVELTY"
  }
]

## 19. Negative results (useful)

- Development objective headroom ZERO on declared A2 circuit_unit/tiny checks when exact finishes inside deadline.
- Superiority path unavailable.
- C2 not admitted.
- Learned mean regret (0.0049519283907807025) did not beat best reference mean (0.0) on tuning; non-inferiority margin 0.02 still held on the preregistered one-sided paired interval.

## 20. Claims status summary

Engineering PASS does not imply quantum advantage, F1 calibration, or held-out H1 success.

## 21. Stage 4 freeze

Stage 4 evidence frozen; legacy Gate C archived; no resume of e85ee977 / 41c28597; formulation_gate_c_closure_check not invoked.

## 22. Package / versions

f1q `0.5.0`; qiskit `1.4.6` (Apache-2.0); numpy/scipy/pydantic as in environment.json.

## 23. Phase 6 boundary

Next authorised stage after review: Stage 6 local pilot + resource/precision estimation, **not** hardware. PHASE_6_BOUNDARY_PILOT_READY: true (engineering PASS). PHASE_6_SUPERIORITY_PILOT_READY: false.

## 24. Manifest rule

`STAGE_5_MANIFEST.json` excludes itself from its own digest and states that rule.

## 25. Run receipt

elapsed_s `31.938904667040333`; status `PASS`; bank_evals `23040`; split_total `224`.

## 26. Evidence-path index

| Artifact | Path |
|----------|------|
| Run evidence | `evidence/stage5/6ad68021-f19c-44e7-b166-13ab44dad31b/` |
| Docs summaries | `docs/evidence/stage5/` |
| Report | `docs/STAGE_5_REPORT.md` |
| Final verify | `docs/evidence/stage5/STAGE_5_FINAL_VERIFY.json` |
| Claims | `claims_evidence.json` |
| Headroom | `headroom_results.json` |
| Circuits | `circuit_checks.json` / `circuit_resources.json` |
| Bank / donors | `parameter_bank_receipt.json` / `donor_inventory.json` |
| Selector | `selector_training_receipt.json` / `selector_tuning_results.json` |
| Splits | `split_audit.json` |
| C2 | `c2_admission.json` |
| Manifest | `STAGE_5_MANIFEST.json` |

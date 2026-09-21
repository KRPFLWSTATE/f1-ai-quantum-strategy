# Phases 1–6 Acceptance Report (Authoritative pre–Phase 7)

**Document class:** consolidated audit, correction, and acceptance  
**Starting commit (independently inspected):** `ab35715fd640d3743b1635d32a09c41a17a1a76e`  
**Actual starting commit this campaign:** `ab35715fd640d3743b1635d32a09c41a17a1a76e` (clean tree; matches)  
**Corrected Stage 6 run:** `2a3fb275-6c37-4bbc-bdb4-addede80b5c3`  
**Correction wall / CPU:** 115.3 s / 113.4 s  
**Final packaging commit:** *(recorded after push in final receipt; not embedded before commit)*  
**QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **QPU_EXECUTION_AUTHORISED:** false  
**FINAL_TEST_ACCESSED:** false · **Phase 7 started:** false

Evidence rules applied: claims labelled as proposed / implemented / verified by named check / simulated / physically measured / unsupported. Successful commands alone are insufficient.

---

## 0. Dependency map (requirements → implementation → tests → evidence → claims)

| Layer | Artifacts |
|-------|-----------|
| Requirements | `docs/protocol/` dossier v3.1 + `REQUIREMENTS_TRACEABILITY.md`; stage prompts under `docs/prompts/` |
| Implementation | `src/f1q/` (stages 1–6); Stage 6 corrected modules `metrics_pilot`, `noisy`, `capacity`, `sizing`, `novelty`, `corrected_run`, `verify_corrected` |
| Tests | `tests/stage6/test_shot_accounting.py`, `tests/stage6/test_phase6_smoke.py`; prior stage tests reused |
| Raw evidence | Stage 1–5 under `evidence/stage*/`; Stage 6 historical `evidence/stage6/bd83cb22-…/` **preserved**; corrected `evidence/stage6_corrected/2a3fb275-…/` |
| Derived | pilot summaries, sizing bootstrap, capacity arithmetic, novelty JSON, readiness matrix |
| Permitted claims | See `docs/CLAIMS.md` (updated): engineering verification ≠ F1 value ≠ quantum advantage |

---

## 1. Issue register (Phases 1–6)

Machine-readable: `evidence/stage6_corrected/2a3fb275-6c37-4bbc-bdb4-addede80b5c3/issue_register.json`.

| ID | Sev | Stage | Reproduction | Scientific impact | Correction | Evidence | Disposition |
|----|-----|-------|--------------|-------------------|------------|----------|-------------|
| P6-SHOT-CAP | CRITICAL | 6 | `min(pool_size,2**n)` → 8q drew 256 labelled 1024 | Invalid shot-budget / best-of-pool claims | Remove cap; resample | Historical 8q pools invalidated; corrected all pools 1024 | CORRECTED_AND_VERIFIED |
| P6-NOISE-JITTER | CRITICAL | 6 | Uniform+jitter ≠ gate channels | Noise resilience / noisy runtime unsupported | Withdraw; DensityMatrix 1q/2q depolarizing | Historical panel class withdrawn; new panel | CORRECTED_AND_VERIFIED |
| P6-CAPACITY-HARDCODE | HIGH | 6 | Hard-coded timings; 25.46h; seed risk | Reduced matrix not accepted | Measure components; blocks≠cases | Historical capacity claims superseded | CORRECTED_AND_VERIFIED |
| P6-SIZING-PLACEHOLDER | HIGH | 6 | Bootstrap string; 80 blocks/cases | Unjustified N | Execute bootstrap; disclose saturation | Historical sizing superseded | CORRECTED_AND_VERIFIED |
| P6-PROTOCOL-GATE-E | HIGH | 6 | Ready=true under BLOCKED_DRAFT; Gate E overstated | False Phase 7 readiness | Gate E fail intended contribution; ready=false | Prior PASS withdrawn | CORRECTED_AND_VERIFIED |
| P6-A2-CAUSAL | HIGH | 5–6 | Duration revealed epoch 1 | Not operational race-decision model | Redesign spec; readiness false | No silent A2 patch | BLOCKED |
| P6-ZERO-HEADROOM | HIGH | 5–6 | Exact classical timely | No superiority path | Retain ZERO; no manufacture | Confirmed on corrected pilot | VERIFIED_BY_REUSABLE_EVIDENCE |
| P1–P5 open residuals | LOW–MED | 1–5 | See §2 | Scoped | No full campaign rerun | Reuse accepted reports | VERIFIED_BY_REUSABLE_EVIDENCE / documented limitations |

---

## 2. Phase-by-phase acceptance (one category each)

Categories used **exactly**: VERIFIED_NOW | VERIFIED_BY_REUSABLE_EVIDENCE | CORRECTED_AND_VERIFIED | DEFERRED_TO_A_SPECIFIC_LATER_STAGE | BLOCKED | NOT_APPLICABLE_WITH_JUSTIFICATION.

### Phase 1 — environment and execution

| Requirement | Category | Notes |
|-------------|----------|-------|
| Project isolation / root boundary | VERIFIED_NOW | `python -m f1q doctor` project_boundary ok |
| Dependency lock / reproducible entry points | VERIFIED_NOW | doctor dependency_lock + dossier hash match; `.venv/bin/python` |
| Ledger schema / failed attempts / atomic writes / resume | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 1 report + bootstrap receipts; not re-campaigned |
| Config/source invalidate incompatible cache | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 1/2 fail-closed patterns in code + prior reports |
| Dry runs cannot submit QPU | VERIFIED_NOW | `hardware_execution_enabled=false`; QPU_EXECUTION_AUTHORISED false |
| Secrets not committed | VERIFIED_NOW | No secrets in correction commit set; doctor/config draft |
| Provenance/licences for used deps | VERIFIED_BY_REUSABLE_EVIDENCE | `docs/PROVENANCE.md` + lockfile; qiskit 1.4.6 used |

**PHASE_1_ACCEPTANCE:** `PASS` (software infrastructure; not scientific novelty).

### Phase 2 — corpus and splits

| Requirement | Category | Notes |
|-------------|----------|-------|
| Family parameters → instance construction | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 2 report + generator validate history |
| Family labels ↔ mechanisms | VERIFIED_BY_REUSABLE_EVIDENCE | Generator families; labels ≠ validated F1 coverage |
| SC/VSC labels vs model behaviour | VERIFIED_BY_REUSABLE_EVIDENCE | Restricted-menu cases in Phase 6; not full race SC/VSC ops |
| Seed/fingerprint independence across partitions | VERIFIED_BY_REUSABLE_EVIDENCE | Split audits; namespaces alone insufficient — audits recorded |
| Independent blocks / checkpoints / circuit cases / seeds | VERIFIED_BY_REUSABLE_EVIDENCE | Phase 5/6 split artifacts |
| Inspect splits without opening final-test outcomes | VERIFIED_NOW | Corrected calibration audit `final_test_accessed=false` |
| Accidental test exposure | VERIFIED_NOW | None detected in corrected split audit |

**PHASE_2_ACCEPTANCE:** `PASS_WITH_DOCUMENTED_LIMITATIONS` (generated corpus; not F1 calibration).

### Phase 3 — simulator and causal interface

| Requirement | Category | Notes |
|-------------|----------|-------|
| Checkpoint/resumption evidence | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 3 / 3.2 / 3.3 reports |
| Observations / hidden future / time / pit commitment / expiry / fallback | VERIFIED_BY_REUSABLE_EVIDENCE | Simulator checks; adapter validation in Phase 6 |
| Bounded SC/VSC, two-car, hidden-future, late-result checks | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 3 matrix evidence |
| Distinguish Stage 3 validity vs A2 adapter validity | VERIFIED_NOW | Causal adapter: simulator checks pass; **operational A2 readiness false** |
| Helper test ≠ experiment invokes helper | VERIFIED_BY_REUSABLE_EVIDENCE | Documented in Stage 3/6 reports |

**PHASE_3_ACCEPTANCE:** `PASS_WITH_DOCUMENTED_LIMITATIONS` (simulator software). **A2 operational causal:** BLOCKED.

### Phase 4 — formulation and classical references

| Requirement | Category | Notes |
|-------------|----------|-------|
| Direct-cost / QUBO / independent-solver checks | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 4 closure + erratum |
| Active experiment uses accepted encoding/penalties/ties | VERIFIED_BY_REUSABLE_EVIDENCE | Phase 5 A2 uses Stage 4 formulation lineage |
| Classical timing includes preprocessing | VERIFIED_BY_REUSABLE_EVIDENCE | Stage 4/5 timing disclosures |
| Exact refs where applicable | VERIFIED_BY_REUSABLE_EVIDENCE | Enumeration/MILP paths |
| Legacy exhaustive archived; bounded ≠ exhaustive | VERIFIED_BY_REUSABLE_EVIDENCE | `LEGACY_GATE_ACTION: ARCHIVED_DO_NOT_RESUME` |

**PHASE_4_ACCEPTANCE:** `CLOSED_WITH_DOCUMENTED_LIMITATIONS` (engineering). Legacy exhaustive: PARTIAL archived.

### Phase 5 — learning and circuits

| Requirement | Category | Notes |
|-------------|----------|-------|
| Active models/donors/features match corrected evidence | VERIFIED_BY_REUSABLE_EVIDENCE | `e6b3588b-…` + final acceptance `1c7631e…` |
| No calib/test leakage in fitting/selection | VERIFIED_BY_REUSABLE_EVIDENCE | Phase 5 split audit; Phase 6 calib isolated namespace |
| Bank fits vs per-instance variational refs | VERIFIED_BY_REUSABLE_EVIDENCE | Disclosed incomplete historical variational vectors |
| Executable circuit path Phase 6 uses | VERIFIED_NOW | C0/C1 simulate + Qiskit cross-check in corrected verify |
| Repaired C1 evidence | VERIFIED_BY_REUSABLE_EVIDENCE | Final acceptance repair; not altered |
| Bit order / relative-phase-sensitive comparison | VERIFIED_BY_REUSABLE_EVIDENCE | Phase 5 final acceptance |
| One-hot vs semantic legality separated | VERIFIED_NOW | Exact metrics fields in corrected pilot |
| Prep/cost/mixer resources accurate | VERIFIED_BY_REUSABLE_EVIDENCE | `actual_circuit_resources.json` |
| C2 outside protocol | VERIFIED_BY_REUSABLE_EVIDENCE | NOT_ADMITTED |
| No claim XY/donor selection as new algorithms | VERIFIED_NOW | Novelty v2 |

**PHASE_5_ACCEPTANCE:** `PASS_WITH_DOCUMENTED_LIMITATIONS`.

### Phase 6 — mechanism pilot / Gates E–F (corrected)

| Requirement | Category | Notes |
|-------------|----------|-------|
| Shot accounting | CORRECTED_AND_VERIFIED | All pools 1024 draws |
| Noise evidence | CORRECTED_AND_VERIFIED | Gate-channel sensitivity model; historical withdrawn |
| Precision / bootstrap | CORRECTED_AND_VERIFIED | Executed; saturated-zero endpoint |
| Resource estimates | CORRECTED_AND_VERIFIED | Measurement-backed |
| Gate E scientific value | CORRECTED_AND_VERIFIED | FAIL_FOR_INTENDED_CONTRIBUTION |
| Operational readiness | BLOCKED | A2 surrogate |
| Superiority | BLOCKED | ZERO headroom |
| Phase 7 auto-start | NOT_APPLICABLE_WITH_JUSTIFICATION | Explicitly not authorised |

**PHASE_6_ACCEPTANCE:** `CORRECTED_WITH_DOCUMENTED_LIMITATIONS`.

---

## 3. Shot accounting (Section C)

**Defect:** with-replacement sampling was capped at Hilbert dimension, so 8-qubit pools labelled 1024 contained only 256 draws (feas max 256). 12-qubit pools were already 1024.

**Correction:** `pool_sample_metrics` always draws `pool_size` with replacement; records `requested_shots`, `actual_draws`, `counts_sum`, `shot_conservation_ok`, seed, optional distribution/circuit/parameter IDs, legal/invalid counts, lex-first tie rule.

**Regression tests (VERIFIED_NOW):** `tests/stage6/test_shot_accounting.py` — 1024 draws on 8q; counts sum; duplicates allowed; all-invalid handled.

**Corrected evidence:** every pool in run `2a3fb275-…` has `actual_draws=1024`. 8q mean feasible-in-pool **1001.9** (was **250.5**). Old 256-draw results retained historically under superseded run id — **not** relabelled as 1024.

---

## 4. Noise evidence (Section D)

**Withdrawn class:** probability mix toward uniform + Gaussian jitter.  
**Replacement:** DensityMatrix evolution applying documented 1q/2q depolarizing after native gates on actual C0/C1 circuits (prep+mixer included); separate exact noisy probs and finite-shot pools; ≤10q; synthetic ≠ IBM.  
**Checks:** analytical self-check; zero-noise vs independent ideal **32/32**; finite nonnegative normalised.  
**If Aer absent:** implemented without Aer using `qiskit.quantum_info` (compatible installed stack).

---

## 5. Pilot summaries and precision (Section E)

Admitted arms: C0/C1 × p=1/2 × {learned, fixed, nn, random} on 48 cases.

| Metric | Corrected result |
|--------|------------------|
| Exact inside deadline | 48/48 |
| Mean strict-improve vs exact | 0.0 |
| Best-of-pool normalised regret | **identically 0** (saturated) |
| Mean one-hot ≈ legal mass | ≈ 0.980 |
| Mean optimal mass | ≈ 0.052 |
| DEVELOPMENT_HEADROOM | ZERO |

Paired block bootstrap: average SC/VSC within block; equal-weight eight families; n_boot=2000; seed=20260921; **EXECUTED**. CI95 `[0,0]`. Independent-block recommendation status: `DEGENERATE_ZERO_OBSERVED_HALFWIDTH` → protocol floor **80 blocks** (not superiority power). Endpoint not swapped post-calibration.

---

## 6. Resources (Section F)

Hard-coded performance constants **removed** from claimed measured estimates.  
Measured: instance+QUBO, enum, features, C0/C1 evolution, exact scan, one 1024 pool, gate-noise DM when ≤8q.  
Arithmetic: unique distributions × cold cost + pools × incremental pool cost + variational evals × measured eval + classical + packaging; **seeds not double-counted**.  
CPU vs wall tracked on correction campaign (115.3 wall / 113.4 CPU). Parallelism assumption: ≤2 workers.  
**80 blocks ≠ 80 cases** resolved: 80 blocks ⇒ 160 SC+VSC case rows in proposed reduced matrix. Variational reference retained at reduced nonzero budget; superiority excluded.

---

## 7. Scientific value and F1 scope (Section G)

### Decisions

1. **Engineering correctness (post-correction):** PASS_WITH_DOCUMENTED_LIMITATIONS for Stage 6 software/pilot accounting.  
2. **Narrow mechanism study readiness:** artifacts acceptable with limitations; **PHASE_7_MECHANISM_READY=false** until freeze/amendment/review.  
3. **Operational simulator study readiness:** **false** (A2 revealed-duration; no observation→policy→commitment path).  
4. **Superiority claims readiness:** **false** (ZERO headroom; do not manufacture classical failure).  
5. **Adequacy for AI–quantum–F1 objective:** **INSUFFICIENT** — Gate E `FAIL_FOR_INTENDED_CONTRIBUTION`.

SC/VSC/tyre/traffic labels select generator families; mechanism outcomes remain dominated by exact classical on microcases — **not** validated motorsport coverage.

### Operational redesign specification (required; not implemented here)

1. Replace A2 revealed-at-epoch-1 duration with event-timed observation projection from simulator `DecisionObservation`.  
2. Retrain selector / rebuild bank under new features — **do not** reuse Phase 5 training as unchanged.  
3. Validate action expiry and pit-entry commitment on live continuation streams for A2 policies.  
4. Wire independent evaluator with separate random banks and event-keyed CRN.  
5. Do not open final-test until Gate E/F and causal readiness pass for the admitted scope.

---

## 8. Final acceptance artifacts (Section H)

| Artifact | Path |
|----------|------|
| This report | `docs/PHASES_1_TO_6_ACCEPTANCE_REPORT.md` |
| Stage 6 corrected report | `docs/STAGE_6_CORRECTED_REPORT.md` |
| Protocol freeze v2 | `docs/STAGE_6_PROTOCOL_FREEZE_V2.md` |
| Novelty reassessment | `docs/STAGE_6_NOVELTY_COMPARISON.md` |
| Issue register | `evidence/stage6_corrected/2a3fb275-…/issue_register.json` |
| Requirements map | `docs/evidence/stage6_corrected/REQUIREMENTS_MATRIX.json` |
| Raw/derived evidence | `evidence/stage6_corrected/2a3fb275-…/` |
| Manifest | `…/STAGE_6_CORRECTED_MANIFEST.json` |
| Verifier | `…/STAGE_6_CORRECTED_FINAL_VERIFY.json` (**15/15**) |
| Source inventory | `…/source_tree_inventory.json` (includes new files; not patch-hash alone) |

Acyclic: evidence/report → manifest → verifier. Historical Stage 6/5 evidence preserved with path+hash inventory checks.

---

## 9. What was verified vs outside coverage

**Verified now:** shot conservation on corrected pools; gate-channel analytical + zero-noise panel; bootstrap execution; measurement-backed capacity flags; readiness booleans; doctor; split isolation; C1 cross-check; protected historical file inventory.

**Outside coverage / not claimed:** full Phase 1–5 campaign reruns; exhaustive Gate C; physical IBM noise; operational F1 value; quantum advantage; absolute novelty; final-test outcomes; Phase 7 experiments; absence of all possible defects.

---

## 10. Final receipt fields

See packaging section after commit/push in the agent final response. Pre-commit values:

- PHASE_1_ACCEPTANCE: PASS  
- PHASE_2_ACCEPTANCE: PASS_WITH_DOCUMENTED_LIMITATIONS  
- PHASE_3_ACCEPTANCE: PASS_WITH_DOCUMENTED_LIMITATIONS (operational A2 BLOCKED)  
- PHASE_4_ACCEPTANCE: CLOSED_WITH_DOCUMENTED_LIMITATIONS  
- PHASE_5_ACCEPTANCE: PASS_WITH_DOCUMENTED_LIMITATIONS  
- PHASE_6_ACCEPTANCE: CORRECTED_WITH_DOCUMENTED_LIMITATIONS  
- BLOCKING_ISSUES_REMAINING: operational causal redesign; Gate E fail for intended contribution; Phase 7 not authorised  
- NONBLOCKING_LIMITATIONS: saturated regret endpoint; 3 blocks/family calib uncertainty; abstract-only for some papers; no Aer (qi DensityMatrix used)  
- SHOT_ACCOUNTING: CORRECTED  
- NOISE_EVIDENCE_CLASS: synthetic_gate_depolarizing_sensitivity_model  
- PRECISION_ANALYSIS_EXECUTED: true  
- INDEPENDENT_BLOCK_COUNT_JUSTIFIED: DEGENERATE_ZERO_OBSERVED_HALFWIDTH (protocol floor 80 blocks)  
- RESOURCE_ESTIMATES_MEASUREMENT_BACKED: true  
- GATE_E_SCIENTIFIC_VALUE: FAIL_FOR_INTENDED_CONTRIBUTION  
- GATE_F_LOCAL_PRECISION_AND_RESOURCES: PASS_WITH_LIMITATIONS  
- F1_CONTRIBUTION_STATUS: INSUFFICIENT  
- PROTOCOL_STATUS: MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED  
- FINAL_TEST_ACCESSED: false  
- PHASE_7_MECHANISM_READY: false  
- PHASE_7_OPERATIONAL_READY: false  
- PHASE_7_SUPERIORITY_READY: false  
- SOURCE_COMMIT: ab35715fd640d3743b1635d32a09c41a17a1a76e  
- QPU_JOBS: 0 · QPU_USAGE_SECONDS: 0 · QPU_EXECUTION_AUTHORISED: false

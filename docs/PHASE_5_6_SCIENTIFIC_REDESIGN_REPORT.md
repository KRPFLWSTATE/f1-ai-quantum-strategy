# Phases 5–6 scientific redesign report

**Document class:** consolidated A2 residual correction + A3 operational redesign  
**Starting commit:** `d05f9d3099eddd693b244c0258ca5a185c8201a1` (matched `origin/main`; clean tree at start)  
**A2 residual run:** `e437fa3d-c29c-43c3-9a55-708c1b36f5e6`  
**A3 run:** `a5fdb488-9a90-47f9-a4f5-7f77a74180a6`  
**Campaign wall / CPU:** 178.3 s / 177.1 s  
**Interrupted attempts retained:** residual `49fec8ee-…`; A3 freeze-only `e12246d1-…` (first campaign crashed on reserved-partition spec; not overwritten)  
**QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **QPU_EXECUTION_AUTHORISED:** false  
**FINAL_TEST_ACCESSED:** false · **Phase 7 started:** false

Evidence labels: proposed / implemented / verified by named check / simulated. Not physically measured. Not F1-calibrated. Not quantum advantage.

---

## 0. What was preserved

Phases 1–4 remain closed. Frozen Phase 5 evidence under `evidence/stage5/` was not altered. Historical Phase 6 `evidence/stage6/bd83cb22-…` and corrected `evidence/stage6_corrected/2a3fb275-…` were not overwritten. A2 zero-headroom and Gate E fail-for-intended-contribution on the A2 surrogate are retained. Final-test remains sealed.

A3 is a **pre-final-test protocol amendment**, not an A2 continuation. A2 calibration cannot confirm A3. Amendment: `docs/PROTOCOL_AMENDMENT_A3.md`.

---

## 1. A2 residual package (new superseding evidence)

Path: `evidence/stage6_a2_residual/e437fa3d-c29c-43c3-9a55-708c1b36f5e6/`  
Supersession: `supersession.json` (does not rewrite 2a3fb275 or bd83cb22).

### 1A. Sampling histograms

Implementation: `pool_sample_metrics` now persists `requested_shots`, `actual_draws`, sparse `histogram_sparse`, `histogram_sum`, seed, RNG id/bit-generator/numpy version, `distribution_hash`, circuit/parameter/instance/policy IDs, legal / semantic-invalid / decoding-invalid counts, selected candidate, lex-first tie rule.

Unique probability vectors: 58 lossless `npz` files under `distributions/` with hashes. Histograms independently recover draws (`histogram_sum == actual_draws`).

Regeneration: frozen Phase 5 donors `e6b3588b-…`; **no** retraining or circuit optimisation. Deterministic instances from `phase6.calib.*` salt. Reduced residual matrix: 8 families × 1 block × SC+VSC × {C0_p1,C1_p1} × {learned,fixed} × 3 pool seeds.

| Quantity | Count |
| --- | ---: |
| Pools | 192/192 |
| Draws per pool | 1024/1024 |
| Unique distributions | 58 |
| Shot conservation | 192/192 |

Tests: `tests/stage6/test_residual_histograms_noise.py` (1024 draws on 8q; duplicates; histogram sum; two known legal outcomes with analytical hit probability \(1-(1-p)^n\); all-invalid; lex-first ties).

### 1B. Native-basis noise

Module: `src/f1q/stage6/native_noise.py`. Transpile C0/C1 to `rz/sx/x/cx`; qiskit 1.4.6; seed_transpiler recorded; optimisation level 1; **no coupling map; no routing claim**. Virtual-RZ declared: 1q depolarizing after `sx/x` only; 2q after every `cx`. Prep/cost/mixer included after decomposition. Same depolarizing Kraus convention as the logical panel.

Prior 2a3fb275 panel is **relabelled** as logical-gate-level sensitivity (channels on undecomposed CRY/CPhase/RXX/RYY), not native-basis.

Native panel: 16/16 completed; zero-noise transpiled vs independent ideal **16/16**; channel count == eligible native gates **16/16**; analytical fixtures pass (1q p=1 after X → mixed; 2q p=1 after CX matches Pauli-twirl closed form \((4I-\rho)/15\), which is **not** \(I/4\); negative control: CRY logical 2q channels=1 vs native cx=2).

### 1C. Paired A2 summaries (descriptive only)

Source: all 48/48 corrected 2a3fb275 pilot units. Class: `DESCRIPTIVE_DIAGNOSTICS`. Best-of-pool regret remains saturated at 0; **not** promoted to a new A2 primary.

| Contrast | n | mean diff |
| --- | ---: | ---: |
| learned vs fixed (C0 p=1 regret) | 48 | 0.0 |
| learned vs NN | 48 | 0.0 |
| learned vs random | 48 | 0.0 |
| C1 vs C0 matched p=1 (legal mass) | 48 | +0.0523 |
| C0 p=2 vs p=1 (optimal mass) | 48 | −0.00026 |

Stratified equal-family-weight block bootstrap executed (n_boot=2000, seed=20260921); SC/VSC pairing preserved.

### 1D. Resource grid (measured)

8q (standard) and 12q (force_branching). **10q not a native A2 size** (would require dummy padding; not used). ≥5 reps for statevector evolution; wall + process CPU; actual variational objective; native-basis noisy DM on 8q only (12q DM refused). Historical 0.5 h **excluded**. One 8q p=1 timing **not** used for every size/depth.

Representative medians (wall s): 8q C0 p=1 cold 0.0037; 8q C1 p=1 0.0087; 12q C0 p=1 0.106; 12q C1 p=2 0.220; 8q native noisy C0 ~0.37; 8q native noisy C1 ~1.01.

Arithmetic: unique distributions × evolution + pools × incremental sampling; counted once.

---

## 2. A3 operational architecture

Package: `src/f1q/a3/`. CLI: `python -m f1q.a3` and `python -m f1q run --plan a3_redesign`.

The solver calls **actual** Stage 3 interfaces: `RaceSimulator.initialize`, `advance_to_checkpoint`, `observe`, `validate_plan`, `consider_recommendation`, `continue_to_finish`. Evaluator is `outcome()["team_loss"]` (`normalized_team_rank_loss`), **not** proxy QUBO cost.

Observation uses only DecisionObservation fields (lap, regime status, cars/compounds/ages, gaps, inventories, pit-lane loss, crew, forecasts, deadline/expiry). Hidden: future interruption duration, future traffic, service draws, final evaluator outcomes. Forbidden-token scan rejects duration leakage.

Rolling-horizon menu (F1 reasons, not enlarged to break enumeration): per car continue vs pit_now (preferred unused compound) or delay-1 if pit expired; later info-set is contingent completion keyed by a future **observable**, not hidden duration; stacking represented as shared-crew pair cost on simultaneous pit_now.

C0/C1 are candidate generators inside that horizon. Classical portfolio: exact menu enum / greedy / local / SA / uniform legal / diversity top-k / mandatory continuation fallback. Fairness: equal downstream k. Quantum value defined as marginal simulator loss after strong classical candidates are present.

New A3 ridge models on causal + QUBO-structure features only (`no_hidden_future_features`, `no_evaluator_outcome_features`). Dispatcher: classical-only / classical+C0 / classical+C1 with mandatory fallback if predicted benefit, uncertainty, or deadline fails.

### Adversarial validation (7/7)

`evidence/a3/a5fdb488-…/causal_adversarial.json`

- identical observables + different hidden futures → same pre-divergence policy
- future-duration leakage rejected
- late results → frozen classical fallback
- pit-entry commitment + action expiry enforced
- two-car shared-crew conflicts represented
- accepted actions pass through actual continuation
- evaluator from continuation, not proxy QUBO

Direct-cost/QUBO agreement: 8/8 legal assignments, max abs diff \(7.2\times 10^{-16}\).

---

## 3. Partitions and bounded pilot

Planned: 24 anchors, 120 train, 80 tune, 24 calib, 80 final-test hash-only. Isolation OK; no A2 ID reuse; final-test unopened.

Executed (8-family balanced): **8/24** anchors, **8/120** train (16 SC+VSC case rows), **8/80** tune (16), **8/24** calib (16). Shortfall: anchors 16, train 112, tune 72, calib 16. Worlds: 4 train / 8 calib (predeclared start 8; 8192/32768 not run; SE scale to 8192 = \(\sqrt{8/8192}=0.03125\)).

Freeze written **before** calib outcomes: `protocol_freeze.json`.

Primary estimand on 8/8 paired blocks: mean difference **0.0** (CI95 [0,0], n_boot=2000). Dispatcher chose `classical_only` on **16/16** calib rows (predicted marginal utility ~0; residual std \(10^{-6}\)). Fallback rate 0; timely rate 1.0. Harm frequency 0. Classical matched offline on **16/16** case rows because the menu is fully enumerable inside the deadline.

**OPERATIONAL_DECISION_HEADROOM:** `ZERO_ON_CHECKED_CALIBRATION_MENU_FULLY_ENUMERABLE`  
**Experiment:** `UNINFORMATIVE_FOR_QUANTUM_MARGINAL` — difficulty was not manufactured.

---

## 4. Gates and Phase 7

| Gate | Result |
| --- | --- |
| Gate E | `UNRESOLVED` |
| Gate F | `PASS_WITH_LIMITATIONS` |
| F1 contribution | `BOUNDARY_STUDY_IMPLEMENTED` / uninformative quantum marginal |
| Protocol | `A3_CALIBRATION_PILOT_PREDECLARED` (not final-test authorised) |
| PHASE_7_BOUNDARY_STUDY_READY | false (explicit later prompt required; uninformative quantum marginal) |
| PHASE_7_OPERATIONAL_READY | false |
| PHASE_7_SUPERIORITY_READY | false |

Independent verifier: **16/16** (`FINAL_VERIFY.json`), inspecting histograms, distribution hashes, native counts, QUBO agreement, causal invariance, continuation, split isolation, paired denominators, recomputed mean 0.0, feature provenance, manifest hashes, readiness flags.

---

## 5. Resources / Phase 7 projection

This campaign: **0.049 CPU-h** (177 s). Residual sampling 7 s; native panel ~16 s; A3 train/tune/calib ~150 s.

Phase 7 80-block continuation at **8 worlds** (same protocol): order **0.2–0.5 CPU-h**.  
8192 worlds by naive scaling: order **~200 CPU-h** (not run; exceeds a 24 h ceiling). Do not treat 8-world SEs as 8192-world precision.

---

## 6. Claims ledger (honest)

- A3 causal integration: **verified by named check**
- A2 residual histograms/native noise: **verified by named check**
- Quantum improvement: **unsupported** (uninformative on this menu)
- Quantum advantage / first / team performance: **unsupported / prohibited**
- A2 superiority path: still **false** (zero proxy headroom)

---

## 7. Failures and deviations

- First campaign attempt `e12246d1-…` failed: `ScenarioSpec` rejects reserved partition labels `training|calibration`. Fixed by materialising fixtures as `partition=development` with namespace `a3.{split}`. Interrupted freeze retained.
- First residual `49fec8ee-…` completed before that crash; authoritative residual is `e437fa3d-…`.
- A3 menu fully enumerable → quantum arm never dispatched on calib (16/16 classical_only). Reported as uninformative, not PASS.
- 10q resource cell absent (not a native A2 size).
- Full 224+ training not executed (ceiling); machinery present; shortfall recorded.
- Native 2q p=1 is Pauli-twirl \((4I-\rho)/15\), not \(I/4\).
- Abstract-only access for Aguad & Thraves EJOR and RSRL; Kolstee listing only.

Entry points: `python -m f1q.a3` · targeted tests `tests/stage6/test_residual_histograms_noise.py` and `tests/a3/test_a3_core.py` (16 passed before campaign).

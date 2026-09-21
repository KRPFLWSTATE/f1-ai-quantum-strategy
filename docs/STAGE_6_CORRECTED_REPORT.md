# Stage 6 Corrected Report

**PHASE_6_ACCEPTANCE:** `CORRECTED_WITH_DOCUMENTED_LIMITATIONS`  
**Supersedes:** run `bd83cb22-6a38-4d21-9267-3253f52587d7` / `docs/STAGE_6_REPORT.md` (preserved)  
**Corrected run_id:** `2a3fb275-6c37-4bbc-bdb4-addede80b5c3`  
**Evidence:** `evidence/stage6_corrected/2a3fb275-6c37-4bbc-bdb4-addede80b5c3/`  
**Docs mirror:** `docs/evidence/stage6_corrected/`  
**GATE_E_SCIENTIFIC_VALUE:** `FAIL_FOR_INTENDED_CONTRIBUTION` (prior `PASS_FOR_DEFINED_SCOPE` withdrawn)  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `PASS_WITH_LIMITATIONS`  
**PROTOCOL_STATUS:** `MECHANISM_SCOPE_DRAFT_V2_NOT_FINAL_TEST_AUTHORISED`  
**SHOT_ACCOUNTING:** `CORRECTED`  
**NOISE_EVIDENCE_CLASS:** `synthetic_gate_depolarizing_sensitivity_model`  
**DEVELOPMENT_HEADROOM:** `ZERO`  
**PHASE_7_MECHANISM_READY:** `false`  
**PHASE_7_OPERATIONAL_READY:** `false`  
**PHASE_7_SUPERIORITY_READY:** `false`  
**FINAL_TEST_ACCESSED:** `false`  
**QPU_JOBS:** `0` · **QPU_USAGE_SECONDS:** `0` · **QPU_EXECUTION_AUTHORISED:** `false`

Wall time (correction campaign): **115.3 s**. CPU time: **113.4 s**.

---

## 1. Defects corrected

| ID | Defect | Correction |
|----|--------|------------|
| P6-SHOT-CAP | `min(pool_size, 2**n)` capped 8q pools at 256 while labelled 1024 | Removed Hilbert cap; `actual_draws==1024` on all pools |
| P6-NOISE-JITTER | Uniform mix + Gaussian jitter sold as depolarizing | Withdrawn; DensityMatrix 1q/2q depolarizing on actual C0/C1 |
| P6-CAPACITY-HARDCODE | Hard-coded 0.36s/pool → 25.46h; seed double-count risk | Measured component timings; explicit arithmetic; blocks≠cases |
| P6-SIZING-PLACEHOLDER | Bootstrap string only; 80 blocks vs 80 cases | Executed stratified block bootstrap; protocol floor disclosed |
| P6-PROTOCOL-GATE-E | BLOCKED_DRAFT + MECHANISM_READY true; Gate E overstated | Gate E fail for intended contribution; mechanism ready false |
| P6-A2-CAUSAL | Revealed-at-epoch-1 surrogate | Remains BLOCKED for operational readiness |
| P6-ZERO-HEADROOM | Exact classical dominance | Retained; no manufactured superiority path |

Historical noisy panel class: `WITHDRAWN_AS_GATE_LEVEL_NOISE_EVIDENCE:probability_mix_toward_uniform_plus_gaussian_jitter_not_gate_channels`.

## 2. Corrected pilot denominators

| Quantity | Planned | Completed | Failed |
|----------|--------:|----------:|-------:|
| Calibration blocks | 24 | 24 | — |
| Cases (SC+VSC) | 48 | 48 | 0 |

- Namespace `phase6.calib.*`; final-test not accessed.
- All pools: `requested_shots=1024`, `actual_draws=1024`, `shot_conservation_ok=true`.
- 8q feasible-in-pool mean **1001.9** (was **250.5** under the Hilbert cap).
- Best-of-pool normalised regret **identically 0** across arms (saturated under exact incumbent).
- Mean exact one-hot ≈ legal mass ≈ **0.980**; mean optimal mass ≈ **0.052**.

## 3. Precision

Stratified equal-family-weight block bootstrap **EXECUTED** (n_boot=2000, seed=20260921).  
CI95 on block-mean best-of-pool regret: `[0.0, 0.0]` — **DEGENERATE_ZERO_OBSERVED_HALFWIDTH**.  
Recommended held-out **80 independent blocks** is the **protocol floor**, not a variance-powered superiority sample size.  
Do not equate 80 blocks with 80 cases: SC/VSC are paired checkpoints → **160 case rows**.

## 4. Resources (measurement-backed)

Representative measured costs include QUBO construction, enum, features, C0/C1 evolution, exact scan, one 1024-draw pool, and gate-depolarizing density-matrix (≤8q).  
Prior unsupported **25.46 h** extrapolation **withdrawn**.  
Full-dossier extrapolation from measured components ≈ **0.80 CPU-h** (conservative ×2 band still ≪24h on this machine for the amortised model; uncertainty labelled).  
Reduced proposed matrix: **80 blocks / 160 case rows**, 10 pool seeds, retained reduced variational budget; estimated ≈ **0.14 CPU-h** (serial).

## 5. Noise

New panel: synthetic **gate depolarizing** via `qiskit.quantum_info.DensityMatrix` on actual circuits; prep+mixer included; zero-noise **32/32** vs independent ideal; finite nonnegative normalised probs.  
**Not** measured IBM noise. Historical panel preserved but withdrawn as gate-noise evidence.

## 6. Gate E / F1 contribution

Nearest literature (abstract/metadata + selected full text where fetched): classical DP/game-theory F1 pit strategy (Carrasco Heine & Thraves 2023; Aguad & Thraves 2024); MILP/stochastic F1 strategy theses; RL race-strategy work (e.g. arXiv:2512.21570 abstract/PDF fetched); QAOA/XY mixers as standard quantum methods.  
**Adequacy for AI–quantum–F1 objective:** `INSUFFICIENT`. Engineering cleanliness and zero-headroom alone are not the required research contribution.  
Operational causal readiness remains **false** (A2 revealed-duration surrogate).

## 7. Verification

`STAGE_6_CORRECTED_FINAL_VERIFY.json`: **15/15** checks pass, including shot conservation, noise class, bootstrap executed, measurement-backed capacity, readiness conditions, protected historical inventory (path+hash), Phase 5 final-acceptance manifest.

## 8. Phase 7

**Not started.** No automatic authorisation. Mechanism follow-up requires dated amendment + review even after this correction; operational/superiority paths remain closed.

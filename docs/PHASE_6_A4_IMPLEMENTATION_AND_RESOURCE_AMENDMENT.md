# Phase 6 A4 implementation and resource amendment

**Document class:** prospective, pre-outcome A4 implementation/resource amendment.  
**Status:** written before any new training, tuning, or calibration outcome of the authorised completion run is opened.  
**Authority:** Cursor Phase 6 completion prompt (this conversation); dossier v3.1; `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`; Phase 6 freeze documents.  
**Does not rewrite** `docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf`.  
**QPU_EXECUTION_AUTHORISED:** false. **PHASE_7_AUTHORISED:** false. **FINAL_TEST_ACCESSED:** false.

Evidence labels used below: proposed / implemented. No new experimental observation is claimed in this document.

## 1. Why this amendment exists

Run `3de109c7-30d9-4cb0-827f-dbd82c4c509d` is preserved byte-for-byte. Its truthful statement that **no 120/80/24 corpus ran** remains valid. Its non-admission is **not** an adequate scientific resource conclusion:

- eight workers were reported while execution loops were sequential;
- projection divided by an assumed parallel factor although no real worker pool executed the campaign;
- the admission probe covered C0-p1, a fixed donor, one stochastic seed, and 64 draws, not the frozen scientific contract;
- `PreparedCase` was constructed then ignored by the decision path;
- `pool_draws: 1024` in config was overridden by hard-coded 64/256;
- `--execute-phase6` stopped at `campaign_raw_complete`.

Disposition of that run in the new lineage: `SUPERSEDED_RESOURCE_MODEL_ONLY`. Files under `evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/` are not modified.

Prior failed A4 run `09806343-f940-4f33-9e0f-eb2855d0714b` remains the hash-verified source of the 24-anchor / 288-start donor fits. Those fits are **not** refit under the new run ID.

## 2. Resource constraints: dossier vs implementation-added walls

The previous **75-minute campaign ceiling** and **60-minute admission threshold** were **implementation-added constraints**, not the dossier’s canonical Phase 6 resource ceiling.

The dossier’s governing local resource constraints (`docs/protocol/dossier_extracted.txt` § resource paragraph; protocol freeze) are:

1. use **no more than 60% of measured RAM**;
2. **checkpoint-bounded units**;
3. a **provisional 24 CPU-hour ceiling**.

The 24 CPU-hour figure is a **ceiling**, not evidence that any particular matrix fits, and **not** a scientific sample-size rule.

### 2.1 This attempt’s additional user-protection wall

This attempt adds a separate **user-protection wall-clock ceiling of 4 hours (14,400 s)** for the authoritative campaign command.

Admission must project **no more than 3 hours 12 minutes (11,520 s)** conservative wall time, leaving a 20% wall reserve.

This wall ceiling **does not convert 24 CPU-hours into a scientific sample-size rule**.

### 2.2 CPU accounting (two definitions)

| Definition | Bound | Includes | Excludes |
|---|---:|---|---|
| Campaign CPU | 86,400 CPU-seconds | admission probes, corpus computation, analysis, verification | installation; ordinary tests |
| Process accounting | reported raw | `RUSAGE_SELF` + `RUSAGE_CHILDREN` (user+sys) | n/a |

Both definitions and the raw process counters are recorded on the admission receipt and campaign resource artifact.

### 2.3 Why a pre-test redesign is permitted

No outcome of the **new** run has been opened. Implementation repair and prospective resource correction are therefore permitted by the dossier’s pre-test redesign rule. After outcomes open, source changes require a new run ID.

## 3. Prospective world ladders

Resource-driven selection may choose **only** among these predeclared ladders. It may reduce redundant resampling by reusing exact distributions and cached world outcomes. It **may not** drop parent blocks, circuit families, depths, budgets, registered policies, calibration blocks, or the **2,048-world calibration start**.

Planning and evaluation banks are independent. Calibration evaluation **starts at 2,048 paired worlds per checkpoint**.

| Ladder | Training planning / evaluation | Tuning planning / evaluation | Calibration planning / evaluation | Offline planning / evaluation |
|---|---:|---:|---:|---:|
| preferred | 8 / 64 | 16 / 256 | 64 / 2,048 | 64 / 2,048 |
| baseline | 4 / 32 | 8 / 128 | 32 / 2,048 | 32 / 2,048 |
| minimum | 2 / 16 | 4 / 64 | 16 / 2,048 | 16 / 2,048 |

The Phase 6 variance diagnostic chooses a Stage 7 production target from **2,048, 8,192, or 32,768**. Phase 6 need not execute all three counts at every checkpoint. It estimates the choice from stored paired per-world losses and runs a predeclared higher-count validation subset only if needed to validate the extrapolation **and** it fits the cap.

If even the minimum ladder cannot fit after the required implementation repairs and **real** parallel measurement, this attempt will not invent a pass. It will execute the largest prospectively valid, explicitly limited resource pilot that fits, preserve required diagnostics, and close as `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`. That is a last-resort honest outcome, not the default path, and not permission to skip implementation.

## 4. Frozen scientific contract this repair must implement

These are requirements, not optional suggestions:

1. One immutable `PreparedCase` per case; all arms/donors/depths/policies/budgets/seeds consume it; preparation counters prove once-per-case.
2. Real process pool; `choose_workers()` controls execution; spawn context; BLAS/OpenMP = 1 per worker; worker count `min(cpu_count-2, floor(0.60 * RAM / measured_peak_worker_RSS), 8)` with floor 1; measured RSS plus documented safety multiplier (1.5×) replaces the old 512 MiB assumption.
3. Coordinator writes ordered JSONL; workers return serialisable bundles; atomic fsynced writes.
4. Circuit distributions computed once per unique `(prepared_case_hash, family, depth, donor_parameters, simulator_version)`; 1,024-draw pools resample that distribution; C1 stays on the legal one-hot subspace (no dense `2^n` allocation).
5. Byte-bounded caches; matched K = 4 unique slots including fallback; hybrid **replaces** classical slots.
6. Frozen scenario latency keyed by case/option/budget/seed; isolated local compute latency reported separately; never called provider latency; no component hard-coded to zero; no divide-by-two of paired turnaround; no artificial sleep to consume a budget.
7. Config enforced: `pool_draws=1024`; family/depths `C0_p1,C0_p2,C1_p1,C1_p2`; budgets 5, 10, 30, 60, 120 s (30 s primary); three Phase 6 policy seeds.
8. Donor-selector targets are sampled normalised regret and/or useful-candidate yield from 1,024-draw pools, not a circular energy proxy. Parent-grouped out-of-fold for any headline learned-policy result on training cases. Tuning freezes donor policy and one depth per C0/C1 **before** calibration opens.
9. Per-instance best-found variational reference is a **fixed-budget reference**, not a certified quantum optimum.
10. Local noisy diagnostic labelled `LOCAL_SYNTHETIC_NOISE`, never IBM/device noise; excluded without fabrication if the model fails validation.
11. Allocator `g(z,m,b)` uses real observable case features; training labels are independent-evaluation reduction in normalised team loss under the complete acceptance-and-fallback policy, including zeros/negatives/failures/late/stale/invalid/fallback.
12. Calibration residual uses frozen `g_hat` (not a global mean), independent paired evaluation worlds, predeclared MC allowance, and finite-sample order statistic `ceil((n+1)*0.95)` clipped to n (for n=24: the **maximum** residual).
13. Offline reference evaluates every legal plan on dedicated offline banks; never assigned from the online classical result.
14. CLI performs raw corpus, analysis, gates, report, manifest, independent verification, and package verification **in order**. `campaign_raw_complete` is not Phase 6 completion.
15. Seed hierarchy (explicit, recorded before execution):

| Loop | Count | Role |
|---|---:|---|
| `policy_seed` | 3 | outer Phase 6 stochastic arm identity `{0,1,2}` |
| `circuit_resample_seed` | 1 per policy_seed | derived `hash(policy_seed, case, family_depth)`; **not** an extra ×3 |
| mechanism resampling seeds | 30 | donor-selector / pool diagnostic only |
| Stage 7 design seeds | 10 | **not executed** in Phase 6 |

Expected operational row arithmetic (per case, after freeze) is recorded in `OPERATION_LEDGER.json` before the campaign.

## 5. What this amendment does not authorise

- Phase 7 execution.
- QPU submission, IBM credential access, or hardware mocks presented as physical data.
- Opening reserved final-test or shift outcomes.
- Weakening denominators after seeing outcome signs.
- Replacing missing observations with zeros, fixtures, expected values, or copied historical values.
- Treating admission, software repair, or local simulation as scientific novelty, F1 calibration, quantum advantage, or hardware readiness.
- Resuming `3de109c7-…`, `09806343-…`, `e85ee977-…`, `41c28597-…`, or `fcbb3e38-…`.

## 6. Machine-readable companion

Written into the new run directory **before outcomes** as `IMPLEMENTATION_RESOURCE_AMENDMENT.json`, with the same numeric ladders, ceilings, seed hierarchy, and supersession statement.

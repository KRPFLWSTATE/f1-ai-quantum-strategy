# Phase 6 validated closure report

**Authoritative run:** `fc5f0e00-d9e0-4f89-9eea-498461094969`  
**PHASE_6_STATUS / ENGINEERING:** `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`  
**SELECTED_DESIGN:** `NONE_RESOURCE_LIMIT`  
**START_COMMIT:** `dcfe1cde7f02643d7a2d258d961e7ce2b4e62461`  
**REVIEWED_SOURCE_COMMIT:** `885f1adffb3b65865dbc752c9b0ca0442eb8fd52`  
**Phase 7 started:** no. `PHASE_7_AUTHORISED=false`.

## 1. Disposition of `0b697910-e8a2-474b-bc77-bc69ebb8e9c3`

`PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`. Files under `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/` are unmodified. Expected-failure audit: `docs/evidence/phase6_validated/0B697910_EXPECTED_FAILURE.json` (copied into this run). Verifier `ok=False` with `n_pass=15/18`. Valid engineering observations (real PIDs, local timing, no QPU/final-test) remain; scientific/resource closure is not accepted.

## 2. Scalar/batched parity and speed

Parity `ok=True` cells `3072` hash `7ba095f46f131041988da06db153c36fff450a5747ff6dd0b58d7465c9a08ae8` families `['fam.green_pit_high.tyre_near_linear.traffic_dense', 'fam.green_pit_high.tyre_near_linear.traffic_sparse', 'fam.green_pit_high.tyre_nonlinear.traffic_dense', 'fam.green_pit_high.tyre_nonlinear.traffic_sparse', 'fam.green_pit_low.tyre_near_linear.traffic_dense', 'fam.green_pit_low.tyre_near_linear.traffic_sparse', 'fam.green_pit_low.tyre_nonlinear.traffic_dense', 'fam.green_pit_low.tyre_nonlinear.traffic_sparse']` regimes `['SC', 'VSC']` classes `['changed-state', 'fallback', 'fallback_continuation', 'late', 'recommendation', 'stale', 'timely']`.  
Speed rows: `[{'batched_cpu_s': 144.37753299999986, 'batched_wall_s': 146.907975209062, 'n_plans': 2, 'n_worlds': 128, 'parity_ok': True, 'rss_bytes': 118390784, 'scalar_cpu_s': 142.58147999999983, 'scalar_wall_s': 144.44794483296573, 'speedup_cpu': 0.9875600243148632, 'speedup_wall': 0.9832546165543741}, {'batched_cpu_s': 577.2071930000002, 'batched_wall_s': 588.0719086250756, 'n_plans': 2, 'n_worlds': 512, 'parity_ok': True, 'rss_bytes': 136790016, 'scalar_cpu_s': 581.7975649999998, 'scalar_wall_s': 591.6696594170062, 'speedup_cpu': 1.0079527283368412, 'speedup_wall': 1.0061178756188884}, {'batched_cpu_s': 2402.725372, 'batched_wall_s': 2464.210418707924, 'n_plans': 2, 'n_worlds': 2048, 'parity_ok': True, 'rss_bytes': 256376832, 'scalar_cpu_s': 2304.0843289999993, 'scalar_wall_s': 2343.3270510410657, 'speedup_cpu': 0.9589461849658278, 'speedup_wall': 0.9509443809063018}]`. Production kernel `{'batched_calls': 32, 'batched_worlds': 2626, 'parity_scalar_calls': 0, 'scalar_calls': 0}`. Cache `{'admission': {'bytes': 5624165, 'entries': 156, 'evictions': 0, 'hits': 0, 'keys_by_class': {'continuation': 156}, 'max_bytes': 67108864, 'max_bytes_observed': 5624165, 'misses': 156}, 'distribution': {'bytes': 896, 'entries': 7, 'evictions': 0, 'hits': 2, 'keys_by_class': {'continuation': 7}, 'max_bytes': 33554432, 'max_bytes_observed': 896, 'misses': 7}, 'kernel': {'batched_calls': 32, 'batched_worlds': 2626, 'parity_scalar_calls': 0, 'scalar_calls': 0}}`.

## 3. F/R admission arithmetic and selection

Design F fit `{'admission_wall_limit_s': 11520.0, 'campaign_cpu_cap_s': 86400.0, 'campaign_wall_cap_s': 14400.0, 'cpu_ok': False, 'disk_ok': True, 'fits': False, 'ram_ok': True, 'wall_ok': False}` projection `{'components_s': {'circuit_s': 2.3361390640959137, 'distributions': 168202.01261490578, 'evaluation_worlds': 1931289.7241600598, 'n_legal_measured': 100, 'offline': 7632.912304562827, 'per_eval_world_s': 0.5969806534829445, 'per_world_s': 0.5963212737939708, 'planning_worlds': 963197.203712783, 'prepare': 72.31433545835316}, 'conservative_multiplier': 1.253373168851195, 'parallel_wall_s': {'conservative': 1101289.124199452, 'p50': 732216.8366457463, 'p95': 1101289.124199452, 'point': 732216.8366457463}, 'serial_cpu_s': {'conservative': 3848349.666875159, 'p50': 3070394.16712777, 'p95': 3848349.666875159, 'point': 3070394.16712777}}`.  
Design R fit `{'admission_wall_limit_s': 11520.0, 'campaign_cpu_cap_s': 86400.0, 'campaign_wall_cap_s': 14400.0, 'cpu_ok': False, 'disk_ok': True, 'fits': False, 'ram_ok': True, 'wall_ok': False}` projection `{'components_s': {'circuit_s': 2.3361390640959137, 'distributions': 168202.01261490578, 'evaluation_worlds': 447873.9896238164, 'n_legal_measured': 100, 'offline': 7632.912304562827, 'per_eval_world_s': 0.5969806534829445, 'per_world_s': 0.5963212737939708, 'planning_worlds': 481865.75378705125, 'prepare': 36.15716772917658}, 'conservative_multiplier': 1.253373168851195, 'parallel_wall_s': {'conservative': 396560.54286255076, 'p50': 263662.1935628493, 'p95': 396560.54286255076, 'point': 263662.1935628493}, 'serial_cpu_s': {'conservative': 1385742.943870696, 'p50': 1105610.8254980654, 'p95': 1385742.943870696, 'point': 1105610.8254980654}}`.  
Selected `NONE_RESOURCE_LIMIT`. Admitted `False`. Limited pilot `False`.  
If neither fits, no 4/4/2 outcome-bearing substitute was run.

External compute requirement: `{'admission_wall_limit_s': 11520.0, 'aggregates_f': {'ablations': 336, 'calib_checkpoints': 48, 'calib_parents': 24, 'evaluation_worlds': 3235096, 'latency': 12, 'mechanism_resamples': 72000, 'n_budgets': 5, 'n_policy_seeds': 3, 'offline': 8, 'planning_world_evals_upper': 403808, 'policy_seeds_included_in_world_counts': True, 'train_checkpoints': 240, 'train_parents': 120, 'tune_checkpoints': 160, 'tune_parents': 80}, 'aggregates_r': {'ablations': 168, 'calib_checkpoints': 24, 'calib_parents': 24, 'evaluation_worlds': 750232, 'latency': 12, 'mechanism_resamples': 72000, 'n_budgets': 5, 'n_policy_seeds': 3, 'offline': 8, 'planning_world_evals_upper': 202016, 'policy_seeds_included_in_world_counts': True, 'train_checkpoints': 120, 'train_parents': 120, 'tune_checkpoints': 80, 'tune_parents': 80}, 'campaign_cpu_cap_s': 86400.0, 'design_f_fit_detail': {'admission_wall_limit_s': 11520.0, 'campaign_cpu_cap_s': 86400.0, 'campaign_wall_cap_s': 14400.0, 'cpu_ok': False, 'disk_ok': True, 'fits': False, 'ram_ok': True, 'wall_ok': False}, 'design_f_fits': False, 'design_r_fit_detail': {'admission_wall_limit_s': 11520.0, 'campaign_cpu_cap_s': 86400.0, 'campaign_wall_cap_s': 14400.0, 'cpu_ok': False, 'disk_ok': True, 'fits': False, 'ram_ok': True, 'wall_ok': False}, 'design_r_fits': False, 'note': 'future authorised attempt requires conservative CPU<=86400 and wall<=11520 on the enumerated F or R ledger after measured batched speedup'}`.

## 4. Full denominators and exclusions

Fresh partitions: 120/80/24 parents with `a4.v2.*` IDs, disjoint from retired diagnostic parents. Corpus train/tune/calib rows for this run: executed only if F or R admitted. Resource-limit closeout opens no registered parent outcomes.

## 5. Donor/AI model methods

Sampled 1,024-draw decoded labels (`f1q.a4.donor_labels`). Expectation is diagnostic only. Per-instance variational reference is a real local fit, not a bank lookup.

## 6. Circuit mechanism and matched-K flow

Production evaluation calls `evaluate_candidates_batched`. Scalar `_simulate_plan_world` is parity-only.

## 7. Frozen allocator and ablations

Calibration units are constructed only after hashing `TUNING_FREEZE.json`. Ablations execute real rows (`ablation_specs`). Not applicable as Gate E/F evidence when design is NONE_RESOURCE_LIMIT.

## 8. Calibration q, harm, paired effects, MC, Stage 7 sizing

Unclaimed unless 24 fresh parent maxima exist. Resource-limit: q is NA (no 24-parent calibration).

## 9. Resource use and projection accuracy

Admission wall `4488.215427499963` CPU `5210.3775319999995`. Conservative multiplier uses max(1.15, 26010/20752). Efficiency is measured, not 0.55.

## 10. Gate E/F derivations

Gate E: `{'GATE_E_SCIENTIFIC_VALUE': 'UNCLAIMED_RESOURCE_LIMIT', 'SUPERIORITY_PATH_AVAILABLE': False, 'BOUNDARY_MECHANISM_PATH_AVAILABLE': False, 'reason': 'neither Design F nor Design R admitted; Gate E unclaimed; no limited-pilot substitution'}`  
Gate F: `{'GATE_F_LOCAL_PRECISION_AND_RESOURCES': 'FAIL', 'PHASE_7_BOUNDARY_STUDY_READY': False, 'PHASE_7_OPERATIONAL_READY': False, 'PHASE_7_SUPERIORITY_READY': False, 'PHASE_7_AUTHORISED': False, 'reason': 'no 24-parent calibration corpus; F/R not admitted'}`  
`SUPERIORITY_PATH_AVAILABLE=false` (proxy headroom zero). Limited-pilot `PASS_BOUNDARY_MECHANISM` is not confirmatory.

## 11. F1 integration meaning and limits

Local simulator mechanism description only. Not F1 calibration, not hardware, not novelty-verified.

## 12. Allowed/prohibited claims

See `CLAIMS_LEDGER.json`.

## 13. Defect → fix → test → evidence

See `docs/PHASE_6_0B697910_INVALIDATION.md` and `REPAIR_TRACEABILITY.json`.

## 14. Reproduction and artifact index

`python -m f1q.a4 --verify-run fc5f0e00-d9e0-4f89-9eea-498461094969`  
Evidence: `/Users/kawinperera/f1-ai-quantum-strategy-phase6-validated/evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969`  
Prompt compliance: `21/21`.

---
Generated from `/Users/kawinperera/f1-ai-quantum-strategy-phase6-validated/evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969`. Phase 7 was not started.

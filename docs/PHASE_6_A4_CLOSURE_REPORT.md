# Phase 6 A4 closure report

**Document class:** A4 causal checkpoint candidate-generation and downstream-reranking benchmark.  
**Terminal status:** `INCOMPLETE_ENGINEERING`  
**PHASE_6_ENGINEERING:** `FAIL`  
**GATE_E_SCIENTIFIC_VALUE:** `FAIL`  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `FAIL`  
**Starting commit:** `bcc740cd71ea5b6367b9332a300bf89590656ffc`  
**Reviewed source commit:** `f3c3c88ab1e9ab2dc95458e4ab775b284aded41f`  
**Authoritative run id:** `3de109c7-30d9-4cb0-827f-dbd82c4c509d`  
**Admission decision:** `NOT_ADMITTED` (`selected_world_level=NONE`)  
**Authoritative admission wall:** 1250.1 s  
**QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **QPU_EXECUTION_AUTHORISED:** false  
**FINAL_TEST_ACCESSED:** false · **Phase 7 started:** false · **PHASE_7_AUTHORISED:** false

Evidence labels: proposed / implemented / verified by named check / simulated. Not physically measured. Not F1-calibrated. Not quantum advantage. Generated synthetic checkpoints are not historical race validation. Calibration diagnostics were not produced because the corpus was not started.

---

## 0. Executive verdict

Phase 6 A4 **source repair, tests, and measured admission completed**. The registered 120/80/24 corpus **was not started**. Conservative projected wall time for every predeclared world-count ladder exceeds the 60-minute admission limit (20% reserve of the 75-minute ceiling). Terminal status is therefore **`INCOMPLETE_ENGINEERING`**, not `CLOSED_NOT_READY_FOR_PHASE7` and not a scientific negative result on quantum candidates.

A3 run `a5fdb488-9a90-47f9-a4f5-7f77a74180a6` remains an **unsuccessful implementation attempt**. Its effect, offline-headroom, dispatcher, Gate E, and Gate F numbers stay **superseded and are not scientific evidence**. Prior failed A4 run `09806343-f940-4f33-9e0f-eb2855d0714b` is **preserved, not resumed**.

| Gate / flag | Result |
| --- | --- |
| PHASE_6_STATUS | `INCOMPLETE_ENGINEERING` |
| PHASE_6_ENGINEERING | `FAIL` |
| GATE_E_SCIENTIFIC_VALUE | `FAIL` |
| GATE_F_LOCAL_PRECISION_AND_RESOURCES | `FAIL` |
| OPERATIONAL_DOWNSTREAM_HEADROOM | `ZERO` (inherited proxy; corpus unrun) |
| PHASE_7_BOUNDARY_STUDY_READY | false |
| PHASE_7_OPERATIONAL_READY | false |
| PHASE_7_SUPERIORITY_READY | false |
| PHASE_7_AUTHORISED | false |
| SUPERIORITY_PATH_AVAILABLE | false |
| PROXY_HEADROOM | ZERO |
| Independent verifier (final, admission-only required set) | 18/18 PASS |

---

## 1. Authority, start commit, reviewed source, evidence-tree identity

Repository: `KRPFLWSTATE/f1-ai-quantum-strategy`. Dossier v3.1 (`docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf`, sha256 `2c6fd0851d12a281bb7f7bad7d4cc522f4606a3c3df32c43cad1ca9146b83b76`, 33 pages).

This closure is bound to:

- start commit `bcc740cd71ea5b6367b9332a300bf89590656ffc`
- reviewed source commit `f3c3c88ab1e9ab2dc95458e4ab775b284aded41f` (pushed to `origin/main` before admission)
- run directory `evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/`
- review mirror `docs/evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/`

The evidence-tree identity is the run UUID plus `MANIFEST.json` inventory hash written after this report. `FINAL_EVIDENCE_COMMIT` is resolved only after the evidence commit exists and is printed in the Cursor receipt; it is not self-referenced inside this file.

Config hash (`configs/stage6_a4_closure.yaml`): `20593ae250ba7c8dceeb8bfb0152fc6ae14a578cf25a615dafb54165d55ce460`.

---

## 2. Dossier scope: why this is Phase 6 rather than Stage 7

The dossier defines Stage 6 as the local pilot, calibration, precision, and resource-estimation stage. Stage 7 is the full local study and confirmatory primary analysis. This attempt implemented the A4 amendment and measured whether the registered development partitions could fit the 75-minute ceiling. They did not. No Stage 7 campaign, final-test opening, or QPU path was authorised or executed.

---

## 3. Defect-to-fix-to-test traceability

All 29 listed `bcc740c` defects were confirmed in live source and recorded in `REPAIR_TRACEABILITY.json` (`n_items=29`, `all_confirmed=true`). Summary:

| IDs | Area | Repair |
| --- | --- | --- |
| 1–6 | data/model | Donor-bank v2 + `DonorRanker` distinct from allocator `RidgeModel`; all four family/depths; zero-utility labels retained; `g(z,m,b)` option/budget features; tuning compares real policies |
| 7–13 | causal/deadline/cache | Scientific split identity in `namespace`/`PreparedCase.split`; remaining duration distinct from absolute end; spec budget written into the simulator; uncapped full precommit arrival; complete cache keys |
| 14–20 | treatment | One `PreparedCase` per case; `family_depth` executed; three quantum seed receipts; matched K with fallback+incumbent; `found_by` merge; offline helper evaluates every legal plan |
| 21–29 | runtime/verify/report | Measured admission (no new anchors); fail-fast structural errors; verifier hashes every manifest entry and recomputes `q` when present; no `/tmp` receipts; Gate E/F not inferred from `legal_plan_count>K` |

Focused development tests: **52 collected / 52 passed / 0 failed / 0 skipped**. Authoritative run-local focused: same 52/52. Full suite: **238 passed, 1 skipped** (`tests/formulation/test_gate_c.py` archived Stage 4 resume smoke, documented skip).

---

## 4. Immutable historical lineage and reuse hashes

Historical directories under `evidence/stage5/`, `evidence/stage6/bd83cb22-…`, `evidence/stage6_corrected/2a3fb275-…`, `evidence/stage6_a2_residual/e437fa3d-…`, `evidence/a3/a5fdb488-…`, and `evidence/stage6_a4/09806343-…` were not overwritten.

| Artifact | Required SHA-256 | Reuse |
| --- | --- | --- |
| prior `MANIFEST.json` | `8f620c8fc9048cf27c304847efe7fa79a3eb00aac2f7af6a7b5f0c97db0be70e` | verified |
| `ANCHOR_FITS.jsonl` | `b4d3f84212e674a3bcdb8dbf06cb4baf62d773b6dbd75728d916107484e2e27a` | 288/288 starts, 24 anchors, not refit |
| `NATIVE_NOISE_CORRECTION.json` | `5daa9944fe0bbc0e8c837d5002bf0e0bb271db559901480501d1fd57b3adb84d` | copied; synthetic not IBM |
| `A3_INVALIDATION.json` | `4b9743aea6273eee511133b12e0fde130103aae10c5ec1002484f9a642cd277d` | pinned copied bytes |
| `PARTITIONS.json` | `31f4b985b15face11752de1094282441d837acd362941c0e2c66e2686602c9f5` | 24/120/80/24; final-test IDs/hash only |
| `PROTOCOL_AMENDMENT_A4.json` | `7ee7d9af1e7371c193c32eb4a03751127ed9c7004e6d391957c0e508b5aca9c3` | A4 checkpoint question |

Live A3 defect inspection was written to `A3_INVALIDATION_LIVE.json`; all eleven constructions remain confirmed.

---

## 5. Corrected causal / action / deadline semantics

Implemented and unit-tested: full current-info action menu (continue / pit_now / delay 1–2); `effective_remaining_s = max(0, effective_end_race_s - decision_time_race_s)`; five-budget spec field `primary_nominal_budget_s`; uncapped precommit latency as `arrival_delay_s`; late recommendations remain late. ScenarioSpec.partition stays the Stage-2 legal fixture `development`; train/tune/calib/anchor identity is `namespace=a4.{split}` and `PreparedCase.split`. Final-test/test/shift materialisation raises.

Admission probes exercised budgets `[5, 10, 30, 60, 120]` on four real prepared cases. Median measured pair wall: **13.872 s**. Median precommit on those rows is about 4.6–6.6 s (local monotonic; not provider latency).

---

## 6. Split and child-row denominators

| Split | Planned parents | Completed | Requirement |
| --- | ---: | ---: | --- |
| Reused anchors | 24 | 24 verified / 288 starts | no refit |
| Training | 120 | 0 | NOT_PRODUCED (admission failed) |
| Tuning | 80 | 0 | NOT_PRODUCED |
| Calibration | 24 | 0 | NOT_PRODUCED |
| Final test | 80 IDs/hash only | 0 executed | unopened |

---

## 7. Donor-bank and donor-selector methods/results

`DONOR_BANK_V2.json` rebuilt from pinned anchors: four keys `C0_p1/C0_p2/C1_p1/C1_p2`, 8 donors × 8 families = **32/32**. Coverage-aware one-best-per-family, not global-eight.

`DONOR_SELECTOR_TRAINING.jsonl`, `DONOR_SELECTOR_TUNING.jsonl`, `DONOR_SELECTOR_MODELS.json`: **NOT_PRODUCED** (corpus not started). DonorRanker vs RidgeModel separation is implemented and tested.

---

## 8. Allocator training / tuning / calibration-q

Option set `stop/fallback, classical_only, C0_p1, C0_p2, C1_p1, C1_p2`. Regularisation grid `[0.1, 1.0, 10.0]` is in config. Training labels, tuning selection, and calibration `q` were **not computed on the corpus**. `CALIBRATION_MARGIN_Q.json`: **NOT_PRODUCED**.

---

## 9. Classical comparator and matched-K fairness

K=4 implemented: mandatory fallback + strongest classical incumbent protected; quantum fills residual slots only; duplicate hashes merge `found_by`. Tests prove K unique hashes where legal count permits. Corpus matched-K counts: **NOT_PRODUCED**.

---

## 10. Circuit/depth mechanism coverage

Software executes C0p1, C0p2, C1p1, C1p2 (tested). Training/tuning corpus coverage: **NOT_PRODUCED**.

---

## 11. Stochastic-seed and pool accounting

`assemble_portfolio` records three quantum `seed_receipts` when `n_stochastic_seeds=3` (tested). Tune/calib corpus seed accounting: **NOT_PRODUCED**. Config pool draws: 1024 local simulated samples, not QPU shots.

---

## 12. Planning / evaluation / offline bank design

Disjoint banks `planning_bank`, `evaluation_bank`, `offline_planning_bank`, `offline_evaluation_bank`. Evaluation payloads rejected from planning helpers (tested). Complete cache keys include budget, arrival, commitment epoch, simulator/interface/evaluator versions. Corpus world outcomes: **NOT_PRODUCED**.

---

## 13. Offline all-plan results

`evaluate_offline_reference` evaluates every legal joint plan on a dedicated offline planning bank and scores only the selected plan on a disjoint offline evaluation bank (`copied_from_arm=False`; tested). Eight-case corpus offline: **NOT_PRODUCED**.

---

## 14. Descriptive calibration effects, harm, uncertainty

**NOT_PRODUCED.** Calibration was never opened. Do not treat missing values as zeros.

---

## 15. Isolated operational latency versus campaign resources

Admission measured 20 real classical+hybrid pair timings across four families/regimes and five budgets. Median pair wall 13.872 s; admission-measure wall 284.3 s after tests. Worker rule: `min(cpu_safe=cpus-2, memory_safe=60%RAM/512MiB, 8)` → **8 workers** on 10 logical CPUs / 25.8 GiB RAM. Isolated six-case-by-two-arm `OPERATIONAL_LATENCY.jsonl` panel: **NOT_PRODUCED** (reserved for an admitted campaign). These are local measurements, not IBM/cloud latency.

Conservative projected authoritative wall (seconds):

| Level | serial_s | parallel_s | conservative_s | fits ≤3600 s |
| --- | ---: | ---: | ---: | --- |
| preferred | 157784.5 | 35860.1 | 48411.2 | false |
| baseline | 143973.8 | 32721.3 | 44173.8 | false |
| minimum | 86141.3 | 19577.6 | 26429.7 | false |

Minimum conservative projection is **7.34 hours**, above the 60-minute admission cap.

---

## 16. Precision and Stage 7 sizing

**NOT_PRODUCED.** No 24-parent calibration residuals, no `q`, no Stage 7 block/world sizing from this run. `STAGE7_RECOMMENDED_BLOCKS=NA`. `STAGE7_WORLD_TARGET_FEASIBILITY=NA`. Hardware budget: `NOT_EVALUATED_NOT_AUTHORISED`.

---

## 17. Per-family boundary table and F1 usefulness limits

**NOT_PRODUCED.** Proxy headroom remains ZERO from the accepted A2/Stage 4 lineage. No F1 team-performance claim is permitted.

---

## 18. Gate E / F / readiness derivation

- **Engineering FAIL** because the 120/80/24 parents, eight offline cases, calibration `q`, and full scientific verifier set were not produced.
- **Gate E FAIL** because no experimental matched-K quantum-incremental-at-K corpus exists to support `PASS_BOUNDARY_MECHANISM`. Implementation tests are not Gate E evidence.
- **Gate F FAIL** because 24 calibration parents, `q`, MC uncertainty, Stage 7 sizing, and campaign resource evidence from the corpus do not exist.
- All Phase 7 readiness flags false. `PHASE_7_AUTHORISED` remains false.

---

## 19. Tests, verifier, hashes, reproducibility

Development (pre-commit): doctor PASS; `pip check` PASS; focused 52/52; full 238 passed + 1 skipped.

Authoritative admission reruns (same reviewed commit, into this run):

- focused: 52 passed, 0 failed, 0 skipped, exit 0; junit sha256 `065e1daad3b0c6fbbbc8190f0621ff2a6d46babde32aa578fe2c9b14f28f22bd`
- full: 238 passed, 1 skipped, 0 failed, exit 0; junit sha256 `0d76e8e3dbb2e9aec28750631c4080c8ea54cd83727f7d0bb6046ba4d66fa041`
- doctor/status/pip: all exit 0

Independent verifier: PRE_REPORT_VERIFY 17/17; final admission-only set 18/18 including every manifest entry hash. Commands:

```text
python -u -m f1q.a4 --admission-check --config configs/stage6_a4_closure.yaml
python -u -m f1q.a4 --execute-phase6 --config configs/stage6_a4_closure.yaml --run-id 3de109c7-30d9-4cb0-827f-dbd82c4c509d
```

The execute command was **not invoked** (`ADMISSION_RECEIPT.admitted=false`; execute refuses a failed admission).

---

## 20. Failures, exclusions, deviations, unresolved limitations

1. **Pre-start diagnostic (not a scientific run):** dirty worktree at `bcc740c` was Stage 4 residue for `41c28597-…` and `fcbb3e38-…`. Class `PRESTART_DIAGNOSTIC_ONLY`. Named stash `03dc2e1f6d0004e9e4081f18b585398606e491d9`; sibling basename `f1q-prephase6-quarantine-20260921T195640Z`; recovery patch sha256 `36202cab32e20538cdd49441d2824ff2dddbaaeac21365cdb315f261e36bfc62`. Not Phase 6 input.
2. **Stale Gate C writer PID 94709** (`python -m f1q run --plan formulation_gate_c_closure_check`, PPID 1, cwd=repo) held the ledger lock; SIGTERM only; exited within 10 s; flushed three `fcbb3e38` records plus a `docs/evidence/stage4_2` diagnostic, stashed (`497b23158f6d16599c5231408c88fabdea0e5387`). Not Phase 6 input. That forbidden plan was not resumed.
3. **Admission NOT_ADMITTED:** no ladder ≤ 3600 s after 20% reserve. Corpus not started. Empty scientific JSONLs were not fabricated.
4. Projection uses measured pair wall × registered case/option/seed counts with a 0.55 parallel efficiency and 1.35 p95 multiplier. Shared-case caching in a real campaign might be faster; the measured non-admission still forbids starting a knowingly incomplete corpus.
5. Ledger still lists historical `fcbb3e38-…` as `running` because the process was terminated, not scientifically completed. Do not resume it.
6. `NOVELTY_STATUS` remains `PROPOSED_NOT_LITERATURE_VERIFIED`.

Scientific exclusions enum (`CLOSED_DECISION_WINDOW`, `NO_LEGAL_NONFALLBACK_ACTION`): unused; corpus unrun.

---

## 21. Claims allowed / prohibited

Allowed: software repair implemented; named pytest/doctor/pip/admission checks; simulated admission-probe losses on synthetic checkpoints; honest non-admission.

Prohibited: quantum advantage; literature-first/novelty; physically measured IBM noise; F1 team performance; Phase 7 execution; treating calibration as primary; converting missing corpus rows to zero; calling this a completed negative scientific Phase 6 result.

---

## 22. Lineage note on the blocked recovery prompt

The previous Phase 6 recovery prompt stopped at a nonempty `git status --porcelain` at `bcc740c`. That receipt was a **pre-start worktree diagnostic**, not an authoritative Phase 6 run. This file's run UUID is the single authoritative admission identifier. Quarantined Stage 4 files were not used as Phase 6 input.

---

## 23. Evidence-path index

- Evidence: `evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/`
- Review mirror (small artifacts): `docs/evidence/stage6_a4/3de109c7-30d9-4cb0-827f-dbd82c4c509d/`
- Prior failed A4 (immutable): `evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/`
- Repair table: `REPAIR_TRACEABILITY.json`
- Reuse: `REUSED_EVIDENCE.json`
- Admission: `ADMISSION_RECEIPT.json`, `START_STATE.json`, `PRESTART_QUARANTINE.json`
- Tests: `tests/focused.xml`, `tests/full.xml`, `tests/focused_receipt.json`, `tests/full_receipt.json`
- Unproduced scientific files: `NOT_PRODUCED.json`
- Verifier: `PRE_REPORT_VERIFY.json`, `FINAL_VERIFY.json`, `FINAL_PACKAGE_VERIFY.json`
- Manifest: `MANIFEST.json` (excludes itself, `FINAL_VERIFY.json`, `FINAL_PACKAGE_VERIFY.json`)

Next authorised stage: **NONE — await user review**. Do not start Phase 7. Do not open final-test. Do not submit QPU jobs.

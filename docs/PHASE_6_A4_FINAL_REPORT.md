# Phase 6 A4 final report — scientific supersession and closure

**Document class:** A4 causal checkpoint candidate-generation and downstream-reranking benchmark.  
**Starting commit:** `be9e11e3ca0e92d4579f060071e07b44e0932bae`  
**Reviewed source commit:** `8cc52607a6fabfe35ae9d4d681f8792c39a51176`  
**Authoritative run id:** `09806343-f940-4f33-9e0f-eb2855d0714b`  
**Elapsed wall / CPU:** 4513.297090625041 s / 4506.20293 s  
**QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **QPU_EXECUTION_AUTHORISED:** false  
**FINAL_TEST_ACCESSED:** false · **Phase 7 started:** false

Evidence labels: proposed / implemented / verified by named check / simulated. Not physically measured. Not F1-calibrated. Not quantum advantage. Generated synthetic checkpoints are not historical race validation.

---

## 0. Executive verdict

A3 run `a5fdb488-9a90-47f9-a4f5-7f77a74180a6` is an **unsuccessful implementation attempt**. Its effect, offline-headroom, dispatcher, Gate E, and Gate F numbers are **superseded and are not scientific evidence**. Independently confirmed A3 defects: `True`.

A4 **software** implements a checkpoint candidate-generation / downstream-reranking experiment (complete executable action menu, matched K=4, disjoint planning/evaluation banks, fitted donors on all 24 anchors, independent verifier). The **authoritative campaign did not produce a scientific A4 effect**. Measured preflight showed the 75-minute minima cannot process every required block (`minima_fit: false`); calibration and offline finite-simulation references were **not opened**. All 120 training parent blocks were attempted, but every hybrid training case failed (`error: "0"`, KeyError on `donors[0]` because `DONOR_BANK[family]` is a dict `{"selected":[...]}` rather than a list). Tuning completed 47/80 parent blocks, all dispatched `classical_only`. Primary estimand is therefore **NA**. This prompt forbids a repair-and-rerun cycle. Gates E and F are **FAIL**.

| Gate | Result |
| --- | --- |
| GATE_E_SCIENTIFIC_VALUE | `FAIL` |
| GATE_F_PRECISION_AND_RESOURCES | `FAIL` |
| OPERATIONAL_DOWNSTREAM_HEADROOM | `ZERO_OR_UNMEASURED_ON_OFFLINE_SUBSET` |
| PHASE_7_BOUNDARY_STUDY_READY | `False` |
| PHASE_7_OPERATIONAL_READY | `False` |
| PHASE_7_SUPERIORITY_READY | `False` |

Primary paired parent-block mean difference (classical_only − dispatched) at 30 s: **None**. Interval: stratified block bootstrap n_boot=2000 seed=20260921 bounds={}. Positive would favour A4; a valid negative or zero is acceptable if treatments actually differ.

Independent verifier: 29/34 ok=False.

---

## 1. Inherited accepted work (not reopened)

Phases 1–4 remain closed (`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`; legacy Gate C `PARTIAL` / `ARCHIVED_DO_NOT_RESUME`). Frozen Phase 5 evidence under `evidence/stage5/` was not altered. Historical Phase 6 `bd83cb22-…` and corrected `2a3fb275-…` were not overwritten. A2 residual `e437fa3d-…` is preserved; its 192-pool histogram run is a **balanced method-validation subset**, not a full empirical supersession of all historical pools. A3 artifacts under `evidence/a3/a5fdb488-…` are preserved byte-for-byte as an unsuccessful attempt. A3 causal-interface smoke checks remain valid only where independently reconfirmed.

---

## 2. A3 invalidation table

Source confirmation (`inspect_a3_defects` on live A3 modules):

| Defect | Confirmed |
| --- | --- |
| `decide_from_observation` executes `downstream_candidates[0]` | True |
| Hybrid portfolio appends quantum up to `2*equal_k` | True |
| Offline loss copied from classical mean | True |
| Later info-set not executed | True |
| Two-action menu `acts[:2]` | True |
| No anchor optimisation loop | True |
| Hard-coded 45-minute reduction | True |
| Ridge labels from hybrid that shares classical-first execution | True |
| Random `default_params` | True |
| Per-world losses not written for primary | True |
| Verifier internal consistency only | True |

A3 report claimed “16 passed before campaign” for targeted tests; `tests/a3/test_a3_core.py` has 3 tests and `tests/stage6/test_residual_histograms_noise.py` has 5 (8 pytest cases). The “16/16” figure is the A3 **artifact verifier** check count, not pytest. Those A3 effect numbers remain non-scientific.

See `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`.

---

## 3. A2 noise convention correction

One dimension-independent mixture is used for logical and native panels:

`E_p(rho) = (1-p) rho + p I/d`, `d=2**n`. Identity probability `1-p*(d**2-1)/d**2`; each non-identity Pauli `p/d**2`. `p=1` → `I/2` (1q) and `I/4` (2q). Synthetic; **not** IBM-calibrated.

Native panel status: `COMPLETED`; analytical `True`. Historical 2q `p=1` closed form `(4I-ρ)/15` is superseded. Old outputs preserved; this A4 tree holds the replacement panel.

192-pool label: evidence/stage6_a2_residual/e437fa3d-c29c-43c3-9a55-708c1b36f5e6 192-pool histogram run is a balanced method-validation subset (8 families × 1 parent × SC/VSC × {C0_p1,C1_p1} × {learned,fixed} × 3 seeds), not a full empirical supersession of all historical pools.

---

## 4. A4 causal architecture

A4 is a **static checkpoint benchmark**: one observable decision, legal current actions only, downstream simulation reranking, then independent evaluation. It is not a multi-epoch policy. No encoded variable is omitted from the executed `RaceSimulator` plan.

Scientific question (frozen): A4_checkpoint_candidate_generation_downstream_reranking — Under the same observable checkpoint, deadline and downstream simulation-evaluation budget, can an AI-gated portfolio containing C0 or C1 quantum-generated legal candidates improve independent simulated team loss over the strongest tuning-selected classical portfolio?

Quantum proxy superiority is unavailable when exact enumeration already finds the proxy optimum. The only admissible contribution is useful alternative-candidate generation under proxy/evaluator mismatch and a finite downstream budget K.

---

## 5. F1 action semantics

Per selected car, legal choices are constructed from the causal observation and inventory:

- `continue`
- `pit_now` for each distinct unused compound (lex-first equivalent set_id)
- `delay_laps=1` and `delay_laps=2` for each distinct unused compound when remaining laps permit

In-pit cars admit continuation only. Expired `pit_now` is not relabelled as next lap. Double stacking is a delay cost, not a prohibition. Every encoded action round-trips through decode → `validate_plan` → `consider_recommendation`.

Calibration menu sizes (first 8 rows): []

---

## 6. Exact / QUBO / MILP

For each development instance the campaign builds the QUBO and an independent linearised MILP. Training/calibration records `legal_plan_count`. Direct/QUBO agreement is required in `verify_direct_qubo_milp` before an arm proceeds (`direct_cost_qubo_ok` on decision records). Enumeration of legal joint plans is deadline-feasible on this menu (product of per-car actions, typically tens to low hundreds).

---

## 7. Splits and actual counts

Salt `a4.partitions.v1.20260921`. Planned: {'anchors': 24, 'calibration': 24, 'final_test_registered': 80, 'training': 120, 'tuning': 80}. Final-test: n=80 materialised=False opened=False id_sha256=0bab82d65403c1355611a7923b568d9d7798f79160211aad18a14b5d92675054.

| Split | Planned | Attempted parent blocks | Successful treatment rows |
| --- | ---: | ---: | ---: |
| Anchors | 24 | 24 | 288 starts (C0/C1 × p=1/2 × 3; max_evals=15) |
| Training | 120 | 120 | 0 (all hybrid case rows failed; receipt `n_train_fail=240`) |
| Tuning | 80 | 47 | 119 JSONL rows, all `choice=classical_only` |
| Calibration | 24 | 0 | 0 (stop-before-calibration) |
| Final-test | 80 | 0 | 0 (IDs/hash only; sealed) |

Receipt `n_train_blocks=120` counts failed JSONL block IDs; it is **not** successful hybrid execution. Training JSONL unique failed errors: `{"0"}` (KeyError 0). Tune JSONL rows: 119. Calib case rows: 0. Anchor fit rows: 288. Offline JSONL rows: 0.

Worlds (frozen from preflight, 20% headroom reserved): {'calibration': {'evaluation': 16, 'planning': 8}, 'training': {'evaluation': 4, 'planning': 2}, 'tuning': {'evaluation': 8, 'planning': 4}}. Max optimiser evaluations per start (uniformly reduced if required): 15. Arithmetic: median_case=13.424s at 2-plan/4-eval; scale by (4*n_plan+n_eval)/12; usable=0.8*4500s; anchors=288 starts * 15 evals * avg(c0,c1). Minima fit: False.

---

## 8. Parameter training, donor selector, allocator

All 24 registered anchors were executed for C0/C1 × p=1/p=2 × 3 starts (288 starts, uniformly reduced to 15 objective evaluations per start from measured `t_c0≈0.569s`, `t_c1≈0.012s`). Donors were written to `DONOR_BANK.json` as `{C0_p1,C0_p2,C1_p1,C1_p2} → {selected, n_selected, n_successful_starts}`. That dict-of-records shape was passed into `select_donor(..., donors=donor_bank[key])`, which indexes `donors[0]`. Training hybrid (`always_c1`, `donor_policy=learned`) therefore raised `KeyError(0)` on every case. No genuine treatment-difference labels were collected. The ridge allocator was fit on a 2-row intercept-only fallback (`note` in `ALLOCATOR_MODEL.json` if present: no genuine labels). Tuning then dispatched `classical_only` on every completed row. Conservative residual was not applied to calibration because calibration was not opened.

---

## 9. Classical / quantum portfolios

K = 4 unique downstream slots including mandatory continuation fallback. Hybrid **replaces** classical slots with quantum-origin candidates; it does not append a second budget. Planning-bank mean loss with lex plan-hash ties selects the winner; candidate array order cannot win.

Classical generators: exact proxy ranking, greedy+local, simulated annealing, uniform legal sampling, deterministic diversity, mandatory fallback. Quantum: C0/C1 at p=1 and p=2 with fitted donors (not per-instance random default angles).

Calibration: classical vs dispatched plan difference cases 0/0; quantum-origin selected 0/0.

---

## 10. Real offline references

Offline JSONL rows: **0**. The offline finite-simulation reference was **not evaluated**. Protocol required stopping before calibration when minima cannot fit; offline uses calibration blocks and was therefore skipped. `OFFLINE_REFERENCE_ACTUALLY_EVALUATED: false`. This is not an A3-style copy of an arm loss; it is an unrun reference.

---

## 11. Main and mechanism results

Primary mean difference: **None**. Parent blocks: 0. Positive blocks: 0. Negative blocks: 0. Bootstrap: {'status': 'EMPTY'}.

Mechanism (exploratory): {'always_c0_vs_classical': None, 'always_c1_vs_classical': None, 'exploratory': True}

Minimum worthwhile effect 0.02 with sensitivity 0.01 and 0.05 (frozen). Do not interpret zero variance from identical plans as precision.

---

## 12. Deadline / latency

Nominal budgets 5, 10, 30, 60, 120 s with 30 s primary. Effective deadline is the earlier of the nominal budget and pit-entry cutoff minus communication margin, via `consider_recommendation`. Local measured generation times are in calibration `generation_s`. Inserted scenario latency is simulator clock, **not** IBM/cloud latency.

Resource accounting: {'cpu_s': 4506.20293, 'elapsed_s': 4513.297090625041, 'preflight': {'arithmetic': 'median_case=13.424s at 2-plan/4-eval; scale by (4*n_plan+n_eval)/12; usable=0.8*4500s; anchors=288 starts * 15 evals * avg(c0,c1)', 'frozen_max_evals': 15, 'frozen_worlds': {'calibration': {'evaluation': 16, 'planning': 8}, 'training': {'evaluation': 4, 'planning': 2}, 'tuning': {'evaluation': 8, 'planning': 4}}, 'median_case_s': 13.423619124980178}, 'qpu_jobs': 0, 'qpu_usage_seconds': 0}

---

## 13. Precision and Phase 7 projection

{'bootstrap': {'status': 'EMPTY'}, 'do_not_use_zero_variance_from_identical_plans_as_precision': True, 'n_calib_parent_blocks': 0, 'phase7_not_sized_as_authorised': True, 'worlds': {'calibration': {'evaluation': 16, 'planning': 8}, 'training': {'evaluation': 4, 'planning': 2}, 'tuning': {'evaluation': 8, 'planning': 4}}}

Phase 7 is **not authorised** by this prompt. `PHASE_7_BOUNDARY_STUDY_READY` remains false until Gates E and F both pass **and** an explicit later prompt authorises Phase 7. `PHASE_7_SUPERIORITY_READY` is false (no admissible superiority estimand is claimed).

---

## 14. Novelty boundary

A4 is implemented local methodology for checkpoint candidate generation under a finite reranking budget. It does **not** establish literature-first status, quantum advantage, or F1 team improvement. Novelty comparison remains `PROPOSED_NOT_LITERATURE_VERIFIED`.

---

## 15. Failures / deviations

- A3 scientific results superseded as invalid implementation.
- **Gate F FAIL:** measured preflight `minima_fit=false` (median case 13.424 s at 2-plan/4-eval; minima projection 10954 s vs remain-after-anchors 2291 s). Stop-before-calibration executed. Tuning hit the 75-minute ceiling at 47/80 parent blocks (`+4513 s`).
- **Training hybrid arm failed on every case:** `TRAINING_RESULTS.jsonl` error `"0"` = `KeyError(0)` from `select_donor` on a donor-bank dict. Receipt `n_train_fail=240`, `n_train_case_rows=0`. No repair/rerun in this prompt.
- **No calibration outcomes, no paired primary effect, no offline finite-simulation scores.**
- Independent verifier 29/34 FAIL: `tune_parent_count` 47≠80; `calib_parent_count` 0≠24; `matched_k_on_calib` empty; `offline_actually_evaluated` false; `offline_not_copied_from_arm` false (empty file).
- Verifier `train_parent_count` PASS is bookkeeping on failed JSONL block IDs, not successful treatment execution.
- Native 2q convention change: historical A2 residual panel used a different 2q `p` meaning; A4 panel uses I/4 at p=1. Analytical fixtures and Kraus vs closed form passed.
- Traffic density is a spec family factor; service duration is deterministic from pit parts and crew wait — not independently jittered per world. Regime duration **is** varied by event-keyed CRN.
- C1 is simulated in the one-hot legal subspace (mixer-invariant, equivalent C1). C0 uses full 2^n.
- Full pytest: 1 skip, `tests/formulation/test_gate_c.py:519` (`F1Q_STAGE4_RESUME_SMOKE=1`); noncritical; must not resume archived legacy Gate C runs.

---

## 16. Claims allowed / prohibited

{'labels': 'proposed/implemented/verified_by_named_check/simulated', 'no_first_claim': True, 'no_quantum_advantage': True, 'no_real_team_performance': True, 'synthetic_checkpoints_not_historical': True}

Allowed: software implemented; named checks; simulated losses on synthetic checkpoints.  
Prohibited: quantum advantage; first/novel without literature work; physically measured IBM noise; F1 team performance; Phase 7 execution.

---

## 17. Evidence paths

- Evidence: `evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/`
- Review mirror: `docs/evidence/stage6_a4/09806343-f940-4f33-9e0f-eb2855d0714b/`
- Manifest inventory sha256: e914c91b3fb821f911fd7e50e63e3599b4acc646cc8a1a66afc9f86019682c3a

QPU/final-test statements are verified from executable boundaries (`f1q.a4.qpu_guard`, sealed partitions), not merely JSON flags.

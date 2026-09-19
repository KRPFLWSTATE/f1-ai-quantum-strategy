# Stage 4.1 report — formulation semantics, evaluator, evidence, and packaging repair

Evidence from the local ledger, named artifacts, and pytest. Chat recollection is not evidence. Claims are labeled. Stage 4 Gate C PASS is **superseded**. Gate C (formulation agreement) here is a software/evidence gate only. It does **not** establish quantum advantage, F1 calibration, circuit novelty, or publication results.

Prior Stage 4 run `e8b87881-74a6-46c7-b48e-6b2496a5d586` and failed run `1c5b0748-5406-4933-8e41-4f943f4296c7` are preserved unchanged. New evidence uses run `c4d0a199-9cea-4214-83ab-97964f2bf1ac`.

```text
STAGE_4_1_STATUS: COMPLETE
STARTING_HEAD_AND_TREE: HEAD 0b69a415f230a8ccca4b82ecb74faef74908f3b0 dirty=false at Stage 4.1 start; doctor ok; diagnostic-stage3-3 --verify match=true; pytest 108 passed + 1 skipped (baseline); hardware_execution_enabled false; scientific_protocol DRAFT; package 0.4.0
ENDING_HEAD_LOCAL_COMMIT_AND_TREE: HEAD d184027228c54a9210b9df0a192e2a5f48e9f264 dirty=false after authorized Stage 4.1 commit (review ZIP/sidecars intentionally untracked); not pushed
PRIOR_STAGE_4_EVIDENCE_PRESERVED: true — e8b87881-74a6-46c7-b48e-6b2496a5d586 and 1c5b0748-5406-4933-8e41-4f943f4296c7 untouched; Stage 4 Gate C PASS claim superseded
PRE_REPAIR_REPRODUCTION: docs/evidence/stage4_1/pre_repair_reproduction.json — R1 unmet 28 eps / 56 cars / 13 on-track-10 (match); three invalid optima legal=true with terminal unmet; R3 3535/1492/2043 with cap>36; R4 hardcoded 0.95; R5 age-blind key; R6 adjacent half-service; R7 terminal legality missing + label-order panel; R8 eval undercount + MILP value-only; R9 receipt Stage-2 text; R10 clean-extract zip 732606bc… ≠ final 30fbcf9e…; all_stated_reproductions_matched=true
ROOT_CAUSES_AND_VERSIONED_FIXES: one-stop language rejects same-compound-while-unmet; continuation re-invokes compound_obligation.v1@1.1.0 after one-shot; public pit_entry_frac; age-aware reduction; service-interval overlap pair term; terminal evaluator legality; uncapped cross-check; tie-aware panel; heuristic/MILP accounting; stage-aware receipts; packaging sidecars. Versions: action/compiler/qubo/classical/formulation 1.1.0; simulator 1.0.3; interface 3.0.1; package 0.4.1
DOWNSTREAM_POLICY_SEMANTICS: compound_obligation.v1@1.1.0 — one solver-visible stop; same-compound while unmet rejected; continuation = immediate alternate pit when unmet; post-one-shot stores continuation then reinvokes; in-pit continuation preserves commitment; apply_plan clears stale on-track pending atomically
HISTORICAL_INVALID_CASES_CORRECTED: 0003/03/SC, 0005/07/VSC, 0007/06/VSC — prior soft same-compound optima no longer admitted as proxy optima under repaired menus; new optima pass evaluator semantic_legal (verified by formulation_repair_check matrix + tests)
PUBLIC_GEOMETRY_AND_ACTION_REDUCTION: pit_entry_frac sourced from simulator track config into PublicPhysicsConfig; reduction kind_delay_compound_age_lex_set.v1 with member maps; different ages not merged (tested)
PAIR_INTERACTION_DERIVATION: wait=max(0, earlier_arrival+service_stationary_s−later_arrival) from predicted box arrivals; zero when arrival unknown or no overlap; arbitrary adjacent-lap half-service deleted
COMPLETE_PAIR_CROSS_CHECK: expected/checked/failed = 3361/3361/0 (regenerated total; was 3535 under Stage 4 menus; hidden_cap=false; validate+round-trip+analytical/sim semantic)
EVALUATOR_TERMINAL_LEGALITY: checkpoint_instruction_valid, execution_success, instructed_vs_executed, terminal_obligation_satisfied, semantic_legal/legal with reason_codes; legal≡semantic_legal
TIE_AWARE_PANEL: 8 cases; dedup identical joint IDs; Kendall tau-b / pairwise ties; n_agree=3, n_disagree_reversal=1, several single-plan cases after exact=greedy dedup (no label-order artifact as scientific ranking)
QUBO_ISING_AND_PENALTY_REVALIDATION: regenerated under repaired costs; Gate unit ok=true; conventions preserved (upper+diag); numerical Stage 4 goldens not reused
ENUMERATION_MILP_DP_AGREEMENT: 64/64 MILP agrees including selected pair ∈ enumeration minimizer set; DP exact only when pair≡0
HEURISTIC_AND_TIMING_ACCOUNTING: uniform=1+n_samples; annealing=1+steps; greedy counts direct scorer calls; compile_s vs scan_s vs milp_s separated
DEVELOPMENT_MATRIX: planned/completed/failed = 64/64/0; development only; run c4d0a199-9cea-4214-83ab-97964f2bf1ac
PROXY_HEADROOM_AND_GATE_E: heuristic_proxy_headroom=0 on all 64; gate_e_warning=true — blocking design limitation for Stage 5, not quantum promise
FULL_REGRESSION_AND_STAGE_3_3_VERIFY: pytest exit 0 (all formulation + suite); doctor ok; status readiness stage4_1-complete-pending-independent-review; diagnostic-stage3-3 --verify match=true after rewrite for simulator 1.0.3
NEW_RUN_ID_AND_RECEIPT: c4d0a199-9cea-4214-83ab-97964f2bf1ac ; evidence/formulation/receipts/c4d0a199-9cea-4214-83ab-97964f2bf1ac.json
RECEIPT_ERRATUM: Stage 4 receipt next_permitted_work wrongly said Stage 2 awaiting… — erratum in evidence/.../formulation.pre_repair_erratum/stage4_receipt_erratum.json; new receipt states Stage 5 blocked pending independent review / Gate E
RESOURCE_USAGE: max_workers=1; RAM ceiling 60%; Stage 4.1 cap 1800s; duration_monotonic_s≈74.69; QPU_USAGE_SECONDS=0; NEW_PHYSICAL_QPU_JOBS_SUBMITTED=0
FROZEN_REVIEW_ZIP_SHA256: 4df5571d13eef1c87cc00ee361b2dd422dbdb732e6633af08bbd1229273d84b4
INNER_MANIFEST_MEMBERS_AND_AGGREGATE: 164 non-manifest members + MANIFEST.sha256.json; aggregate c450a3dddad33adce7acc2ebd6011ab6ddebece6629d910dca812e6408f0742f
FINAL_CLEAN_EXTRACT_VERIFICATION: review/STAGE_4_1_FINAL_VERIFY.json ok=true; sidecar review/STAGE_4_1_REVIEW.manifest.json sha256 b34440b9f1521a30198d8691506535ea1dd55106c221f881bc614527ef5a881f; targeted formulation pytest exit 0; spotcheck milp_agree=true
GATE_C_FORMULATION: PASS
STAGE_5_AUTHORISED: false
SCIENTIFIC_PROTOCOL: DRAFT
RESERVED_PARTITIONS_MATERIALIZED: none
LEARNED_MODELS_TRAINED: 0
QUANTUM_CIRCUITS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_SECONDS: 0
IBM_OR_OTHER_CREDENTIAL_REQUESTED_OR_USED: false
PUSH_PERFORMED: false
NEXT_PERMITTED_WORK: independent review of Stage 4.1; Stage 5 blocked pending that review and Gate E decision
```

## Commands actually run (representative)

| Command | Exit |
| --- | --- |
| `python -m f1q doctor` | 0 |
| `python -m f1q status` | 0 |
| `python -m f1q simulator diagnostic-stage3-3 --verify` (start) | 0 |
| `python -m pytest` (baseline) | 0 |
| pre-repair reproduction script → `docs/evidence/stage4_1/pre_repair_reproduction.json` | 0 |
| `python -m f1q simulator diagnostic-stage3-3 --write` then `--verify` | 0 |
| `python -m f1q run --plan formulation_repair_check` | 0 |
| `python -m pytest` (post-repair) | 0 |
| clean-extract of frozen `review/STAGE_4_1_REVIEW.zip` | 0 |

No `git push`. No IBM/QPU/provider call. No Stage 5 QAOA / learned selectors. No reserved-split materialization.

## Superseded vs retained

**Superseded (Stage 4):** Gate C PASS as end-to-end formulation semantics; pair adjacent-lap coefficient; cross-check coverage claim; evaluator `legal=true` without terminal obligation; panel label-order disagreements as ranking evidence; receipt next-work Stage 2 text; review clean-extract self-consistency for ZIP `30fbcf9e…`.

**Retained:** QUBO/Ising algebraic conventions (upper+diag, x=(1−Z)/2, strict penalty form); independent MILP separation from QUBO; Stage 4 run identifiers as history; Gate E zero-headroom warning.

## Closing

Local commit records authorized Stage 4.1 repair software and evidence. Push was not performed. Stage 5 is not authorised.

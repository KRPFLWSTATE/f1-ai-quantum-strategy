# Stage 4.1 — formulation semantics, evaluator, evidence, and packaging repair

Project: `f1-ai-quantum-strategy`

Work only in the existing isolated repository. This prompt authorizes a narrow Stage 4.1 repair, a fresh bounded local validation run, one local commit, and a new review package. Implement the repair, execute the checks, save immutable new evidence under a new run ID, and return the requested artifacts. Do not respond with a plan alone.

Stage 4 is **not accepted** and Stage 5 is blocked. Preserve the completed Stage 4 run `e8b87881-74a6-46c7-b48e-6b2496a5d586`, the failed run `1c5b0748-5406-4933-8e41-4f943f4296c7`, their receipts, and every prior artifact exactly as historical evidence. Do not edit, replace, delete, or reuse them. The new report must explicitly supersede the affected Stage 4 conclusions without pretending the original run did not occur.

## Non-negotiable boundaries

- Zero additional spending. Use only the existing environment and free/open-source dependencies.
- Keep `hardware_execution_enabled: false`.
- Do not request, inspect, enter, print, store, or test any IBM or other provider credential.
- Do not contact IBM or any quantum provider, query balances/backends, or submit physical jobs.
- Do not implement Stage 5, QAOA circuits, mixers, parameter fitting, learned selectors, dispatch models, AI training, hardware menus, or provider submission.
- Do not materialize or inspect reserved training, tuning, calibration, test, or shift partitions. Use only hand fixtures and the existing 64-case development preview.
- Do not scrape F1 data or claim empirical Formula One calibration, quantum advantage, circuit novelty, or scientific superiority.
- Do not run the conditional 1,200-instance panel or a large campaign.
- Do not push to GitHub. Do not publish or create automation.
- Preserve all prior evidence. All repaired results require a new plan/run ID, new output paths, new hashes, and an explicit provenance chain.

## Establish state before editing

Read `AGENTS.md`, `PROJECT_STATUS.md`, the Stage 4 prompt, `docs/STAGE_4_REPORT.md`, the Stage 4 action/compiler/QUBO/reference documentation, the Stage 3.3 closure material, the current simulator policy/interface/engine code, all Stage 4 source/tests, both Stage 4 receipts, and the review-package manifest/verification files.

Run and record:

```text
git status --short
git rev-parse HEAD
python -m f1q doctor
python -m f1q status
python -m f1q simulator diagnostic-stage3-3 --verify
python -m pytest
```

Never reset or hide a discrepancy. Record the exact starting HEAD, tree state, Python/dependency versions, test count, and exits.

## Independent-review findings that must be reproduced and resolved

Treat these as defect reports, not as conclusions to copy blindly. Reproduce each from source and raw evidence before changing code, save a machine-readable pre-repair diagnostic, and fail loudly if a stated reproduction unexpectedly differs.

### R1 — admitted “complete” plans can violate the compound obligation

The action generator admits a same-compound `pit_now`/`delay_laps` plan when `_obligation_feasible_after` predicts that `compound_obligation.v1` can make another stop. The compiler, however, applies its downstream obligation stop only for `continuation`, not after a scheduled same-compound stop. The simulator consumes a one-shot pit/delay policy at pit entry by replacing it with an inert stored `continuation`, which prevents the dynamic baseline obligation intent from being resumed. The evaluator validates only the instruction at the checkpoint and sets `legal=true` without checking terminal obligation satisfaction.

Across the submitted 64 development checkpoints, reproduce at least these facts:

- 28 episodes / 56 selected cars have an unmet two-compound obligation at the checkpoint;
- 13 of those cars are on track with a 10-action reduced menu;
- three reported proxy-optimal actions make a same-compound stop while the obligation is unmet and finish with only `soft` in `used_compounds`:
  - family `0003`, episode `03`, SC: `car.fictional.windrow.a|delay_laps|2|soft|car.fictional.windrow.a.set.soft.1`;
  - family `0005`, episode `07`, VSC: `car.fictional.lakemere.b|delay_laps|2|soft|car.fictional.lakemere.b.set.soft.1`;
  - family `0007`, episode `06`, VSC: `car.fictional.redcliff.a|delay_laps|2|soft|car.fictional.redcliff.a.set.soft.1`.

For each, record checkpoint state, admitted action, compiler stop sequence/cost, simulator pit/service events, terminal compounds, terminal obligation status, and evaluator legality. This defect invalidates Gate C even if the QUBO algebra is correct.

### R2 — downstream-policy semantics are not one shared, executable definition

`docs/ACTION_MODEL.md` says continuation uses frozen `compound_obligation.v1`; `policies.py` defines an immediate obligation intent; the compiler describes a near-horizon stop; and the post-one-shot simulator stores `continuation` in a way that can suppress the baseline policy. Cars already in the pit lane also admit only `continuation`, but the compiler models a generic future full stop rather than explicitly accounting for the already committed/in-progress service state.

Create one authoritative, versioned downstream-policy specification and make the action generator, simulator adapter/engine, compiler, documentation, and tests obey it. A plan must have the same stop sequence semantics everywhere. “Frozen” means a versioned deterministic policy, not an undocumented change in behavior.

Required behavior:

- An on-track car with an unmet obligation must not finish illegally under an admitted complete plan.
- If a same-compound stop is admitted because a downstream alternate-compound stop remains feasible, that later stop must actually occur in both the compiler semantics and simulator execution, with every pit loss/interaction represented once.
- Alternatively, if the Stage 4.1 supported action language is intentionally limited to one future stop, reject same-compound actions while the obligation is unmet. Do not claim a downstream stop that the plan cannot execute.
- `continuation` must invoke the documented downstream policy rather than becoming a permanent inert “stay out” instruction.
- Continuing an already in-progress pit service must preserve its committed service target and must not invent an unrelated extra stop. If the required target is not solver-visible, either expose the minimum legitimate own-team committed-plan field through the public observation schema with provenance and tests, or define a sound observable-only deterministic inference. Never read private state in the action generator/compiler.
- Applying a new plan on track must clear or replace stale `pit_this_lap`, `pending_compound`, and `pending_set_id` state atomically; continuing an in-progress service must preserve the active commitment. Add rollback tests.
- Record planned stops and executed stops in an auditable normalized form so compiler/evaluator semantic comparisons can be automated.

If production simulator or observation/interface semantics change, bump the appropriate simulator/interface/policy versions, document the amendment, rerun every affected Stage 3/3.3 diagnostic and the full regression suite, and create new repair evidence. Never rewrite prior Stage 3 evidence.

### R3 — cross-check coverage was capped and checked only input validation

The submitted code truncates reduced-menu pairs to the first 36 per episode. The 64 records contain 3,535 reduced legal pairs, but only 1,492 were recorded as checked, leaving 2,043 unrecorded despite the Stage 4 requirement to check every admitted complete joint plan.

Remove the cap for this small domain. For all 3,535 reduced pairs:

1. call the public simulator validator;
2. record validation agreement;
3. verify action-to-simulator payload round trip;
4. run semantic terminal checks where required by the policy (including compound obligation, instructed set/compound, stop timing tolerance, and one-shot/downstream transitions).

Also verify the full-to-reduced equivalence relation without simulating every full Cartesian product unnecessarily: every removed full action must be proven cost- and semantics-equivalent to its representative using all cost-relevant observable attributes. Report exact denominators, failures, and failure codes. No hidden cap or favorable sample.

### R4 — action expiry uses a hard-coded pit-entry fraction

`formulation/actions.py::_missed_pit_entry` hard-codes `0.95` even though pit-entry geometry is configuration. Add the public pit-entry fraction (and any other strictly required public geometry) to the versioned public formulation configuration and source it from simulator config. Use it consistently in admission and tests. Add non-0.95 fixtures proving behavior changes with configuration.

### R5 — equivalence reduction does not prove physical-set equivalence

The key `(kind, delay_laps, compound)` ignores set age and any other cost/semantic attributes. Do not silently merge merely because present development unused sets happen to look alike.

Either retain all physical sets, or define a versioned equivalence signature containing every compiler- and simulator-relevant observable attribute. Before reduction, assert and record that all members are equivalent under the direct compiler and plan semantics. Add a fixture with two same-compound sets of different age/condition proving they are not merged. Preserve member-to-representative maps and degeneracy counts.

### R6 — pair interaction contains an unsupported adjacent-lap penalty

The compiler adds `0.5 * service_stationary_s` whenever planned pit laps are adjacent and labels this a shared-crew/rejoin interaction. Cars stopping roughly one lap apart do not incur half a service time merely because their integer pit-lap indices differ by one. No derivation or public arrival-time calculation supports that coefficient.

Delete the arbitrary adjacent-lap rule. Replace the pair term with one of the following, documented and hand-tested:

- a public-observable predicted service-interval overlap calculation, where extra wait is derived from predicted box-arrival times and shared-crew service duration; or
- zero when available public timing is insufficient to establish overlap.

Same nominal pit lap is not automatically a full service-time wait unless the arrival/service intervals support it. Record the equation, units, assumptions, boundary cases, and no-double-counting proof. Do not add a new traffic/rejoin coefficient without a defensible derivation and source.

### R7 — evaluator legality and ranking diagnostics are unsound

`evaluate_joint_plan_on_checkpoint` reports `legal=true` after pre-execution validation and does not verify terminal compound obligations or action semantics. Repair it to report separately:

- checkpoint instruction validity;
- execution success;
- instructed versus executed stop sequence;
- terminal compound-obligation satisfaction;
- overall semantic legality with explicit reason codes;
- final used compounds, selected tyre sets, stop times/laps, and relevant terminal classification.

Do not label a terminally illegal plan legal.

The panel also compares `(value, label)` sorted lists. Exact and greedy are often identical plans under different labels, and evaluator ties are broken lexicographically, creating false order disagreements. In the submitted panel all eight exact/greedy entries duplicate the same plan; two of the reported three disagreements are evaluator-loss tie artifacts, while one case is a genuine ordering difference.

Repair the panel to:

- deduplicate identical joint action IDs before evaluation while retaining provenance labels;
- identify proxy ties and evaluator ties under declared tolerances;
- use a tie-aware measure (pairwise concordant/discordant/tied counts and, where defined, Kendall tau-b or an equivalently explicit statistic);
- distinguish reversal, tie/loss of discrimination, and agreement;
- never convert label ordering into scientific ranking evidence.

Rerun the predeclared eight-family development panel after the formulation repair. Do not tune coefficients from it.

### R8 — reference and budget accounting is incomplete

Repair and test all of the following:

- `uniform_legal_sample` evaluates one initial state plus `n_samples` loop states but reports only `n_samples` evaluations;
- simulated annealing evaluates an initial state plus `steps` proposals but reports only `steps` evaluations;
- any greedy preselection/scoring count must equal actual direct-scorer calls, including repeated calls;
- the MILP agreement flag compares only objective value; it must also verify that the selected MILP pair belongs to the enumeration minimizer set under the declared tolerance/tie policy;
- record solver status, primal/dual bound if available, MIP gap, solver tolerances, threads, preprocessing, warm-start/cache policy, and measured wall time honestly;
- timing budgets must separate compilation/preprocessing from online solve/scan time; do not use a single accumulated timer ambiguously.

Do not replace the working independent MILP with QUBO brute force. Preserve the valid mathematical separation.

### R9 — receipt/status text is stale

The completed Stage 4 receipt says `next_permitted_work` is “Stage 2 awaiting its implementation prompt,” which is false. Preserve that immutable receipt and issue an explicit erratum in new evidence. Fix the receipt/status-generation source and add a stage-aware test. The new Stage 4.1 receipt must state that Stage 5 is blocked pending independent review and the Gate E/headroom decision. It must not authorize hardware or ask for credentials.

### R10 — final review-package verification is not for the submitted final ZIP

The uploaded final ZIP SHA-256 is:

```text
30fbcf9e166c0c767817ea9608020dd66bf51bc9846834f6310d3ad18c5a446b
```

Its inner `MANIFEST.sha256.json` is internally sound: all 547 non-manifest members, byte counts, per-file SHA-256 values, and canonical aggregate `96b73f0bbb3486a9d40e8196c3d4ce882061dc939f064fb2a4f50a27bfadb08e` verify. However, the bundled `docs/evidence/stage4/clean_extract_verify.json` and the archived report refer to ZIP SHA-256 `732606bc...`, proving that clean-extract evidence was generated for an earlier candidate and the archive was rebuilt afterward. The external report was then updated to `30fbcf...`. The archive also contains `docs/.DS_Store` and `docs/evidence/.DS_Store`.

The repaired package must avoid circular self-hashing:

1. Create the final inner manifest over every intended member except itself; verify paths, bytes, per-file hashes, and the documented canonical aggregate.
2. Exclude `.DS_Store`, caches, environments, mutable ledgers, credentials, private/reserved data, and unrelated files.
3. Build `review/STAGE_4_1_REVIEW.zip` once from the frozen staging tree.
4. Compute its SHA-256 and do not modify or rebuild that ZIP afterward.
5. Extract that exact final ZIP into a new temporary directory; verify safe paths/no symlinks, every member hash/size, the aggregate, imports, record spot-checks, and targeted tests using the documented environment.
6. Write the ZIP self-digest and final clean-extract results only to external files created after the ZIP is frozen, for example `review/STAGE_4_1_REVIEW.manifest.json` and `review/STAGE_4_1_FINAL_VERIFY.json`. Do not insert those files back into the ZIP.
7. Generate the external final report after verification. It may name the frozen ZIP hash and external verification hashes. The ZIP must not contain a stale copy claiming to be the final self-verification report.
8. Return the report, ZIP, external sidecar, and external final-verification JSON.

## Preserve the sound mathematical layer, then revalidate it with repaired costs

Independent review reproduced a representative 14-variable instance with:

- 16,384/16,384 QUBO-to-Ising energy equalities;
- strict penalty proof `B=648.6842468600425`, `v_min=1`, `M=649.6842468600425`;
- all feasible penalties zero and all infeasible penalties at least `M`;
- enumeration and MILP value `7587.166542883901` with the same selected pair;
- scale-restoration error about `2.18e-11`.

Do not rewrite working QUBO/Ising code merely for novelty. The repair changes action semantics and coefficient tables, so regenerate all instances and rerun the complete direct-cost, centring, QUBO, Ising, scaling, decoding, strict-penalty, enumeration, MILP, and zero-interaction-reference checks on the new records. Any numerical value from the superseded run is historical, not an expected golden answer.

Add an independent test expression for small QUBOs rather than comparing a helper with itself. Keep the upper-plus-diagonal convention and physical offsets explicit.

## Required regression tests

In addition to every existing test, add focused tests that would have failed the submitted Stage 4 code:

1. On-track unmet obligation + delayed same-compound stop: either the plan is rejected or an alternate-compound downstream stop is executed and charged; terminal obligation must pass.
2. On-track unmet obligation + continuation: documented downstream policy executes identically in compiler semantics and simulator plan semantics.
3. In-pit continuation: active committed service completes on the intended set without a fictitious unrelated stop.
4. Applying a new plan replaces stale pending intent on track but preserves active in-pit commitment; exception rollback restores all fields.
5. Evaluator marks an otherwise executable terminal obligation violation illegal with a reason code.
6. Reproduce all three historical invalid optimum cases and demonstrate corrected behavior under new versions.
7. Configured pit-entry fractions below and above 0.95 alter expiry correctly.
8. Same-compound physical sets with different observable condition are not merged.
9. Pair wait equals a hand-derived service-interval overlap; adjacent-lap actions with no overlap have zero pair cost.
10. All 3,535 current reduced pairs are validator-cross-checked with exact denominator reporting and no cap.
11. Full-to-reduced members pass cost and semantics equivalence assertions.
12. Panel deduplicates identical exact/greedy plans and classifies ties without label-order artifacts.
13. Uniform/annealing/greedy reported evaluations equal instrumented direct-scorer calls.
14. MILP selected pair is in the tolerance-defined enumeration minimizer set, including exact-tie fixtures.
15. Receipt `next_permitted_work` is stage-aware.
16. Final-package test rejects a clean-extract record whose ZIP hash differs from the frozen archive.
17. Packaging rejects `.DS_Store`, symlinks, traversal names, caches, credentials, mutable ledger files, and undeclared members.

Use hand-derived fixtures and the three named real development reproductions. Do not weaken assertions to make the old outcome pass.

## New bounded Stage 4.1 run

Create a new plan named `formulation_repair_check` (or an equally explicit Stage 4.1 name) under a new UUID. It must include, at minimum:

1. pre-repair reproduction/erratum registration;
2. action/downstream-policy semantic checks;
3. compiler/direct-cost and pair-timing checks;
4. QUBO/Ising/penalty gate;
5. enumeration/MILP/DP/heuristic references;
6. complete 64-case development matrix;
7. all-pair validator/semantic cross-check;
8. tie-aware eight-family evaluator panel;
9. Stage 3.3 diagnostic/source restoration if simulator code changed;
10. source snapshot and final evidence consistency.

Use one worker unless measured evidence justifies two, retain the 60% RAM ceiling, and keep the cumulative local cap at 30 minutes. Preserve partial artifacts and resume by checksum if interrupted. Never omit a slow/failing case. Record planned/completed/failed denominators, exact seeds, machine/dependency versions, source/config hashes, wall times, RAM settings, failure codes, `QPU_USAGE_SECONDS: 0`, and `NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0`.

Regenerate the 64 development records under the new formulation/compiler/policy versions. Recompute action counts, optima, ties, headroom, timings, panel diagnostics, and Gate C from raw records. Do not copy Stage 4 summary values. If exact enumeration again eliminates heuristic proxy headroom, report it plainly. Do not manufacture difficulty. Mark Gate E as a blocking design limitation for the next architecture decision rather than evidence of quantum promise.

## Acceptance gate

Stage 4.1 Gate C passes only if all of the following are true:

- every admitted action is a complete executable plan with one authoritative downstream-policy meaning;
- all terminal obligations and instructed stop semantics pass for every required development cross-check;
- the three historical invalid optimum reproductions are corrected and evidenced;
- public geometry replaces the hard-coded 0.95 admission rule;
- action reduction is proven semantics- and cost-preserving;
- the pair interaction has a derived observable-time basis or is zero where overlap cannot be established;
- all 3,535 current reduced pairs (or the newly regenerated exact total, explicitly reconciled) are checked, with zero hidden cap;
- evaluator legality is terminal and semantic, and panel comparisons are deduplicated and tie-aware;
- direct/centred costs, QUBO, Ising, decoding, penalties, enumeration, independent MILP, and restricted DP agree where applicable;
- heuristic and timing accounting is exact;
- all existing and new tests, doctor, status, Stage 3.3 diagnostic verification, and any required simulator repair diagnostics pass;
- the new receipt/status text is correct and prior evidence is preserved;
- the exact frozen final ZIP passes safe clean-extract verification, all inner hashes/aggregate, targeted tests, and record spot-checks, with matching external sidecar hash;
- no provider, QPU, reserved split, learned model, circuit, push, or spending occurs.

If any item fails, report `GATE_C_FORMULATION: FAIL` or `PARTIAL`, preserve evidence, and stop. Do not begin Stage 5.

## Documentation and versioning

Update the current action-model, compiler, simulator amendment (if applicable), QUBO/reference, status, README, CLI, schema, and testing documentation. Bump every behaviorally changed version. State exactly which Stage 4 claims are superseded and which mathematical checks remain supported.

After all checks pass, create one local commit containing only authorized Stage 4.1 source, tests, docs, and immutable evidence. Do not commit environments, credentials, caches, mutable ledger databases, private data, reserved data, review ZIPs, or unrelated changes. Do not push.

## Required return and stop point

Return these four files:

```text
docs/STAGE_4_1_REPORT.md
review/STAGE_4_1_REVIEW.zip
review/STAGE_4_1_REVIEW.manifest.json
review/STAGE_4_1_FINAL_VERIFY.json
```

The report must provide this concise machine-auditable summary:

```text
STAGE_4_1_STATUS: COMPLETE | PARTIAL | BLOCKED
STARTING_HEAD_AND_TREE:
ENDING_HEAD_LOCAL_COMMIT_AND_TREE:
PRIOR_STAGE_4_EVIDENCE_PRESERVED:
PRE_REPAIR_REPRODUCTION:
ROOT_CAUSES_AND_VERSIONED_FIXES:
DOWNSTREAM_POLICY_SEMANTICS:
HISTORICAL_INVALID_CASES_CORRECTED:
PUBLIC_GEOMETRY_AND_ACTION_REDUCTION:
PAIR_INTERACTION_DERIVATION:
COMPLETE_PAIR_CROSS_CHECK: expected/checked/failed
EVALUATOR_TERMINAL_LEGALITY:
TIE_AWARE_PANEL:
QUBO_ISING_AND_PENALTY_REVALIDATION:
ENUMERATION_MILP_DP_AGREEMENT:
HEURISTIC_AND_TIMING_ACCOUNTING:
DEVELOPMENT_MATRIX: planned/completed/failed; development only
PROXY_HEADROOM_AND_GATE_E:
FULL_REGRESSION_AND_STAGE_3_3_VERIFY:
NEW_RUN_ID_AND_RECEIPT:
RECEIPT_ERRATUM:
RESOURCE_USAGE:
FROZEN_REVIEW_ZIP_SHA256:
INNER_MANIFEST_MEMBERS_AND_AGGREGATE:
FINAL_CLEAN_EXTRACT_VERIFICATION:
GATE_C_FORMULATION: PASS | PARTIAL | FAIL
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

Then stop. Do not begin Stage 5, do not push, and do not ask for an IBM API key.

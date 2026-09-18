# Cursor Stage 2 — generated scenarios and causal checkpoint contracts

For `f1-ai-quantum-strategy`, following the supplied Stage 1 report. Scientific reference: `F1_AI_Quantum_Research_Dossier_v3_1.pdf`.

Read this file in full and execute the authorized work. Complete the bounded Stage 1 verification below, then implement Stage 2 if its prerequisites pass. Return evidence, not only a plan. Routine engineering choices are yours to resolve and document.

## 1. Scope and current evidence

The supplied Stage 1 report records a separate local repository, a private empty GitHub repository under KRPFLWSTATE, Python 3.12.13 on macOS arm64, a local ledger, a successful interrupted/resumed bootstrap, passing checks and no physical QPU submissions. These are reported facts to corroborate from the local files, not permission to claim an independent audit has already occurred.

Read root `AGENTS.md`, `PROJECT_STATUS.md`, the actual ledger and bootstrap receipts, `docs/STAGE_1_REPORT.md`, `docs/DEVIATIONS.md`, the source snapshot records and dossier sections 5–8, 15, 17–19 and 23–26. Respect existing path protection and preserve the earlier research project unchanged.

This prompt authorizes local Stage 2 implementation and a small development preview. It does not authorize the full corpus, scientific comparison runs, model fitting, circuit work, provider login, QPU jobs, paid services, historical-data downloads, GitHub pushes, remote automation or article drafting. Keep the scientific protocol DRAFT and hardware execution disabled. Do not create another repository.

## 2. Close three Stage 1 evidence gaps before proceeding

### A. Final source identity

Inspect current Git HEAD, branch, status and remote. The report describes checks before a setup commit but does not give the final commit. Record the current situation without changing history. Verify the recorded snapshot `320dc0f9e7457e31d2a05a7d998b2bedb909447559e04acf1866cb6704aaa583` against its retained source manifest and bytes. Do not assume a commit identifies earlier uncommitted code.

Identify which source snapshot contains the `_ledger`/`UnboundLocalError` repair and which verification records apply to it. Documentation-only changes need not invalidate scientific code identity, but the recorded hashing policy must distinguish them explicitly. If the original snapshot cannot be reconstructed, retain its receipt, report that limitation and create a new identified verification run; never rewrite the old evidence to suggest it was complete.

### B. Checks after the repair

Inspect the actual test log, doctor output, concurrency evidence and interruption/resume receipts. Establish whether the relevant checks ran against the repaired source. If the evidence is absent or stale, run the small Stage 1 suite once on the identified current source and save its exact command, exit status and logs. Exercise the original doctor failure path so a failed ledger initialization produces a controlled error rather than referencing an unassigned variable. Tests must use isolated temporary ledgers, not damage production evidence.

### C. Installation outside the source directory

Verify what the fresh-environment check actually did. A successful import from the repository root alone does not establish that the package installed correctly. If not already evidenced, install the project and locked dependencies into a clean local environment, then run its documented CLI/import checks from a temporary directory outside the source tree, with `PYTHONPATH` unset. Use an explicit project-root option or the documented root-resolution mechanism. Save the interpreter path, installed package location and outputs without exposing secrets.

Write `docs/STAGE_1_FOLLOWUP.md` with verified findings, any repairs, source fingerprints and remaining limits. Preserve the original report and bootstrap raw records. Distinguish an evidence omission from an actual defect. If a ledger, authorization or isolation defect remains unresolved, complete its repair before Stage 2 execution. Do not treat a missing local Git author identity alone as a scientific blocker; preserve a complete source snapshot and report it.

## 3. What Stage 2 should produce

Implement a reproducible **scenario-specification generator**, split registry, random-stream contract, causal observation schema and corpus audit. Produce a small development preview with explicit assumptions and an evidence receipt.

Stage 3 will implement and validate race evolution. Stage 2 must not pretend that arbitrarily sampled snapshots are already valid race trajectories. Its episode specifications should define initialization and the intended checkpoint condition; Stage 3 must advance the state and validate that checkpoint before admitting it to the scientific corpus. Mark development schema fixtures as fixtures, and scenario specifications as awaiting simulator validation.

Stage 2 completion means that generation, interfaces and audits work. It does not mean SC/VSC dynamics, tyre models, F1 calibration or counterfactual validity have passed.

## 4. Versioned configuration and scenario hierarchy

Implement the dossier's eight families as the Cartesian product of:

- low/high green pit loss;
- near-linear/nonlinear tyre degradation;
- sparse/dense traffic.

Define the factors, units, family identifiers, distribution forms, bounds and any dependencies in a versioned configuration. The dossier's proposed starting domain is a fictional 20-car field, 12–45 remaining laps, green laps of 75–110 seconds and green pit loss of 18–28 seconds. These are assumptions, not measured F1 calibration.

For unspecified quantities, choose explicit provisional values or distributions needed for the development preview, document why they permit useful mechanism tests and flag them for the later pilot. Do not invent citations or describe these choices as established F1 parameters. If a quantity depends on Stage 3 physics, specify its interface and pending validation instead of returning a meaningless numeric default. Clarify whether pit-loss values include service time to prevent later double counting.

The hierarchy is family → independent parameter block → eight separate episode specifications → checkpoint request. Each block shares its sampled block parameters across its episodes. Four episodes request an SC checkpoint and four request VSC. Each episode has its own initial conditions and keyed random streams. This is a balanced conditional design, not an estimator of natural safety-car incidence.

Include consistent race horizon, completed laps and remaining laps; fictional car/team identifiers; the selected two-car team; starting positions/gaps; dry-weather scope; tyre compound/set inventory; completed compound obligations; fuel assumptions and uncertainty; pit-lane and shared-service state; rival-policy configuration references; and the prescribed checkpoint location/time rule. Do not implement rival decision-making or continuation simulation here.

Keep a serialized scenario specification distinct from a solver-visible checkpoint. A request to condition on SC or VSC may be part of the generator; the checkpoint observation includes that condition only when it is causally revealed. Never include the realized future duration in the solver-visible state.

## 5. Split registry and deterministic identities

Encode and audit these planned counts without generating their scientific outcomes:

| Partition | Blocks | Episodes/checkpoints planned |
| --- | ---: | ---: |
| Training | 120 | 960 |
| Tuning | 16 | 128 |
| Calibration | 24 | 192 |
| Primary test floor | 80 | 640 |
| Separate shift panel | 40 | 320 |

The first four partitions total 240 blocks and 1,920 planned checkpoints; including the shift panel gives 280 and 2,240. Primary-test sizing can later increase to 160 blocks in multiples of eight, before test exposure and following the dossier's sizing procedure. At that maximum the totals including shift are 360 blocks and 2,880 checkpoints. Store these as planned counts, never completed counts.

Allocate the main partitions evenly across the eight families. For the shift panel, provide an explicit draft allocation and a schema for predeclared shifts; do not claim a finalized distribution-shift study. Its changes and counts must be frozen before its eventual use.

All descendants retain their parent block's partition. Reject duplicate identities and partition reassignment. Distinct IDs alone do not establish statistical independence: record shared block parameters and the stream construction, and keep the block as the inferential unit. Do not pick examples by favorable optimization outcomes.

Use stable namespaced identifiers and a documented, versioned hash/key derivation. Do not use Python's process-randomized `hash()`, a global mutable RNG or row order to generate persistent identities. Keys must separate block parameters, episode generation, fitting, online scoring and final evaluation. Later evaluation keys should support event identity such as driver, lap, event type and replication so changed action paths do not desynchronize unrelated draws.

Stage 2 may record partition identities/count metadata and test their assignment algorithm with fixtures. Keep calibration/test/shift realization and all evaluation outcomes unopened. A development preview must use a separate development namespace that is in none of these partitions. Production commands to materialize reserved partitions must remain unavailable or explicitly gated for their later authorized stage.

For later reproducibility, document where private simulation seeds and complete state will be retained and how observation builders exclude them. Interface isolation prevents accidental information leakage; do not call it cryptographic protection against someone with full repository access.

## 6. Causal schemas and the Stage 3 interface

Separate at least these concepts in types and serialized data:

1. ScenarioSpec: generated assumptions, initialization and checkpoint request.
2. SimulatorState: complete physical/RNG state for later simulator continuation; never passed directly to a solver.
3. DecisionObservation: only information available at its observation time.
4. CheckpointEnvelope: identity, validation status, observation, state reference, timing metadata and provenance, with explicit separation between solver and evaluator access.

Use an explicit allowlist/projection to construct DecisionObservation. Every observed or estimated quantity needs value, unit, source, availability time and known/inferred/assumed status. Observed availability cannot exceed the decision time. A forecast may concern a future event, but must be labeled as a forecast with its issuance time and uncertainty, never as the known realization. Unknown values require a reason and must not silently become zero.

Include per-car pit-entry commitment cutoffs, communication margin and state-validity timing. Define compatible clock units and origins. Accept meaningful expired-action states for later fallback tests while rejecting impossible time ordering; do not silently relabel a missed pit opportunity as next lap. Proposed nominal budgets remain distinct from effective cutoffs.

Validate structural consistency: unique cars and positions, selected team membership, nonnegative durations/ages/inventories, valid units and ranges, consistent tyre-set use, and compatible horizon values. Define how ordered gaps and lap deficits will be represented. For unsupported cases, provide an explicit rejection code rather than forcing misleading state values. Do not assert physical reachability merely because these checks pass.

Retain the dossier's exclusions: wet transitions, red flags, sprint-specific rules, tyre damage and detailed energy deployment. Double stacking is not inherently illegal. Compound obligations and any team restrictions must be explicit model configuration, not invented FIA requirements.

Document the Stage 3 handoff: initialize a state, advance it to the prescribed checkpoint, apply/reveal the declared regime, construct the observation, preserve the resume state and validate it. Define expected inputs/outputs and errors. Unimplemented simulator execution must fail explicitly; it must not return placeholder race results.

## 7. Bounded development preview and audit

Authorize exactly one initial development preview of **eight blocks, one per family, with eight episode specifications per block: 64 specifications total, 32 SC and 32 VSC**. It is engineering development data, not training/test evidence and not 64 validated race checkpoints. Any failed attempt and necessary repair/retry must remain recorded; do not repeatedly regenerate until the examples look attractive.

Implement idempotent generation and ledger-backed resume using the existing Stage 1 infrastructure. Preserve the actual source/configuration identity for each attempt. Extend the ledger schema with versioned migrations if needed; do not reset it or erase bootstrap history.

Provide documented CLI operations to validate a generator configuration, plan partition counts without realization, generate the development preview, audit its artifacts, and resume an interrupted authorized unit. Reuse existing command conventions where practical. “Do a run” continues to resolve one recorded authorized unit; it must not automatically expand into the entire corpus.

The preview audit should report configured versus realized development counts, family/regime balance, unique block/episode IDs, partition assignments, schema rejections, assumption provenance, source/config hashes, deterministic fingerprints and the pending simulator-validation status. Generate these tables from the artifacts rather than hard-coding expected totals into the report.

Store excluded/rejected cases and reasons. Retries need distinct attempt IDs, deterministic keys and a declared bounded retry policy. Do not replace rejected cases invisibly. Do not manufacture solver scores, final positions, useful-candidate probabilities or hardware metrics.

## 8. Acceptance checks tied to concrete risks

Implement and execute checks for:

- All eight factor combinations, correct main split counts at floor and maximum, and per-block SC/VSC balance.
- Deterministic substantive output across fresh processes and changed iteration order; distinguish immutable payload fingerprints from timestamps and run IDs.
- No block leakage across partitions and no development-preview inclusion in scientific splits.
- Domain-separated stream keys and event-keyed draw consistency; changing a fitting seed must not change generated episode assumptions or evaluator-bank keys.
- Observation construction excluding private seeds, future realized regime duration, future rival decisions and evaluator-only fields. Reject an observation with a future availability time; permit correctly labeled forecasts issued before the checkpoint.
- Structural validity, impossible configurations, documented exclusions, and expired-action representations with useful reason codes.
- Interrupted generation and resume preserving completed artifacts; configuration/source mismatch and corruption blocking silent reuse.
- A small independent audit that recomputes counts and identity membership from serialized artifacts rather than asking the generator to validate its own expected counts.

Use hand-constructed cases for boundary conditions, not only generator outputs. Run the relevant Stage 1 regressions after integration because schemas and ledger behavior are shared. Stop expanding checks once these risks are resolved; no arbitrary coverage-percentage target is required.

## 9. Deliverables, state and stop point

Save source, tests, generator configuration, schema versions, split plan and development artifacts. Add `docs/GENERATOR_SPEC.md`, `docs/STAGE_2_REPORT.md` and the Stage 1 follow-up. Update provenance, decisions, deviations, traceability and project status. Preserve all original evidence. Keep raw data and sanitized release manifests distinct; do not delete development evidence just because it is ignored by Git.

A local commit is allowed with the existing identity after review; do not push. Identify any documentation edits made after the final checked code snapshot. Make the package commands reproducible from the documented environment.

Return:

```text
STAGE_1_FOLLOWUP: PASS | BLOCKED, with report path
FINAL_SOURCE_AND_COMMIT:
STAGE_2_STATUS: COMPLETE | PARTIAL | BLOCKED
IMPLEMENTED_COMMANDS:
GENERATOR_AND_SCHEMA_VERSIONS:
CONFIGURATION_HASH:
PARTITION_PLAN_COUNTS:
DEVELOPMENT_PREVIEW: actual blocks/specifications/families/SC/VSC
VALIDATED_RACE_CHECKPOINTS: actual count; expected 0 pending Stage 3
RESERVED_PARTITIONS_MATERIALIZED: actual state; expected none
REJECTIONS_AND_FAILED_ATTEMPTS:
CHECKS: actual passed/failed/not-run and log paths
RUN_ID_AND_RECEIPT:
ASSUMPTIONS_REQUIRING_STAGE_3_OR_PILOT_VALIDATION:
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_COMPARISON_EXPERIMENTS_EXECUTED: actual count; expected 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: actual count; expected 0
QPU_USAGE_FROM_THIS_STAGE: actual value; expected 0, account not queried
PUSH_PERFORMED: actual value; expected false
NEXT_STAGE: 3 — simulator adapter and independent mechanism checks
```

Fill every field from actual evidence. Include the full concise report in chat and save its file so the user can return it to ChatGPT. Stop after Stage 2. If successful, the next work is simulator selection, provenance inspection and causal evolution/continuation checks under a separate implementation prompt.

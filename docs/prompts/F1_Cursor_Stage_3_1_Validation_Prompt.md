# Cursor Stage 3.1 — resolve simulator validation gaps

Project: `f1-ai-quantum-strategy`. This is a focused follow-up within Stage 3 of the ten-stage dossier, not authorization for Stage 4. Implement necessary repairs and produce reviewable evidence. Do not simply relabel existing gates PASS.

## 1. Scope and existing evidence

Read current project instructions, status, the v3.1 dossier's simulator/deadline requirements, `SIMULATOR_MODEL.md`, `SIMULATOR_SELECTION.md`, `SIMULATOR_VALIDATION.md`, `STAGE_3_REPORT.md`, the two development amendments, simulator source and tests. Inspect the raw mechanism results and receipts for run `e2258740-1d08-4427-8305-b149ed504a73` and source snapshot `26ed935ce0dbba00963bbe5766c77f1247fed491d2a9cf697f692c1cf5a4e6c1`.

The report records 64 admitted development checkpoints, zero replay discrepancies, eight diagnostic interventions and 68 passing tests. These are useful software checks. They do not by themselves answer the specific questions below.

Only local inspection, targeted fixes, development fixtures, bounded diagnostic reruns, source preservation and a local review bundle are authorized. Keep reserved scientific partitions unopened, protocol DRAFT, and hardware disabled. No IBM login or API key is needed. No QPU jobs, paid services, model fitting, QUBO/circuit implementation, GitHub push, or alteration of the earlier research project.

First determine whether each concern is an actual defect, a gap in the report, or an explicit modeling assumption. Reuse valid existing evidence where it answers the question. Do not rewrite a working subsystem merely to increase a test count. Preserve original reports and records; corrections get new versions with reasons.

## 2. Fuel uncertainty and the development amendment

The report says actual fuel is estimate plus an offset and is floored to horizon need when this is inside the uncertainty band. Inspect the exact implementation and `development_spec.fuel.v1`.

Document the joint generation model for public estimate, private actual fuel and error: distributions, support, dependence on the known horizon, and any clipping, truncation, rejection or resampling. A floor can place probability mass exactly at the minimum sufficient fuel and change the stated error distribution. It is not automatically invalid, but it must not remain described as an unchanged uniform or unbiased uncertainty model.

Check whether minimum fuel is computed from information available at initialization, a declared conservative bound, or private realized future consumption. Do not use future draws to repair the initial state invisibly. Distinguish an intentionally conditioned fictional corpus from an unconditioned physical population.

Choose and document a coherent provisional generation rule that guarantees the supported no-refueling domain where intended. Either retain a transparently specified conditioned distribution with its implications, or amend generation so sufficient fuel is sampled directly with a declared reserve and observation error. Do not force symmetric or unbiased error if the chosen conditional model does not have it. Label all parameters assumptions; this is not empirical fuel calibration.

Publish a small deterministic audit over the existing 64 specifications: public estimate, private initial fuel in development evidence, modeled need, error, and whether any correction/rejection occurred. Keep private values out of solver observations. Summarize correction/rejection counts, error range and any mass at the fuel threshold. Use a few hand-derived edge cases to test the distribution transformation and impossible-state rejection; another large sampling campaign is unnecessary.

If generation changes, version the amendment/configuration and create new linked development artifacts. Never overwrite the original Stage 2 specs or silently change the already reported Stage 3 population.

## 3. Temporal resolution and numerical accuracy

The restricted model uses tick-resolution overtaking. The report provides an extremely small free-track error but allows a 0.5-second race-time tolerance. Inspect whether that tolerance is justified for that oracle; a tolerance should reflect known numerical error and the quantity being checked, not simply be much larger than the observed residual.

Separate analytical-oracle tolerances from discretization sensitivity and physical model uncertainty. Define the numerical acceptance criteria before running the new comparison, record their rationale, and preserve failures. The following are provisional engineering gates, not team-supplied tolerances or a guarantee of research precision:

- For deterministic free-track cases with an analytic answer, derive a floating-point/truncation error allowance from the actual algorithm. If the model can meet a tight bound without time discretization error, do not keep 0.5 seconds merely because it passes.
- For a tick-based implementation, compare the configured step h, h/2 and h/4 on fixed inputs, policies and event-keyed draws. Do not redraw stochastic events when refining the step. If the relevant component uses exact event timing, demonstrate that property and refine any remaining tick-based components.
- Use an initial finest-pair target of 0.01 seconds for pit commitment, service start/end and rejoin event times where those events exist, and 0.05 seconds for car finish times in nondegenerate fixtures. These are conservative development targets, not validated campaign thresholds. Report maximum errors and whether the observed changes support convergence. Passing two levels alone does not prove convergence.
- Require stable legality, fallback decisions, event ordering and classification in nondegenerate controlled cases. Treat deliberately constructed ties/near-ties separately: report sensitivity and a declared ambiguity band; do not change tolerances or discard cases to hide a flip.

Use a fixed hash-selected panel of eight existing development episodes, one per family and four SC/four VSC where possible, plus the small boundary fixtures. Select before reviewing resolution-dependent outcomes. Report which quantities are absent/not applicable, not fabricated zeros. Do not sort traces differently at each resolution to hide event correspondence errors.

Repair an actual discretization defect or choose a justified finer default within resources. If an event or outcome remains materially resolution-dependent, report the limitation and leave the corresponding gate PARTIAL/FAIL. Do not present temporal instability as a measured strategy effect. Final campaign-level Monte Carlo and across-block precision remain later tasks.

## 4. Behavioral causal isolation

The current summary says no private tokens appear in observations and duration is unknown before release. That is necessary but not sufficient evidence that future state cannot affect a current policy.

Create paired complete states with identical past/current physical state, observations and revealed information. Change only an unrevealed future realization, such as SC release time after both comparison instants or a future rival/random event. Before either changed event is revealed, confirm identical serialized observations and identical decisions for the same policy seed. After revelation, causal divergence is allowed and should be demonstrated in one fixture.

Trace the actual policy call path and allowed inputs. A sanitized JSON output does not prove isolation if the policy also receives the full state, private RNG, future schedule, mutable back-reference or callable that reveals it. Enforce a narrow observation interface and test it. Include a spy/adversarial fixture that makes accidental private access fail conspicuously.

Do not demand identical observations after changing an already-realized physical quantity. The paired test must hold relevant history/current state fixed; document exactly what changes and why it is still future information at the comparison time.

Preserve fresh-process replay checks and branch isolation. If current evidence already contains this behavioral test, cite the exact records and source instead of rerunning an equivalent test unnecessarily.

## 5. Common commitment time and operational validity

Inspect the production deadline path, not only a standalone cutoff helper. Under the fixed registered menu and identical starting information, run two recommendations with different arrival times, both before the effective deadline. The race must advance under the same fallback, and the registered protocol must apply them at the same commitment epoch. Early arrival must not silently allow an earlier pit action.

Save a trace showing checkpoint time, nominal budget, absolute cutoffs, communication margin, effective end, result arrival, fallback evolution, validation time and actual action application time. Units/origins must align. Keep the documented exclusive arrival boundary if intentional, and test exactly at, just before and just after it. No missed pit-now command may silently become a later-lap pit.

Include one intervening observable event that invalidates a recommendation. Check that the fallback is still feasible at commitment and through the supported continuation. Closed-pit behavior may remain an explicit unsupported-input rejection if that is the declared domain; do not claim a modeled pit closure mechanism merely because a schema rejects it.

These are injected scenario delays, not measured quantum/cloud latency. If the simulator cannot represent the commitment protocol, classify its current capability as static-checkpoint only and block the operational deadline claim.

## 6. SC/traffic evidence and supported scope

Inspect the SC production equations and existing tests. A single reduction in aggregate gap sum does not establish correct per-car ordering, queue spacing or absence of instantaneous movement.

Add only missing targeted checks: no prohibited on-track passes under SC; nonnegative progress/elapsed time; finite catch-up; queue-spacing behavior from both above and below the target; pit exit into the controlled train; and restart with state continuity. Distinguish on-track ordering from legitimate pit-related order changes. The simplified unit-circle model can remain restricted, but its stated mechanics must hold consistently.

For VSC, verify the actual pace-control mechanism has no intentional SC bunching rule. Do not impose identical gaps as a universal invariant when heterogeneous speeds, pit stops or other causal mechanisms would change them. Include a heterogeneous fixture if current tests only use identical cars.

Retain the independent shared-crew oracle. Add an end-to-end pit example only if the existing production test does not establish that service waiting actually propagates into rejoin/continuation time. Test time effects directly; do not require a fixed rank improvement/deterioration where traffic could change it.

Document exactly which simulator mechanisms are verified and which are stylized assumptions. A useful synthetic benchmark is possible, but code consistency is not physical or real-world validation. Do not label the model F1-calibrated or operationally validated.

## 7. Upstream-selection wording and resource reporting

The selection report says the legacy dependency pins need a separate unsupported environment. Separate facts from inference: the old pins are not the current project's working stack; no modernized minimal adapter was executed; adopting one was an engineering choice not pursued. Unless actually investigated, do not claim that all supported modern ports/adapters are impossible. The restricted independent model remains allowed by the dossier; this follow-up does not require rebuilding the project on TUM.

Resource compliance is currently unmeasured for RAM. Add a lightweight, documented memory observation during the new check plan and a practical stopping mechanism against the configured ceiling. Report what is measured: peak/current RSS, parent versus worker scope, sampling interval and platform units. One worker alone does not prove memory use stayed below 60%. Do not claim a hard instantaneous guarantee from periodic sampling.

Retain one worker initially and the existing 30-minute total simulator-execution limit for this follow-up. If the targeted work cannot complete within that limit, preserve partial evidence and report the remaining risk. Do not substitute more scenarios for the specific missing checks or open a reserved split.

## 8. Evidence, review bundle and stop point

Create a ledger-backed `simulator_followup` plan or equivalent, with stable scope/config/source identity, resumability and receipts. Record deterministic selections, criteria before execution, all attempted resolutions, failures, repairs and code/config changes. If production behavior changes, supersede the affected Stage 3 evidence explicitly and rerun the affected checks on the new source. Run shared regressions once after integration.

Save `docs/STAGE_3_1_REPORT.md` and update model/validation/selection documents with dated changes, preserving the earlier version through the evidence/version history. Completion requires the targeted gates to be evidenced, not just the test command to exit zero.

Also create a small local `review/STAGE_3_1_REVIEW.zip` for the user to upload to ChatGPT. Whitelist the current simulator source and its necessary in-project helpers, relevant tests/fixtures, package metadata/lock, simulator/generator/interface/run-plan configurations, the two amendments, model/selection/validation/follow-up documents, and machine-readable targeted results/receipts. Include a manifest with SHA-256 for every member and instructions identifying the exact checked snapshot and how to rerun the targeted checks. Include small fictional development inputs needed by those checks when appropriate.

Do not include `.git`, virtual environments, package caches, credentials, account files, environment-variable dumps, unrelated projects or reserved evaluation data. Scan the selected members for secrets without printing any matched secret. If a check needs an omitted file, name that dependency and its reason instead of claiming the bundle is self-contained. This is local packaging only; do not upload it or push it automatically. The user will attach it for review.

Return and save:

```text
STAGE_3_1_STATUS: COMPLETE | PARTIAL | BLOCKED
CHECKED_SOURCE_COMMIT_AND_SNAPSHOT:
FUEL_MODEL: retained/amended, distributions and correction counts
RESOLUTION_PANEL_AND_CRITERIA:
RESOLUTION_RESULTS: maximum errors, order/rank/legality flips, ambiguity cases
BEHAVIORAL_LEAKAGE_CHECK:
COMMON_COMMITMENT_CHECK:
SC_VSC_TRAFFIC_CHECKS:
UPSTREAM_SELECTION_WORDING_CORRECTED_OR_JUSTIFIED:
MEMORY_MEASUREMENT_SCOPE_AND_PEAK:
REGRESSIONS_AND_FAILURES:
SUPERSEDED_STAGE_3_EVIDENCE:
RUN_IDS_AND_RECEIPTS:
SUPPORTED_DOMAIN_AND_REMAINING_LIMITATIONS:
STAGE_4_PREREQUISITES: PASS | PARTIAL | FAIL, with reasons
REVIEW_BUNDLE_PATH_AND_MANIFEST:
RESERVED_PARTITIONS_MATERIALIZED: actual state, expected none
SCIENTIFIC_PROTOCOL: DRAFT
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: actual count, expected 0
QPU_ACCOUNT_QUERIED: false expected
PUSH_PERFORMED: false expected
```

Stop after saving the report and review bundle. Do not start Stage 4. The next prompt follows review of these specific findings; a successful follow-up is not permission to claim novelty or scientific performance results.

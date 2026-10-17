# Continuation contract draft — archive the intended empirical study

**DRAFT_NOT_AUTHORISED_FOR_EXECUTION**

This draft is the contract for recommended route 3 in `docs/POST_PHASE_6_RESEARCH_DISPOSITION.md`. It is not an experiment, not a Phase 6 restart, and not Phase 7. Nothing in this file authorises training, tuning, calibration, final-test access, a simulator change, a new admission, a miniature outcome-bearing pilot, QPU use, or spending.

## Starting source

- Evidence commit: `53ce10d187c2140511c7419863b5447119496a77`
- Reviewed source named by the closure receipt: `885f1adffb3b65865dbc752c9b0ca0442eb8fd52`
- Admission timings were produced at `dc2996733a6161111f10664070e55a291fe2da0b`
- Start commit of run `fc5f0e00-d9e0-4f89-9eea-498461094969`: `dcfe1cde7f02643d7a2d258d961e7ce2b4e62461`
- No descendant of the evidence commit existed on `origin/main` when this draft was written

## Work this draft allows after a future authorisation

Only preservation and claim control:

1. Leave `evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969/` byte-for-byte, including `FINAL_VERIFY.json` and `0B697910_EXPECTED_FAILURE.json`.
2. Leave historical evidence byte-for-byte: `evidence/stage5/`, `evidence/stage6/bd83cb22-…`, `evidence/stage6_corrected/`, `evidence/stage6_a2_residual/`, `evidence/a3/`, and `evidence/stage6_a4/` runs `09806343-…`, `3de109c7-…`, `0b697910-…`, and `fc5f0e00-…`.
3. Keep the recorded status `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`, `SELECTED_DESIGN=NONE_RESOURCE_LIMIT`, Gate E `UNCLAIMED_RESOURCE_LIMIT`, Gate F `FAIL`.
4. Point future readers to `docs/POST_PHASE_6_RESEARCH_DISPOSITION.md` for the present-tense interpretation `RESOURCE_STOP_PARTIALLY_SUPPORTED_WITH_DOCUMENTED_GAPS`.
5. Do not delete, stash, or rewrite unrelated dirty worktrees.

No source, config, simulator, model, protocol, or readiness-flag edit is part of this draft.

## Immutable evidence

The closure package under `evidence/stage6_a4/fc5f0e00-d9e0-4f89-9eea-498461094969/`, the validated closure report, Designs F and R, the resource amendment, and `docs/PHASE_6_0B697910_INVALIDATION.md`. Unit-ledger identities verified at review:

- `UNIT_LEDGER_R.json` = `UNIT_LEDGER.json` = `OPERATION_LEDGER.json` = `f1b4ecb97ad4750772845582943c3b102122221bdfb59ae8bcdeaae31ee34af8`
- `UNIT_LEDGER_F.json` = `2d31a6cf1eb288d5dfb7abe85b76ec6521ca90155211a59d8b64ce69d4c241a0`

## Acceptance criteria if this draft is later authorised

- Historical Phase 6 status string remains `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT_VALIDATED`.
- `PHASE_7_DESIGN_READY` remains false and no Phase 7 artifact is created.
- Train/tune/calib executed parents remain 0/120, 0/80, and 0/24.
- The two ledger hashes above still match.
- No new outcome JSONL is created for the registered panel.
- Claims stay inside the limits below.

## Resource assumptions and uncertainty

The current envelope stays in force: 86,400 CPU-seconds, 11,520 seconds admission wall, 14,400 seconds campaign wall, and at most 60% of RAM, with checkpoint-bounded units. Published Design R is 384.9285955196378 CPU-hours and 110.15570635070854 wall-hours. Published Design F is 1,068.986018576433 CPU-hours and 305.9136456109589 wall-hours. Corrected sensitivities are lower and still over both caps; see the disposition. This draft does not adopt the corrected figures as a new budget and does not relax the caps.

## Outcome-blind design selection

No design is selected. `NONE_RESOURCE_LIMIT` stands. Selection must not be reopened by effect signs, because no registered outcomes exist. A future route 1 or route 2 authorisation would have to restate the selection rule before any outcome is opened.

## Claim limits

Allowed after archival:

- Local simulator mechanism description.
- Engineering record of a resource stop on this implementation.
- The statement that registered Designs F and R do not fit the stated envelope on the measured configuration, with the accounting gaps in the disposition.

Not allowed:

- Quantum advantage, F1 calibration, hardware readiness, or a verified novel algorithm.
- A null result, or any claim that quantum candidates cannot help.
- Superiority, including any use of zero proxy headroom as if it were a downstream simulator result.
- Treating the clean-extract miniature, the parity panel, or the `0b697910` diagnostic as confirmatory Gate E or Gate F on the 120/80/24 panel.
- Publication of a results paper from this corpus.

Existing literature status remains the unresolved / insufficient record in `docs/STAGE_6_NOVELTY_COMPARISON.md`. This draft does not add bibliographic verification.

## Required new authorisation

This file does not authorise itself. A later user prompt must explicitly say that the empirical study is archived under the current constraints. Choosing route 1 (separate simulator-performance project) or route 2 (different resource envelope) is a different prompt and voids this draft rather than extending it.

## Stop conditions

Stop immediately if work would open a registered parent outcome, materialise final-test or shift outcomes, resume `e85ee977`, `41c28597`, `fcbb3e38`, `3de109c7`, `09806343`, `0b697910`, or `fc5f0e00`, submit a provider job, spend money, or rename a recovery run as Phase 7. Feasibility is not permission.

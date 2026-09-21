# A3 invalidation and A4 protocol amendment

**Disposition:** A3 run `a5fdb488-9a90-47f9-a4f5-7f77a74180a6` is preserved as an **unsuccessful implementation attempt**. Its effect, offline-headroom, dispatcher, Gate E, and Gate F results are **superseded and are not scientific evidence**. A3 causal-interface smoke checks may be retained only where independently valid. Phases 1–4 remain closed. Phase 5 A2 findings remain historical; transfer to A4 must be revalidated.

This document cites live A3 source. It is not a copy of the prompt’s defect list without confirmation.

## Independently confirmed A3 defects

1. **`decide_from_observation` executes the first portfolio member.** In `src/f1q/a3/loop.py` (`decide_from_observation`), the executed plan is `port["downstream_candidates"][0]["plan"]`. Combined with `assemble_portfolio` in `src/f1q/a3/agents.py`, which places classical candidates first (`merged = classical[:equal_k]`) and **appends** quantum rows up to `equal_k * 2`, `always_hybrid_c0` normally executes the same first classical plan. Quantum candidates are not downstream-evaluated for selection.

2. **Stated equal candidate budget is not implemented.** `assemble_portfolio` can retain up to twice `equal_k` unique plans. A4 requires replacement of classical slots so that every arm has exactly K unique downstream slots including the mandatory fallback.

3. **Offline reference is assigned, not measured.** In `src/f1q/a3/campaign.py`, `offline_plan_loss = cl["mean_loss"]` and `classical_matches_offline` is incremented whenever `menu_fully_enumerated = True`. Equality is by construction.

4. **Later-information-set variables do not affect the race.** `policy_to_simulator_plan` (`src/f1q/a3/problem.py`) writes `contingent_completion` from `LATER_INFO` but only `CURRENT_INFO` actions enter the simulator plan. Forecast scenarios `forecast_short` / `forecast_long` do not create distinct executable contingent decisions.

5. **Action domain is continue vs one preferred pit (or delay).** `build_menu_and_instance` truncates with `acts[:2]`. It omits the dossier’s normal delay-1, delay-2, and eligible compound/set alternatives as a full menu.

6. **Anchors are listed, not optimised.** `execute_campaign` records anchor IDs in partitions/freeze. There is no loop fitting C0/C1 donors on the 24 anchors.

7. **`reduced_execution_subset(..., per_family=1)`** in `src/f1q/a3/partitions.py` preselects 8 blocks per split and hard-codes a 45-minute shortfall reason. The recorded A3 campaign wall was about 178 seconds. No measured preflight justified that reduction.

8. **Ridge labels are circular.** Training labels are `classical_only` minus `always_hybrid_c0` while hybrid executes the same first classical plan (defect 1), producing near-zero labels and `classical_only` dispatch.

9. **Random default angles.** `default_params` in `src/f1q/a3/loop.py` draws `standard_normal` gammas/betas per instance rather than a fitted A3 donor bank with the stated anchor budget.

10. **Eight calibration blocks and eight worlds** do not establish Gate F. Per-world losses are not retained for the primary comparison (`pilot_blocks.json` stores means). Square-root extrapolation is not a precision study. `PASS_WITH_LIMITATIONS` was used despite the failed minimum.

11. **Verifier** (`src/f1q/a3/verify.py`) checks internal artifact consistency. It does not test portfolio treatment separation, actual offline optimisation, equal downstream budgets, or execution of every encoded decision variable.

12. **Report vs test-count mismatch.** `docs/PHASE_5_6_SCIENTIFIC_REDESIGN_REPORT.md` states targeted tests “16 passed before campaign” for `tests/a3/test_a3_core.py` and `tests/stage6/test_residual_histograms_noise.py`. Those files contain 3 and 5 pytest functions respectively (8 cases). The 16/16 figure is the **artifact verifier** check count, not pytest.

## A4 amendment (operational)

A4 is a causal **checkpoint candidate-generation and downstream-reranking** benchmark for a dry-weather two-car SC/VSC pit decision. It is not a fake multi-epoch policy. Encoded variables are current executable choices only.

Key question: under the same observable checkpoint, deadline, and downstream simulation-evaluation budget K, can an AI-gated portfolio containing C0 or C1 quantum-generated legal candidates improve independent simulated team loss over the strongest tuning-selected classical portfolio—and when is quantum participation unnecessary or harmful?

A4 requires: full legal action menu; matched K with replacement not append; disjoint planning/evaluation banks; real offline finite-simulation references; fitted donors on all 24 anchors; measured preflight before reducing optimiser evaluations; all 24/120/80/24 parent blocks executed; independent verifier that recomputes.

Machine-readable companion: `evidence/stage6_a4/<run_id>/A3_INVALIDATION.json` and `PROTOCOL_AMENDMENT_A4.json`.

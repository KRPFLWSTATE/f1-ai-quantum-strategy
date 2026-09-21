# A3 protocol freeze (calibration pilot — not final-test authorised)

**Status:** `A3_CALIBRATION_PILOT_PREDECLARED`  
**Evidence:** `evidence/a3/a5fdb488-9a90-47f9-a4f5-7f77a74180a6/protocol_freeze.json`  
**Written before opening calibration outcomes:** true  
**Source commit at freeze:** `d05f9d3099eddd693b244c0258ca5a185c8201a1`

## Frozen

- Architecture: A3 causal rolling-horizon (not A2 revealed-duration)
- Primary estimand: mean paired block difference `classical_only_loss − safely_dispatched_hybrid_loss` on independent simulator `team_rank_loss`
- Worlds: start 8/checkpoint (predeclared); 8192/32768 by extrapolation only
- Arms: classical_only; safely_dispatched_hybrid; always_hybrid_c0; threshold_rule
- Random banks: fitting / online_scoring / evaluation; event-keyed CRN
- Final-test: 80 blocks registered by ID hash; outcomes unopened
- QPU: forbidden
- Gate E does **not** require a positive quantum result

## Reduced execution (not full N)

Executed 8/24 anchors, 8/120 train, 8/80 tune, 8/24 calib (1 block/family). Shortfall recorded in `reduced_execution.json`. Do not relabel as the full plan.

## Unresolved / blocked

- Quantum marginal uninformative on the checked enumerable menu (classical matches offline)
- Phase 7 not authorised
- Hardware / IBM noise
- Final-test analysis

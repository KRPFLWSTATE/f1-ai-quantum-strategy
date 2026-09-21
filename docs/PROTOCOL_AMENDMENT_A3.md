# Protocol amendment A3 — pre-final-test architecture change

**Status:** dated amendment, 2026-09-21  
**Does not rewrite the dossier PDF.**  
**Does not reopen final-test.**  
**A2 is not an unchanged continuation under A3.**

## Why a redesign was required

Architecture A2 is a restricted synthetic scenario-tree with SC/VSC duration revealed at epoch 1. Stage 6 (corrected run `2a3fb275-…`) verified:

- exact classical enumeration is timely on the checked domain → `DEVELOPMENT_HEADROOM: ZERO`
- best-of-pool normalised regret is identically 0 (saturated)
- Gate E `FAIL_FOR_INTENDED_CONTRIBUTION` for the intended AI–quantum–F1 contribution
- operational causal readiness false (no observation → commitment → continuation → independent evaluator path)

Those are reusable negative results. They are not repaired by relabelling A2 as operational.

## Reusable A2 findings (keep)

- Phases 1–4 closed engineering lineage; do not resume `e85ee977` / `41c28597`
- Phase 5 C0/C1 executable circuits, repaired C1 prep, frozen donors under `e6b3588b-…`
- Shot-accounting correction (1024 draws, no Hilbert cap)
- Logical-gate depolarizing sensitivity panel (synthetic ≠ IBM)
- Zero proxy headroom on A2 instances
- Final-test seal; `QPU_EXECUTION_AUTHORISED: false`

## Non-transferable as A3 confirmation

- A2 selector weights, NN tables, and calibration IDs (`phase6.calib.*`)
- A2 revealed-duration features and QUBO-as-objective scoring
- A2 best-of-pool regret as a primary operational endpoint
- Any claim that A2 calibration confirms A3

A2 donors may be used only as **initial angle seeds**. Every A3 fit has its own parameters, eval history, budget, and provenance.

## New estimands and comparators

Primary A3 estimand (predeclared): mean paired block-level difference in **independent simulator loss**

`classical_only_loss − safely_dispatched_hybrid_loss`

Positive favours dispatched hybrid. A negative or zero boundary result is acceptable if operationally meaningful. Proxy QUBO ties and exact proxy optima are **not** quantum improvement.

Comparators: always classical; always hybrid C0/C1; fixed circuit; NN transfer; random donor; transparent threshold rule; offline full-menu reference (labelled offline).

## Fresh partitions

A3 IDs use namespace `a3.{anchor,train,tune,calib,finaltest}.*`. Planned: 24 anchors, 120 train, 80 tune, 24 calib, 80 final-test **registered by count and hash only**. Final-test outcomes are unmaterialised and unopened. A2 IDs/seeds/outcomes are development history only.

This campaign executed an 8-family-balanced reduced subset (1 block/family per split) because of the 45-minute local compute ceiling. Shortfall is recorded; it must not be relabelled as full N.

## Permitted claims

- A3 implements a real causal simulator decision path (verified by named adversarial checks)
- A2 residual histogram and native-basis noise corrections (new evidence directory)
- Honest UNRESOLVED/FAIL/uninformative outcomes

## Prohibited claims

- First / absolute novelty
- Quantum advantage
- Real-team or F1 performance
- Phase 7 started or authorised
- A2 models are A3 models
- Final-test results
- Native-basis IBM noise (synthetic only)

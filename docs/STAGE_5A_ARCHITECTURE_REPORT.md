# Stage 5A — Architecture Decision Report

**Status:** PASS (architecture selected; no execution authorised)  
**Base commit:** `1bdcb88a797e17dc9e29df262b6e02a1c17a1a51`  
**NOVELTY_STATUS:** `PROPOSED_NOT_LITERATURE_VERIFIED`  
**QPU_EXECUTION_AUTHORISED:** false  
**Evidence class:** architecture decision / experiment contract only — not simulated, not measured, not a superiority claim.

## Executive decision

Select **A2 — Two-car multi-epoch scenario-contingent strategy-policy optimisation** under uncertain SC/VSC duration and restart conditions, with non-anticipativity, shared pit-crew / double-stack costs, tyre availability, operational deadlines, and a deterministic classical safe fallback.

Reject continuing Stage 4 single-checkpoint proxy QAOA as a superiority design: Stage 4 bounded closure recorded **`PROXY_HEADROOM: ZERO`** (64/64). Genuine headroom must come from **F1 decision complexity** (multi-epoch contingent policies), not from manufacturing hard constraints or hiding exact classical enumeration.

## Context (evidence-labelled)

| Claim | Label |
|-------|--------|
| Stage 4 engineering closed with documented limitations | verified by Stage 4 Closure Report v2 |
| Legacy exhaustive Gate C PARTIAL; archived; do not resume | verified by `docs/STAGE_4_CLOSURE_ERRATUM.md` |
| Exact legal enumeration removes all proxy headroom on development checkpoints | verified by Stage 4 bounded closure (`PROXY_HEADROOM: ZERO`) |
| Selected Stage 5 architecture creates optimisation headroom | **proposed** (not yet implemented or measured) |
| Quantum advantage / speedup / practical superiority | **unsupported** — not claimed |
| Literature novelty of QAOA / mixers / warm-starts / allocation | prior art exists (dossier §); contribution remains **PROPOSED_NOT_LITERATURE_VERIFIED** |

## Options matrix (≥3 legitimate Phase 5 architectures)

| ID | Architecture | F1 operational value | Combinatorial growth source | AI role | Quantum role | Decision vars / constraints | Non-anticipativity / causal validity | Logical vars / qubits + interactions (ESTIMATED) | Classical exact + heuristic baselines | Local sim + current IBM feasibility | Scientific falsifiability | Principal failure modes |
|----|--------------|----------------------|-----------------------------|---------|--------------|-----------------------------|--------------------------------------|--------------------------------------------------|--------------------------------------|--------------------------------------|---------------------------|-------------------------|
| **A1** | Single-checkpoint two-car QUBO/QAOA on Stage 4 proxy | Recognisable pit-now / delay / continue decision | Per-car action menu × joint pair term | Optional donor/allocator only | Sample / optimise one-hot joint plan | Stage 4 binaries + one-hot penalties | Single information set; no multi-epoch tree | ESTIMATED: tens of logical qubits (as Stage 4 menus); sparse pair couplings | Exact legal table + MILP (already dominate) | Local exact trivial; IBM irrelevant for superiority | Would falsify only sampling quality, not optimisation value | **Zero headroom** (observed); superiority design impossible |
| **A2** ★ | Multi-epoch scenario-contingent joint strategy policies | SC/VSC duration uncertainty, restart, double-stack, inventory, deadlines | Scenario tree × epochs × joint actions × inventory/crew | Scenario / outcome / risk estimates (calibrated probabilities); **not** the optimiser | Combinatorial **policy selection** / structured QUBO-QAOA on non-anticipative policy encoding | Policy binaries per information set; one-hot; inventory; crew timing; non-anticipativity equalities | Explicit information sets; no look-ahead to private τ or future draws | ESTIMATED: tiny ~20–40 logical; small ~60–120; medium ~150–400; larger ≫500 (see ladder) | Exhaustive (tiny/small), MILP/CP-SAT, local search, random feasible | Tiny–small local classical exact; medium local QAOA sim; larger classical heuristics only; current IBM: small–edge of medium only | Null: no better than classical under matched budget; headroom gate before any superiority claim | Model misspecification; anticipative leakage; AI overconfidence; circuit noise; classical still wins |
| **A3** | Multi-stop green-flag sequence planning (no scenario tree) | Multi-stop tyre strategy under known green | Stop-count × lap slots × compounds × sets × crew | Tyre/fuel residual predictors | Sequence QUBO | Sequence binaries + inventory + crew | Weaker: less SC/VSC causal structure | ESTIMATED: similar growth to A2 without scenario factor (often smaller) | Same classical suite | Similar to A2 but less operational headroom from uncertainty | Falsifiable on sequence cost | May recreate near-enumerable menus; weaker link to Stage 4 SC/VSC domain |
| **A4** | Multi-agent rival-reactive game at checkpoint | High operational colour | Joint team × discretised rival responses | Rival-intent / response models | Game-form QUBO / sampling | Huge joint action space | Hard: rival private info | ESTIMATED: often ≫10³ logical without aggressive reduction | Exact rarely available | Poor exact baselines; IBM infeasible for honest instances | Weak without exact small games | Intractable verification; hidden AI=optimiser bleed; unfalsifiable “advantage” |

★ = selected.

### Rejected / not selected

- **A1:** fails genuine-headroom criterion (Stage 4 measurement).  
- **A3:** legitimate but secondary; weaker SC/VSC non-anticipativity story than A2.  
- **A4:** fails exact-small-instance and clean verification requirements for Stage 5B entry.

## Selected architecture (A2) — formal outline

### Problem (proposed)

Given a causal checkpoint observation \(z\) (solver-visible only), a finite scenario set \(\mathcal{S}\) for unresolved SC/VSC duration / restart conditions with **AI-supplied** probabilities \(\hat{p}(s\mid z)\) (or calibrated risk functionals), and a finite epoch / information-set index \(t = 1..T\):

Find a **non-anticipative joint strategy policy** \(\pi\) for the two selected cars that minimises expected (or risk-adjusted) team analytical / simulated loss subject to:

1. **Causal validity:** decisions at information set \(I_t\) use only observables available in \(I_t\) (no private \(\tau\), no future pit draws).  
2. **Action language:** at each admissible epoch, each car selects from an admitted menu (pit_now / delay_1–2 / continuation + compound/set) consistent with Stage 4 action-model lineage, extended only as needed for multi-epoch inventory.  
3. **Shared crew:** double-stack modelled as finite wait cost from service-interval overlap (not invented hard prohibition).  
4. **Tyre availability / obligations:** unused sets, compound obligations, commitment residuals.  
5. **Operational deadline:** commitment cutoff / budget \(B\); late quantum output does not move the registered epoch — classical fallback applies.  
6. **Classical safe fallback:** feasible incumbent revalidated at commitment (dossier-compatible).

### How genuine headroom is created

Stage 4 zero headroom applies to **one information set, one joint plan table**. A2 lifts the decision object to a **policy over a scenario tree**. Even when each leaf menu is classically enumerable, the **non-anticipative policy space** grows with scenarios × epochs × joint admissible actions, so exact classical dominance is no longer automatic at small–medium ladder rungs. Headroom is therefore from **F1 contingent decision structure**, not from deleting classical baselines or inventing illegal stacking rules.

### F1 value

Recognisable race-operations problem: under SC/VSC, teams must choose contingent pit/continue policies for both cars without knowing duration or restart, while managing double-stack delay, tyre sets, and a hard radio/commitment deadline.

### Boundaries

| Layer | Responsibility | Must not do |
|-------|----------------|-------------|
| **AI** | \(\hat{p}(s\mid z)\), calibrated outcome/risk estimates, optional latency/success predictors for allocation | Solve the combinatorial policy; replace exact references; train on held-out test |
| **Quantum** | Sample / search a clearly encoded combinatorial policy-selection QUBO (or constraint-preserving variant) under matched shot/time budgets | Claim advantage without headroom + classical baselines; fit variational angles on QPU in Stage 5B without separate auth |
| **Classical** | Exact tiny/small; MILP/CP-SAT; heuristics; random feasible; deterministic fallback; scoring | Be hidden when it attains optimum; be replaced by AI silently |

### Size ladder (all figures ESTIMATED — not measured)

| Rung | Scenarios \|S\| | Epochs T | ESTIMATED decision / logical vars | ESTIMATED feasible-policy or search-space size | ESTIMATED logical qubits | Constraint / coupling burden (ESTIMATED) | Classical verification |
|------|----------------:|---------:|----------------------------------:|-----------------------------------------------:|-------------------------:|------------------------------------------|------------------------|
| Tiny | 2 | 2 | 24–40 | \(10^3\)–\(10^5\) policies / encodings | 24–40 | One-hot + few non-anticipativity + soft crew | Exhaustive + MILP |
| Small | 4 | 3 | 60–120 | \(10^6\)–\(10^9\) (policy space; reduced encodings lower) | 60–120 | Dense cross-car + scenario linking | Exhaustive if reduced; else MILP/CP-SAT + heuristic |
| Medium | 8 | 4 | 150–400 | Often beyond full exhaustive | 150–400 | Heavy; needs reduction / decomposition | MILP/CP-SAT time-capped + strong heuristics; no claim of exact |
| Larger | 16 | 5+ | ≫500 | Heuristic-only regime | ≫500 | Exceeds comfortable NISQ mapping | Heuristic + random + gap certificates only |

**IBM / local-sim (ESTIMATED, qualitative):** tiny–small: local statevector / shot sim feasible for shallow QAOA; medium: noisy sim only with aggressive depth limits; larger: not current-hardware-honest without decomposition. No provider jobs in Stage 5A.

### Quantum formulation comparison (recommendation)

| Formulation | Role | Testable benefit? | Recommendation |
|-------------|------|-------------------|----------------|
| Penalty QUBO + standard QAOA (C0/C1 lineage) | Baseline encoding of policy selection + one-hot penalties | Compare feasible yield, best-of-pool loss vs classical at matched budget | **Primary Stage 5B circuit approach** |
| Warm-start QAOA | Seed from classical incumbent / LP relaxation | Must beat cold QAOA and classical incumbent on useful-candidate yield | **Secondary**, only if incumbent ≠ proven global on that rung |
| Constraint-preserving / feasibility-preserving mixer | Mix inside one-hot (+ optional policy-justified paired exchanges) | Mechanism: preserve feasibility; requires unitary checks, feasible-graph connectivity, comparison to penalty QAOA, falsification if useful yield↓ or cost↑ at matched budget | **Optional substudy**; admit only if hard constraints are genuine (one-hot / non-anticipativity), **not** invented no-stack rules |

Custom mixer admission (dossier-aligned): published transition semantics; ideal zero infeasible amplitude to tolerance; connectivity matches feasible graph; transpiled resources within registered bounds; development trade-off vs penalty QAOA. Failure → retain report; keep simpler circuits.

### Risks and limitations

- Estimates only; Stage 5B must measure actual sizes on frozen encodings.  
- AI probability error can dominate “optimisation” gaps — must report separately.  
- Non-anticipativity bugs create spurious quantum-looking gains.  
- Medium+ rungs may remain classically practical with MILP — useful negative result.  
- No claim of quantum advantage, speedup, or operational deployment readiness.  
- Stage 4 evidence frozen; A2 must not reopen Gate C matrix runs.

### Stage 5B entry criteria

See `docs/STAGE_5A_EXPERIMENT_CONTRACT.md`. Summary: frozen encoding of A2 tiny+small; exact classical references green; headroom gate **non-zero** on declared development instances; simulator-before-any-hardware; `QPU_EXECUTION_AUTHORISED` remains false until a later explicit prompt; no IBM credentials in-repo; zero spend.

### Decision record

```text
STAGE_5A: PASS
SELECTED_ARCHITECTURE: A2_multi_epoch_scenario_contingent_strategy_policy
GENUINE_HEADROOM_SOURCE: non_anticipative_scenario_tree_policy_space
NOVELTY_STATUS: PROPOSED_NOT_LITERATURE_VERIFIED
QPU_JOBS: 0
```

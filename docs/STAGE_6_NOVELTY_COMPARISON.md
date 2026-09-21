# Stage 6 Novelty Comparison (Corrected reassessment)

**GATE_E_SCIENTIFIC_VALUE:** `FAIL_FOR_INTENDED_CONTRIBUTION`  
**Prior label withdrawn:** `PASS_FOR_DEFINED_SCOPE`  
**GATE_E_NARROW_MECHANISM_ARTIFACTS:** `PASS_WITH_DOCUMENTED_LIMITATIONS`  
**F1_CONTRIBUTION_STATUS:** `INSUFFICIENT`  
**Machine artifact:** `evidence/stage6_corrected/2a3fb275-6c37-4bbc-bdb4-addede80b5c3/novelty_comparison.json`  
**Search date:** 2026-09-21 (WebSearch + dossier bibliography; access class noted per source)

This document updates `docs/STAGE_6_NOVELTY_COMPARISON.md` conclusions without deleting the historical Phase 6 narrative.

## Method

Targeted WebSearch for F1 pit-stop optimisation / learning / QUBO / QAOA (2023–2025). Full text fetched where tool returned PDF content (selected theses/preprints). Many journal articles remain **abstract/metadata only**. Unavailable dossier-only citations remain unavailable.

## Theme comparisons

### 1. F1 DP / classical race optimisation

- **Nearest:** Carrasco Heine & Thraves (CEJOR 2023); Aguad & Thraves (EJOR 2024) — DP / Stackelberg game pit-stop strategies with yellow-flag uncertainty (abstract/metadata verified).
- **Also:** MILP/stochastic pit-stop theses; RL vs mathematical programming F1 strategy work (Zenodo/EJOR submission 2025; arXiv:2512.21570 PDF fetched — learning-based F1 strategies with energy/tyre/pits).
- **Our difference (proposed):** deadline-aware AI/quantum allocation over QUBO with learned donor selection and auditable interfaces.
- **Experiment testing value:** Phase 6 mechanism pilot on synthetic A2 — **does not** demonstrate motorsport decision value.
- **Fair comparator:** classical exact enumeration (timely) and DP/MILP race baselines (not yet operationally integrated).
- **Verdict:** classical F1 strategy literature is stronger on actual race decisions; our work does not displace it.

### 2. F1 QUBO / annealing

- **Nearest:** dossier bibliographic Kolstee (2026) entry (not independently re-fetched); generic QUBO tooling; MILP F1 simulation frameworks (not quantum).
- **Our difference:** C0/C1 circuit families + bank/selector under split discipline.
- **Verdict:** QUBO encoding of combinatorial decisions is not novel by itself; no F1 quantum advantage shown.

### 3. Learned race strategy / AI

- **Nearest:** RL/ML race-strategy literature (dossier citations; arXiv:2512.21570).
- **Our difference:** inspectable ridge donor ranking over a frozen parameter bank.
- **Verdict:** standard ML selection practice; held-out operational usefulness unsupported.

### 4. QAOA parameter transfer

- **Nearest:** Farhi et al. QAOA; warm-start / cross-problem transfer literature (abstract/metadata).
- **Our difference:** application framing under motorsport split constraints.
- **Verdict:** parameter transfer is not a new quantum algorithm; no held-out H2 claim.

### 5. Constraint-preserving mixers

- **Nearest:** Hadfield et al. XY / constrained QAOA (dossier [8]).
- **Our difference:** none claimed; C1 uses standard ring XY.
- **Verdict:** engineering legality only.

### 6. Algorithm selection / deadlines

- **Nearest:** metareasoning / algorithm-selection literature; dossier allocator requirements.
- **Our difference:** proposed integration with F1 causal checkpoints + quantum package.
- **Verdict:** runtime allocator **unimplemented**; deadline-aware claim incomplete.

## Contribution assessment (honest)

| Criterion | Result |
|-----------|--------|
| Zero demonstrated proxy headroom | Yes (blocks superiority) |
| Standard C0/C1 | Yes |
| Restricted synthetic observability (revealed duration) | Yes — not operational causal |
| Strong classical comparators timely | Yes |
| SC/VSC/tyre/traffic labels ⇒ validated motorsport coverage | **No** |
| Engineering cleanliness alone ⇒ research contribution | **No** |
| Adequacy for project AI–quantum–F1 objective | **INSUFFICIENT** |

**Surviving engineering artifact (not Gate E pass):** corrected shot-accurate mechanism tables and measurement-backed resource envelopes on the restricted A2 surrogate.

**Redesign before superiority:** do not manufacture classical failure; any enlargement must follow a justified motorsport decision requirement and retain strong classical comparisons plus causal observation→policy→commitment paths.

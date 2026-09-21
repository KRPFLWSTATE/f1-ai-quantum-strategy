# Stage 6 — Novelty / Gate E Comparison

**GATE_E_SCIENTIFIC_VALUE:** `PASS_FOR_DEFINED_SCOPE`

No absolute novelty or “first” claims. Abstract-only vs full-text access is labelled per source.

## f1_dp_classical: F1 DP / classical race optimisation

- **On the optimization of pit stop strategies via dynamic programming**
  - URL: https://doi.org/10.1007/s10100-022-00806-4
  - Access: `abstract_metadata_and_secondary_summaries`
  - Authors: Carrasco Heine, O.F.; Thraves, C.
  - Venue: Central European Journal of Operations Research, 2023
- **Optimizing pit stop strategies in Formula 1 with dynamic programming and game theory**
  - URL: https://doi.org/10.1016/j.ejor.2024.06.020
  - Access: `abstract_metadata`
  - Authors: Aguad, F.; Thraves, C.
  - Venue: European Journal of Operational Research, 2024, 319(3), 908–919
- **Their contribution:** Classical DP/SDP and Stackelberg-game pit-stop/compound strategies with yellow-flag uncertainty and competitor interaction; race-time / win-probability objectives.
- **Our proposed difference:** Deadline-aware AI/quantum allocation over QUBO encodings with learned donor selection and auditable causal checkpoint interfaces — not a claim to replace DP race optimisation.
- **Evidence needed:** Operational evaluator under live causal simulator + nonzero headroom OR a clearly scoped mechanism result that changes team practice (latency/yield/fallback).
- **Unresolved overlap:** Both address SC/VSC-aware strategy; classical DP remains the stronger F1-ops baseline.

## f1_qubo_annealing: F1 QUBO / annealing

- **Kolstee, S. (2026). Optimizing Formula 1 Pit Stop Strategies Using QUBO and Quantum Annealing — dossier [3]**
  - URL: docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf
  - Access: `dossier_bibliographic_entry`
- **A simulation framework for Formula 1 race strategy based on pit-stop optimization**
  - URL: https://optimization-online.org/2026/02/a-simulation-framework-for-formula-1-race-strategy-based-on-pit-stop-optimization/
  - Access: `full_text_pdf_fetched`
  - Authors: Borruso, M.; Avella, P.; Marino, M.
  - Venue: Optimization Online preprint, 2026
- **D-Wave Ocean docs: QUBO / BQM models**
  - URL: https://docs.dwavequantum.com/en/latest/concepts/models.html
  - Access: `full_text_docs`
- **Their contribution:** Discrete F1 strategy as MILP/simulation; dossier cites Kolstee (2026) QUBO/annealing F1 work; generic QUBO tooling for annealers.
- **Our proposed difference:** Explicit C0/C1 circuit families + learned parameter-bank donor selection under split discipline, with headroom gate before superiority claims. Dossier already disclaims 'first F1 QUBO'.
- **Evidence needed:** Held-out mechanism usefulness vs classical discrete solvers under matched budgets.
- **Unresolved overlap:** QUBO/Ising encoding of combinatorial race decisions is not novel by itself.

## learned_race_strategy: Learned race strategy / AI

- **Dossier §11/§16 runtime AI comparisons; dossier [4][5] RL race-strategy citations**
  - URL: docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf
  - Access: `full_text_dossier_v3_1`
- **Their contribution:** Broad RL/ML race-strategy literature exists; dossier requires fixed/NN/random comparators.
- **Our proposed difference:** Inspectable ridge donor ranking over a frozen parameter bank (not angle averaging).
- **Evidence needed:** Held-out H2 intervals on eligible operational or mechanism endpoints.
- **Unresolved overlap:** Learned policy selection over classical features is standard ML practice.

## quantum_param_transfer: Quantum parameter transfer / learned donor selection

- **Farhi et al. QAOA (arXiv:1411.4028) — dossier [7]**
  - URL: https://arxiv.org/abs/1411.4028
  - Access: `abstract_metadata`
- **Egger et al. Warm-starting quantum optimization — dossier [9]**
  - URL: https://quantum-journal.org/papers/q-2021-06-17-479/
  - Access: `abstract_metadata`
- **Nguyen et al. Cross-Problem Parameter Transfer in QAOA — dossier [11]**
  - URL: https://arxiv.org/abs/2504.10733
  - Access: `abstract_metadata`
- **Their contribution:** QAOA and parameter reuse / warm-start / cross-problem transfer methods are established.
- **Our proposed difference:** Application framing: audited bank + selector under motorsport split/causal constraints.
- **Evidence needed:** Improvement over fixed/NN/random on held-out eligible endpoints.
- **Unresolved overlap:** Parameter transfer itself is not a new quantum algorithm.

## constraint_mixers: Constraint-preserving mixers

- **Hadfield et al. Quantum approximate optimization with hard and soft constraints — dossier [8]**
  - URL: https://arxiv.org/abs/1709.03489
  - Access: `abstract_metadata`
- **Their contribution:** XY and related mixers preserve one-hot / feasible subspaces.
- **Our proposed difference:** None claimed as algorithmic novelty; C1 uses standard ring XY exchanges.
- **Evidence needed:** N/A for novelty; legality/yield is engineering evidence only.
- **Unresolved overlap:** C1 is a standard constraint-preserving construction.

## algorithm_selection_deadline: Algorithm selection / deadline-aware computation

- **Dossier §14–§15 runtime allocator / deadlines; metareasoning and algorithm-selection citations**
  - URL: docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf
  - Access: `full_text_dossier_v3_1`
- **Their contribution:** Algorithm-selection and anytime/deadline literature is mature outside F1.
- **Our proposed difference:** Proposed contribution is integration with F1 causal checkpoint + quantum package under spend constraints.
- **Evidence needed:** Implemented runtime allocator + measured end-to-end latency on operational evaluator.
- **Unresolved overlap:** Without allocator evidence, deadline-aware claim remains unimplemented.

## Contribution assessment

- Zero demonstrated proxy headroom: `True`
- Standard C0/C1: `True`
- Restricted synthetic observability: `True`
- Surviving scoped contribution: `True`

### Surviving research question

Within a restricted synthetic A2 circuit-mechanism scope: what are the legality yields, sample regrets, and resource envelopes of frozen C0/C1 + donor policies versus exact/uniform classical baselines under matched shot budgets — and which integration blockers prevent an operational F1 race-decision claim?

### Practical relevance

Practical relevance today is engineering: an auditable negative headroom result, repaired circuit provenance, and a blocked operational path until causal integration. This does not establish F1 performance value or quantum advantage.

### Redesign before full campaign

Before any superiority campaign: enlarge model until exact classical is not timely, or abandon H1 for a mechanism/boundary protocol amendment. Do not permanently replace the project's F1 objective with an unrelated toy benchmark.


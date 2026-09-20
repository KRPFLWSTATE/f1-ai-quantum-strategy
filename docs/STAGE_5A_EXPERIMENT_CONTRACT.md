# Stage 5A — Experiment Contract (preregistered)

**Binding for Stage 5B design.** No solver campaigns, circuits, simulator superiority trials, or QPU jobs are authorised by this document alone.  
**NOVELTY_STATUS:** `PROPOSED_NOT_LITERATURE_VERIFIED`  
**Architecture:** A2 — two-car multi-epoch scenario-contingent strategy-policy optimisation.  
**Base commit at Stage 5A:** `1bdcb88a797e17dc9e29df262b6e02a1c17a1a51`

## 1. Scientific object

Optimise / sample a **non-anticipative joint strategy policy** for two team cars under uncertain SC/VSC duration and restart scenarios, subject to shared crew wait costs, tyre availability, compound obligations, and operational commitment deadlines, with a **deterministic classical safe fallback**.

## 2. Hypotheses and nulls (freeze before any Stage 5B outcomes)

| ID | Statement | Null |
|----|-----------|------|
| **H0-headroom** | On the frozen tiny/small development encoding, exact classical references leave **nonzero** optimisation headroom relative to the registered incumbent/fallback | Headroom = 0 on all declared instances → **stop superiority path**; report and restrict to sampling/integration studies only |
| **H1** (primary, only if H0-headroom passes) | Under matched end-to-end time and resource budgets, the proposed quantum-inclusive generator + acceptance/fallback policy improves expected team loss vs the strongest classical policy selected on **tuning** data | No improvement (paired difference ≤ 0 within preregistered tolerance / CI rule) |
| **H2** (exploratory) | AI scenario/risk estimates improve downstream decision quality vs uniform or misspecified scenario weights, holding the optimiser fixed | No improvement |
| **H3** (exploratory, circuits) | Warm-start and/or constraint-preserving mixers improve useful feasible-candidate yield per unit execution cost vs penalty QAOA at matched shots/depth | No improvement / worse after cost accounting |

**Minimum worthwhile effect (proposed research threshold, not team preference):** freeze numeric Δ on the Stage 5B loss definition **before** viewing test outcomes (dossier suggests ~0.02 normalised team-rank loss as a prior research setting; Stage 5B must restate the exact frozen number). Sensitivity at neighbouring thresholds allowed only as secondary.

**No post-hoc metric substitution:** primary endpoint frozen here may be refined in Stage 5B **design** docs before any test peek; after peek, metrics cannot be swapped.

## 3. Metrics (preregistered families)

1. **Feasibility:** fraction of samples / candidates satisfying one-hot, inventory, non-anticipativity, and deadline-valid commitment checks (raw and, if used, repaired — repair reported separately).  
2. **Optimality gap:** vs exact optimum on tiny/small; vs best classical bound/heuristic on medium+.  
3. **Utility / regret:** expected (or risk-adjusted) team loss under frozen evaluation worlds; regret vs exact / vs best classical.  
4. **Deadline performance:** timely acceptance rate; late-arrival rate; fallback invocation rate.  
5. **Resource:** wall time split (compile / classical search / queue-wait / execution / postprocess); shots; logical→physical qubit map size; two-qubit gate count (when circuits exist).  
6. **AI calibration (H2):** proper scoring / calibration error of \(\hat{p}(s\mid z)\) on held-out scenarios — reported separately from optimiser gap.

## 4. Baselines (mandatory)

- Exhaustive legal / policy enumeration on tiny (and small when feasible).  
- Independent **MILP** and/or **CP-SAT** (free/open solvers only).  
- Strong classical **heuristics** (local search / greedy improvement) with exact evaluation of candidates.  
- **Uniform random** feasible policies.  
- Deterministic **classical safe fallback** (feasible incumbent revalidated at commitment).

Exact enumeration, when it finishes inside the operational deadline, is an **operational classical competitor**, not an offline-only oracle.

## 5. Ablations

- Scenario count and epoch depth (size ladder rungs).  
- AI probabilities vs uniform vs oracle (oracle = analysis only; not a deployable arm).  
- Penalty QUBA/QAOA vs warm-start vs (optional) constraint-preserving mixer.  
- With vs without soft crew pair costs.  
- Allocator: always-classical / always-quantum / margin-aware (dossier-style) — quantum arms only when authorised.

## 6. Shots, seeds, and partitions

- **Shots:** freeze per-arm shot budget in Stage 5B design before execution; no unbudgeted extra QPU shots.  
- **Seeds:** separate streams for scenario worlds, policy stochasticity, and sampler seeds; record all.  
- **Train / tune / eval separation:** AI components fit on training blocks only; tune thresholds on tuning; **eval/test sealed** until Stage 5B explicitly opens them. Do not materialise reserved scientific partitions in Stage 5A.  
- Common random numbers across arms where applicable.

## 7. Simulator-before-hardware gates

1. Encoding + classical references agree on tiny.  
2. Nonzero headroom gate (H0-headroom) on declared development set.  
3. Ideal/noisy **local** circuit simulation (when circuits exist) before any provider path.  
4. Hardware remains **`hardware_execution_enabled: false`** until a later prompt sets `QPU_EXECUTION_AUTHORISED: true`.  
5. Queue wait vs execution time accounted separately; queue time does not count as algorithmic superiority.

## 8. Separations (non-negotiable)

- **AI ≠ optimisation:** AI supplies probabilities/risk/latency estimates; classical/quantum solvers own combinatorial search.  
- **Proxy ≠ race truth:** analytical proxies and simulator evaluators remain distinct; neither is F1 calibration.  
- **Fallback causal:** late or invalid candidates never peek at hidden futures.

## 9. Negative results (useful by contract)

Useful negatives include: zero headroom on A2 tiny/small; classical MILP dominates within deadline; AI adds no value; warm-start/mixer fails cost-adjusted yield test; noisy/hardware yield collapses. Such outcomes **close** the corresponding claim path without forcing circuit elaboration for novelty labels.

## 10. Stage 5B authorisation conditions (exact)

Stage 5B may begin **only** when all hold:

1. User issues an explicit Stage 5B work-unit prompt.  
2. This contract and `docs/STAGE_5A_ARCHITECTURE_REPORT.md` remain the selected architecture (A2) unless a superseding Stage 5A revision is authorised.  
3. Implementation work is limited to **local** encoding, classical baselines, and (if authorised in that prompt) **local** circuit simulation — **no** QPU submission.  
4. `QPU_EXECUTION_AUTHORISED` remains **false**; no IBM credentials requested, stored, or used.  
5. Zero additional spending; no paid fall-through.  
6. Stage 4 evidence, closure ZIPs, and formulation gate paths remain **frozen** (no resume of `e85ee977` / `41c28597`; no `formulation_gate_c_closure_check`).  
7. Headroom gate protocol implemented before any superiority statistical test on sealed eval.

### Later QPU authorisation (Stage 5C+; not now)

Physical QPU jobs require a **separate** explicit user prompt that sets hardware execution authorised, defines shot budgets, device, and spend ceiling (default ceiling = 0). Until then: **qpu_jobs = 0**.

## 11. Out of scope for Stage 5A / immediate 5B

- Learned QAOA angle banks trained for superiority claims without separate authorisation.  
- Provider authentication or balance inspection.  
- Wet / red-flag / sprint mechanisms.  
- Claiming quantum advantage, speedup, or practical team superiority.

## 12. Contract checksum note

Integrity of this file is recorded in `docs/evidence/stage5a/STAGE_5A_VERIFY.json` after Stage 5A packaging.

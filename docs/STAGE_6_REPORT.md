# Stage 6 / Phase 6 — Local Mechanism Pilot, Precision & Resources, Gate E

**PHASE_6_COMPLETION:** `COMPLETE_WITH_DOCUMENTED_LIMITATIONS`  
**PHASE_6_ENGINEERING:** `PASS_WITH_DOCUMENTED_LIMITATIONS`  
**GATE_E_SCIENTIFIC_VALUE:** `PASS_FOR_DEFINED_SCOPE`  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `PASS_WITH_LIMITATIONS`  
**PROTOCOL_STATUS:** `BLOCKED_DRAFT`  
**ADMITTED_SCIENTIFIC_SCOPE:** `local_A2_circuit_mechanism_and_resource_estimation;restricted_synthetic_revealed_duration_surrogate;no_operational_race_decision;no_H1_superiority;no_QPU`  
**CAUSAL_OPERATIONAL_READINESS:** `False`  
**DEVELOPMENT_HEADROOM:** `ZERO`  
**SUPERIORITY_PATH_AVAILABLE:** `False`  
**PHASE_7_MECHANISM_READY:** `True`  
**PHASE_7_OPERATIONAL_READY:** `False`  
**PHASE_7_SUPERIORITY_READY:** `False`  
**FINAL_TEST_ACCESSED:** `False`  
**QPU_JOBS:** `0`  
**QPU_USAGE_SECONDS:** `0`  
**QPU_EXECUTION_AUTHORISED:** `false`

Evidence class: local ideal-circuit mechanism pilot + synthetic noisy feasibility panel + literature comparison.  
Not physically measured IBM noise. Not a held-out scientific superiority claim. Not actual F1 operational value.

---

## 1. Executive verdict

Phase 6 completed a **bounded local mechanism pilot** on an isolated 24-block calibration cohort (48 SC/VSC cases) using frozen Phase 5 corrected models/donors and repaired C1 circuits. Exact classical enumeration finishes inside the operational deadline on completed cases, so **proxy improvement vs exact is structurally zero** and the **superiority path remains unavailable**. Stage 3 causal/deadline interfaces validate on development fixtures, but the A2 experiment remains a **restricted synthetic revealed-at-epoch-1 surrogate** — **operational race-decision readiness is false**. Gate E is **`PASS_FOR_DEFINED_SCOPE`** for a mechanism/resource research question only. Full dossier Phase 7 counts exceed the provisional 24 CPU-hour ceiling; a **reduced Phase 7 matrix** fits and requires a **dated amendment before final-test access**. Phase 7 was **not** started. No QPU jobs.

## 2. Starting point and provenance

| Item | Value |
|------|-------|
| Authorised Phase 5 final-acceptance commit | `1c7631e609a12562155ba978cb50790f3ed2b6f7` |
| Actual starting / source commit | `1c7631e609a12562155ba978cb50790f3ed2b6f7` |
| Dirty-tree patch hash | `645d4e08e4f9a666f53d32c7fb6c507e1fdc3323c1344723a9763297967dbe5d` |
| Corrected Phase 5 run (reused) | `e6b3588b-ab97-48c9-82f4-616785aa3611` |
| Superseded Phase 5 run (not used for tuning choices) | `6ad68021-f19c-44e7-b166-13ab44dad31b` |
| Phase 6 run_id | `bd83cb22-6a38-4d21-9267-3253f52587d7` |
| Evidence | `evidence/stage6/bd83cb22-6a38-4d21-9267-3253f52587d7/` |
| Docs mirror | `docs/evidence/stage6/` |
| Elapsed compute (wall) | `323.6 s` |

Differences vs `1c7631e`: recorded in git history after this Phase 6 commit lands. Working tree at freeze used the recorded dirty hash if any.

Phase 5 final-acceptance manifest verified once (no campaign rerun): see `verify_payload.json`.

## 3. Requirement-to-evidence map (dossier §§11–19, Gates E/F)

See `evidence/stage6/bd83cb22-6a38-4d21-9267-3253f52587d7/requirements_map.json`.

| Req | Dossier | Evidence artifact |
|-----|---------|-------------------|
| Freeze before calibration | §§11–16 | `protocol_freeze.json` / `docs/STAGE_6_PROTOCOL_FREEZE.md` |
| Calibration cohort 24×SC/VSC | §7/§18 | `calibration_splits.json` |
| C0/C1 × p=1/2 × policies | §12–13/§17 | `pilot_units/*.json`, `pilot_receipt.json` |
| Precision + headroom gate | §18–19/§26 | `precision_targets_predeclared.json`, `statistical_sizing.json` |
| Capacity / Phase 7 estimates | §17 | `capacity_estimates.json` |
| Gate E novelty | §10/§26 | `novelty_comparison.json`, `docs/STAGE_6_NOVELTY_COMPARISON.md` |
| Causal gap | §15/§23 | `causal_adapter.json` |

**Phase 7 planned-not-executed:** full ideal panel, held-out primary analysis, ablations, dossier variational cap.  
**Phase 8 hardware deferred:** backend, submission path, hardware blocks.  
**Unresolved prerequisites:** causal redesign+retrain; nonzero headroom for H1; dated amendment for reduced Phase 7 before final-test.

## 4. Protocol freeze (pre-calibration)

Frozen **before** inspecting calibration outcomes:

- Model weights / feature defs / donor-bank hashes (corrected Phase 5 artifacts)
- Policies: learned, fixed (tuning-selected), NN, seeded random-donor
- Circuits: C0/C1, p=1/p=2; repaired C1 prep; C2 not admitted
- Classical comparators: exact enumeration, uniform legal sampling, greedy fallback, MILP when timely
- Objective: dossier normalised regret; ties ≠ improvements; improvement tolerance `1e-08`
- Noisy panel predeclared: depth `p1`, noise `depolarizing_1q_1e-3_2q_1e-2`, ≤10 qubits

**Bank vs variational reference:** bank fit records prove bank parameter vectors; Phase 5 per-instance variational reference published mainly as summarised regrets — **disclosed; not invented or campaign-rerun** solely to fill gaps. No fresh variational campaign in this pilot.

Full freeze: `docs/STAGE_6_PROTOCOL_FREEZE.md`.

## 5. Calibration cohort and denominators

| Quantity | Planned | Completed | Failed |
|----------|--------:|----------:|-------:|
| Calibration blocks | 24 | 24 | — |
| Cases (SC+VSC) | 48 | 48 | 0 |
| Per family | 3 blocks | equal family design | — |

- Namespace: `phase6.calib.*` — **no overlap** with Phase 5 train/tune IDs  
- **Final-test accessed:** false  
- Split audit ok: `True`

Reconcile vs dossier planned scientific calibration (24 blocks, 3/family): **aligned**. Phase 5 used a separate development train/tune materialisation; reserved generator calibration partition was previously unmaterialized — Phase 6 registers an **isolated calibration cohort** under `phase6.calib.*` before outcomes.

## 6. Bounded mechanism pilot results

Policies × family-depths on each case: learned / fixed / NN / random × C0_p1 / C0_p2 / C1_p1 / C1_p2.  
1024 shots/pool × 10 seeds (repeated measurements). Ideal distributions computed once per (case, params) then resampled.

| Finding | Result |
|---------|--------|
| Cases with exact inside deadline | 48 / 48 |
| Mean strict-improve vs exact | 0.0 |
| Max strict-improve vs exact | 0.0 |
| DEVELOPMENT_HEADROOM | ZERO |
| SUPERIORITY_PATH_AVAILABLE | false |

When the incumbent is exact, **strictly positive proxy improvement is impossible** within tolerance; ties are not counted as improvements; weak-fallback gaps are **not** superiority headroom.

Failed/excluded units retained under `pilot_units/*.failed.json` and `pilot_receipt.json`.

### Noisy feasibility panel

Status: `COMPLETED`. Predeclared depth `p1`. Synthetic depolarizing proxy — **not IBM measurement**. Zero-noise consistency: **32/32** after exact-identity repair (initial panel had 30/32 due to unnecessary zero-noise jitter; mechanism pilot unchanged). Rows: `32`. Artifact: `noisy_panel.json`.

## 7. F1 causal-integration gap

| Experiment class | Status |
|------------------|--------|
| Restricted A2 circuit experiment | Implemented (revealed-at-epoch-1 surrogate) |
| Operational race-decision experiment | **Not established** |

Stage 3 `check_causal` / `check_deadline` adapter validation: `adapter_validation_pass=True`.  
**CAUSAL_OPERATIONAL_READINESS:** false.

Dossier runtime allocator / uncertainty margin / independent evaluator / ablations → see `causal_adapter.json` blockers.  
**Working circuits alone ≠ F1 value.**

Redesign (do not silently patch A2 while reusing training):  
{
  "required_for_operational_readiness": [
    "Replace A2 revealed-at-epoch-1 duration assumption with event-timed observation projection from simulator DecisionObservation",
    "Retrain donor selector / rebuild parameter bank under new feature definitions (do not reuse Phase 5 training evidence as unchanged)",
    "Validate action expiry and pit-entry commitment on live continuation streams for A2 policies",
    "Wire independent evaluator with separate random banks (train/online/final) and event-keyed CRN",
    "Do not open final-test outcomes until Gate E/F and causal readiness pass"
  ],
  "must_not": [
    "Patch A2 generator to remove revealed-duration while claiming old training evidence unchanged",
    "Treat working C0/C1 circuits alone as F1 operational value"
  ]
}

## 8. Precision and study sizing

Predeclared mechanism precision targets (before outcomes): `precision_targets_predeclared.json`.  
Operational H1 sizing: **`NOT_APPLICABLE`** — causal evaluator unavailable; headroom gate blocks superiority; **do not** use zero variance to justify an 80-block powered superiority study; **do not** transfer δ=0.02 operational margin onto circuit probabilities.

Monte Carlo operational worlds (2048/8192/32768): **`NOT_ESTIMABLE`** — operational evaluator unaffordable/unavailable; do not substitute surrogate objective variation for race-outcome uncertainty.

Pilot limitation: **only 3 blocks/family** — large uncertainty. Blocks are independent units; preserve SC/VSC pairing and policy seeds; equal family weight; stratified block bootstrap for mechanism summaries.

## 9. Machine capacity and Phase 7 estimates

Machine: ncpu=10, mem_GiB=24.0, RAM budget 60%.

| Matrix | Est. CPU-hours | Fits 24h ceiling? |
|--------|---------------:|-------------------|
| Full dossier ideal+var+noisy (extrapolation) | 25.456777777777777 | False |
| Feasible reduced Phase 7 (proposed) | 1.758 | True |

Proposed Phase 7 counts (mechanism; **no H1**):  
```json
{
  "mechanism_calibration_reuse": "forbidden_as_final_test",
  "held_out_mechanism_cases": 80,
  "families": 2,
  "depths": 2,
  "policies": 4,
  "pool_seeds": 10,
  "ideal_pools": 12800,
  "variational_reference_cases": 40,
  "variational_max_evals_per_case": 40,
  "variational_evals": 1600,
  "noisy_cases": 16,
  "noisy_pools": 640,
  "ablations": "deferred_minimal_set_post_mechanism",
  "conditional_scaling": "excluded",
  "superiority_H1": "NOT_INCLUDED_zero_headroom_gate"
}
```

Arithmetic:  
```json
{
  "ideal_pools_12800_x_amortised_0_36s": 1.28,
  "variational_1600_x_0_05s": 0.022222222222222223,
  "noisy_640_x_2_0s": 0.35555555555555557,
  "classical_enum_80_x_0_01s": 0.00022222222222222223,
  "report_packaging": 0.1,
  "sum": 1.758
}
```

**Reduced scope needs a dated justified amendment before final-test access.**  
Repaired circuit resources from Phase 5 final acceptance are reused (native-basis decomp ≠ topology routing; no 30–40q practical claim).

## 10. Gate E — scientific value and novelty

Verdict: **`PASS_FOR_DEFINED_SCOPE`**  
Full comparison tables: `docs/STAGE_6_NOVELTY_COMPARISON.md`.

Surviving research question:  
> Within a restricted synthetic A2 circuit-mechanism scope: what are the legality yields, sample regrets, and resource envelopes of frozen C0/C1 + donor policies versus exact/uniform classical baselines under matched shot budgets — and which integration blockers prevent an operational F1 race-decision claim?

Practical relevance:  
> Practical relevance today is engineering: an auditable negative headroom result, repaired circuit provenance, and a blocked operational path until causal integration. This does not establish F1 performance value or quantum advantage.

Redesign before full campaign:  
> Before any superiority campaign: enlarge model until exact classical is not timely, or abandon H1 for a mechanism/boundary protocol amendment. Do not permanently replace the project's F1 objective with an unrelated toy benchmark.

No absolute novelty / “first” claims. Unavailable sources remain unavailable.

## 11. Verification

Targeted checks: `9` / `9` pass; ok=`True`.  
Smoke enumeration + representative C1 consistency + split isolation + zero-headroom handling + denominator reconciliation + immutable Phase 5 evidence.  
**Did not** run monolithic historical suites or archived Gate C campaigns.

## 12. Deviations and failures

```json
[
  {
    "id": "full_dossier_phase7_exceeds_24h_ceiling",
    "action": "use_feasible_reduced_matrix_with_dated_amendment"
  },
  {
    "id": "historical_variational_param_vectors_not_fully_archived",
    "disclosure": "Parameter-bank fit records prove bank training fits retained parameter vectors. They do NOT prove that separate per-instance variational-reference fits from Phase 5 retained full parameter vectors in published evidence beyond summarised regrets. Phase 6 does not campaign-rerun historical variational references solely to fill gaps; new fits (if any) save params + eval histories."
  }
]
```

Pilot failures: `0` — see `pilot_receipt.json`.

## 13. Exact next-stage readiness

| Gate / path | Ready? | Condition |
|-------------|--------|-----------|
| Phase 7 mechanism (reduced matrix) | **YES** (after dated amendment + independent review) | Preserve comparisons; no final-test until amendment |
| Phase 7 operational | **NO** | Causal model change + retrain + evaluator |
| Phase 7 superiority (H1) | **NO** | Nonzero headroom gate + operational eligibility |
| Phase 8 hardware | **NO** | QPU still unauthorised; Phase 7 not complete |
| Feasibility assessment ≠ permission | Recorded | Do not auto-start Phase 7 |

**Do not begin Phase 7 automatically.**

## 14. Receipt fields

- REPORT_PATH: `docs/STAGE_6_REPORT.md`  
- MANIFEST: `docs/evidence/stage6/STAGE_6_MANIFEST.json` (and evidence twin)  
- FINAL_VERIFY: `docs/evidence/stage6/STAGE_6_FINAL_VERIFY.json`  
- SOURCE_COMMIT: `1c7631e609a12562155ba978cb50790f3ed2b6f7`  
- ELAPSED_COMPUTE_SECONDS: `323.613`  
- QPU_JOBS / QPU_USAGE_SECONDS / QPU_EXECUTION_AUTHORISED: `0` / `0` / `false`

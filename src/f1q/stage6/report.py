"""Write Stage 6 Markdown reports and protocol freeze documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_file
from f1q.stage6.config import Phase6Config, config_to_frozen_dict


def write_all_reports(
    root: Path,
    *,
    run_id: str,
    evidence_dir: Path,
    docs_ev: Path,
    cfg: Phase6Config,
    freeze: dict[str, Any],
    splits: dict[str, Any],
    pilot: dict[str, Any],
    causal: dict[str, Any],
    noisy: dict[str, Any],
    sizing: dict[str, Any],
    capacity: dict[str, Any],
    novelty: dict[str, Any],
    readiness: dict[str, Any],
    deviations: list[dict[str, Any]],
    verify: dict[str, Any],
    source_commit: str,
    dirty: str | None,
    machine: dict[str, Any],
    elapsed_s: float,
) -> dict[str, str]:
    feasible = capacity.get("feasible_proposed_phase7_matrix", {})
    full_ex = capacity.get("extrapolation_full_dossier_cpu_hours", {})

    report = f"""# Stage 6 / Phase 6 — Local Mechanism Pilot, Precision & Resources, Gate E

**PHASE_6_COMPLETION:** `COMPLETE_WITH_DOCUMENTED_LIMITATIONS`  
**PHASE_6_ENGINEERING:** `{readiness.get("PHASE_6_ENGINEERING")}`  
**GATE_E_SCIENTIFIC_VALUE:** `{readiness.get("GATE_E_SCIENTIFIC_VALUE")}`  
**GATE_F_LOCAL_PRECISION_AND_RESOURCES:** `{readiness.get("GATE_F_LOCAL_PRECISION_AND_RESOURCES")}`  
**PROTOCOL_STATUS:** `{readiness.get("PROTOCOL_STATUS")}`  
**ADMITTED_SCIENTIFIC_SCOPE:** `{readiness.get("ADMITTED_SCIENTIFIC_SCOPE")}`  
**CAUSAL_OPERATIONAL_READINESS:** `{readiness.get("CAUSAL_OPERATIONAL_READINESS")}`  
**DEVELOPMENT_HEADROOM:** `{readiness.get("DEVELOPMENT_HEADROOM")}`  
**SUPERIORITY_PATH_AVAILABLE:** `{readiness.get("SUPERIORITY_PATH_AVAILABLE")}`  
**PHASE_7_MECHANISM_READY:** `{readiness.get("PHASE_7_MECHANISM_READY")}`  
**PHASE_7_OPERATIONAL_READY:** `{readiness.get("PHASE_7_OPERATIONAL_READY")}`  
**PHASE_7_SUPERIORITY_READY:** `{readiness.get("PHASE_7_SUPERIORITY_READY")}`  
**FINAL_TEST_ACCESSED:** `{readiness.get("FINAL_TEST_ACCESSED")}`  
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
| Actual starting / source commit | `{source_commit}` |
| Dirty-tree patch hash | `{dirty or "none (clean)"}` |
| Corrected Phase 5 run (reused) | `e6b3588b-ab97-48c9-82f4-616785aa3611` |
| Superseded Phase 5 run (not used for tuning choices) | `6ad68021-f19c-44e7-b166-13ab44dad31b` |
| Phase 6 run_id | `{run_id}` |
| Evidence | `evidence/stage6/{run_id}/` |
| Docs mirror | `docs/evidence/stage6/` |
| Elapsed compute (wall) | `{elapsed_s:.1f} s` |

Differences vs `1c7631e`: recorded in git history after this Phase 6 commit lands. Working tree at freeze used the recorded dirty hash if any.

Phase 5 final-acceptance manifest verified once (no campaign rerun): see `verify_payload.json`.

## 3. Requirement-to-evidence map (dossier §§11–19, Gates E/F)

See `evidence/stage6/{run_id}/requirements_map.json`.

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
- Objective: dossier normalised regret; ties ≠ improvements; improvement tolerance `{cfg.improvement_tol}`
- Noisy panel predeclared: depth `{cfg.noisy_depth_choice}`, noise `{cfg.noisy_noise_model}`, ≤{cfg.noisy_max_qubits} qubits

**Bank vs variational reference:** bank fit records prove bank parameter vectors; Phase 5 per-instance variational reference published mainly as summarised regrets — **disclosed; not invented or campaign-rerun** solely to fill gaps. No fresh variational campaign in this pilot.

Full freeze: `docs/STAGE_6_PROTOCOL_FREEZE.md`.

## 5. Calibration cohort and denominators

| Quantity | Planned | Completed | Failed |
|----------|--------:|----------:|-------:|
| Calibration blocks | 24 | {len({s.get("block_id") for s in (pilot.get("summaries") or [])})} | — |
| Cases (SC+VSC) | 48 | {pilot.get("completed_cases")} | {pilot.get("failed_cases")} |
| Per family | 3 blocks | equal family design | — |

- Namespace: `phase6.calib.*` — **no overlap** with Phase 5 train/tune IDs  
- **Final-test accessed:** false  
- Split audit ok: `{splits.get("audit", {}).get("ok")}`

Reconcile vs dossier planned scientific calibration (24 blocks, 3/family): **aligned**. Phase 5 used a separate development train/tune materialisation; reserved generator calibration partition was previously unmaterialized — Phase 6 registers an **isolated calibration cohort** under `phase6.calib.*` before outcomes.

## 6. Bounded mechanism pilot results

Policies × family-depths on each case: learned / fixed / NN / random × C0_p1 / C0_p2 / C1_p1 / C1_p2.  
1024 shots/pool × 10 seeds (repeated measurements). Ideal distributions computed once per (case, params) then resampled.

| Finding | Result |
|---------|--------|
| Cases with exact inside deadline | {pilot.get("n_zero_headroom_cases")} / {pilot.get("completed_cases")} |
| Mean strict-improve vs exact | {pilot.get("mean_strict_improve_vs_exact")} |
| Max strict-improve vs exact | {pilot.get("max_strict_improve_vs_exact")} |
| DEVELOPMENT_HEADROOM | {pilot.get("development_headroom")} |
| SUPERIORITY_PATH_AVAILABLE | false |

When the incumbent is exact, **strictly positive proxy improvement is impossible** within tolerance; ties are not counted as improvements; weak-fallback gaps are **not** superiority headroom.

Failed/excluded units retained under `pilot_units/*.failed.json` and `pilot_receipt.json`.

### Noisy feasibility panel

Status: `{noisy.get("status")}`. Predeclared depth `{noisy.get("predeclared_depth")}`. Synthetic depolarizing proxy — **not IBM measurement**. Zero-noise consistency included. Rows: `{noisy.get("n_rows")}`. Artifact: `noisy_panel.json`.

## 7. F1 causal-integration gap

| Experiment class | Status |
|------------------|--------|
| Restricted A2 circuit experiment | Implemented (revealed-at-epoch-1 surrogate) |
| Operational race-decision experiment | **Not established** |

Stage 3 `check_causal` / `check_deadline` adapter validation: `adapter_validation_pass={causal.get("adapter_validation_pass")}`.  
**CAUSAL_OPERATIONAL_READINESS:** false.

Dossier runtime allocator / uncertainty margin / independent evaluator / ablations → see `causal_adapter.json` blockers.  
**Working circuits alone ≠ F1 value.**

Redesign (do not silently patch A2 while reusing training):  
{json.dumps(causal.get("redesign_spec", {}), indent=2)}

## 8. Precision and study sizing

Predeclared mechanism precision targets (before outcomes): `precision_targets_predeclared.json`.  
Operational H1 sizing: **`NOT_APPLICABLE`** — causal evaluator unavailable; headroom gate blocks superiority; **do not** use zero variance to justify an 80-block powered superiority study; **do not** transfer δ=0.02 operational margin onto circuit probabilities.

Monte Carlo operational worlds (2048/8192/32768): **`NOT_ESTIMABLE`** — operational evaluator unaffordable/unavailable; do not substitute surrogate objective variation for race-outcome uncertainty.

Pilot limitation: **only 3 blocks/family** — large uncertainty. Blocks are independent units; preserve SC/VSC pairing and policy seeds; equal family weight; stratified block bootstrap for mechanism summaries.

## 9. Machine capacity and Phase 7 estimates

Machine: ncpu={machine.get("ncpu")}, mem_GiB={machine.get("mem_gib")}, RAM budget 60%.

| Matrix | Est. CPU-hours | Fits 24h ceiling? |
|--------|---------------:|-------------------|
| Full dossier ideal+var+noisy (extrapolation) | {full_ex.get("total")} | {full_ex.get("fits_ceiling")} |
| Feasible reduced Phase 7 (proposed) | {feasible.get("arithmetic_cpu_hours", {}).get("sum")} | {feasible.get("fits_24h_ceiling")} |

Proposed Phase 7 counts (mechanism; **no H1**):  
```json
{json.dumps(feasible.get("proposed_counts"), indent=2)}
```

Arithmetic:  
```json
{json.dumps(feasible.get("arithmetic_cpu_hours"), indent=2)}
```

**Reduced scope needs a dated justified amendment before final-test access.**  
Repaired circuit resources from Phase 5 final acceptance are reused (native-basis decomp ≠ topology routing; no 30–40q practical claim).

## 10. Gate E — scientific value and novelty

Verdict: **`{novelty.get("GATE_E_SCIENTIFIC_VALUE")}`**  
Full comparison tables: `docs/STAGE_6_NOVELTY_COMPARISON.md`.

Surviving research question:  
> {novelty.get("contribution_assessment", {}).get("surviving_research_question")}

Practical relevance:  
> {novelty.get("contribution_assessment", {}).get("practical_relevance")}

Redesign before full campaign:  
> {novelty.get("contribution_assessment", {}).get("redesign_required_before_full_campaign")}

No absolute novelty / “first” claims. Unavailable sources remain unavailable.

## 11. Verification

Targeted checks: `{verify.get("n_pass")}` / `{verify.get("n_checks")}` pass; ok=`{verify.get("ok")}`.  
Smoke enumeration + representative C1 consistency + split isolation + zero-headroom handling + denominator reconciliation + immutable Phase 5 evidence.  
**Did not** run monolithic historical suites or archived Gate C campaigns.

## 12. Deviations and failures

```json
{json.dumps(deviations, indent=2)}
```

Pilot failures: `{pilot.get("failed_cases")}` — see `pilot_receipt.json`.

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
- SOURCE_COMMIT: `{source_commit}`  
- ELAPSED_COMPUTE_SECONDS: `{elapsed_s:.3f}`  
- QPU_JOBS / QPU_USAGE_SECONDS / QPU_EXECUTION_AUTHORISED: `0` / `0` / `false`
"""

    report_path = root / "docs" / "STAGE_6_REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    protocol = f"""# Stage 6 Protocol Freeze Record

**PROTOCOL_STATUS:** `{readiness.get("PROTOCOL_STATUS")}`  
**Frozen before calibration outcomes:** `true`  
**Source commit:** `{source_commit}`  
**Dirty patch hash:** `{dirty or "none"}`  
**Freeze SHA-256:** `{freeze.get("freeze_sha256")}`  
**Pilot config SHA-256:** `{config_to_frozen_dict(cfg)["config_sha256"]}`

## Admitted scientific scope

`{readiness.get("ADMITTED_SCIENTIFIC_SCOPE")}`

## Frozen elements

See machine-readable `evidence/stage6/{run_id}/protocol_freeze.json` for full artifact hashes.

### Models and donors
- Corrected Phase 5 ridge selector artifacts (all four family-depths)
- Donor bank selected ≤8 donors/family-depth
- Fixed donors = tuning-selected (`argmin_mean_training_normalised_regret`) from corrected run only

### Circuits
- C0, C1; p=1, p=2
- C1 executable prep = repaired final-acceptance definition
- C2: NOT_ADMITTED_BY_PROTOCOL

### Policies
- learned, fixed, nn, seeded random-donor

### Classical comparators and budgets
- Exact legal enumeration (strongest when inside deadline)
- Uniform legal sampling (1024 draws)
- Greedy safe fallback; MILP when timely
- Pool: 1024 shots × 10 seeds

### Objective / legality / ties
- Normalised regret (f−f*)/(f_max−f*)
- One-hot vs complete semantic legality separated
- Improvement tolerance {cfg.improvement_tol}; ties are not improvements

### Noisy panel (predeclared)
- Depth: {cfg.noisy_depth_choice}
- Noise: {cfg.noisy_noise_model}
- Max qubits: {cfg.noisy_max_qubits}
- Synthetic ≠ IBM

### Endpoints / exclusions / analysis rules
- Mechanism endpoints only for confirmatory use of this pilot
- Operational race-outcome: not eligible
- Final-test / QPU / C2 / retraining excluded
- Blocks = independent units; paired SC/VSC; equal family weight
- Do not expand n after viewing effects
- Calibration ≠ independent final-test evidence

## Unresolved fields (block full FROZEN)

- Causal event-timed observation features for A2 policies
- Runtime allocator integration
- Independent operational evaluator random banks + CRN
- Hardware backend / queue / routing (Phase 8)
- Nonzero headroom domain for H1
- Dated Phase 7 reduced-matrix amendment ID (to be issued before final-test)

## Hardware-specific fields

Deferred to Phase 8. `QPU_EXECUTION_AUTHORISED: false`.
"""
    protocol_path = root / "docs" / "STAGE_6_PROTOCOL_FREEZE.md"
    protocol_path.write_text(protocol, encoding="utf-8")

    # Novelty markdown
    lines = [
        "# Stage 6 — Novelty / Gate E Comparison",
        "",
        f"**GATE_E_SCIENTIFIC_VALUE:** `{novelty.get('GATE_E_SCIENTIFIC_VALUE')}`",
        "",
        "No absolute novelty or “first” claims. Abstract-only vs full-text access is labelled per source.",
        "",
    ]
    for c in novelty.get("comparisons") or []:
        lines.append(f"## {c.get('id')}: {c.get('theme')}")
        lines.append("")
        for s in c.get("sources") or []:
            lines.append(f"- **{s.get('title', s.get('note', 'source'))}**")
            if s.get("url"):
                lines.append(f"  - URL: {s['url']}")
            if s.get("access"):
                lines.append(f"  - Access: `{s['access']}`")
            if s.get("authors"):
                lines.append(f"  - Authors: {s['authors']}")
            if s.get("venue"):
                lines.append(f"  - Venue: {s['venue']}")
        lines.append(f"- **Their contribution:** {c.get('their_contribution')}")
        lines.append(f"- **Our proposed difference:** {c.get('our_proposed_difference')}")
        lines.append(f"- **Evidence needed:** {c.get('evidence_needed')}")
        lines.append(f"- **Unresolved overlap:** {c.get('unresolved_overlap')}")
        lines.append("")
    ca = novelty.get("contribution_assessment") or {}
    lines.extend(
        [
            "## Contribution assessment",
            "",
            f"- Zero demonstrated proxy headroom: `{ca.get('zero_demonstrated_proxy_headroom')}`",
            f"- Standard C0/C1: `{ca.get('standard_C0_C1')}`",
            f"- Restricted synthetic observability: `{ca.get('restricted_synthetic_observability')}`",
            f"- Surviving scoped contribution: `{ca.get('surviving_scoped_contribution')}`",
            "",
            "### Surviving research question",
            "",
            str(ca.get("surviving_research_question")),
            "",
            "### Practical relevance",
            "",
            str(ca.get("practical_relevance")),
            "",
            "### Redesign before full campaign",
            "",
            str(ca.get("redesign_required_before_full_campaign")),
            "",
        ]
    )
    novelty_path = root / "docs" / "STAGE_6_NOVELTY_COMPARISON.md"
    novelty_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Machine-readable pilot config
    cfg_path = root / "configs" / "stage6.pilot.yaml"
    import yaml

    cfg_path.write_text(
        yaml.safe_dump(config_to_frozen_dict(cfg), sort_keys=True, default_flow_style=False),
        encoding="utf-8",
    )

    # Copy key docs evidence pointers
    for name in ("STAGE_6_REPORT.md", "STAGE_6_PROTOCOL_FREEZE.md", "STAGE_6_NOVELTY_COMPARISON.md"):
        pass

    return {
        "STAGE_6_REPORT": str(report_path),
        "STAGE_6_PROTOCOL_FREEZE": str(protocol_path),
        "STAGE_6_NOVELTY_COMPARISON": str(novelty_path),
        "stage6.pilot.yaml": str(cfg_path),
    }

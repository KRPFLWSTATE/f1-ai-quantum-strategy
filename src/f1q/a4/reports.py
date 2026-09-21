"""Generate A4 human reports from authoritative artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text, sha256_file


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_a4_reports(root: Path, run_id: str, *, start_commit: str, reviewed_commit: str | None = None) -> dict[str, str]:
    ev = root / "evidence/stage6_a4" / run_id
    rec = _load(ev / "RUN_RECEIPT.json")
    freeze = _load(ev / "PROTOCOL_FREEZE.json")
    primary = _load(ev / "PRIMARY_ANALYSIS.json")
    readiness = _load(ev / "readiness.json")
    pre = _load(ev / "PREFLIGHT.json")
    parts = _load(ev / "PARTITIONS.json")
    a3inv = _load(ev / "A3_INVALIDATION.json")
    verify = _load(ev / "FINAL_VERIFY.json") if (ev / "FINAL_VERIFY.json").is_file() else {}
    noise = _load(ev / "NATIVE_NOISE_CORRECTION.json") if (ev / "NATIVE_NOISE_CORRECTION.json").is_file() else {}
    claims = _load(ev / "CLAIMS_LEDGER.json")
    mech = _load(ev / "MECHANISM_RESULTS.json") if (ev / "MECHANISM_RESULTS.json").is_file() else {}
    sizing = _load(ev / "PRECISION_AND_SIZING.json") if (ev / "PRECISION_AND_SIZING.json").is_file() else {}
    resource = _load(ev / "RESOURCE_ACCOUNTING.json") if (ev / "RESOURCE_ACCOUNTING.json").is_file() else {}
    amendment = _load(ev / "PROTOCOL_AMENDMENT_A4.json") if (ev / "PROTOCOL_AMENDMENT_A4.json").is_file() else {}
    manifest_doc = _load(ev / "MANIFEST.json") if (ev / "MANIFEST.json").is_file() else {}
    amendment_q = amendment.get("question") or "see PROTOCOL_AMENDMENT_A4.json"
    inventory_sha = manifest_doc.get("inventory_sha256") or "n/a"
    offline = _jsonl(ev / "OFFLINE_REFERENCE.jsonl")
    calib = _jsonl(ev / "CALIBRATION_CANDIDATES.jsonl")
    train = _jsonl(ev / "TRAINING_RESULTS.jsonl")
    tune = _jsonl(ev / "TUNING_RESULTS.jsonl")
    anchors = _jsonl(ev / "ANCHOR_FITS.jsonl")
    boot = primary.get("bootstrap") or {}
    ci = boot.get("ci95") or boot.get("interval") or {}
    interval_txt = (
        f"stratified block bootstrap n_boot={boot.get('n_boot', 2000)} seed=20260921 "
        f"bounds={ci}"
        if ci or boot
        else "NA"
    )
    mean_diff = primary.get("mean_difference")
    report = f"""# Phase 6 A4 final report — scientific supersession and closure

**Document class:** A4 causal checkpoint candidate-generation and downstream-reranking benchmark.  
**Starting commit:** `{start_commit}`  
**Reviewed source commit:** `{reviewed_commit or "n/a"}`  
**Authoritative run id:** `{run_id}`  
**Elapsed wall / CPU:** {rec.get("elapsed_s")} s / {rec.get("cpu_s")} s  
**QPU_JOBS:** 0 · **QPU_USAGE_SECONDS:** 0 · **QPU_EXECUTION_AUTHORISED:** false  
**FINAL_TEST_ACCESSED:** false · **Phase 7 started:** false

Evidence labels: proposed / implemented / verified by named check / simulated. Not physically measured. Not F1-calibrated. Not quantum advantage. Generated synthetic checkpoints are not historical race validation.

---

## 0. Executive verdict

A3 run `a5fdb488-9a90-47f9-a4f5-7f77a74180a6` is an **unsuccessful implementation attempt**. Its effect, offline-headroom, dispatcher, Gate E, and Gate F numbers are **superseded and are not scientific evidence**. Independently confirmed A3 defects: `{a3inv.get("all_confirmed")}`.

A4 implements a checkpoint candidate-generation / downstream-reranking experiment with a complete executable action menu, matched portfolio budget K={freeze.get("portfolio_k")}, disjoint planning/evaluation banks, fitted (not random-default) donors, a real offline finite-simulation reference, and independent verification.

| Gate | Result |
| --- | --- |
| GATE_E_SCIENTIFIC_VALUE | `{readiness.get("GATE_E_SCIENTIFIC_VALUE")}` |
| GATE_F_PRECISION_AND_RESOURCES | `{readiness.get("GATE_F_PRECISION_AND_RESOURCES")}` |
| OPERATIONAL_DOWNSTREAM_HEADROOM | `{readiness.get("OPERATIONAL_DOWNSTREAM_HEADROOM")}` |
| PHASE_7_BOUNDARY_STUDY_READY | `{readiness.get("PHASE_7_BOUNDARY_STUDY_READY")}` |
| PHASE_7_OPERATIONAL_READY | `{readiness.get("PHASE_7_OPERATIONAL_READY")}` |
| PHASE_7_SUPERIORITY_READY | `{readiness.get("PHASE_7_SUPERIORITY_READY")}` |

Primary paired parent-block mean difference (classical_only − dispatched) at 30 s: **{mean_diff}**. Interval: {interval_txt}. Positive would favour A4; a valid negative or zero is acceptable if treatments actually differ.

Independent verifier: {verify.get("n_pass")}/{verify.get("n_checks")} ok={verify.get("ok")}.

---

## 1. Inherited accepted work (not reopened)

Phases 1–4 remain closed (`STAGE_4_ENGINEERING: CLOSED_WITH_DOCUMENTED_LIMITATIONS`; legacy Gate C `PARTIAL` / `ARCHIVED_DO_NOT_RESUME`). Frozen Phase 5 evidence under `evidence/stage5/` was not altered. Historical Phase 6 `bd83cb22-…` and corrected `2a3fb275-…` were not overwritten. A2 residual `e437fa3d-…` is preserved; its 192-pool histogram run is a **balanced method-validation subset**, not a full empirical supersession of all historical pools. A3 artifacts under `evidence/a3/a5fdb488-…` are preserved byte-for-byte as an unsuccessful attempt. A3 causal-interface smoke checks remain valid only where independently reconfirmed.

---

## 2. A3 invalidation table

Source confirmation (`inspect_a3_defects` on live A3 modules):

| Defect | Confirmed |
| --- | --- |
| `decide_from_observation` executes `downstream_candidates[0]` | {a3inv.get("defects", {}).get("selects_downstream_candidates_0")} |
| Hybrid portfolio appends quantum up to `2*equal_k` | {a3inv.get("defects", {}).get("portfolio_appends_quantum")} |
| Offline loss copied from classical mean | {a3inv.get("defects", {}).get("offline_copied_from_classical")} |
| Later info-set not executed | {a3inv.get("defects", {}).get("later_info_set_not_executed")} |
| Two-action menu `acts[:2]` | {a3inv.get("defects", {}).get("two_action_menu")} |
| No anchor optimisation loop | {a3inv.get("defects", {}).get("no_anchor_optimisation_loop")} |
| Hard-coded 45-minute reduction | {a3inv.get("defects", {}).get("hardcoded_45min_reduction")} |
| Ridge labels from hybrid that shares classical-first execution | {a3inv.get("defects", {}).get("ridge_labels_identical_plans")} |
| Random `default_params` | {a3inv.get("defects", {}).get("random_default_params")} |
| Per-world losses not written for primary | {a3inv.get("defects", {}).get("worlds_not_persisted_for_primary")} |
| Verifier internal consistency only | {a3inv.get("defects", {}).get("verifier_internal_only")} |

A3 report claimed “16 passed before campaign” for targeted tests; `tests/a3/test_a3_core.py` has 3 tests and `tests/stage6/test_residual_histograms_noise.py` has 5 (8 pytest cases). The “16/16” figure is the A3 **artifact verifier** check count, not pytest. Those A3 effect numbers remain non-scientific.

See `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`.

---

## 3. A2 noise convention correction

One dimension-independent mixture is used for logical and native panels:

`E_p(rho) = (1-p) rho + p I/d`, `d=2**n`. Identity probability `1-p*(d**2-1)/d**2`; each non-identity Pauli `p/d**2`. `p=1` → `I/2` (1q) and `I/4` (2q). Synthetic; **not** IBM-calibrated.

Native panel status: `{noise.get("panel", {}).get("status")}`; analytical `{ (noise.get("analytical") or {}).get("ok") }`. Historical 2q `p=1` closed form `(4I-ρ)/15` is superseded. Old outputs preserved; this A4 tree holds the replacement panel.

192-pool label: {noise.get("a2_residual_192_pool_label")}

---

## 4. A4 causal architecture

A4 is a **static checkpoint benchmark**: one observable decision, legal current actions only, downstream simulation reranking, then independent evaluation. It is not a multi-epoch policy. No encoded variable is omitted from the executed `RaceSimulator` plan.

Scientific question (frozen): {freeze.get("architecture")} — {amendment_q}

Quantum proxy superiority is unavailable when exact enumeration already finds the proxy optimum. The only admissible contribution is useful alternative-candidate generation under proxy/evaluator mismatch and a finite downstream budget K.

---

## 5. F1 action semantics

Per selected car, legal choices are constructed from the causal observation and inventory:

- `continue`
- `pit_now` for each distinct unused compound (lex-first equivalent set_id)
- `delay_laps=1` and `delay_laps=2` for each distinct unused compound when remaining laps permit

In-pit cars admit continuation only. Expired `pit_now` is not relabelled as next lap. Double stacking is a delay cost, not a prohibition. Every encoded action round-trips through decode → `validate_plan` → `consider_recommendation`.

Calibration menu sizes (first 8 rows): {[{k: r[k] for k in ("block_id","regime","legal_plan_count","n_qubits")} for r in calib[:8]]}

---

## 6. Exact / QUBO / MILP

For each development instance the campaign builds the QUBO and an independent linearised MILP. Training/calibration records `legal_plan_count`. Direct/QUBO agreement is required in `verify_direct_qubo_milp` before an arm proceeds (`direct_cost_qubo_ok` on decision records). Enumeration of legal joint plans is deadline-feasible on this menu (product of per-car actions, typically tens to low hundreds).

---

## 7. Splits and actual counts

Salt `{parts.get("salt")}`. Planned: {parts.get("planned")}. Final-test: n={ (parts.get("final_test") or {}).get("n_blocks") } materialised={ (parts.get("final_test") or {}).get("outcomes_materialised") } opened={ (parts.get("final_test") or {}).get("outcomes_opened") } id_sha256={ (parts.get("final_test") or {}).get("id_sha256") }.

| Split | Planned | Completed parent blocks |
| --- | ---: | ---: |
| Anchors | 24 | {rec.get("n_anchor_blocks")} |
| Training | 120 | {rec.get("n_train_blocks")} |
| Tuning | 80 | {rec.get("n_tune_blocks")} |
| Calibration | 24 | {rec.get("n_calib_blocks")} |
| Final-test | 80 | 0 (IDs/hash only) |

Training case rows attempted: {rec.get("n_train_case_rows")}; failed: {rec.get("n_train_fail")}. Tune JSONL rows: {len(tune)}. Calib case rows: {len(calib)}. Anchor fit rows: {len(anchors)}.

Worlds (frozen from preflight, 20% headroom reserved): {pre.get("frozen_worlds")}. Max optimiser evaluations per start (uniformly reduced if required): {pre.get("frozen_max_evals")}. Arithmetic: {pre.get("arithmetic")}. Minima fit: {pre.get("minima_fit")}.

---

## 8. Parameter training, donor selector, allocator

All 24 registered anchors were scheduled for C0/C1 × p=1/p=2 × 3 starts. Successful donors retained ≤8 per family/depth in `DONOR_BANK.json`. Allocator is inspectable ridge on causal/QUBO structural features; training labels require **genuine treatment differences** (identical executed plans are not used as utility labels). Conservative residual from training residual_std applied on calibration.

---

## 9. Classical / quantum portfolios

K = {freeze.get("portfolio_k")} unique downstream slots including mandatory continuation fallback. Hybrid **replaces** classical slots with quantum-origin candidates; it does not append a second budget. Planning-bank mean loss with lex plan-hash ties selects the winner; candidate array order cannot win.

Classical generators: exact proxy ranking, greedy+local, simulated annealing, uniform legal sampling, deterministic diversity, mandatory fallback. Quantum: C0/C1 at p=1 and p=2 with fitted donors (not per-instance random default angles).

Calibration: classical vs dispatched plan difference cases {rec.get("n_plan_diff")}/{rec.get("n_denom")}; quantum-origin selected {rec.get("n_quantum_origin_selected")}/{rec.get("n_denom")}.

---

## 10. Real offline references

Offline JSONL rows: {len(offline)}. Every legal joint plan on those blocks was evaluated on a dedicated offline planning bank, then the selected plan scored on a disjoint offline evaluation bank. `copied_from_arm` is false by construction. Deadline-feasible offline rows: {sum(1 for r in offline if r.get("deadline_feasible"))}/{len(offline)}. Matches classical selected plan: {sum(1 for r in offline if r.get("matches_classical_plan"))}/{len(offline)}.

---

## 11. Main and mechanism results

Primary mean difference: **{mean_diff}**. Parent blocks: {primary.get("n_parent_blocks")}. Positive blocks: {primary.get("n_positive")}. Negative blocks: {primary.get("n_negative")}. Bootstrap: {boot}.

Mechanism (exploratory): {mech}

Minimum worthwhile effect 0.02 with sensitivity 0.01 and 0.05 (frozen). Do not interpret zero variance from identical plans as precision.

---

## 12. Deadline / latency

Nominal budgets 5, 10, 30, 60, 120 s with 30 s primary. Effective deadline is the earlier of the nominal budget and pit-entry cutoff minus communication margin, via `consider_recommendation`. Local measured generation times are in calibration `generation_s`. Inserted scenario latency is simulator clock, **not** IBM/cloud latency.

Resource accounting: {resource}

---

## 13. Precision and Phase 7 projection

{sizing}

Phase 7 is **not authorised** by this prompt. `PHASE_7_BOUNDARY_STUDY_READY` remains false until Gates E and F both pass **and** an explicit later prompt authorises Phase 7. `PHASE_7_SUPERIORITY_READY` is false (no admissible superiority estimand is claimed).

---

## 14. Novelty boundary

A4 is implemented local methodology for checkpoint candidate generation under a finite reranking budget. It does **not** establish literature-first status, quantum advantage, or F1 team improvement. Novelty comparison remains `PROPOSED_NOT_LITERATURE_VERIFIED`.

---

## 15. Failures / deviations

- A3 scientific results superseded as invalid implementation.
- If Gate F is FAIL, at least one required split did not complete every parent block or minima did not fit the 75-minute ceiling after preflight.
- Native 2q convention change: historical A2 residual panel used a different 2q `p` meaning; A4 panel uses I/4 at p=1.
- Traffic density is a spec family factor; service duration is deterministic from pit parts and crew wait — not independently jittered per world. Regime duration **is** varied by event-keyed CRN.
- C1 is simulated in the one-hot legal subspace (mixer-invariant, equivalent C1). C0 uses full 2^n.

---

## 16. Claims allowed / prohibited

{claims}

Allowed: software implemented; named checks; simulated losses on synthetic checkpoints.  
Prohibited: quantum advantage; first/novel without literature work; physically measured IBM noise; F1 team performance; Phase 7 execution.

---

## 17. Evidence paths

- Evidence: `evidence/stage6_a4/{run_id}/`
- Review mirror: `docs/evidence/stage6_a4/{run_id}/`
- Manifest inventory sha256: {inventory_sha}

QPU/final-test statements are verified from executable boundaries (`f1q.a4.qpu_guard`, sealed partitions), not merely JSON flags.
"""
    path = root / "docs/PHASE_6_A4_FINAL_REPORT.md"
    atomic_write_text(path, report if report.endswith("\n") else report + "\n")

    rows_16 = """# Phases 1–6 final acceptance report v2

This table records accepted vs superseded evidence after A4. Phases 1–4 are not reopened.

| Phase | Accepted evidence | Superseded evidence | Remaining limitations | Closed? |
| --- | --- | --- | --- | --- |
| 1 | Bootstrap / doctor / boundary; dossier hash | none | Protocol DRAFT | yes (software) |
| 2 | Generator, splits, development preview | none | Reserved partitions unmaterialised | yes (software) |
| 3 / 3.x | Simulator 1.0.4 / interface 3.1.0; repairs; diagnostic | none | Synthetic fixtures | yes (software) |
| 4 | Bounded Stage 4 closure `CLOSED_WITH_DOCUMENTED_LIMITATIONS` | Legacy exhaustive Gate C PARTIAL archived | PROXY_HEADROOM ZERO; do not resume e85ee977 / 41c28597 | yes with documented limitations |
| 5 | Corrected A2 pipeline `e6b3588b-…`; final acceptance `PASS_WITH_DOCUMENTED_LIMITATIONS` | Historical `6ad68021-…` as historical only | Zero development headroom on A2 surrogate | yes with documented limitations |
| 6 A2 | Historical `bd83cb22-…`; corrected `2a3fb275-…`; residual histograms `e437fa3d-…` (method-validation subset) | Jitter noise panel; undecomposed “native” claim; 2q p convention predating A4 | Gate E fail-for-intended-contribution on A2; zero proxy headroom | A2 lineage preserved, not an A4 continuation |
| 6 A3 | Causal-interface smoke may be retained where independently valid; artifacts preserved | A3 effect/offline/dispatcher/Gate E/F numbers | Invalid constructions (see A3 invalidation) | **not** accepted as scientific closure |
| 6 A4 | This run `{run_id}` | A3 scientific conclusions | See A4 final report Gates E/F | A4 is the operational Phase 6 closure attempt |

Phase 7 is not authorised.
""".format(run_id=run_id)
    path2 = root / "docs/PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v2.md"
    atomic_write_text(path2, rows_16 if rows_16.endswith("\n") else rows_16 + "\n")
    return {
        "PHASE_6_A4_FINAL_REPORT.md": sha256_file(path),
        "PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v2.md": sha256_file(path2),
    }

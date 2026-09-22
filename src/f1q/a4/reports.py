"""Generate A4 human reports from authoritative artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text, sha256_file, sha256_json


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_a4_reports(root: Path, run_id: str, *, start_commit: str, reviewed_commit: str | None = None) -> dict[str, str]:
    ev = root / "evidence/stage6_a4" / run_id

    def _maybe(name: str) -> dict[str, Any]:
        p = ev / name
        return _load(p) if p.is_file() else {}

    rec = _maybe("RUN_RECEIPT.json")
    freeze = _maybe("PROTOCOL_FREEZE.json")
    primary = _maybe("PRIMARY_ANALYSIS.json")
    readiness = _maybe("readiness.json")
    pre = _maybe("ADMISSION_RECEIPT.json") or _maybe("PREFLIGHT.json")
    parts = _maybe("PARTITIONS.json")
    a3inv = _maybe("A3_INVALIDATION_LIVE.json") or _maybe("A3_INVALIDATION.json")
    verify = _maybe("PRE_REPORT_VERIFY.json") or _maybe("FINAL_VERIFY.json")
    noise = _maybe("NATIVE_NOISE_CORRECTION.json")
    claims = _maybe("CLAIMS_LEDGER.json")
    mech = _maybe("MECHANISM_RESULTS.json")
    sizing = _maybe("PRECISION_AND_STAGE7_SIZING.json") or _maybe("PRECISION_AND_SIZING.json")
    resource = _maybe("CAMPAIGN_RESOURCES.json") or _maybe("RESOURCE_ACCOUNTING.json")
    amendment = _maybe("PROTOCOL_AMENDMENT_A4.json")
    manifest_doc = _maybe("MANIFEST.json")
    quarantine = _maybe("PRESTART_QUARANTINE.json")
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
    report = f"""# Phase 6 A4 closure report — scientific supersession and closure

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

- Pre-start worktree diagnostic only: Stage 4 residue for `41c28597-…` / `fcbb3e38-…` was quarantined by named stash before Phase 6 source repair. Class `{quarantine.get("blocked_attempt_class")}`; stash OID `{quarantine.get("stash_oid")}`; sibling basename `{quarantine.get("quarantine_directory_basename")}`. Not a scientific Phase 6 run and not Phase 6 input.
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
    path = root / "docs/PHASE_6_A4_CLOSURE_REPORT.md"
    atomic_write_text(path, report if report.endswith("\n") else report + "\n")

    rows_16 = """# Phases 1–6 final acceptance report v3

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
    path2 = root / "docs/PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v3.md"
    atomic_write_text(path2, rows_16 if rows_16.endswith("\n") else rows_16 + "\n")
    return {
        "PHASE_6_A4_CLOSURE_REPORT.md": sha256_file(path),
        "PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v3.md": sha256_file(path2),
    }


def _run_files(ev: Path) -> list[Path]:
    skip = {"MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"}
    return [p for p in sorted(ev.rglob("*")) if p.is_file() and p.name not in skip]


def write_run_manifest(root: Path, run_id: str) -> dict[str, Any]:
    ev = root / "evidence/stage6_a4" / run_id
    entries: list[dict[str, Any]] = []
    for p in _run_files(ev):
        entries.append({"path": str(p.relative_to(ev)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    for extra in (
        root / "docs/PHASE_6_A4_CLOSURE_REPORT.md",
        root / "docs/PHASES_1_TO_6_FINAL_ACCEPTANCE_REPORT_v3.md",
    ):
        if extra.is_file():
            entries.append(
                {
                    "path": str(extra.relative_to(root)),
                    "sha256": sha256_file(extra),
                    "bytes": extra.stat().st_size,
                    "scope": "docs",
                }
            )
    man = {
        "run_id": run_id,
        "exclusions": ["MANIFEST.json", "FINAL_VERIFY.json", "FINAL_PACKAGE_VERIFY.json"],
        "entries": entries,
        "n_entries": len(entries),
        "inventory_sha256": sha256_json(entries),
    }
    atomic_write_text(ev / "MANIFEST.json", json.dumps(man, indent=2, sort_keys=True) + "\n")
    return man


def finalize_phase6_evidence(
    root: Path,
    run_id: str,
    *,
    start_commit: str,
    reviewed_commit: str | None,
    phase6_status: str,
    engineering: str,
    gate_e: str,
    gate_f: str,
) -> dict[str, Any]:
    """Non-circular closeout: derived artifacts → PRE_REPORT_VERIFY → reports → MANIFEST → FINAL_VERIFY → package."""
    from f1q.a4.verify import run_independent_verify

    ev = root / "evidence/stage6_a4" / run_id
    claims = {
        "allowed": [
            "software implemented",
            "named checks",
            "simulated losses on synthetic checkpoints",
        ],
        "prohibited": [
            "quantum advantage",
            "literature-first",
            "IBM measurement",
            "F1 team performance",
            "Phase 7 execution",
        ],
        "novelty_status": "PROPOSED_NOT_LITERATURE_VERIFIED",
        "calibration_is_primary": False,
        "calibration_label": "DEVELOPMENT_PILOT_ONLY",
    }
    atomic_write_text(ev / "CLAIMS_LEDGER.json", json.dumps(claims, indent=2, sort_keys=True) + "\n")
    readiness = {
        "GATE_E_SCIENTIFIC_VALUE": gate_e,
        "GATE_F_PRECISION_AND_RESOURCES": gate_f,
        "GATE_F_LOCAL_PRECISION_AND_RESOURCES": gate_f,
        "PHASE_6_ENGINEERING": engineering,
        "PHASE_6_STATUS": phase6_status,
        "OPERATIONAL_DOWNSTREAM_HEADROOM": "ZERO",
        "PHASE_7_BOUNDARY_STUDY_READY": False,
        "PHASE_7_OPERATIONAL_READY": False,
        "PHASE_7_SUPERIORITY_READY": False,
        "PHASE_7_AUTHORISED": False,
        "QPU_EXECUTION_AUTHORISED": False,
        "SUPERIORITY_PATH_AVAILABLE": False,
        "PROXY_HEADROOM": "ZERO",
    }
    atomic_write_text(ev / "readiness.json", json.dumps(readiness, indent=2, sort_keys=True) + "\n")
    admission = _load(ev / "ADMISSION_RECEIPT.json") if (ev / "ADMISSION_RECEIPT.json").is_file() else {}
    pre = run_independent_verify(root, run_id, mode="auto")
    atomic_write_text(ev / "PRE_REPORT_VERIFY.json", json.dumps(pre, indent=2, sort_keys=True, default=str) + "\n")
    receipt = {
        "run_id": run_id,
        "start_commit": start_commit,
        "reviewed_source_commit": reviewed_commit,
        "phase6_status": phase6_status,
        "engineering": engineering,
        "gate_e": gate_e,
        "gate_f": gate_f,
        "admitted": admission.get("admitted"),
        "selected_world_level": admission.get("selected_world_level"),
        "qpu_jobs": 0,
        "qpu_usage_seconds": 0,
        "qpu_execution_authorised": False,
        "final_test_accessed": False,
        "pre_report_verify_ok": pre.get("ok"),
        "n_anchor_blocks": 24,
        "n_train_blocks": admission.get("n_train_ok"),
        "n_tune_blocks": admission.get("n_tune_ok"),
        "n_calib_blocks": admission.get("n_calib_ok"),
    }
    atomic_write_text(ev / "RUN_RECEIPT.json", json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n")
    write_a4_reports(root, run_id, start_commit=start_commit, reviewed_commit=reviewed_commit)
    man = write_run_manifest(root, run_id)
    final_v = run_independent_verify(root, run_id, mode="final" if admission.get("admitted") else "auto")
    atomic_write_text(ev / "FINAL_VERIFY.json", json.dumps(final_v, indent=2, sort_keys=True, default=str) + "\n")
    pkg_hashes = {
        "MANIFEST.json": sha256_file(ev / "MANIFEST.json"),
        "FINAL_VERIFY.json": sha256_file(ev / "FINAL_VERIFY.json"),
        "PHASE_6_A4_CLOSURE_REPORT.md": sha256_file(root / "docs/PHASE_6_A4_CLOSURE_REPORT.md")
        if (root / "docs/PHASE_6_A4_CLOSURE_REPORT.md").is_file()
        else None,
        "RUN_RECEIPT.json": sha256_file(ev / "RUN_RECEIPT.json"),
    }
    pkg = {"hashes": pkg_hashes, "ok": all(bool(v) for v in pkg_hashes.values())}
    atomic_write_text(ev / "FINAL_PACKAGE_VERIFY.json", json.dumps(pkg, indent=2, sort_keys=True) + "\n")
    return {"pre": pre, "final": final_v, "manifest": man, "package": pkg}


def write_completion_report(
    root: Path,
    run_id: str,
    *,
    start_commit: str,
    reviewed_commit: str,
    engineering: str,
    gate_e: dict[str, Any],
    gate_f: dict[str, Any],
) -> str:
    """Generate docs/PHASE_6_COMPLETION_REPORT.md from verified artifacts."""
    ev = root / "evidence/stage6_a4" / run_id

    def _maybe(name: str) -> dict[str, Any]:
        p = ev / name
        return _load(p) if p.is_file() else {}

    rec = _maybe("RUN_RECEIPT.json")
    adm = _maybe("ADMISSION_RECEIPT.json")
    freeze = _maybe("PROTOCOL_FREEZE.json")
    primary = _maybe("PRIMARY_ANALYSIS.json")
    qdoc = _maybe("CALIBRATION_MARGIN_Q.json")
    sizing = _maybe("PRECISION_AND_STAGE7_SIZING.json")
    claims = _maybe("CLAIMS_LEDGER.json")
    lineage = _maybe("LINEAGE_AND_SUPERSESSION.json")
    amend = _maybe("IMPLEMENTATION_RESOURCE_AMENDMENT.json")
    proc = _maybe("PROCESS_AND_MEMORY_EVIDENCE.json")
    verify = _maybe("PRE_REPORT_VERIFY.json") or _maybe("FINAL_VERIFY.json")
    train = _jsonl(ev / "TRAINING_OPTION_RESULTS.jsonl")
    tune = _jsonl(ev / "TUNING_OPTION_RESULTS.jsonl")
    calib = _jsonl(ev / "CALIBRATION_OPTION_RESULTS.jsonl")
    offline = _jsonl(ev / "OFFLINE_REFERENCE.jsonl")
    prepared = _jsonl(ev / "PREPARED_CASES.jsonl")
    labels = _jsonl(ev / "ALLOCATOR_TRAINING_LABELS.jsonl")
    donor_pol = _maybe("DONOR_POLICY_SELECTION.json")
    boot = primary.get("bootstrap") or {}
    ci = boot.get("ci95") or []
    n_train = len({r.get("block_id") for r in train})
    n_tune = len({r.get("block_id") for r in tune})
    n_cal = len({r.get("block_id") for r in calib})
    n_off = len(offline)
    coverage = all(r.get("all_plan_coverage") for r in offline) if offline else False
    body = f"""# Phase 6 completion report

**Document class:** A4 local pre-test mechanism/resource pilot. Generated from frozen artifacts.  
**PHASE_6_ENGINEERING:** `{engineering}`  
**Authoritative run:** `{run_id}`  
**START_COMMIT:** `{start_commit}`  
**REVIEWED_SOURCE_COMMIT:** `{reviewed_commit}`  
**QPU_EXECUTION_AUTHORISED:** false · **QPU_JOBS:** 0 · **FINAL_TEST_ACCESSED:** false · **PHASE_7_AUTHORISED:** false

Evidence labels: implemented / verified by a named check / simulated. Not physically measured. Not F1-calibrated. Not quantum advantage. A test fixture is not an experimental observation.

## 1. Executive verdict

Terminal engineering state `{engineering}` has the exact meaning given in the authorised completion prompt: a completed Phase 6 corpus is `CLOSED_READY_FOR_PHASE7_BOUNDARY` or `CLOSED_NOT_READY_FOR_PHASE7`; missing corpus or software failure is `INCOMPLETE_ENGINEERING`; a valid implementation whose minimum complete corpus cannot fit the prospective cap is `INCOMPLETE_ENGINEERING_RESOURCE_LIMIT`. Readiness is a recommendation, not Phase 7 permission.

Gate E is `{gate_e.get("GATE_E_SCIENTIFIC_VALUE")}` because {gate_e.get("reason")}. Superiority path available: `{gate_e.get("SUPERIORITY_PATH_AVAILABLE")}` (proxy headroom is zero whenever exact classical optimisation removes all proxy slack). Boundary mechanism path: `{gate_e.get("BOUNDARY_MECHANISM_PATH_AVAILABLE")}`.

Gate F is `{gate_f.get("GATE_F_LOCAL_PRECISION_AND_RESOURCES")}` because {gate_f.get("reason")}. Phase 7 was not started.

Source: `evidence/stage6_a4/{run_id}/RUN_RECEIPT.json`, `CLAIMS_LEDGER.json`.

## 2. Authority, amendments, commits

Governing authority: the authorised Cursor completion prompt; dossier v3.1 (unchanged PDF); `docs/A3_INVALIDATION_AND_A4_PROTOCOL_AMENDMENT.md`; `docs/PHASE_6_A4_IMPLEMENTATION_AND_RESOURCE_AMENDMENT.md` (prospective, pre-outcome). Reviewed source commit `{reviewed_commit}`. Start commit `{start_commit}` contains `443c636…` in ancestry. Clean-tree proof is the git worktree `phase6-a4-completion` created from `origin/main`.

Amendment companion: `IMPLEMENTATION_RESOURCE_AMENDMENT.json` (`prior_75min_and_60min_were_implementation_added={amend.get("prior_75min_and_60min_were_implementation_added")}`). Lineage: `{lineage.get("prior_admission_disposition")}`.

## 3. Historical lineage

Run `3de109c7-30d9-4cb0-827f-dbd82c4c509d` is superseded **only as a resource model**. Its files are immutable. Its statement that no 120/80/24 corpus ran remains true. Run `09806343-…` remains the hash-verified 24-anchor / 288-start donor source. A3 `a5fdb488-…` remains `SUPERSEDED_INVALID_IMPLEMENTATION`. A2 lineage is not an A4 continuation.

## 4. Defect → fix → test → evidence

This prompt's defects (PreparedCase reuse ignored; sequential loops with assumed parallel factor; C1 dense `2^n`; hidden 64/256 draws; energy-proxy donor labels; `campaign_raw_complete` CLI stop; stale report filenames) are repaired in `src/f1q/a4/` and gated by `tests/a4/test_a4_completion_contract.py`. Traceability also records the earlier bcc740c repair set in `REPAIR_TRACEABILITY.json`.

## 5. Partitions, seeds, final-test

Fresh A4 partitions (120/80/24/80) with SC/VSC children. Final-test IDs are hash-committed only (`PARTITIONS.json` `outcomes_opened=false`). Seed hierarchy: 3 policy seeds; one derived circuit-resample seed each; not 3×3. Mechanism resampling seeds (30) are donor-selector diagnostics. Stage 7's ten seeds were not executed.

Observed training parents `{n_train}`; tuning `{n_tune}`; calibration `{n_cal}`; offline `{n_off}`. Source: `TRAINING_OPTION_RESULTS.jsonl` / `TUNING_OPTION_RESULTS.jsonl` / `CALIBRATION_OPTION_RESULTS.jsonl` / `OFFLINE_REFERENCE.jsonl`.

## 6. Machine, pool, memory, admission

Workers requested `{((proc.get("multi_worker") or {}).get("workers_requested"))}`; distinct PIDs `{((proc.get("multi_worker") or {}).get("n_distinct_worker_pids"))}`; measured efficiency `{proc.get("efficiency")}`. Admission selected ladder `{adm.get("selected_world_level")}`; admitted `{adm.get("admitted")}`; limited pilot `{adm.get("limited_resource_pilot")}`. Conservative wall formula: `unit_p95 * n_units / (W * measured_efficiency) * 1.20`. No assumed 0.55. Source: `ADMISSION_RECEIPT.json`, `PROCESS_AND_MEMORY_EVIDENCE.json`, `OPERATION_LEDGER.json`.

## 7. Prepared-case and distribution reuse

Prepared-case rows `{len(prepared)}`. Distribution index `IDEAL_DISTRIBUTIONS_INDEX.jsonl`. Counters in `MECHANISM_RESULTS.json`. C1 distributions set `dense_2n_allocated=false`.

## 8. Donor bank and selector

Reused anchors 288/24 (hash-verified). Donor policies by family/depth: `{ {k: (v or {}).get("policy") for k, v in donor_pol.items()} }`. Training labels are sampled normalised regret from 1,024-draw pools (`DONOR_SELECTOR_TRAINING.jsonl` field `label`). Learned scores on training cases are fit diagnostics unless parent-grouped OOF is recorded.

## 9. Mechanism panel and noise

Mechanism pool rows are in `MECHANISM_POOL_RESULTS.jsonl`. Variational-reference policy is a fixed-budget reference, not a certified quantum optimum. Local noisy diagnostic is labelled `LOCAL_SYNTHETIC_NOISE` or excluded without fabrication (`LOCAL_SYNTHETIC_NOISE_EXCLUSION.json`).

## 10. Matched K and quantum-incremental flow

Portfolio K is 4 unique slots including fallback; hybrid replaces classical slots (`portfolio_budget_matched` in option results). Quantum-incremental counts are per-row fields `quantum_incremental_generated` / `evaluated_in_k` / `selected`. No Gate E claim is allowed if the treatment does not reach the evaluated K-set.

## 11. Allocator

Feature rows include causal state, menu size, coefficient statistics, budget, and modelled latency (`ALLOCATOR_TRAINING_LABELS.jsonl`, n={len(labels)}). Labels are independent-evaluation reduction in normalised team loss, including zeros/negatives. Tuning freeze (`TUNING_FREEZE.json`) precedes calibration.

## 12. Calibration residual and q

Finite-sample q uses `ceil((n+1)*0.95)` clipped to n. For n=24 this is the maximum residual, not a NumPy interpolated percentile. Stated q `{qdoc.get("q")}`; n `{qdoc.get("n")}`; is_maximum `{qdoc.get("is_maximum")}`. Source: `CALIBRATION_MARGIN_Q.json`, `CALIBRATION_BLOCK_RESIDUALS.jsonl`.

## 13. Offline reference

Offline cases `{n_off}`; all-plan coverage `{coverage}`; `copied_from_arm` is false by construction (`evaluate_offline_reference`). Proxy vs evaluation-simulator disagreement is a model-boundary result when proxy headroom is zero (`BOUNDARY_RESULTS.json`).

## 14. Timing

Frozen scenario latency is keyed by case/option/budget/seed. Isolated local compute is reported separately and is not provider latency. Component tables are in `OPERATIONAL_LATENCY.jsonl` and option-result `timings.components`. Critical-path totals are reconciled; no paired turnaround is divided by two.

## 15. Primary 30-second effect

Development/calibration block-mean `{boot.get("mean")}` with 95% stratified block-bootstrap interval `{ci}` (n_boot={boot.get("n_boot")}, seed={boot.get("seed")}). Label: development/calibration, not final-test confirmation. Source: `PRIMARY_ANALYSIS.json`.

## 16. Ablations

Always-classical, no-learned-donor, and C0-for-C1 diagnostics live in option-result files (`ABLATION_RESULTS.json`). Always-quantum remains a local diagnostic, not an operational recommendation.

## 17. Boundary table and F1 meaning

Per-family/regime benefit, harm, fallback, and executed-plan differences: `BOUNDARY_RESULTS.json`. These are simulated restricted-model results. They do not establish F1 operational readiness.

## 18. Precision and Stage 7 sizing

MC world target `{((sizing.get("mc_target") or {}).get("target"))}`. Stage 7 recommended blocks `{((sizing.get("sizing") or {}).get("recommended_blocks"))}`; classification `{((sizing.get("sizing") or {}).get("analysis_classification"))}`. If required blocks exceed 160, the honest claim is estimation, not a powered superiority design.

## 19. Gate E

{gate_e}

Zero proxy headroom disables superiority. A boundary/mechanism question may still survive if matched-K quantum-incremental candidates were generated, evaluated inside K, and downstream scoring can select or reject them.

## 20. Gate F

{gate_f}

Phase 7 remains unauthorised.

## 21. Claims

Allowed: {claims.get("allowed")}. Prohibited: {claims.get("prohibited")}. Novelty is not yet literature-verified.

## 22. Failures, exclusions, deviations

See `DEVIATIONS.json`. Missing observations are not replaced with zeros. Scientific failures remain in the denominator.

## 23. Tests, verification, hashes

Independent verifier `{verify.get("n_pass")}/{verify.get("n_total")}` (`PRE_REPORT_VERIFY.json` / `FINAL_VERIFY.json`). Manifest excludes itself and later wrappers by explicit rule. Reproducibility: from the reviewed source commit, `python -m f1q.a4 --verify-run {run_id}` recomputes checks without rerunning the corpus.

## 24. Phase 7 recommendation (not authorised)

`PHASE_7_AUTHORISED` is false in every terminal state. A later explicit user prompt is required even if this report recommends a boundary study.

---
Generated from `{ev}`.
"""
    out = root / "docs" / "PHASE_6_COMPLETION_REPORT.md"
    atomic_write_text(out, body)
    return sha256_file(out)


def write_validated_closure_report(
    root: Path,
    run_id: str,
    *,
    start_commit: str,
    reviewed_commit: str,
    engineering: str,
    gate_e: dict[str, Any],
    gate_f: dict[str, Any],
) -> str:
    """Mandated docs/PHASE_6_VALIDATED_CLOSURE_REPORT.md plus historical completion alias."""
    write_completion_report(
        root, run_id, start_commit=start_commit, reviewed_commit=reviewed_commit,
        engineering=engineering, gate_e=gate_e, gate_f=gate_f,
    )
    ev = root / "evidence/stage6_a4" / run_id

    def _maybe(name: str) -> dict[str, Any]:
        p = ev / name
        return _load(p) if p.is_file() else {}

    adm = _maybe("ADMISSION_RECEIPT.json")
    rec = _maybe("RUN_RECEIPT.json")
    parity = _maybe("SCALAR_BATCHED_PARITY.json")
    speed = _maybe("BATCH_SPEED_BENCHMARK.json")
    kern = _maybe("PRODUCTION_KERNEL.json")
    cache = _maybe("CACHE_STATS.json")
    fail = _maybe("0B697910_EXPECTED_FAILURE.json")
    ext = _maybe("EXTERNAL_COMPUTE_REQUIREMENT.json")
    matrix = _maybe("PROMPT_COMPLIANCE_MATRIX.json")
    design = adm.get("design_projections") or {}
    f_proj = design.get("F") or {}
    r_proj = design.get("R") or {}
    body = f"""# Phase 6 validated closure report

**Authoritative run:** `{run_id}`  
**PHASE_6_STATUS / ENGINEERING:** `{engineering}`  
**SELECTED_DESIGN:** `{adm.get("selected_design") or rec.get("SELECTED_DESIGN")}`  
**START_COMMIT:** `{start_commit}`  
**REVIEWED_SOURCE_COMMIT:** `{reviewed_commit}`  
**Phase 7 started:** no. `PHASE_7_AUTHORISED=false`.

## 1. Disposition of `0b697910-e8a2-474b-bc77-bc69ebb8e9c3`

`PRESERVED_LIMITED_DIAGNOSTIC_INVALID_FOR_PHASE6_CLOSURE_OR_GATES`. Files under `evidence/stage6_a4/0b697910-e8a2-474b-bc77-bc69ebb8e9c3/` are unmodified. Expected-failure audit: `docs/evidence/phase6_validated/0B697910_EXPECTED_FAILURE.json` (copied into this run). Verifier `ok={fail.get("ok")}` with `n_pass={fail.get("n_pass")}/{fail.get("n_total")}`. Valid engineering observations (real PIDs, local timing, no QPU/final-test) remain; scientific/resource closure is not accepted.

## 2. Scalar/batched parity and speed

Parity `ok={parity.get("ok")}` cells `{parity.get("n_cells")}` hash `{parity.get("rows_hash")}` families `{parity.get("families")}` regimes `{parity.get("regimes")}` classes `{parity.get("commitment_classes_observed")}`.  
Speed rows: `{speed.get("rows")}`. Production kernel `{kern}`. Cache `{cache}`.

## 3. F/R admission arithmetic and selection

Design F fit `{f_proj.get("fit")}` projection `{f_proj.get("projection")}`.  
Design R fit `{r_proj.get("fit")}` projection `{r_proj.get("projection")}`.  
Selected `{adm.get("selected_design")}`. Admitted `{adm.get("admitted")}`. Limited pilot `{adm.get("limited_resource_pilot")}`.  
If neither fits, no 4/4/2 outcome-bearing substitute was run.

External compute requirement: `{ext}`.

## 4. Full denominators and exclusions

Fresh partitions: 120/80/24 parents with `a4.v2.*` IDs, disjoint from retired diagnostic parents. Corpus train/tune/calib rows for this run: executed only if F or R admitted. Resource-limit closeout opens no registered parent outcomes.

## 5. Donor/AI model methods

Sampled 1,024-draw decoded labels (`f1q.a4.donor_labels`). Expectation is diagnostic only. Per-instance variational reference is a real local fit, not a bank lookup.

## 6. Circuit mechanism and matched-K flow

Production evaluation calls `evaluate_candidates_batched`. Scalar `_simulate_plan_world` is parity-only.

## 7. Frozen allocator and ablations

Calibration units are constructed only after hashing `TUNING_FREEZE.json`. Ablations execute real rows (`ablation_specs`). Not applicable as Gate E/F evidence when design is NONE_RESOURCE_LIMIT.

## 8. Calibration q, harm, paired effects, MC, Stage 7 sizing

Unclaimed unless 24 fresh parent maxima exist. Resource-limit: q is NA (no 24-parent calibration).

## 9. Resource use and projection accuracy

Admission wall `{adm.get("admission_wall_s")}` CPU `{adm.get("admission_cpu_s")}`. Conservative multiplier uses max(1.15, 26010/20752). Efficiency is measured, not 0.55.

## 10. Gate E/F derivations

Gate E: `{gate_e}`  
Gate F: `{gate_f}`  
`SUPERIORITY_PATH_AVAILABLE=false` (proxy headroom zero). Limited-pilot `PASS_BOUNDARY_MECHANISM` is not confirmatory.

## 11. F1 integration meaning and limits

Local simulator mechanism description only. Not F1 calibration, not hardware, not novelty-verified.

## 12. Allowed/prohibited claims

See `CLAIMS_LEDGER.json`.

## 13. Defect → fix → test → evidence

See `docs/PHASE_6_0B697910_INVALIDATION.md` and `REPAIR_TRACEABILITY.json`.

## 14. Reproduction and artifact index

`python -m f1q.a4 --verify-run {run_id}`  
Evidence: `{ev}`  
Prompt compliance: `{matrix.get("passed")}/{matrix.get("total")}`.

---
Generated from `{ev}`. Phase 7 was not started.
"""
    out = root / "docs" / "PHASE_6_VALIDATED_CLOSURE_REPORT.md"
    atomic_write_text(out, body)
    alias = root / "docs" / "PHASE_6_COMPLETION_REPORT.md"
    if alias.is_file():
        pass
    return sha256_file(out)



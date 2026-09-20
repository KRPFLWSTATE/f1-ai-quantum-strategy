"""Stage 4 formulation_check plan units."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from f1q.formulation.config import load_formulation_config
from f1q.formulation.evaluator import assert_compiler_evaluator_separation
from f1q.formulation.instance import build_instance_record
from f1q.formulation.panel import run_evaluator_panel
from f1q.formulation.qubo import build_qubo, verify_penalty_proof
from f1q.formulation.versions import FORMULATION_VERSION
from f1q.hashing import atomic_write_bytes, canonical_json, sha256_file, sha256_json
from f1q.paths import resolve_within
from f1q.schemas import utc_now
from f1q.simulator.config import load_simulator_config
from f1q.simulator.matrix import load_preview_specs
from f1q.simulator.resources import MemoryGuard
from f1q.snapshot import take_source_snapshot

_GUARDS: dict[str, MemoryGuard] = {}


class TimeCapPartial(Exception):
    """Raised when the Stage 4.2 wall-time cap stops a resumable matrix early."""


def execute_formulation_unit(
    *,
    root: Path,
    run_id: str,
    unit_id: str,
    seed: int,
    attempt_id: str,
) -> dict[str, Any]:
    del attempt_id
    rel_dir = f"evidence/formulation/artifacts/{run_id}/{unit_id}"
    dest = resolve_within(root, rel_dir)
    dest.mkdir(parents=True, exist_ok=True)
    cfg, cfg_hash = load_simulator_config(root)
    guard = _GUARDS.setdefault(
        run_id,
        MemoryGuard(
            ceiling_fraction=float(cfg["resource"]["ram_ceiling_fraction"]),
            interval_s=float(cfg["resource"].get("ram_sampling_interval_s") or 1.0),
        ),
    )
    started = time.monotonic()
    form_cfg, _form_hash = load_formulation_config(root)
    cap = float(form_cfg.get("resource", {}).get("stage4_elapsed_cap_s") or 1800.0)
    specs = load_preview_specs(root)
    extra: list[dict[str, Any]] = []
    print(f"UNIT_START {unit_id} cap_s={cap}", flush=True)

    try:
        if unit_id == "formulation.pre_repair_erratum":
            payload = _unit_pre_repair_erratum(root, dest, seed=seed)
        elif unit_id == "formulation.action_model":
            payload = _unit_action_model(cfg, specs, dest, seed=seed)
        elif unit_id == "formulation.compiler_direct_costs":
            payload = _unit_compiler(cfg, specs, dest, seed=seed)
        elif unit_id == "formulation.qubo_ising_gate":
            payload = _unit_qubo(cfg, specs, dest, seed=seed)
        elif unit_id == "formulation.independent_references":
            payload = _unit_refs(cfg, specs, dest, seed=seed)
        elif unit_id == "formulation.development_matrix":
            payload = _unit_matrix(cfg, specs, dest, seed=seed, started=started, cap=cap, guard=guard)
        elif unit_id == "formulation.evaluator_separation_panel":
            payload = _unit_panel(root, cfg, specs, dest, seed=seed)
        elif unit_id == "formulation.stage3_3_diagnostic_restore":
            payload = _unit_stage3_3_restore(root, dest, seed=seed)
        elif unit_id == "formulation.source_restore":
            payload = _unit_source(root, dest, run_id)
        else:
            raise ValueError(f"unknown formulation unit {unit_id}")
    except TimeCapPartial as exc:
        # Persist partial matrix summary already written; stamp unit.json then re-raise.
        payload = {
            "ok": False,
            "partial": True,
            "unit": unit_id,
            "error": str(exc),
            "status": "PARTIAL",
        }
        payload["memory_sample"] = guard.observe()
        payload["formulation_version"] = FORMULATION_VERSION
        payload["simulator_config_hash"] = cfg_hash
        payload["seed"] = seed
        unit_rel = f"{rel_dir}/unit.json"
        atomic_write_bytes(resolve_within(root, unit_rel), canonical_json(_public(payload)) + b"\n")
        raise

    payload["memory_sample"] = guard.observe()
    payload["formulation_version"] = FORMULATION_VERSION
    payload["simulator_config_hash"] = cfg_hash
    payload["seed"] = seed
    payload["machine"] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
    unit_rel = f"{rel_dir}/unit.json"
    digest = atomic_write_bytes(resolve_within(root, unit_rel), canonical_json(_public(payload)) + b"\n")
    extra.append(
        {
            "schema_version": "1.0.0",
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": unit_rel,
            "sha256": digest,
            "kind": "formulation_unit",
            "created_at_utc": utc_now(),
        }
    )
    # Register additional written files
    for path in sorted(dest.glob("*.json")):
        if path.name == "unit.json":
            continue
        rel = f"{rel_dir}/{path.name}"
        extra.append(
            {
                "schema_version": "1.0.0",
                "artifact_id": str(uuid4()),
                "run_id": run_id,
                "unit_id": unit_id,
                "relative_path": rel,
                "sha256": sha256_file(path),
                "kind": "formulation_artifact",
                "created_at_utc": utc_now(),
            }
        )
    return {
        "artifact": extra[0],
        "extra_artifacts": extra[1:],
        "substantive_payload_sha256": sha256_json(_public(payload)),
    }


def _public(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _write(dest: Path, name: str, obj: Any) -> str:
    return atomic_write_bytes(dest / name, canonical_json(obj) + b"\n")


def _unit_pre_repair_erratum(root: Path, dest: Path, *, seed: int) -> dict[str, Any]:
    """Register Stage 4.1 independent-review failure via new Stage 4.2 erratum; preserve prior IDs."""
    import shutil

    src = resolve_within(root, "docs/evidence/stage4_2/pre_repair_reproduction.json")
    if not src.is_file():
        raise FileNotFoundError("missing docs/evidence/stage4_2/pre_repair_reproduction.json")
    shutil.copy2(src, dest / "pre_repair_reproduction.json")
    prior_41 = resolve_within(
        root, "evidence/formulation/receipts/c4d0a199-9cea-4214-83ab-97964f2bf1ac.json"
    )
    prior_4 = resolve_within(
        root, "evidence/formulation/receipts/e8b87881-74a6-46c7-b48e-6b2496a5d586.json"
    )
    prior41 = json.loads(prior_41.read_text(encoding="utf-8"))
    prior4 = json.loads(prior_4.read_text(encoding="utf-8"))
    erratum = {
        "kind": "stage4_1_independent_review_erratum",
        "prior_stage4_run_id": "e8b87881-74a6-46c7-b48e-6b2496a5d586",
        "prior_stage4_1_run_id": "c4d0a199-9cea-4214-83ab-97964f2bf1ac",
        "prior_failed_stage4_run_id": "1c5b0748-5406-4933-8e41-4f943f4296c7",
        "prior_receipts_preserved": True,
        "prior_stage4_1_next_permitted_work": prior41.get("next_permitted_work"),
        "prior_stage4_next_permitted_work": prior4.get("next_permitted_work"),
        "erratum": (
            "Stage 4.1 is not independently accepted. Independent review found F1–F9 defects "
            "(evaluator event schema, in-pit continuation costing, continuation admission, "
            "analytical-vs-terminal pair evidence, circular reduction proof, unreachable "
            "tie_loss classification, Stage 3.3 evidence overwrite, stale docs, and invalid "
            "review packaging/clean-extract). Stage 4.2 repairs these without rewriting prior "
            "run identifiers."
        ),
        "corrected_interpretation": (
            "independent review of Stage 4.2 only; Stage 5 and IBM credential entry remain blocked"
        ),
        "findings_reproduced_path": "docs/evidence/stage4_2/pre_repair_reproduction.json",
        "seed": seed,
        "qpu_usage_seconds": 0,
        "new_physical_qpu_jobs_submitted": 0,
    }
    _write(dest, "stage4_1_independent_review_erratum.json", erratum)
    return {
        "ok": True,
        "unit": "formulation.pre_repair_erratum",
        "prior_stage4_run_preserved": "e8b87881-74a6-46c7-b48e-6b2496a5d586",
        "prior_stage4_1_run_preserved": "c4d0a199-9cea-4214-83ab-97964f2bf1ac",
        "prior_failed_run_preserved": "1c5b0748-5406-4933-8e41-4f943f4296c7",
        "erratum_path": f"{dest.name}/stage4_1_independent_review_erratum.json",
        "seed": seed,
    }


def _unit_stage3_3_restore(root: Path, dest: Path, *, seed: int) -> dict[str, Any]:
    from f1q.simulator.stage3_3_diagnostic import (
        restore_historical_stage3_3_bytes,
        scientific_payload_matches_live,
        verify_historical_stage3_3,
        write_corrected_diagnostic,
    )

    hist = verify_historical_stage3_3(root)
    if not hist["ok"]:
        restore_historical_stage3_3_bytes(root)
        hist = verify_historical_stage3_3(root)
    written = write_corrected_diagnostic(root)  # writes under stage4_2/
    match, detail = scientific_payload_matches_live(root)
    report = {
        "ok": bool(match) and bool(hist["ok"]),
        "unit": "formulation.stage3_3_diagnostic_restore",
        "historical_verify": hist,
        "write": {k: written[k] for k in written if k != "document"},
        "verify_current": detail,
        "match": match,
        "simulator_version": "1.0.4",
        "interface_version": "3.1.0",
        "seed": seed,
        "note": "Historical Stage 3.3 identity restored/verified; current diagnostic under stage4_2 only",
    }
    _write(dest, "stage3_3_restore.json", report)
    return report


def _unit_action_model(cfg, specs, dest, *, seed: int) -> dict[str, Any]:
    from f1q.formulation.actions import generate_action_model
    from f1q.formulation.public_config import public_physics_from_sources
    from f1q.simulator.interface import RaceSimulator

    summaries = []
    for spec in specs:
        sim = RaceSimulator(cfg)
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        obs = sim.observe()
        public = public_physics_from_sources(
            simulator_cfg=cfg,
            block_parameters=spec["block_parameters"],
            compound_obligation=spec.get("compound_obligation"),
        )
        model = generate_action_model(obs, public, selected_car_ids=list(spec["selected_car_ids"]))
        summaries.append(
            {
                "episode_id": spec["episode_id"],
                "full_counts": model["full_counts"],
                "reduced_counts": model["reduced_counts"],
                "n_excluded": len(model["excluded_actions"]),
                "action_dictionary_hash": model["action_dictionary_hash"],
            }
        )
    report = {
        "ok": True,
        "unit": "formulation.action_model",
        "n_episodes": len(summaries),
        "summaries": summaries,
        "seed": seed,
    }
    _write(dest, "action_model_summary.json", report)
    return report


def _unit_compiler(cfg, specs, dest, *, seed: int) -> dict[str, Any]:
    from f1q.formulation.actions import generate_action_model
    from f1q.formulation.compiler import compile_action_costs
    from f1q.formulation.public_config import public_physics_from_sources
    from f1q.simulator.interface import RaceSimulator

    rows = []
    hashes = []
    for idx, spec in enumerate(specs):
        sim = RaceSimulator(cfg)
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        obs = sim.observe()
        public = public_physics_from_sources(
            simulator_cfg=cfg,
            block_parameters=spec["block_parameters"],
            compound_obligation=spec.get("compound_obligation"),
        )
        model = generate_action_model(obs, public, selected_car_ids=list(spec["selected_car_ids"]))
        costs = compile_action_costs(
            obs, public, menus=model["menus"], selected_car_ids=list(spec["selected_car_ids"])
        )
        hashes.append({"episode_id": spec["episode_id"], "coefficient_hash": costs["coefficient_hash"]})
        if idx < 8:
            rows.append(
                {
                    "episode_id": spec["episode_id"],
                    "coefficient_hash": costs["coefficient_hash"],
                    "C_centered": costs["C_centered"],
                    "m1": costs["m1"],
                    "m2": costs["m2"],
                }
            )
    report = {
        "ok": True,
        "unit": "formulation.compiler_direct_costs",
        "sample_rows": rows,
        "all_hashes": hashes,
        "seed": seed,
    }
    _write(dest, "compiler_summary.json", report)
    return report


def _unit_qubo(cfg, specs, dest, *, seed: int) -> dict[str, Any]:
    # Gate C on a hand-small subset + first development episode with reduced menu
    results = []
    for spec in specs[:4]:
        rec = build_instance_record(cfg=cfg, spec=spec, seed=seed, verify_energies=True, cross_check_simulator=True)
        results.append(
            {
                "episode_id": spec["episode_id"],
                "n_vars": rec["qubo"]["variable_map"]["n"],
                "penalty": rec["qubo"]["penalty"],
                "proof_ok": rec["penalty_proof"].get("ok"),
                "s_Q": rec["ising_scaled"]["s_Q"],
                "cross_disagreements": len(rec["simulator_cross_check"]["disagreements"]),
                "record_hash": rec["record_hash"],
            }
        )
        _write(dest, f"{spec['episode_id'].replace('/', '__')}.instance.json", rec)
    report = {
        "ok": all(r["proof_ok"] in {True, None} and r["cross_disagreements"] == 0 for r in results),
        "unit": "formulation.qubo_ising_gate",
        "results": results,
        "seed": seed,
    }
    _write(dest, "qubo_gate_summary.json", report)
    return report


def _unit_refs(cfg, specs, dest, *, seed: int) -> dict[str, Any]:
    rows = []
    agrees = 0
    for spec in specs:
        rec = build_instance_record(cfg=cfg, spec=spec, seed=seed, verify_energies=False, cross_check_simulator=False)
        milp_ok = rec["milp_agrees_with_enumeration"]
        if milp_ok:
            agrees += 1
        rows.append(
            {
                "episode_id": spec["episode_id"],
                "exact": rec["enumeration"]["exact_proxy_minimum"],
                "milp_value": rec["milp"].get("value_with_constant"),
                "milp_agree": milp_ok,
                "dp": rec["dp_analytical"],
                "headroom": rec["proxy_headroom"],
                "timing": rec["timing"],
            }
        )
    report = {
        "ok": agrees == len(specs),
        "unit": "formulation.independent_references",
        "n": len(specs),
        "milp_agreements": agrees,
        "rows": rows,
        "seed": seed,
    }
    _write(dest, "references_summary.json", report)
    return report


def _unit_matrix(cfg, specs, dest, *, seed: int, started: float, cap: float, guard: MemoryGuard) -> dict[str, Any]:
    planned = [s["episode_id"] for s in specs]
    completed = []
    failed = []
    records_meta = []
    skipped_resume = 0
    print(f"MATRIX_START planned={len(planned)} cap_s={cap}", flush=True)
    for spec in specs:
        if time.monotonic() - started > cap:
            break
        guard.observe()
        name = spec["episode_id"].replace("/", "__") + ".record.json"
        existing = dest / name
        if existing.is_file():
            try:
                import json as _json

                prior = _json.loads(existing.read_text(encoding="utf-8"))
                stored_hash = prior.get("record_hash")
                # Fail closed (Stage 4 Final Closure): a nonempty record_hash covering only
                # selected mathematical fields is not authentication of evaluator events /
                # counters. Automatic resume skip is disabled; existing files are preserved.
                print(
                    f"MATRIX_RESUME_REJECT episode={spec['episode_id']} "
                    f"reason=fail_closed_weak_record_hash_not_full_payload_auth "
                    f"stored_hash_present={bool(stored_hash)}",
                    flush=True,
                )
                failed.append(
                    {
                        "episode_id": spec["episode_id"],
                        "failure_code": "RESUME_FAIL_CLOSED",
                        "error": (
                            "automatic matrix resume disabled; "
                            "record_hash covers selected math fields only and must not "
                            "authenticate evaluator events or counters"
                        ),
                    }
                )
                continue
            except Exception as exc:
                failed.append(
                    {
                        "episode_id": spec["episode_id"],
                        "failure_code": "RESUME_FAIL_CLOSED",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
        try:
            rec = build_instance_record(cfg=cfg, spec=spec, seed=seed, verify_energies=False, cross_check_simulator=True)
            _write(dest, name, rec)
            completed.append(spec["episode_id"])
            records_meta.append(
                {
                    "episode_id": spec["episode_id"],
                    "record_hash": rec["record_hash"],
                    "exact": rec["enumeration"]["exact_proxy_minimum"],
                    "headroom": rec["proxy_headroom"]["heuristic_proxy_headroom"],
                    "scan_s": rec["timing"]["scan_s"],
                    "cross_expected": rec["simulator_cross_check"]["expected"],
                    "cross_checked": rec["simulator_cross_check"]["checked"],
                    "cross_failed": rec["simulator_cross_check"]["failed"],
                    "cross_validation_passed": rec["simulator_cross_check"].get("validation_passed"),
                    "cross_round_trip_passed": rec["simulator_cross_check"].get("round_trip_passed"),
                    "cross_terminal_executed": rec["simulator_cross_check"].get("terminal_execution_completed"),
                    "cross_terminal_attempted": rec["simulator_cross_check"].get("terminal_execution_attempted"),
                    "cross_analytical_passed": rec["simulator_cross_check"].get("analytical_admission_passed"),
                    "cross_disagreements": len(rec["simulator_cross_check"]["disagreements"]),
                    "semantic_failures": len(rec["simulator_cross_check"].get("semantic_failures") or []),
                    "failure_code": None,
                    "resumed_from_checksum": False,
                }
            )
            print(
                f"MATRIX_PROGRESS completed={len(completed)}/{len(planned)} "
                f"last={spec['episode_id']} resumed=0 elapsed_s={time.monotonic()-started:.1f}",
                flush=True,
            )
        except Exception as exc:
            failed.append({"episode_id": spec["episode_id"], "failure_code": type(exc).__name__, "error": str(exc)})
    partial = len(completed) < len(planned) and len(failed) == 0
    summary = {
        "ok": len(failed) == 0 and len(completed) == len(planned),
        "partial": partial,
        "unit": "formulation.development_matrix",
        "planned": len(planned),
        "completed": len(completed),
        "failed": len(failed),
        "skipped_resume": skipped_resume,
        "failed_rows": failed,
        "records": records_meta,
        "not_powered_comparison": True,
        "seed": seed,
        "elapsed_s": time.monotonic() - started,
        "cap_s": cap,
        "status": "PARTIAL" if partial else ("FAILED" if failed else "COMPLETE"),
    }
    # Aggregate headroom warning
    headrooms = [r["headroom"] for r in records_meta if r["headroom"] is not None]
    summary["proxy_headroom_stats"] = {
        "min": min(headrooms) if headrooms else None,
        "max": max(headrooms) if headrooms else None,
        "mean": (sum(headrooms) / len(headrooms)) if headrooms else None,
        "zero_count": sum(1 for h in headrooms if abs(h) <= 1e-12),
        "n_with_headroom": len(headrooms),
        "gate_e_warning": bool(headrooms) and all(abs(h) <= 1e-9 for h in headrooms),
    }
    summary["pair_cross_check_totals"] = {
        "expected": sum(int(r.get("cross_expected") or 0) for r in records_meta),
        "validated": sum(int(r.get("cross_validation_passed") or 0) for r in records_meta),
        "round_tripped": sum(int(r.get("cross_round_trip_passed") or 0) for r in records_meta),
        "terminal_executed": sum(int(r.get("cross_terminal_executed") or 0) for r in records_meta),
        "terminal_attempted": sum(int(r.get("cross_terminal_attempted") or 0) for r in records_meta),
        "analytical_admission_passed": sum(int(r.get("cross_analytical_passed") or 0) for r in records_meta),
        "semantic_passed": sum(int(r.get("cross_checked") or 0) for r in records_meta),
        "failed": sum(int(r.get("cross_failed") or 0) for r in records_meta),
        "hidden_cap": False,
    }
    _write(dest, "development_matrix_summary.json", summary)
    if partial:
        raise TimeCapPartial(
            f"STAGE_4_2_TIME_CAP_PARTIAL completed={len(completed)}/{len(planned)} "
            f"elapsed_s={summary['elapsed_s']:.1f} cap_s={cap}"
        )
    return summary


def _unit_panel(root, cfg, specs, dest, *, seed: int) -> dict[str, Any]:
    sep = assert_compiler_evaluator_separation()
    panel = run_evaluator_panel(root=root, cfg=cfg, specs=specs, joint_plan_cap=6)
    panel["seed"] = seed
    panel["compiler_evaluator_separation"] = sep
    panel["ok"] = bool(sep.get("ok")) and panel["n_cases"] == 8
    _write(dest, "evaluator_panel.json", panel)
    return panel


def _unit_source(root: Path, dest: Path, run_id: str) -> dict[str, Any]:
    snap = take_source_snapshot(root)
    snap_path = dest / "source_snapshot.json"
    digest = atomic_write_bytes(snap_path, canonical_json(snap) + b"\n")
    return {
        "ok": True,
        "unit": "formulation.source_restore",
        "run_id": run_id,
        "source_snapshot_hash": snap["hash"],
        "snapshot_sha256": digest,
        "qpu_usage_seconds": 0,
        "new_physical_qpu_jobs": 0,
    }

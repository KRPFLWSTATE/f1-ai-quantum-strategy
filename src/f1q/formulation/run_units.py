"""Stage 4 formulation_check plan units."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    cap = 1800.0  # 30-minute Stage 4 cumulative cap
    specs = load_preview_specs(root)
    extra: list[dict[str, Any]] = []

    if unit_id == "formulation.action_model":
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
    elif unit_id == "formulation.source_restore":
        payload = _unit_source(root, dest, run_id)
    else:
        raise ValueError(f"unknown formulation unit {unit_id}")

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
    for spec in specs:
        if time.monotonic() - started > cap:
            break
        guard.observe()
        try:
            rec = build_instance_record(cfg=cfg, spec=spec, seed=seed, verify_energies=False, cross_check_simulator=True)
            name = spec["episode_id"].replace("/", "__") + ".record.json"
            _write(dest, name, rec)
            completed.append(spec["episode_id"])
            records_meta.append(
                {
                    "episode_id": spec["episode_id"],
                    "record_hash": rec["record_hash"],
                    "exact": rec["enumeration"]["exact_proxy_minimum"],
                    "headroom": rec["proxy_headroom"]["heuristic_proxy_headroom"],
                    "scan_s": rec["timing"]["scan_s"],
                    "cross_disagreements": len(rec["simulator_cross_check"]["disagreements"]),
                    "failure_code": None,
                }
            )
        except Exception as exc:
            failed.append({"episode_id": spec["episode_id"], "failure_code": type(exc).__name__, "error": str(exc)})
    summary = {
        "ok": len(failed) == 0 and len(completed) == len(planned),
        "unit": "formulation.development_matrix",
        "planned": len(planned),
        "completed": len(completed),
        "failed": len(failed),
        "failed_rows": failed,
        "records": records_meta,
        "not_powered_comparison": True,
        "seed": seed,
        "elapsed_s": time.monotonic() - started,
        "cap_s": cap,
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
    _write(dest, "development_matrix_summary.json", summary)
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

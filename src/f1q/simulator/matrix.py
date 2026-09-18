from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from f1q.errors import RejectionError
from f1q.hashing import atomic_write_bytes, canonical_json, sha256_json
from f1q.paths import resolve_within
from f1q.simulator.checks import run_all_mechanism_checks
from f1q.simulator.config import load_simulator_config
from f1q.simulator.engine import event_signature
from f1q.simulator.interface import RaceSimulator
from f1q.simulator.policies import select_obligation_set

PREVIEW_RUN = "8f292588-a328-4232-b425-c36c610a29f5"


def load_preview_specs(root: Path, run_id: str = PREVIEW_RUN) -> list[dict[str, Any]]:
    art = resolve_within(root, f"evidence/development/artifacts/{run_id}")
    specs = []
    for path in sorted(art.rglob("*.spec.json")):
        specs.append(json.loads(path.read_text(encoding="utf-8")))
    return specs


def intervention_episodes(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        by_fam.setdefault(spec["family_id"], []).append(spec)
    selected = []
    for index, family_id in enumerate(sorted(by_fam)):
        want = "SC" if index % 2 == 0 else "VSC"
        pool = [s for s in by_fam[family_id] if s["checkpoint_request"]["requested_regime"] == want]
        if not pool:
            pool = list(by_fam[family_id])
        pool.sort(key=lambda s: hashlib.sha256(s["episode_id"].encode("utf-8")).hexdigest())
        selected.append(pool[0])
    return selected


def _write(path: Path, obj: Any) -> str:
    return atomic_write_bytes(path, canonical_json(obj) + b"\n")


def validate_one_episode(
    cfg: dict[str, Any],
    spec: dict[str, Any],
    *,
    alternative: dict[str, Any] | None = None,
    private_dir: Path | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "episode_id": spec["episode_id"],
        "family_id": spec["family_id"],
        "regime": spec["checkpoint_request"]["requested_regime"],
        "admitted": False,
        "rejected": False,
        "reason": None,
        "resume_error": None,
        "intervention": None,
    }
    try:
        sim = RaceSimulator(cfg)
        sim.initialize(spec)
        sim.advance_to_checkpoint()
        if not sim.engine.state["checkpoint_reached"]:
            raise RejectionError("CHECKPOINT_NOT_VALIDATED", "checkpoint not reached")
        obs = sim.observe()
        blob = sim.serialize()
        if private_dir is not None:
            private_dir.mkdir(parents=True, exist_ok=True)
            rel_name = spec["episode_id"].replace("/", "__") + ".state.json"
            digest = atomic_write_bytes(private_dir / rel_name, canonical_json(blob) + b"\n")
            record["private_state_sha256"] = digest
            record["private_state_filename"] = rel_name
        unint = sim.clone()
        _, out_a = unint.continue_to_finish()
        restored = RaceSimulator(cfg)
        restored.restore(blob, spec)
        _, out_b = restored.continue_to_finish()
        rank_err = max(
            abs(out_a["ranking"]["ranks"][c] - out_b["ranking"]["ranks"][c]) for c in out_a["ranking"]["ranks"]
        )
        t_err = abs(out_a["t"] - out_b["t"])
        record["resume_error"] = {"rank_error": rank_err, "time_error_s": t_err}
        if rank_err != 0 or t_err > 1e-6:
            record["rejected"] = True
            record["reason"] = "RESUME_MISMATCH"
            return record
        record["admitted"] = True
        record["team_loss"] = out_a["team_loss"]
        record["ranks"] = {
            cid: out_a["ranking"]["ranks"][cid] for cid in spec["selected_car_ids"]
        }
        record["observation_checkpoint_id"] = obs.checkpoint_id
        if alternative is not None:
            record["intervention"] = alternative
        return record
    except Exception as exc:
        record["rejected"] = True
        record["reason"] = f"{type(exc).__name__}: {exc}"
        return record


def run_development_matrix(root: Path, dest: Path, *, cap_s: float | None = None, started: float | None = None) -> dict[str, Any]:
    import time

    cfg, cfg_hash = load_simulator_config(root)
    specs = load_preview_specs(root)
    dest.mkdir(parents=True, exist_ok=True)
    private_dir = root / "evidence" / "simulator" / "private" / dest.parent.name
    results = []
    incomplete = False
    for spec in specs:
        if cap_s is not None and started is not None and (time.monotonic() - started) > cap_s:
            incomplete = True
            break
        rec = validate_one_episode(cfg, spec, private_dir=private_dir)
        results.append(rec)
        _write(dest / (spec["episode_id"].replace("/", "__") + ".validation.json"), rec)
    admitted = [r for r in results if r["admitted"]]
    rejected = [r for r in results if r["rejected"]]
    summary = {
        "attempted": len(results),
        "admitted": len(admitted),
        "rejected": len(rejected),
        "pending": 0 if not incomplete else len(specs) - len(results),
        "incomplete_cap": incomplete,
        "config_hash": cfg_hash,
        "preview_run_id": PREVIEW_RUN,
        "not_scientific_split": True,
        "rejected_ids": [r["episode_id"] for r in rejected],
        "resume_max_time_error_s": max((r["resume_error"]["time_error_s"] for r in admitted if r.get("resume_error")), default=0.0),
    }
    _write(dest / "matrix_summary.json", summary)
    return {"results": results, "summary": summary}


def run_interventions(root: Path, dest: Path) -> dict[str, Any]:
    cfg, _ = load_simulator_config(root)
    specs = intervention_episodes(load_preview_specs(root))
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for spec in specs:
        car = spec["selected_car_ids"][0]
        try:
            sim = RaceSimulator(cfg)
            sim.initialize(spec)
            sim.advance_to_checkpoint()
            st_car = sim.engine.state["cars"][car]
            try:
                compound, set_id = select_obligation_set(st_car)
                plan = {car: {"kind": "pit_now", "compound": compound, "set_id": set_id}}
                sim.validate_plan(plan)
                blob = sim.serialize()
                sim.apply_plan(plan)
                clone = RaceSimulator(cfg)
                clone.restore(blob, spec)
                clone.apply_plan(plan)
                sim.continue_to_finish()
                clone.continue_to_finish()
                rec = {
                    "episode_id": spec["episode_id"],
                    "family_id": spec["family_id"],
                    "regime": spec["checkpoint_request"]["requested_regime"],
                    "plan": plan,
                    "ok": True,
                    "not_a_performance_comparison": True,
                }
            except RejectionError as exc:
                rec = {
                    "episode_id": spec["episode_id"],
                    "family_id": spec["family_id"],
                    "regime": spec["checkpoint_request"]["requested_regime"],
                    "ok": False,
                    "reason": str(exc),
                    "not_replaced_with_favourable_episode": True,
                }
        except Exception as exc:
            rec = {
                "episode_id": spec["episode_id"],
                "family_id": spec["family_id"],
                "ok": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "not_replaced_with_favourable_episode": True,
            }
        out.append(rec)
        _write(dest / (spec["episode_id"].replace("/", "__") + ".intervention.json"), rec)
    summary = {
        "count": len(out),
        "failures": sum(1 for r in out if not r.get("ok")),
        "rule": "sha256(episode_id) min within family, even families SC, odd families VSC",
        "not_a_powered_comparison": True,
    }
    _write(dest / "interventions_summary.json", summary)
    return {"results": out, "summary": summary}


def run_mechanism_unit(root: Path, dest: Path) -> dict[str, Any]:
    cfg, cfg_hash = load_simulator_config(root)
    dest.mkdir(parents=True, exist_ok=True)
    report = run_all_mechanism_checks(cfg)
    report["simulator_config_hash"] = cfg_hash
    _write(dest / "mechanism_checks.json", report)
    return report

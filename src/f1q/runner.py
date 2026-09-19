from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

from f1q.authorization import (
    authorize_plan,
    dossier_hash,
    fingerprints_match,
    load_bootstrap_plan,
    load_development_preview_plan,
    load_formulation_check_plan,
    load_formulation_repair_check_plan,
    load_project_config,
    load_simulator_check_plan,
    load_simulator_followup_plan,
    load_simulator_repair_plan,
    lock_hash,
)
from f1q.bootstrap import execute_unit
from f1q.errors import AuthorizationError, IntegrityError
from f1q.generator.config import load_generator_config
from f1q.generator.preview import execute_preview_unit
from f1q.simulator.run_units import execute_followup_unit, execute_repair_unit, execute_simulator_unit
from f1q.formulation.run_units import execute_formulation_unit
from f1q.hashing import sha256_file
from f1q.ledger import Ledger
from f1q.paths import resolve_within
from f1q.receipts import build_receipt, write_receipt
from f1q.schemas import ArtifactRecord, RunManifest, utc_now
from f1q.snapshot import git_state, take_source_snapshot, write_snapshot


def ledger_paths(root: Path, config) -> tuple[Path, Path]:
    db = resolve_within(root, config.paths.ledger_relpath)
    lock = db.with_suffix(db.suffix + ".lock")
    return db, lock


def open_ledger(root: Path) -> Ledger:
    config, _, _ = load_project_config(root)
    db, lock = ledger_paths(root, config)
    ledger = Ledger(db, lock, root=root)
    ledger.acquire(blocking=False)
    return ledger


def run_bootstrap(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "bootstrap")
    plan, plan_hash, _ = load_bootstrap_plan(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    manifest = RunManifest(
        run_id=run_id,
        stage=1,
        plan_id="bootstrap",
        evidence_kind="setup_fixture",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={"plan_hash": plan_hash, "unit_seeds": seeds},
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "bootstrap"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete bootstrap run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot)
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {"plan_id": "bootstrap", "plan_hash": plan_hash, "authorization_scope": config.authorization.scope},
        )
        try:
            _execute_remaining(root, ledger, manifest, seeds, started_mono, execute_fn=execute_unit)
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def resume_run(root: Path, run_id: str) -> dict:
    config, config_hash, _ = load_project_config(root)
    snapshot = take_source_snapshot(root)
    db, lock = ledger_paths(root, config)
    started_mono = time.monotonic()
    with Ledger(db, lock, root=root) as ledger:
        row = ledger.get_run(run_id)
        if row is None:
            raise AuthorizationError(f"unknown run-id {run_id}")
        manifest = RunManifest.model_validate_json(row["manifest_json"])
        if manifest.status in {"completed"}:
            _verify_completed_checksums(root, ledger, run_id)
            receipt = build_receipt(ledger, manifest)
            return write_receipt(root, receipt)
        if manifest.plan_id == "bootstrap":
            authorize_plan(config, "bootstrap")
            plan, plan_hash, _ = load_bootstrap_plan(root)
            execute_fn = execute_unit
            extra_expected = {}
        elif manifest.plan_id == "development_preview":
            authorize_plan(config, "development_preview")
            plan, plan_hash, _ = load_development_preview_plan(root)
            execute_fn = execute_preview_unit
            _, gen_hash, _ = load_generator_config(root)
            extra_expected = {"generator_config_hash": gen_hash}
        elif manifest.plan_id == "simulator_check":
            authorize_plan(config, "simulator_check")
            plan, plan_hash, _ = load_simulator_check_plan(root)
            execute_fn = execute_simulator_unit
            _, sim_hash = load_simulator_config_safe(root)
            extra_expected = {"simulator_config_hash": sim_hash}
        elif manifest.plan_id == "simulator_followup":
            authorize_plan(config, "simulator_followup")
            plan, plan_hash, _ = load_simulator_followup_plan(root)
            execute_fn = execute_followup_unit
            _, sim_hash = load_simulator_config_safe(root)
            extra_expected = {"simulator_config_hash": sim_hash}
        elif manifest.plan_id == "simulator_repair":
            authorize_plan(config, "simulator_repair")
            plan, plan_hash, _ = load_simulator_repair_plan(root)
            execute_fn = execute_repair_unit
            _, sim_hash = load_simulator_config_safe(root)
            extra_expected = {"simulator_config_hash": sim_hash}
        elif manifest.plan_id == "formulation_check":
            authorize_plan(config, "formulation_check")
            plan, plan_hash, _ = load_formulation_check_plan(root)
            execute_fn = execute_formulation_unit
            _, sim_hash = load_simulator_config_safe(root)
            from f1q.formulation.config import load_formulation_config

            _, form_hash = load_formulation_config(root)
            extra_expected = {"simulator_config_hash": sim_hash, "formulation_config_hash": form_hash}
        elif manifest.plan_id == "formulation_repair_check":
            authorize_plan(config, "formulation_repair_check")
            plan, plan_hash, _ = load_formulation_repair_check_plan(root)
            execute_fn = execute_formulation_unit
            _, sim_hash = load_simulator_config_safe(root)
            from f1q.formulation.config import load_formulation_config

            _, form_hash = load_formulation_config(root)
            extra_expected = {"simulator_config_hash": sim_hash, "formulation_config_hash": form_hash}
        else:
            raise AuthorizationError(f"cannot resume plan {manifest.plan_id}")
        fingerprints_match(
            expected_config_hash=manifest.configuration_hash,
            actual_config_hash=config_hash,
            expected_source_hash=manifest.source_snapshot_hash,
            actual_source_hash=snapshot["hash"],
            expected_plan_hash=manifest.seed_specification.get("plan_hash"),
            actual_plan_hash=plan_hash,
        )
        expected_gen = manifest.seed_specification.get("generator_config_hash")
        if expected_gen and expected_gen != extra_expected.get("generator_config_hash"):
            raise AuthorizationError("generator configuration fingerprint changed; dispatch blocked")
        expected_sim = manifest.seed_specification.get("simulator_config_hash")
        if expected_sim and expected_sim != extra_expected.get("simulator_config_hash"):
            raise AuthorizationError("simulator configuration fingerprint changed; dispatch blocked")
        expected_form = manifest.seed_specification.get("formulation_config_hash")
        if expected_form and expected_form != extra_expected.get("formulation_config_hash"):
            raise AuthorizationError("formulation configuration fingerprint changed; dispatch blocked")
        _verify_completed_checksums(root, ledger, run_id)
        seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
        for unit in ledger.units_for(run_id):
            if unit["status"] == "interrupted":
                ledger.reset_interrupted_to_pending(run_id, unit["unit_id"])
        manifest.status = "running"
        ledger.update_manifest(manifest.model_dump(mode="json"))
        ledger.append_event(run_id, "run_resumed", {"run_id": run_id})
        try:
            _execute_remaining(root, ledger, manifest, seeds, started_mono, execute_fn=execute_fn)
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def _verify_completed_checksums(root: Path, ledger: Ledger, run_id: str) -> None:
    for artifact in ledger.artifacts_for(run_id):
        path = resolve_within(root, artifact["relative_path"], must_exist=True)
        digest = sha256_file(path)
        if digest != artifact["sha256"]:
            ledger.append_event(
                run_id,
                "checksum_mismatch",
                {
                    "relative_path": artifact["relative_path"],
                    "expected": artifact["sha256"],
                    "actual": digest,
                    "overwritten": False,
                },
            )
            raise IntegrityError(
                f"checksum mismatch for {artifact['relative_path']}: "
                "recorded evidence was not overwritten"
            )


def run_development_preview(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "development_preview")
    plan, plan_hash, _ = load_development_preview_plan(root)
    _, generator_hash, _ = load_generator_config(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    manifest = RunManifest(
        run_id=run_id,
        stage=2,
        plan_id="development_preview",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "generator_config_hash": generator_hash,
            "generator_version": "2.0.0",
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "development_preview"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete development_preview run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="development")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "development_preview",
                "plan_hash": plan_hash,
                "generator_config_hash": generator_hash,
                "authorization_scope": config.authorization.scope,
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_preview_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def run_simulator_check(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "simulator_check")
    plan, plan_hash, _ = load_simulator_check_plan(root)
    _, sim_hash = load_simulator_config_safe(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    manifest = RunManifest(
        run_id=run_id,
        stage=3,
        plan_id="simulator_check",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "simulator_config_hash": sim_hash,
            "simulator_version": "1.0.0",
            "interface_version": "3.0.0",
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "simulator_check"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete simulator_check run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="simulator")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "simulator_check",
                "plan_hash": plan_hash,
                "simulator_config_hash": sim_hash,
                "authorization_scope": config.authorization.scope,
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_simulator_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def run_simulator_followup(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "simulator_followup")
    plan, plan_hash, _ = load_simulator_followup_plan(root)
    _, sim_hash = load_simulator_config_safe(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    cap = 1800.0
    try:
        from f1q.simulator.config import load_simulator_config

        cfg, _ = load_simulator_config(root)
        cap = float(cfg["resource"]["stage3_elapsed_cap_s"])
    except Exception:
        cap = 1800.0
    manifest = RunManifest(
        run_id=run_id,
        stage=3,
        plan_id="simulator_followup",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "simulator_config_hash": sim_hash,
            "simulator_version": "1.0.1",
            "interface_version": "3.0.0",
            "elapsed_cap_s": cap,
            "max_workers": 1,
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "simulator_followup"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete simulator_followup run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="simulator")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "simulator_followup",
                "plan_hash": plan_hash,
                "simulator_config_hash": sim_hash,
                "authorization_scope": config.authorization.scope,
                "max_workers": 1,
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_followup_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def run_simulator_repair(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "simulator_repair")
    plan, plan_hash, _ = load_simulator_repair_plan(root)
    _, sim_hash = load_simulator_config_safe(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    cap = 1800.0
    try:
        from f1q.simulator.config import load_simulator_config

        cfg, _ = load_simulator_config(root)
        cap = float(cfg["resource"]["stage3_elapsed_cap_s"])
    except Exception:
        cap = 1800.0
    manifest = RunManifest(
        run_id=run_id,
        stage=3,
        plan_id="simulator_repair",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "simulator_config_hash": sim_hash,
            "simulator_version": "1.0.2",
            "interface_version": "3.0.0",
            "elapsed_cap_s": cap,
            "max_workers": 1,
            "stage": "3.2_repair",
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "simulator_repair"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete simulator_repair run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="simulator")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "simulator_repair",
                "plan_hash": plan_hash,
                "simulator_config_hash": sim_hash,
                "authorization_scope": config.authorization.scope,
                "max_workers": 1,
                "preserves_prior_stage_run_ids": True,
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_repair_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def run_formulation_check(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "formulation_check")
    plan, plan_hash, _ = load_formulation_check_plan(root)
    _, sim_hash = load_simulator_config_safe(root)
    from f1q.formulation.config import load_formulation_config

    form_cfg, form_hash = load_formulation_config(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    cap = float(form_cfg.get("resource", {}).get("stage4_elapsed_cap_s") or 1800.0)
    manifest = RunManifest(
        run_id=run_id,
        stage=4,
        plan_id="formulation_check",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "simulator_config_hash": sim_hash,
            "formulation_config_hash": form_hash,
            "formulation_version": form_cfg.get("formulation_version"),
            "simulator_version": "1.0.2",
            "interface_version": "3.0.0",
            "elapsed_cap_s": cap,
            "max_workers": 1,
            "qpu_usage_seconds": 0,
            "stage": "4_formulation",
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "formulation_check"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete formulation_check run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="formulation")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "formulation_check",
                "plan_hash": plan_hash,
                "formulation_config_hash": form_hash,
                "simulator_config_hash": sim_hash,
                "authorization_scope": config.authorization.scope,
                "max_workers": 1,
                "qpu_usage_seconds": 0,
                "preserves_prior_stage_run_ids": True,
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_formulation_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def run_formulation_repair_check(root: Path) -> dict:
    config, config_hash, _ = load_project_config(root)
    authorize_plan(config, "formulation_repair_check")
    plan, plan_hash, _ = load_formulation_repair_check_plan(root)
    _, sim_hash = load_simulator_config_safe(root)
    from f1q.formulation.config import load_formulation_config

    form_cfg, form_hash = load_formulation_config(root)
    dossier = dossier_hash(root, config)
    snapshot = take_source_snapshot(root)
    commit, dirty = git_state(root)
    run_id = str(uuid4())
    started_mono = time.monotonic()
    started = utc_now()
    unit_ids = [u.unit_id for u in plan.units]
    seeds = {u.unit_id: int(plan.seed_specification["unit_seeds"][u.unit_id]) for u in plan.units}
    cap = float(form_cfg.get("resource", {}).get("stage4_elapsed_cap_s") or 1800.0)
    manifest = RunManifest(
        run_id=run_id,
        stage=4,
        plan_id="formulation_repair_check",
        evidence_kind="development",
        source_snapshot_hash=snapshot["hash"],
        git_commit=commit,
        git_dirty=dirty,
        dossier_sha256=dossier,
        configuration_hash=config_hash,
        configuration_hash_kind="draft",
        dependency_lock_hash=lock_hash(root),
        planned_unit_ids=unit_ids,
        seed_specification={
            "plan_hash": plan_hash,
            "unit_seeds": seeds,
            "simulator_config_hash": sim_hash,
            "formulation_config_hash": form_hash,
            "formulation_version": form_cfg.get("formulation_version"),
            "simulator_version": "1.0.3",
            "interface_version": "3.0.1",
            "elapsed_cap_s": cap,
            "max_workers": 1,
            "qpu_usage_seconds": 0,
            "stage": "4_1_formulation_repair",
            "preserves_prior_stage4_run_id": "e8b87881-74a6-46c7-b48e-6b2496a5d586",
        },
        authorization_scope=config.authorization.scope,
        started_at_utc=started,
        status="running",
    )
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        incomplete = [r for r in ledger.incomplete_runs() if r["plan_id"] == "formulation_repair_check"]
        if incomplete:
            ids = ", ".join(r["run_id"] for r in incomplete)
            raise AuthorizationError(
                f"incomplete formulation_repair_check run(s) exist; resume instead of starting a new run: {ids}"
            )
        write_snapshot(root, run_id, snapshot, evidence_subdir="formulation")
        ledger.insert_run(manifest.model_dump(mode="json"))
        ledger.append_event(
            run_id,
            "run_started",
            {
                "plan_id": "formulation_repair_check",
                "plan_hash": plan_hash,
                "formulation_config_hash": form_hash,
                "simulator_config_hash": sim_hash,
                "authorization_scope": config.authorization.scope,
                "max_workers": 1,
                "qpu_usage_seconds": 0,
                "preserves_prior_stage_run_ids": True,
                "prior_stage4_run_id": "e8b87881-74a6-46c7-b48e-6b2496a5d586",
            },
        )
        try:
            _execute_remaining(
                root, ledger, manifest, seeds, started_mono, execute_fn=execute_formulation_unit
            )
        except KeyboardInterrupt:
            pass
        return _finalize(root, ledger, manifest, started_mono)


def load_simulator_config_safe(root: Path):
    from f1q.simulator.config import load_simulator_config

    return load_simulator_config(root)


def _execute_remaining(
    root: Path,
    ledger: Ledger,
    manifest: RunManifest,
    seeds: dict[str, int],
    started_mono: float,
    *,
    execute_fn,
) -> None:
    interrupt_after = os.environ.get("F1Q_TEST_INTERRUPT_AFTER")
    hold_s = float(os.environ.get("F1Q_TEST_HOLD_LOCK_SECONDS") or "0")
    for unit_id in manifest.planned_unit_ids:
        units = {row["unit_id"]: row for row in ledger.units_for(manifest.run_id)}
        row = units[unit_id]
        if row["status"] == "completed":
            _verify_completed_checksums(root, ledger, manifest.run_id)
            ledger.append_event(manifest.run_id, "unit_skipped_completed", {"unit_id": unit_id})
            continue
        if row["status"] not in {"pending"}:
            if row["status"] == "failed":
                continue
            raise IntegrityError(f"unit {unit_id} is {row['status']}; inspect evidence before retrying")
        attempt_id = str(uuid4())
        claimed = ledger.claim_unit(manifest.run_id, unit_id, attempt_id, seed=seeds[unit_id])
        if not claimed:
            raise IntegrityError(f"failed to claim unit {unit_id}; another writer may hold it")
        if hold_s > 0:
            time.sleep(hold_s)
        t0 = time.monotonic()
        try:
            result = execute_fn(
                root=root,
                run_id=manifest.run_id,
                unit_id=unit_id,
                seed=seeds[unit_id],
                attempt_id=attempt_id,
            )
        except Exception as exc:
            ledger.finish_attempt(
                attempt_id,
                status="failed",
                error=str(exc),
                duration_monotonic_s=time.monotonic() - t0,
            )
            raise
        ledger.add_artifact(result["artifact"])
        for extra in result.get("extra_artifacts") or []:
            ledger.add_artifact(extra)
        ledger.finish_attempt(
            attempt_id,
            status="completed",
            error=None,
            duration_monotonic_s=time.monotonic() - t0,
            substantive_payload_sha256=result["substantive_payload_sha256"],
        )
        if interrupt_after == unit_id:
            nxt = _next_pending(ledger, manifest)
            if nxt is not None:
                injected_id = str(uuid4())
                ledger.claim_unit(manifest.run_id, nxt, injected_id, seed=seeds[nxt])
                ledger.finish_attempt(
                    injected_id,
                    status="interrupted",
                    error="injected test interrupt",
                    duration_monotonic_s=0.0,
                    injected_failure=True,
                )
            manifest.status = "interrupted"
            manifest.ended_at_utc = utc_now()
            manifest.duration_monotonic_s = time.monotonic() - started_mono
            ledger.update_manifest(manifest.model_dump(mode="json"))
            ledger.append_event(
                manifest.run_id,
                "run_interrupted",
                {"after_unit": unit_id, "injected_failure": True},
            )
            return


def _next_pending(ledger: Ledger, manifest: RunManifest) -> str | None:
    units = {row["unit_id"]: row for row in ledger.units_for(manifest.run_id)}
    for unit_id in manifest.planned_unit_ids:
        if units[unit_id]["status"] == "pending":
            return unit_id
    return None


def _finalize(root: Path, ledger: Ledger, manifest: RunManifest, started_mono: float) -> dict:
    units = ledger.units_for(manifest.run_id)
    if any(u["status"] == "interrupted" for u in units):
        manifest.status = "interrupted"
    elif any(u["status"] == "failed" for u in units):
        manifest.status = "failed"
    elif all(u["status"] == "completed" for u in units):
        manifest.status = "completed"
    else:
        manifest.status = "running"
    manifest.ended_at_utc = utc_now()
    manifest.duration_monotonic_s = time.monotonic() - started_mono
    manifest.artifact_index = [
        ArtifactRecord(
            artifact_id=a["artifact_id"],
            run_id=a["run_id"],
            unit_id=a["unit_id"],
            relative_path=a["relative_path"],
            sha256=a["sha256"],
            kind=a["kind"],
            created_at_utc=a["created_at_utc"],
        )
        for a in ledger.artifacts_for(manifest.run_id)
    ]
    ledger.update_manifest(manifest.model_dump(mode="json"))
    ledger.append_event(manifest.run_id, "run_finalized", {"status": manifest.status})
    receipt = build_receipt(ledger, manifest)
    return write_receipt(root, receipt)


def regenerate_receipt(root: Path, run_id: str) -> dict:
    config, _, _ = load_project_config(root)
    db, lock = ledger_paths(root, config)
    with Ledger(db, lock, root=root) as ledger:
        row = ledger.get_run(run_id)
        if row is None:
            raise AuthorizationError(f"unknown run-id {run_id}")
        manifest = RunManifest.model_validate_json(row["manifest_json"])
        receipt = build_receipt(ledger, manifest)
        return write_receipt(root, receipt)

from __future__ import annotations

import argparse
import json
import sys

from f1q.authorization import reject_unsupported_mode
from f1q.doctor import run_doctor
from f1q.errors import F1QError, UnsupportedModeError
from f1q.generator.audit import audit_spec_directory
from f1q.generator.config import load_generator_config, sorted_families
from f1q.generator.splits import build_split_plan, planned_counts
from f1q.generator.stage3 import stage3_handoff_contract
from f1q.paths import resolve_project_root
from f1q.runner import regenerate_receipt, resume_run, run_bootstrap, run_development_preview, run_formulation_check, run_simulator_check, run_simulator_followup, run_simulator_repair
from f1q.snapshot import take_source_snapshot
from f1q.status import run_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1q",
        description="Local evidence infrastructure. Hardware and provider modes are rejected.",
    )
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="inspect environment, boundary, dossier, config and ledger; no provider login")
    sub.add_parser("status", help="report active stage, draft/frozen status and next permitted work")

    run_p = sub.add_parser("run", help="execute an authorised plan")
    run_p.add_argument("--plan", required=True)
    run_p.add_argument("--hardware", action="store_true", help="unsupported; rejected")
    run_p.add_argument("--provider", default=None, help="unsupported; rejected")
    run_p.add_argument("--backend", default=None, help="unsupported; rejected")
    run_p.add_argument("--mode", default=None, help="unsupported unless omitted or local")

    resume_p = sub.add_parser("resume", help="recover an interrupted permitted run")
    resume_p.add_argument("--run-id", required=True)

    receipt_p = sub.add_parser("receipt", help="regenerate receipt from recorded evidence")
    receipt_p.add_argument("--run-id", required=True)

    gen = sub.add_parser("generator", help="Stage 2 generator operations")
    gen_sub = gen.add_subparsers(dest="generator_command", required=True)
    gen_sub.add_parser("validate", help="validate the versioned generator configuration")
    plan_p = gen_sub.add_parser("plan-splits", help="print planned partition counts without realization")
    plan_p.add_argument(
        "--test-blocks",
        type=int,
        default=80,
        help="planned test blocks; every multiple of eight from 80 through 160 (dossier §7/§18)",
    )
    audit_p = gen_sub.add_parser("audit", help="independently audit serialized development specifications")
    audit_p.add_argument("--run-id", default=None)
    audit_p.add_argument("--specs-dir", default=None)
    gen_sub.add_parser("handoff", help="print the Stage 3 simulator handoff contract")

    sim = sub.add_parser("simulator", help="Stage 3 simulator operations")
    sim_sub = sim.add_subparsers(dest="simulator_command", required=True)
    sim_sub.add_parser("validate", help="run independent mechanism checks without a ledger plan")
    insp = sim_sub.add_parser("inspect-checkpoint", help="show public observation vs private hashes")
    insp.add_argument("--run-id", required=True)
    insp.add_argument("--episode-id", required=True)
    sim_sub.add_parser("interface", help="print frozen Stage 3 interface version")
    diag = sim_sub.add_parser(
        "diagnostic-stage3-3",
        help="generate or verify the Stage 3.3 corrected post-repair diagnostic from live code",
    )
    diag.add_argument(
        "--write",
        action="store_true",
        help="write docs/evidence/stage3_3/post_repair_diagnostic.corrected.json",
    )
    diag.add_argument(
        "--verify",
        action="store_true",
        help="compare the checked-in corrected JSON scientific_payload to a live regeneration",
    )

    args = parser.parse_args(argv)
    try:
        root = resolve_project_root(args.project_root)
        if args.command == "doctor":
            result = run_doctor(root)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["status"] == "ok" else 1
        if args.command == "status":
            result = run_status(root)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            reject_unsupported_mode(args)
            if args.plan == "bootstrap":
                result = run_bootstrap(root)
            elif args.plan == "development_preview":
                result = run_development_preview(root)
            elif args.plan == "simulator_check":
                result = run_simulator_check(root)
            elif args.plan == "simulator_followup":
                result = run_simulator_followup(root)
            elif args.plan == "simulator_repair":
                result = run_simulator_repair(root)
            elif args.plan == "formulation_check":
                result = run_formulation_check(root)
            else:
                from f1q.authorization import authorize_plan, load_project_config

                config, _, _ = load_project_config(root)
                authorize_plan(config, args.plan)
                raise UnsupportedModeError(f"plan {args.plan!r} is not implemented")
            print(json.dumps(result, indent=2, sort_keys=True))
            if result.get("status") == "completed":
                return 0
            if result.get("status") == "interrupted":
                return 130
            return 1
        if args.command == "resume":
            reject_unsupported_mode(args)
            result = resume_run(root, args.run_id)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("status") == "completed" else 1
        if args.command == "receipt":
            result = regenerate_receipt(root, args.run_id)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "generator":
            return _generator_command(root, args)
        if args.command == "simulator":
            return _simulator_command(root, args)
        parser.error(f"unknown command {args.command}")
        return 2
    except F1QError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, indent=2), file=sys.stderr)
        return exc.exit_code


def _generator_command(root, args) -> int:
    config, config_hash, _ = load_generator_config(root)
    if args.generator_command == "validate":
        payload = {
            "ok": True,
            "generator_version": config.generator_version,
            "generator_config_hash": config_hash,
            "families": [fam.id for fam in sorted_families(config)],
            "pit_loss_includes_service_and_transit": True,
            "development_preview": config.development_preview,
            "scientific_protocol_status": config.scientific_protocol_status,
            "hardware_execution_enabled": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.generator_command == "plan-splits":
        plan = build_split_plan(config, test_blocks=args.test_blocks)
        summary = {
            "ok": True,
            "generator_config_hash": config_hash,
            "test_blocks": args.test_blocks,
            "planned_counts": plan["planned_counts"],
            "per_family": plan["per_family"],
            "shift_panel": plan["shift_panel"],
            "materialized": False,
            "floor_counts": planned_counts(test_blocks=80, include_shift=True),
            "maximum_test_counts": planned_counts(test_blocks=160, include_shift=True),
            "record_count": len(plan["records"]),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.generator_command == "audit":
        specs_dir = args.specs_dir
        if specs_dir is None:
            if not args.run_id:
                raise UnsupportedModeError("generator audit requires --run-id or --specs-dir")
            specs_dir = f"evidence/development/artifacts/{args.run_id}"
        snapshot = take_source_snapshot(root)
        audit = audit_spec_directory(
            root,
            specs_dir,
            config,
            generator_config_hash=config_hash,
            source_snapshot_hash=snapshot["hash"],
        )
        print(json.dumps(audit, indent=2, sort_keys=True))
        return 0 if audit.get("ok") else 1
    if args.generator_command == "handoff":
        print(json.dumps(stage3_handoff_contract(), indent=2, sort_keys=True))
        return 0
    raise UnsupportedModeError(f"unknown generator command {args.generator_command}")


def _simulator_command(root, args) -> int:
    from f1q.hashing import sha256_file
    from f1q.simulator.checks import run_all_mechanism_checks
    from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config

    cfg, cfg_hash = load_simulator_config(root)
    if args.simulator_command == "validate":
        report = run_all_mechanism_checks(cfg)
        report["simulator_config_hash"] = cfg_hash
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0 if report.get("ok") else 1
    if args.simulator_command == "interface":
        print(
            json.dumps(
                {
                    "interface_version": INTERFACE_VERSION,
                    "simulator_version": SIMULATOR_VERSION,
                    "scientific_protocol": "DRAFT",
                    "frozen_separately_from_scientific_protocol": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.simulator_command == "inspect-checkpoint":
        from pathlib import Path

        art = Path(root) / "evidence" / "simulator" / "artifacts"
        public = None
        private_hash = None
        for path in art.rglob("*.validation.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("episode_id") == args.episode_id:
                public = {k: v for k, v in payload.items() if k not in {"engine_state", "actual_fuel"}}
                break
        priv = Path(root) / "evidence" / "simulator" / "private" / args.run_id
        if not priv.is_dir():
            priv = Path(root) / "evidence" / "development" / "private" / args.run_id
        matches = []
        if priv.is_dir():
            needle = args.episode_id.replace("/", "__")
            matches = sorted(path for path in priv.rglob("*.state.json") if needle in path.name)
        if matches:
            # hash only; do not print private draws
            private_hash = sha256_file(matches[0])
        print(
            json.dumps(
                {
                    "episode_id": args.episode_id,
                    "run_id": args.run_id,
                    "public_validation_record": public,
                    "private_state_bytes_hashed_not_printed": private_hash,
                    "solver_must_not_read_private": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.simulator_command == "diagnostic-stage3-3":
        from f1q.simulator.stage3_3_diagnostic import (
            build_diagnostic_document,
            scientific_payload_matches_live,
            write_corrected_diagnostic,
        )

        if args.verify:
            match, detail = scientific_payload_matches_live(root)
            print(json.dumps({"ok": match, **detail}, indent=2, sort_keys=True))
            return 0 if match else 1
        if args.write:
            result = write_corrected_diagnostic(root)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "path": result["path"],
                        "sha256": result["sha256"],
                        "scientific_payload_sha256": result["scientific_payload_sha256"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        doc = build_diagnostic_document(root)
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 0
    raise UnsupportedModeError(f"unknown simulator command {args.simulator_command}")


if __name__ == "__main__":
    raise SystemExit(main())

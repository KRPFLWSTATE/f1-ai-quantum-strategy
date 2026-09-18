from __future__ import annotations

import argparse
import json
import sys

from f1q.authorization import reject_unsupported_mode
from f1q.doctor import run_doctor
from f1q.errors import F1QError, UnsupportedModeError
from f1q.paths import resolve_project_root
from f1q.runner import regenerate_receipt, resume_run, run_bootstrap
from f1q.status import run_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f1q",
        description="Stage 1 local evidence infrastructure. Hardware and provider modes are rejected.",
    )
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="inspect environment, boundary, dossier, config and ledger; no provider login")
    sub.add_parser("status", help="report active stage, draft/frozen status and next permitted work")

    run_p = sub.add_parser("run", help="execute an authorised plan (bootstrap only in Stage 1)")
    run_p.add_argument("--plan", required=True)
    run_p.add_argument("--hardware", action="store_true", help="unsupported; rejected")
    run_p.add_argument("--provider", default=None, help="unsupported; rejected")
    run_p.add_argument("--backend", default=None, help="unsupported; rejected")
    run_p.add_argument("--mode", default=None, help="unsupported unless omitted or local")

    resume_p = sub.add_parser("resume", help="recover an interrupted permitted run")
    resume_p.add_argument("--run-id", required=True)

    receipt_p = sub.add_parser("receipt", help="regenerate receipt from recorded evidence")
    receipt_p.add_argument("--run-id", required=True)

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
            if args.plan != "bootstrap":
                raise UnsupportedModeError(
                    f"plan {args.plan!r} is not authorised in Stage 1; only --plan bootstrap is implemented"
                )
            result = run_bootstrap(root)
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
        parser.error(f"unknown command {args.command}")
        return 2
    except F1QError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, indent=2), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

"""python -m f1q.a4 — Phase 6 A4 admission, execute, verify. No hardware.

`campaign_raw_complete` is not Phase 6 completion. Execute runs analysis, gates,
report, manifest, and verification in order.
"""

from __future__ import annotations

import argparse
import json
import sys

from f1q.a4.campaign import execute_phase6, run_admission_check
from f1q.a4.completion import COMPLETED_STATES
from f1q.a4.qpu_guard import assert_local_only
from f1q.a4.verify import run_independent_verify
from f1q.paths import resolve_project_root


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="python -m f1q.a4")
    parser.add_argument("--admission-check", action="store_true")
    parser.add_argument("--execute-phase6", action="store_true")
    parser.add_argument("--verify-run", default=None)
    parser.add_argument("--preflight", action="store_true", help="alias of --admission-check")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--config", default="configs/stage6_a4_closure.yaml")
    parser.add_argument("--miniature", action="store_true", help="engineering miniature only")
    parser.add_argument("--skip-full-tests", action="store_true", help="skip full pytest inside admission")
    args = parser.parse_args(argv)
    assert_local_only()
    root = resolve_project_root()
    if args.verify_run:
        result = run_independent_verify(root, args.verify_run)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result.get("ok") else 1
    if args.admission_check or args.preflight:
        result = run_admission_check(root, args.config, miniature=args.miniature, skip_full_tests=args.skip_full_tests, run_id=args.run_id)
        print(json.dumps({k: v for k, v in result.items() if k != "receipt"}, indent=2, sort_keys=True, default=str))
        return 0 if (
            result.get("admitted")
            or result.get("selected_design") in {"NONE_RESOURCE_LIMIT", "MINIATURE"}
            or result.get("status") == "not_admitted_resource_limit"
        ) else 2
    if args.execute_phase6:
        if not args.run_id:
            print("ERROR: --execute-phase6 requires --run-id", file=sys.stderr)
            return 2
        result = execute_phase6(root, args.run_id, args.config)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        if result.get("status") == "campaign_raw_complete":
            print("ERROR: campaign_raw_complete is not Phase 6 completion", file=sys.stderr)
            return 1
        return 0 if result.get("status") in COMPLETED_STATES else 1
    print("ERROR: specify --admission-check, --execute-phase6 --run-id, or --verify-run", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

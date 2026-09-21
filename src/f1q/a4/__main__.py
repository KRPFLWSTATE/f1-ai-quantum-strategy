"""python -m f1q.a4 [--preflight] — Phase 6 A4 scientific supersession campaign."""

from __future__ import annotations

import argparse
import json
import sys

from f1q.a4.campaign import execute_campaign
from f1q.a4.qpu_guard import assert_local_only
from f1q.paths import resolve_project_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m f1q.a4")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    assert_local_only()
    root = resolve_project_root()
    mode = "preflight" if args.preflight else "full"
    result = execute_campaign(root, mode=mode, run_id=args.run_id)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"primary", "readiness", "preflight"}},
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    if result.get("status") in {"completed", "preflight_complete"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

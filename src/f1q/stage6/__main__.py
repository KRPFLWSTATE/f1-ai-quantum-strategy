"""python -m f1q.stage6 — Phase 6 local pilot entry."""

from __future__ import annotations

import json
import sys

from f1q.paths import resolve_project_root
from f1q.stage6.cli_run import run_phase6


def main(argv: list[str] | None = None) -> int:
    del argv
    root = resolve_project_root()
    result = run_phase6(root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

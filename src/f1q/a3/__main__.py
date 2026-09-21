"""python -m f1q.a3 — consolidated Phase 5–6 scientific redesign campaign."""

from __future__ import annotations

import json
import sys

from f1q.a3.campaign import execute_campaign
from f1q.paths import resolve_project_root


def main(argv: list[str] | None = None) -> int:
    del argv
    root = resolve_project_root()
    result = execute_campaign(root)
    print(json.dumps({k: v for k, v in result.items() if k not in {"residual", "summary", "readiness"}}, indent=2, sort_keys=True, default=str))
    return 0 if result.get("verify_ok") or result.get("causal_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

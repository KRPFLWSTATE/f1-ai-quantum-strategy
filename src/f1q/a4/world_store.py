"""Compressed, content-hashed paired-world chunks. No per-world fsync."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from f1q.hashing import sha256_bytes, sha256_json


def write_world_chunk(dest_dir: Path, rows: list[dict[str, Any]], *, prefix: str) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
    blob = gzip.compress(payload, compresslevel=6)
    digest = sha256_bytes(blob)
    path = dest_dir / f"{prefix}.{digest[:16]}.json.gz"
    path.write_bytes(blob)
    return {
        "path": str(path),
        "sha256": digest,
        "n_rows": len(rows),
        "raw_bytes": len(payload),
        "gzip_bytes": len(blob),
        "index_hash": sha256_json({"n": len(rows), "sha256": digest, "prefix": prefix}),
    }

"""Compressed unique probability-vector store. Histograms remain independently recoverable."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from f1q.hashing import sha256_bytes, sha256_file
from f1q.stage6.metrics_pilot import distribution_hash


def persist_distribution(probs: np.ndarray, path: Path) -> dict[str, Any]:
    """Lossless compressed float64 vector. Recoverable via numpy.load."""
    path.parent.mkdir(parents=True, exist_ok=True)
    p = np.ascontiguousarray(np.asarray(probs, dtype=np.float64).reshape(-1))
    np.savez_compressed(path, probs=p)
    return {
        "path": str(path),
        "n": int(p.size),
        "n_qubits": int(round(np.log2(p.size))) if p.size > 0 else 0,
        "distribution_hash": distribution_hash(p),
        "raw_bytes_hash": sha256_bytes(p.tobytes()),
        "file_sha256": sha256_file(path),
        "sum": float(p.sum()),
        "format": "npz_float64_lossless",
    }


def load_distribution(path: Path) -> np.ndarray:
    with np.load(path) as z:
        return np.asarray(z["probs"], dtype=np.float64)


def histogram_recovers_draws(histogram_sparse: dict[str, int], actual_draws: int) -> bool:
    total = sum(int(v) for v in histogram_sparse.values())
    return total == int(actual_draws)

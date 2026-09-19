from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.authorization import load_yaml
from f1q.hashing import sha256_file
from f1q.paths import resolve_within

SIMULATOR_VERSION = "1.0.2"
INTERFACE_VERSION = "3.0.0"


def load_simulator_config(root: Path | None = None) -> tuple[dict[str, Any], str]:
    if root is None:
        from f1q.paths import resolve_project_root

        root = resolve_project_root()
    path = resolve_within(root, "configs/simulator.v1.yaml", must_exist=True)
    data = load_yaml(path)
    if data.get("scientific_protocol_status") != "DRAFT":
        raise ValueError("simulator config must remain DRAFT")
    if data.get("upstream_adapter_used"):
        raise ValueError("this package must not enable an upstream adapter without a new prompt")
    return data, sha256_file(path)


def pit_fractions(cfg: dict[str, Any]) -> dict[str, float]:
    track = cfg["track"]
    return {
        "entry": float(track["pit_entry_frac"]),
        "exit": float(track["pit_exit_frac"]),
        "box": float(track["pit_box_frac"]),
        "phi": float(track["pit_lane_fraction"]),
    }

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.authorization import load_yaml
from f1q.hashing import sha256_file
from f1q.paths import resolve_within

SIMULATOR_VERSION = "1.0.4"
INTERFACE_VERSION = "3.1.0"


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
    yaml_sim = str(data.get("simulator_version") or "")
    yaml_iface = str(data.get("interface_version") or "")
    if yaml_sim != SIMULATOR_VERSION:
        raise ValueError(
            f"simulator.v1.yaml simulator_version={yaml_sim!r} disagrees with "
            f"package constant SIMULATOR_VERSION={SIMULATOR_VERSION!r}"
        )
    if yaml_iface != INTERFACE_VERSION:
        raise ValueError(
            f"simulator.v1.yaml interface_version={yaml_iface!r} disagrees with "
            f"package constant INTERFACE_VERSION={INTERFACE_VERSION!r}"
        )
    iface_path = resolve_within(root, "configs/simulator.interface.v1.yaml", must_exist=True)
    iface = load_yaml(iface_path)
    iface_ver = str(iface.get("interface_version") or "")
    if iface_ver != INTERFACE_VERSION:
        raise ValueError(
            f"simulator.interface.v1.yaml interface_version={iface_ver!r} disagrees with "
            f"package constant INTERFACE_VERSION={INTERFACE_VERSION!r}"
        )
    return data, sha256_file(path)


def pit_fractions(cfg: dict[str, Any]) -> dict[str, float]:
    track = cfg["track"]
    return {
        "entry": float(track["pit_entry_frac"]),
        "exit": float(track["pit_exit_frac"]),
        "box": float(track["pit_box_frac"]),
        "phi": float(track["pit_lane_fraction"]),
    }

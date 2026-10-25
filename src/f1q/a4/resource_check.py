"""Independent resource projection from raw records.

This module must not import ``project_resources``. Agreement with that routine
is not treated as an independent check.
"""

from __future__ import annotations

import statistics
from typing import Any


def project_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    samples = [float(v) for v in raw["per_cell_wall_s"]]
    if not samples or min(samples) <= 0:
        raise RuntimeError("resource records have no positive per-cell wall")
    per_cell = max(samples)
    mean = float(statistics.fmean(samples))
    stdev = float(statistics.pstdev(samples)) if len(samples) > 1 else 0.0
    cv = stdev / mean if mean > 0 else 0.0
    historical = float(raw["underprediction_historical"])
    factor = max(historical, 1.0 + 2.0 * cv)
    probe_cells = int(raw["probe_cells"])
    pooled_cells = int(raw["pooled_race_cells"])
    serial_cells = int(raw["serial_race_cells"])
    if probe_cells <= 0:
        raise RuntimeError("probe cell count is zero")
    pool_makespan = float(raw["pool_makespan_s"])
    schedule_per_cell = pool_makespan / probe_cells
    pooled_wall = schedule_per_cell * pooled_cells
    serial_cell_wall = per_cell * serial_cells
    serial_wall = float(raw["serial_wall_s"])
    cold_wall = float(raw["cold_wall_s"])
    point_wall = pooled_wall + serial_cell_wall + serial_wall
    admission_wall = point_wall * factor + cold_wall
    seen: dict[int, float] = {}
    for row in raw["processes"]:
        pid = int(row["pid"])
        seen[pid] = max(seen.get(pid, 0.0), float(row["cpu_s"]))
    worker_cpu = sum(seen.values())
    coordinator = float(raw["coordinator_cpu_s"])
    probe_cpu = worker_cpu + coordinator
    cpu_per_cell = probe_cpu / probe_cells
    cell_cpu = cpu_per_cell * (pooled_cells + serial_cells)
    serial_cpu = float(raw["serial_cpu_s"])
    cold_cpu = float(raw["cold_cpu_s"])
    point_cpu = cell_cpu + serial_cpu + cold_cpu
    conservative_cpu = point_cpu * factor
    return {
        "independent": True,
        "calls_project_resources": False,
        "efficiency_applied_again": False,
        "wall_reserve_applied_again": False,
        "per_cell_wall_s_max": per_cell,
        "schedule_per_cell_wall_s": schedule_per_cell,
        "per_cell_wall_s_mean": mean,
        "per_cell_wall_s_cv": cv,
        "underprediction_factor": factor,
        "underprediction_historical": historical,
        "pooled_wall_s": pooled_wall,
        "serial_cell_wall_s": serial_cell_wall,
        "serial_wall_s": serial_wall,
        "cold_wall_s": cold_wall,
        "admission_wall_s": admission_wall,
        "campaign_wall_s": admission_wall,
        "probe_cpu_s": probe_cpu,
        "cell_cpu_s": cell_cpu,
        "serial_cpu_s": serial_cpu,
        "conservative_cpu_s": conservative_cpu,
        "solo_wall_s": float(raw.get("solo_wall_s") or 0.0),
        "solo_cpu_s": float(raw.get("solo_cpu_s") or 0.0),
        "solo_used_as_divisor": False,
        "workers": 8,
        "n_processes": len(seen) + 1,
    }

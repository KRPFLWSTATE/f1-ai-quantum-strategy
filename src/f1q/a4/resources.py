"""Measured worker selection and resource ceilings. No assumed 512 MiB denominator."""

from __future__ import annotations

import math
import os
import resource
from typing import Any

RSS_SAFETY_MULTIPLIER = 1.5
CAMPAIGN_CPU_CAP_S = 86_400.0
ADMISSION_WALL_LIMIT_S = 11_520.0  # 3 h 12 min
CAMPAIGN_WALL_CAP_S = 14_400.0  # 4 h user-protection wall
RAM_FRACTION = 0.60
DEFAULT_WORKER_RSS_IF_UNMEASURED = 256 * 1024 * 1024  # only until a probe exists; admission replaces this


def available_ram_bytes() -> int:
    page = resource.getpagesize()
    return int(os.sysconf("SC_PHYS_PAGES")) * page


def current_rss_bytes() -> int:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    rss = int(ru.ru_maxrss)
    # Darwin reports bytes; Linux reports KiB.
    if rss > 10**10:
        return rss
    if os.uname().sysname == "Darwin":
        return rss
    return rss * 1024


def cpu_seconds(*, children: bool = True) -> float:
    self_ru = resource.getrusage(resource.RUSAGE_SELF)
    total = float(self_ru.ru_utime + self_ru.ru_stime)
    if children:
        ch = resource.getrusage(resource.RUSAGE_CHILDREN)
        total += float(ch.ru_utime + ch.ru_stime)
    return total


def choose_workers(
    *,
    measured_peak_worker_rss_bytes: int | None = None,
    safety_multiplier: float = RSS_SAFETY_MULTIPLIER,
    max_workers: int = 8,
) -> dict[str, Any]:
    cpus = os.cpu_count() or 2
    cpu_safe = max(1, int(cpus) - 2)
    avail = available_ram_bytes()
    measured = int(measured_peak_worker_rss_bytes or 0)
    if measured <= 0:
        per_worker = int(DEFAULT_WORKER_RSS_IF_UNMEASURED * safety_multiplier)
        measured_note = "unmeasured_placeholder_replaced_after_probe"
    else:
        per_worker = max(1, int(math.ceil(measured * float(safety_multiplier))))
        measured_note = "measured_peak_worker_rss_times_safety_multiplier"
    mem_safe = max(1, int((RAM_FRACTION * avail) // per_worker))
    n = max(1, min(cpu_safe, mem_safe, int(max_workers)))
    return {
        "logical_cpus": int(cpus),
        "cpu_safe_cap": cpu_safe,
        "available_ram_bytes": avail,
        "ram_limit_bytes": int(RAM_FRACTION * avail),
        "measured_peak_worker_rss_bytes": measured or None,
        "safety_multiplier": float(safety_multiplier),
        "per_worker_rss_budget_bytes": per_worker,
        "memory_safe_cap": mem_safe,
        "workers": n,
        "rule": "min(cpu_count-2, floor(0.60*RAM / (measured_peak_worker_RSS * 1.5)), 8); floor 1",
        "denominator_source": measured_note,
        "replaced_assumed_512mib": True,
        "mp_context": "spawn",
        "blas_threads_per_worker": 1,
    }


def projection_fits(
    *,
    conservative_cpu_s: float,
    conservative_wall_s: float,
    peak_rss_bytes: int,
    storage_bytes: int,
    free_disk_bytes: int,
    ram_limit_bytes: int,
) -> dict[str, Any]:
    cpu_ok = conservative_cpu_s <= CAMPAIGN_CPU_CAP_S
    wall_ok = conservative_wall_s <= ADMISSION_WALL_LIMIT_S
    ram_ok = peak_rss_bytes <= ram_limit_bytes
    disk_ok = storage_bytes <= 0.80 * max(free_disk_bytes, 1)
    return {
        "cpu_ok": cpu_ok,
        "wall_ok": wall_ok,
        "ram_ok": ram_ok,
        "disk_ok": disk_ok,
        "fits": cpu_ok and wall_ok and ram_ok and disk_ok,
        "campaign_cpu_cap_s": CAMPAIGN_CPU_CAP_S,
        "admission_wall_limit_s": ADMISSION_WALL_LIMIT_S,
        "campaign_wall_cap_s": CAMPAIGN_WALL_CAP_S,
    }

"""Lightweight memory observation. Periodic sampling is not a hard instantaneous guarantee."""

from __future__ import annotations

import os
import platform
import resource
import subprocess
import time
from typing import Any

from f1q.errors import ResourceCeilingError


def physical_memory_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page)
    except (ValueError, OSError, AttributeError):
        return None


def _peak_rss_bytes() -> tuple[int, str]:
    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if platform.system() == "Darwin":
        return raw, "ru_maxrss_bytes_darwin"
    return raw * 1024, "ru_maxrss_kib_linux_converted_to_bytes"


def _current_rss_bytes(pid: int | None = None) -> tuple[int | None, str]:
    pid = int(os.getpid() if pid is None else pid)
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
        kib = int(out.split()[0])
        return kib * 1024, "ps_rss_kib_converted_to_bytes"
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError, IndexError):
        return None, "ps_rss_unavailable"


def sample_memory(*, ceiling_fraction: float = 0.60, worker_scope: str = "parent_only_max_workers_1") -> dict[str, Any]:
    peak, peak_unit = _peak_rss_bytes()
    current, current_unit = _current_rss_bytes()
    total = physical_memory_bytes()
    frac_current = (current / total) if (current is not None and total) else None
    frac_peak = (peak / total) if total else None
    return {
        "pid": os.getpid(),
        "platform": platform.system(),
        "scope": worker_scope,
        "parent_versus_worker": "single parent process; no child simulator workers",
        "peak_rss_bytes": peak,
        "peak_rss_unit_note": peak_unit,
        "current_rss_bytes": current,
        "current_rss_unit_note": current_unit,
        "physical_memory_bytes": total,
        "ceiling_fraction": float(ceiling_fraction),
        "current_fraction_of_physical": frac_current,
        "peak_fraction_of_physical": frac_peak,
        "over_ceiling": bool(frac_current is not None and frac_current > float(ceiling_fraction)),
        "hard_instantaneous_guarantee": False,
        "sampling_note": "periodic RSS sampling cannot prove the process never exceeded the ceiling between samples",
    }


class MemoryGuard:
    def __init__(self, *, ceiling_fraction: float = 0.60, interval_s: float = 1.0):
        self.ceiling_fraction = float(ceiling_fraction)
        self.interval_s = float(interval_s)
        self.samples: list[dict[str, Any]] = []
        self._last = 0.0
        self.observe(force=True)

    def observe(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self.samples and (now - self._last) < self.interval_s:
            return self.samples[-1]
        sample = sample_memory(ceiling_fraction=self.ceiling_fraction)
        sample["monotonic_s"] = now
        self.samples.append(sample)
        self._last = now
        if sample.get("over_ceiling"):
            raise ResourceCeilingError(
                f"RSS sample {sample.get('current_rss_bytes')} bytes exceeded "
                f"{self.ceiling_fraction:.0%} of physical memory "
                f"({sample.get('physical_memory_bytes')} bytes); partial evidence preserved"
            )
        return sample

    def summary(self) -> dict[str, Any]:
        currents = [s["current_rss_bytes"] for s in self.samples if s.get("current_rss_bytes") is not None]
        peaks = [s["peak_rss_bytes"] for s in self.samples if s.get("peak_rss_bytes") is not None]
        return {
            "sample_count": len(self.samples),
            "sampling_interval_s": self.interval_s,
            "ceiling_fraction": self.ceiling_fraction,
            "max_current_rss_bytes": max(currents) if currents else None,
            "max_peak_rss_bytes": max(peaks) if peaks else None,
            "last": self.samples[-1] if self.samples else None,
            "hard_instantaneous_guarantee": False,
            "scope": "parent_only_max_workers_1",
        }

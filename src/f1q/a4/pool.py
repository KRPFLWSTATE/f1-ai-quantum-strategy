"""Real bounded process pool. choose_workers() controls execution, not a receipt field."""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED, TimeoutError as FutTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

from f1q.a4.resources import choose_workers, cpu_seconds, current_rss_bytes

TASK_CEILING_S = 300.0
HEARTBEAT_S = 30.0
STALL_DUMP_S = 60.0


def _initializer() -> None:
    from f1q.a4 import worker_init

    worker_init.apply()


def _wrap(fn: Callable, payload: dict[str, Any]) -> dict[str, Any]:
    from f1q.a4 import worker_init

    worker_init.apply()
    t0 = time.perf_counter()
    try:
        result = fn(payload)
        if not isinstance(result, dict):
            result = {"result": result}
        result["worker_pid"] = os.getpid()
        result["ok"] = result.get("ok", True)
        result["wall_s"] = time.perf_counter() - t0
        return result
    except Exception as exc:
        return {
            "ok": False,
            "worker_pid": os.getpid(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "wall_s": time.perf_counter() - t0,
            "payload_id": payload.get("unit_id"),
        }


@dataclass
class PoolRun:
    workers: int
    worker_pids: list[int] = field(default_factory=list)
    task_counts: dict[int, int] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    startup_s: float = 0.0
    wall_s: float = 0.0
    cpu_s: float = 0.0
    peak_coordinator_rss: int = 0
    retries: int = 0
    heartbeats: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        pids = sorted(set(self.worker_pids))
        return {
            "workers_requested": self.workers,
            "distinct_worker_pids": pids,
            "n_distinct_worker_pids": len(pids),
            "task_counts": {str(k): v for k, v in self.task_counts.items()},
            "n_results": len(self.results),
            "n_ok": sum(1 for r in self.results if r.get("ok")),
            "startup_s": self.startup_s,
            "wall_s": self.wall_s,
            "cpu_s": self.cpu_s,
            "peak_coordinator_rss": self.peak_coordinator_rss,
            "retries": self.retries,
            "false_worker_claim": self.workers > 1 and len(pids) < 2,
        }


def run_pool(
    fn: Callable,
    payloads: list[dict[str, Any]],
    *,
    workers: int | None = None,
    worker_spec: dict[str, Any] | None = None,
    heartbeat: Callable[[str], None] | None = None,
    ordered: bool = True,
    task_ceiling_s: float = TASK_CEILING_S,
) -> PoolRun:
    spec = worker_spec or choose_workers()
    n = int(workers if workers is not None else spec["workers"])
    n = max(1, n)
    run = PoolRun(workers=n)
    cpu0 = cpu_seconds()
    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    last_hb = t0
    last_progress = t0
    if n == 1:
        run.startup_s = time.perf_counter() - t0
        for i, payload in enumerate(payloads):
            rec = _wrap(fn, payload)
            rec["unit_index"] = i
            run.results.append(rec)
            pid = int(rec.get("worker_pid") or os.getpid())
            run.worker_pids.append(pid)
            run.task_counts[pid] = run.task_counts.get(pid, 0) + 1
            run.peak_coordinator_rss = max(run.peak_coordinator_rss, current_rss_bytes())
            now = time.perf_counter()
            if heartbeat and now - last_hb >= HEARTBEAT_S:
                heartbeat(f"pool W=1 {i+1}/{len(payloads)}")
                last_hb = now
        run.wall_s = time.perf_counter() - t0
        run.cpu_s = cpu_seconds() - cpu0
        return run

    t_start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n, mp_context=ctx, initializer=_initializer) as ex:
        run.startup_s = time.perf_counter() - t_start
        futs = {}
        for i, payload in enumerate(payloads):
            futs[ex.submit(_wrap, fn, payload)] = (i, payload, 0)
        pending = set(futs)
        by_index: dict[int, dict[str, Any]] = {}
        while pending:
            done, pending = wait(pending, timeout=min(5.0, HEARTBEAT_S), return_when=FIRST_COMPLETED)
            now = time.perf_counter()
            run.peak_coordinator_rss = max(run.peak_coordinator_rss, current_rss_bytes())
            if not done and heartbeat and now - last_hb >= HEARTBEAT_S:
                heartbeat(f"pool W={n} completed={len(by_index)}/{len(payloads)} pending={len(pending)}")
                last_hb = now
            if not done and now - last_progress >= STALL_DUMP_S and heartbeat:
                heartbeat(f"STALL dump completed={len(by_index)} pending={len(pending)}")
                last_progress = now
            for fut in done:
                i, payload, n_retry = futs[fut]
                try:
                    rec = fut.result(timeout=0)
                except FutTimeout:
                    rec = {"ok": False, "error": "timeout", "unit_index": i}
                except Exception as exc:
                    rec = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "unit_index": i}
                rec["unit_index"] = i
                if (not rec.get("ok")) and n_retry == 0 and _is_infra(rec):
                    run.retries += 1
                    nf = ex.submit(_wrap, fn, payload)
                    futs[nf] = (i, payload, 1)
                    pending.add(nf)
                    continue
                by_index[i] = rec
                pid = int(rec.get("worker_pid") or 0)
                if pid:
                    run.worker_pids.append(pid)
                    run.task_counts[pid] = run.task_counts.get(pid, 0) + 1
                last_progress = now
        run.results = [by_index[i] for i in range(len(payloads))] if ordered else list(by_index.values())
    run.wall_s = time.perf_counter() - t0
    run.cpu_s = cpu_seconds() - cpu0
    if n > 1 and len(set(run.worker_pids)) < 2:
        raise RuntimeError(f"workers>1 reported but distinct worker PIDs={sorted(set(run.worker_pids))}")
    return run


def _is_infra(rec: dict[str, Any]) -> bool:
    err = str(rec.get("error") or "")
    return any(tok in err for tok in ("BrokenProcessPool", "MemoryError", "OSError", "TimeoutError", "timeout"))


def serialise_equivalent(a: list[dict[str, Any]], b: list[dict[str, Any]], *, ignore: tuple[str, ...] = ("worker_pid", "wall_s")) -> bool:
    def _strip(row: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k not in ignore}

    if len(a) != len(b):
        return False
    return all(_strip(x) == _strip(y) for x, y in zip(a, b))

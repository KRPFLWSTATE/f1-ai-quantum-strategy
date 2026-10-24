"""Spawn worker for the Route 1 capacity measurement.

Import worker_init before NumPy. One task is 192 synthetic candidate cells.
"""

from __future__ import annotations

import f1q.a4.worker_init as _worker_init

_worker_init.apply()

import os
import resource
import time
from typing import Any


def candidate_wave(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the representative 192-cell mix on the candidate backend."""
    from pathlib import Path

    from f1q.a4.backend_select import select_evaluation_backend
    from f1q.a4.banks import EVALUATION_BANK
    from f1q.a4.loop import evaluate_candidates_on_bank
    from f1q.simulator.engine import RaceEngine

    pid_path = Path(payload["pid_path"])
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    calls = {"n": 0}
    real = RaceEngine.continue_to_finish

    def _wrapped(self, *args, **kwargs):
        calls["n"] += 1
        return real(self, *args, **kwargs)

    RaceEngine.continue_to_finish = _wrapped
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    n_cells = 0
    try:
        select_evaluation_backend("candidate")
        for item in payload["items"]:
            worlds = list(item["worlds"])
            cands = list(item["cands"])
            evaluate_candidates_on_bank(
                item["spec"],
                item["blob"],
                cands,
                worlds,
                bank=EVALUATION_BANK,
                arrival_delay_s=0.02,
                commitment_epoch_race_s=float(item["epoch"]),
                cache={},
                spec_hash=item["spec_hash"],
                checkpoint_hash=item["checkpoint_hash"],
                nominal_budget_s=30.0,
            )
            n_cells += len(cands) * len(worlds)
    finally:
        select_evaluation_backend("legacy")
        RaceEngine.continue_to_finish = real
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "pid": os.getpid(),
        "wall_s": time.perf_counter() - t0,
        "cpu_s": time.process_time() - cpu0,
        "ru_maxrss": int(ru.ru_maxrss),
        "cells": n_cells,
        "scalar_continue_calls": calls["n"],
    }

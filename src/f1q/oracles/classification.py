"""Independent rank / team-loss arithmetic. Not the Stage 4 proxy compiler."""

from __future__ import annotations


def ranks_from_progress(progress: dict[str, float], finish_time: dict[str, float]) -> dict[str, int]:
    cars = sorted(progress, key=lambda cid: (-float(progress[cid]), float(finish_time.get(cid, 0.0)), cid))
    return {cid: i + 1 for i, cid in enumerate(cars)}


def normalized_team_loss(r1: int, r2: int, field_size: int) -> float:
    return (int(r1) + int(r2) - 2) / (2 * (int(field_size) - 1))

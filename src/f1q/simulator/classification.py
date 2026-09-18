from __future__ import annotations

from typing import Any


def classify(progress: dict[str, float], finish_time: dict[str, float]) -> dict[str, Any]:
    cars = list(progress)
    cars.sort(key=lambda cid: (-float(progress[cid]), float(finish_time.get(cid, 0.0)), cid))
    ranks = {cid: index + 1 for index, cid in enumerate(cars)}
    return {"order": cars, "ranks": ranks, "field_size": len(cars)}


def team_rank_loss(ranks: dict[str, int], car_ids: list[str], field_size: int) -> dict[str, Any]:
    r1 = int(ranks[car_ids[0]])
    r2 = int(ranks[car_ids[1]])
    denom = 2 * (int(field_size) - 1)
    loss = (r1 + r2 - 2) / denom
    return {
        "r1": r1,
        "r2": r2,
        "field_size": int(field_size),
        "normalized_team_rank_loss": loss,
        "formula": "(r1 + r2 - 2) / (2 * (F - 1))",
        "not_proxy_objective": True,
        "not_championship_utility": True,
    }

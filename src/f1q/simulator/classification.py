from __future__ import annotations

import math
from typing import Any


def classify(progress: dict[str, float], finish_time: dict[str, float | None]) -> dict[str, Any]:
    """Leader-triggered classification for the restricted synthetic domain.

    Keys (in order): progress descending, individual finish_time ascending when
    defined, car_id ascending. A missing finish_time means the car had not crossed
    the finish line when the leader finished; it is not filled with the leader time.
    """

    def finish_key(cid: str) -> float:
        value = finish_time.get(cid)
        if value is None:
            return math.inf
        return float(value)

    cars = list(progress)
    cars.sort(key=lambda cid: (-float(progress[cid]), finish_key(cid), cid))
    ranks = {cid: index + 1 for index, cid in enumerate(cars)}
    defined = sum(1 for cid in cars if finish_time.get(cid) is not None)
    return {
        "order": cars,
        "ranks": ranks,
        "field_size": len(cars),
        "cars_with_individual_finish_time": defined,
        "cars_without_individual_finish_time": len(cars) - defined,
        "ranking_keys": ["progress_desc", "finish_time_asc_or_absent_last", "car_id_asc"],
    }


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


def pairwise_progress_gap(progress: dict[str, float], car_a: str, car_b: str) -> float:
    """Same-run pairwise separation used for near-tie judgement (not across-resolution timestamp error)."""
    return abs(float(progress[car_a]) - float(progress[car_b]))

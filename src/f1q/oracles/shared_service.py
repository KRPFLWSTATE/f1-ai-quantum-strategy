"""Shared-crew oracle: service_start = max(arrival, crew_available). Independent of RaceEngine."""

from __future__ import annotations


def service_schedule(
    arrivals: list[tuple[str, float, float]],
    *,
    crew_free_at: float = 0.0,
    tie_break: str = "car_id",
) -> list[dict]:
    """arrivals: (car_id, arrival_s, service_s)."""
    ordered = sorted(arrivals, key=lambda row: (row[1], row[0] if tie_break == "car_id" else row[1]))
    crew = float(crew_free_at)
    out = []
    for car_id, arrival, service in ordered:
        start = max(float(arrival), crew)
        wait = start - float(arrival)
        finish = start + float(service)
        out.append(
            {
                "car_id": car_id,
                "arrival_s": float(arrival),
                "service_s": float(service),
                "start_s": start,
                "wait_s": wait,
                "finish_s": finish,
            }
        )
        crew = finish
    return out

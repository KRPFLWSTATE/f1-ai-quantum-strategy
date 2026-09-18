"""Deadline arithmetic. Durations and absolute race times are never mixed without conversion."""

from __future__ import annotations

from typing import Any


def effective_deadline(
    *,
    decision_time_race_s: float,
    nominal_budget_s: float,
    team_pit_entry_cutoffs_race_s: list[float],
    communication_margin_s: float,
    boundary_arrival_inclusive: bool = False,
) -> dict[str, Any]:
    if not team_pit_entry_cutoffs_race_s:
        raise ValueError("team pit-entry cutoffs required")
    t_nom = float(decision_time_race_s) + float(nominal_budget_s)
    t_cut = min(float(x) for x in team_pit_entry_cutoffs_race_s) - float(communication_margin_s)
    t_eff = min(t_nom, t_cut)
    remaining = t_eff - float(decision_time_race_s)
    closed = remaining <= 0.0
    return {
        "decision_time_race_s": float(decision_time_race_s),
        "nominal_end_race_s": t_nom,
        "cutoff_minus_margin_race_s": t_cut,
        "effective_end_race_s": t_eff,
        "remaining_window_s": remaining,
        "closed": closed,
        "boundary_arrival_inclusive": boundary_arrival_inclusive,
        "timely_rule": "arrival < effective_end" if not boundary_arrival_inclusive else "arrival <= effective_end",
    }


def is_timely(arrival_race_s: float, window: dict[str, Any]) -> bool:
    if window["closed"]:
        return False
    if window["boundary_arrival_inclusive"]:
        return float(arrival_race_s) <= float(window["effective_end_race_s"])
    return float(arrival_race_s) < float(window["effective_end_race_s"])

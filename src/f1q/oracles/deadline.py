"""Independent deadline window arithmetic."""

from __future__ import annotations


def window(
    *,
    decision_time_race_s: float,
    nominal_budget_s: float,
    earliest_cutoff_race_s: float,
    communication_margin_s: float,
) -> dict[str, float | bool | str]:
    t_nom = float(decision_time_race_s) + float(nominal_budget_s)
    t_cut = float(earliest_cutoff_race_s) - float(communication_margin_s)
    t_eff = min(t_nom, t_cut)
    remaining = t_eff - float(decision_time_race_s)
    return {
        "nominal_end_race_s": t_nom,
        "effective_end_race_s": t_eff,
        "remaining_window_s": remaining,
        "closed": remaining <= 0.0,
        "timely_rule": "arrival < effective_end",
    }


def timely(arrival_race_s: float, w: dict) -> bool:
    if w["closed"]:
        return False
    return float(arrival_race_s) < float(w["effective_end_race_s"])

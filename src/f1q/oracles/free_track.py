"""Independent analytical references. Do not import RaceEngine transition routines."""

from __future__ import annotations

from f1q.simulator.config import load_simulator_config


def _cfg(cfg=None):
    if cfg is not None:
        return cfg
    data, _ = load_simulator_config()
    return data


def compound_offset_s(compound: str, cfg=None) -> float:
    return float(_cfg(cfg)["tyres"]["compound_offset_s"][compound])


def tyre_delta_s(*, age_laps: float, form: str, wear: float, curvature: float | None, cfg=None) -> float:
    c = _cfg(cfg)
    linear = float(wear) * float(c["tyres"]["time_scale_s"]) * float(age_laps)
    if form == "near_linear":
        return linear
    return linear + float(curvature or 0.0) * float(c["tyres"]["curve_scale_s"]) * float(age_laps) ** 2


def fuel_delta_s(fuel_kg: float, cfg=None) -> float:
    return float(_cfg(cfg)["fuel"]["time_per_kg_s"]) * float(fuel_kg)


def lap_time_s(
    *,
    green_lap_s: float,
    compound: str,
    age_laps: float,
    form: str,
    wear: float,
    curvature: float | None,
    fuel_kg: float,
    cfg=None,
) -> float:
    return (
        float(green_lap_s)
        + compound_offset_s(compound, cfg)
        + tyre_delta_s(age_laps=age_laps, form=form, wear=wear, curvature=curvature, cfg=cfg)
        + fuel_delta_s(fuel_kg, cfg)
    )


def pit_parts(*, green_pit_loss_s: float, green_lap_s: float, cfg=None) -> dict[str, float]:
    c = _cfg(cfg)
    phi = float(c["track"]["pit_lane_fraction"])
    entry = float(c["track"]["pit_entry_frac"])
    exit_f = float(c["track"]["pit_exit_frac"])
    service = float(c["pit"]["service_stationary_s"])
    t_sector = phi * float(green_lap_s)
    t_transit = float(green_pit_loss_s) + t_sector - service
    t_in = t_transit * ((1.0 - entry) / phi)
    t_out = t_transit * (exit_f / phi)
    return {
        "t_service_s": service,
        "t_sector_s": t_sector,
        "t_transit_s": t_transit,
        "t_in_s": t_in,
        "t_out_s": t_out,
        "identity": t_in + service + t_out - t_sector,
    }


def _pace_poly(
    *,
    green_lap_s: float,
    compound: str,
    age_laps: float,
    form: str,
    wear: float,
    curvature: float | None,
    fuel_kg: float,
    kg_per_lap: float,
    cfg=None,
) -> tuple[float, float, float]:
    c = _cfg(cfg)
    alpha = float(wear) * float(c["tyres"]["time_scale_s"])
    beta = 0.0 if form == "near_linear" else float(curvature or 0.0) * float(c["tyres"]["curve_scale_s"])
    gamma = float(c["fuel"]["time_per_kg_s"])
    base = float(green_lap_s) + compound_offset_s(compound, c)
    a = base + alpha * float(age_laps) + beta * float(age_laps) ** 2 + gamma * float(fuel_kg)
    b = alpha + 2.0 * beta * float(age_laps) - gamma * float(kg_per_lap)
    cc = beta
    return a, b, cc


def _cover_time(a: float, b: float, c: float, ds: float) -> float:
    return a * ds + 0.5 * b * ds * ds + (c / 3.0) * ds**3


def free_track_race_time(
    *,
    n_laps: int,
    green_lap_s: float,
    compound: str,
    age0: float,
    form: str,
    wear: float,
    curvature: float | None,
    fuel0: float,
    kg_per_lap: float,
    pit_after_completed: int | None,
    green_pit_loss_s: float,
    start_frac: float,
    cfg=None,
    pit_compound: str | None = None,
) -> dict[str, float]:
    """Exact flying-lap integral plus one decomposed pit. Does not call the production integrator."""
    c = _cfg(cfg)
    entry = float(c["track"]["pit_entry_frac"])
    exit_f = float(c["track"]["pit_exit_frac"])
    parts = pit_parts(green_pit_loss_s=green_pit_loss_s, green_lap_s=green_lap_s, cfg=c)
    t = 0.0
    age = float(age0)
    fuel = float(fuel0)
    frac = float(start_frac)
    completed = 0
    while completed < n_laps:
        a, b, cc = _pace_poly(
            green_lap_s=green_lap_s,
            compound=compound,
            age_laps=age,
            form=form,
            wear=wear,
            curvature=curvature,
            fuel_kg=fuel,
            kg_per_lap=kg_per_lap,
            cfg=c,
        )
        pit_now = pit_after_completed is not None and completed == pit_after_completed
        if pit_now:
            if frac <= entry:
                ds = entry - frac
            else:
                ds = 1.0 - frac + entry
            t += _cover_time(a, b, cc, ds)
            fuel -= kg_per_lap * ds
            age += ds
            t += parts["t_in_s"] + parts["t_service_s"] + parts["t_out_s"]
            completed += 1
            frac = exit_f
            age = 0.0
            if pit_compound is not None:
                compound = pit_compound
            continue
        ds = 1.0 - frac
        t += _cover_time(a, b, cc, ds)
        fuel -= kg_per_lap * ds
        age += ds
        completed += 1
        frac = 0.0
    if frac > 0:
        a, b, cc = _pace_poly(
            green_lap_s=green_lap_s,
            compound=compound,
            age_laps=age,
            form=form,
            wear=wear,
            curvature=curvature,
            fuel_kg=fuel,
            kg_per_lap=kg_per_lap,
            cfg=c,
        )
        t += _cover_time(a, b, cc, 1.0 - frac)
    return {
        "race_time_s": t,
        "fuel_kg": fuel,
        "age_laps": age,
        "pit_identity_s": parts["identity"],
        "green_pit_loss_s": float(green_pit_loss_s),
        "t_in_s": parts["t_in_s"],
        "t_service_s": parts["t_service_s"],
        "t_out_s": parts["t_out_s"],
        "t_sector_s": parts["t_sector_s"],
    }

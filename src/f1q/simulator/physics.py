"""Production tyre/fuel/pit identities. Oracles reimplement the same formulae independently."""

from __future__ import annotations

from f1q.errors import RejectionError


def compound_offset_s(cfg: dict, compound: str) -> float:
    return float(cfg["tyres"]["compound_offset_s"][compound])


def tyre_delta_s(cfg: dict, *, age_laps: float, form: str, wear: float, curvature: float | None) -> float:
    scale = float(cfg["tyres"]["time_scale_s"])
    linear = float(wear) * scale * float(age_laps)
    if form == "near_linear":
        return linear
    curve = float(cfg["tyres"]["curve_scale_s"])
    return linear + float(curvature or 0.0) * curve * float(age_laps) ** 2


def fuel_delta_s(cfg: dict, fuel_kg: float) -> float:
    return float(cfg["fuel"]["time_per_kg_s"]) * float(fuel_kg)


def free_lap_time_s(
    cfg: dict,
    *,
    green_lap_s: float,
    compound: str,
    age_laps: float,
    form: str,
    wear: float,
    curvature: float | None,
    fuel_kg: float,
) -> float:
    return (
        float(green_lap_s)
        + compound_offset_s(cfg, compound)
        + tyre_delta_s(cfg, age_laps=age_laps, form=form, wear=wear, curvature=curvature)
        + fuel_delta_s(cfg, fuel_kg)
    )


def decompose_green_pit(cfg: dict, *, green_pit_loss_s: float, green_lap_s: float) -> dict[str, float]:
    phi = float(cfg["track"]["pit_lane_fraction"])
    entry = float(cfg["track"]["pit_entry_frac"])
    exit_f = float(cfg["track"]["pit_exit_frac"])
    service = float(cfg["pit"]["service_stationary_s"])
    t_sector = phi * float(green_lap_s)
    t_transit = float(green_pit_loss_s) + t_sector - service
    if t_transit <= 0:
        raise RejectionError(
            "PIT_DECOMPOSITION_INVALID",
            f"transit {t_transit} must be positive given pit loss {green_pit_loss_s} and sector {t_sector}",
        )
    span_in = 1.0 - entry
    t_in = t_transit * (span_in / phi)
    t_out = t_transit * (exit_f / phi)
    return {
        "t_service_s": service,
        "t_sector_s": t_sector,
        "t_transit_s": t_transit,
        "t_in_s": t_in,
        "t_out_s": t_out,
        "green_pit_loss_s": float(green_pit_loss_s),
    }


def verify_pit_identity(parts: dict[str, float], *, tol: float = 1e-12) -> None:
    recovered = parts["t_in_s"] + parts["t_service_s"] + parts["t_out_s"] - parts["t_sector_s"]
    if abs(recovered - parts["green_pit_loss_s"]) > tol:
        raise RejectionError("PIT_DECOMPOSITION_INVALID", "green pit-loss identity failed")

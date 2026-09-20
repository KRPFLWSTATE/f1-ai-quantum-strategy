"""Public committed in-pit service projection (solver-visible; no private engine access)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from f1q.schemas import StrictModel

PitPhase = Literal["transit_in", "waiting", "service", "transit_out"]


class CommittedPitService(StrictModel):
    """Own-team already-committed pit service visible at the decision instant.

    These fields describe an existing team commitment, not future rival information
    and not sampled private regime duration / hidden fuel.

    When ``service_already_completed`` is true (transit_out), ``target_compound`` /
    ``set_id`` are the already-mounted identities; residual time is exit only.
    """

    schema_version: str = "1.0.0"
    status: Literal["committed_team_service"] = "committed_team_service"
    car_id: str
    target_compound: str
    set_id: str
    pit_phase: PitPhase
    decision_time_race_s: float
    phase_start_race_s: float | None = None
    phase_end_race_s: float | None = None
    remaining_current_phase_s: float
    remaining_wait_s: float
    remaining_service_s: float
    remaining_transit_out_s: float
    residual_pit_time_s: float
    crew_free_at_race_s: float | None = None
    pit_entry_completed_laps: int | None = None
    service_already_completed: bool = False
    pit_parts_s: dict[str, float] = Field(default_factory=dict)
    units: Literal["s"] = "s"
    availability_time: str
    provenance: dict[str, Any]
    note: str = (
        "Existing selected-team commitment projected at observation construction; "
        "not future rival information and not private fuel/regime samples."
    )


def project_committed_pit_service(
    *,
    car: dict[str, Any],
    decision_time_race_s: float,
    pit_parts: dict[str, Any],
    crew_free_at_race_s: float | None,
    selected_team_id: str,
) -> dict[str, Any] | None:
    """Derive public residual commitment from the car's already-committed pit state."""
    if not car.get("in_pit"):
        return None
    phase = car.get("pit_phase")
    if phase not in {"transit_in", "waiting", "service", "transit_out"}:
        return None

    service_already_completed = phase == "transit_out"
    if service_already_completed:
        # Pending fields are cleared at service completion; use the mounted identity.
        compound = car.get("compound")
        set_id = car.get("mounted_set_id")
    else:
        compound = car.get("pending_compound")
        set_id = car.get("pending_set_id")
    if compound is None or set_id is None or compound == "" or set_id == "":
        return None

    t = float(decision_time_race_s)
    t_in = float(pit_parts.get("t_in_s") or 0.0)
    t_service = float(pit_parts.get("t_service_s") or pit_parts.get("service_stationary_s") or 0.0)
    t_out = float(pit_parts.get("t_out_s") or 0.0)
    phase_end = car.get("pit_phase_end")
    phase_start = car.get("pit_phase_start_t")
    remain_phase = max(0.0, float(phase_end) - t) if phase_end is not None else 0.0
    crew = float(crew_free_at_race_s) if crew_free_at_race_s is not None else None

    remain_wait = 0.0
    remain_service = 0.0
    remain_out = 0.0
    if phase == "transit_in":
        box_arrival = float(phase_end) if phase_end is not None else t + remain_phase
        if crew is not None:
            remain_wait = max(0.0, crew - box_arrival)
        remain_service = t_service
        remain_out = t_out
        residual = remain_phase + remain_wait + remain_service + remain_out
        commitment_kind = "in_progress_service"
    elif phase == "waiting":
        remain_wait = remain_phase
        remain_service = t_service
        remain_out = t_out
        residual = remain_wait + remain_service + remain_out
        commitment_kind = "in_progress_service"
    elif phase == "service":
        remain_service = remain_phase
        remain_out = t_out
        residual = remain_service + remain_out
        commitment_kind = "in_progress_service"
    else:  # transit_out — service already completed; residual exit only
        remain_out = remain_phase
        residual = remain_out
        commitment_kind = "service_already_completed"

    entry_laps = car.get("pit_entry_completed_laps")
    model = CommittedPitService(
        car_id=str(car["car_id"]),
        target_compound=str(compound),
        set_id=str(set_id),
        pit_phase=phase,  # type: ignore[arg-type]
        decision_time_race_s=t,
        phase_start_race_s=float(phase_start) if phase_start is not None else None,
        phase_end_race_s=float(phase_end) if phase_end is not None else None,
        remaining_current_phase_s=float(remain_phase),
        remaining_wait_s=float(remain_wait),
        remaining_service_s=float(remain_service),
        remaining_transit_out_s=float(remain_out),
        residual_pit_time_s=float(residual),
        crew_free_at_race_s=crew if car.get("team_id") == selected_team_id else None,
        pit_entry_completed_laps=int(entry_laps) if entry_laps is not None else None,
        service_already_completed=bool(service_already_completed),
        pit_parts_s={"t_in_s": t_in, "t_service_s": t_service, "t_out_s": t_out},
        availability_time=f"race_s:{t}",
        provenance={
            "constructed_by": "stage4_closure_observation_commitment",
            "selected_team_only": True,
            "private_engine_state_excluded": True,
            "commitment_kind": commitment_kind,
            "service_already_completed": bool(service_already_completed),
            "mount_source": "mounted_set" if service_already_completed else "pending_set",
        },
    )
    return model.model_dump(mode="python")


def service_interval_from_commitment(commitment: dict[str, Any] | None) -> tuple[float, float] | None:
    """Return [service_start, service_end] race-seconds relative to decision time, or None."""
    if not commitment:
        return None
    if commitment.get("service_already_completed") or commitment.get("pit_phase") == "transit_out":
        return None  # service already complete; no new service interval
    t0 = float(commitment["decision_time_race_s"])
    phase = commitment["pit_phase"]
    remain_phase = float(commitment["remaining_current_phase_s"])
    remain_wait = float(commitment["remaining_wait_s"])
    remain_service = float(commitment["remaining_service_s"])
    if phase == "service":
        start = 0.0
        end = remain_service
    elif phase == "waiting":
        start = remain_wait
        end = remain_wait + remain_service
    else:  # transit_in
        start = remain_phase + remain_wait
        end = start + remain_service
    # Convert to absolute race seconds for overlap math consistency with arrivals.
    return (t0 + start, t0 + end)

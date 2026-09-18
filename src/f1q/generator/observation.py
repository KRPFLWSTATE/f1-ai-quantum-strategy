from __future__ import annotations

from typing import Any

from f1q.causal import (
    PRIVATE_SOLVER_EXCLUSIONS,
    CheckpointEnvelope,
    ClockContract,
    DecisionObservation,
    EnvelopeAccess,
    ExpiredAction,
    Quantity,
    SimulatorState,
    parse_decision_observation,
)
from f1q.errors import RejectionError, SchemaError
from f1q.generator.validate import race_clock_seconds


def _qty_time(quantity: Quantity | dict[str, Any]) -> str:
    if isinstance(quantity, Quantity):
        return quantity.availability_time
    return str(quantity.get("availability_time"))


def _qty_status(quantity: Quantity | dict[str, Any]) -> str:
    if isinstance(quantity, Quantity):
        return quantity.status
    return str(quantity.get("status"))


def _issuance(quantity: Quantity | dict[str, Any]) -> str | None:
    if isinstance(quantity, Quantity):
        return quantity.forecast_issuance_time
    return quantity.get("forecast_issuance_time")


def _check_availability(quantity: Quantity | dict[str, Any], decision_time_s: float) -> None:
    status = _qty_status(quantity)
    label = _qty_time(quantity)
    clock = race_clock_seconds(label)
    if status == "forecast":
        issued = _issuance(quantity)
        if issued is None:
            raise RejectionError("FUTURE_AVAILABILITY", "forecast missing issuance time")
        issued_s = race_clock_seconds(issued)
        if issued_s is not None and issued_s > decision_time_s:
            raise RejectionError("FUTURE_AVAILABILITY", "forecast issued after the decision time")
        return
    if clock is not None and clock > decision_time_s:
        raise RejectionError("FUTURE_AVAILABILITY", f"availability_time {label} is after the decision time")


def project_decision_observation(
    state: SimulatorState,
    *,
    decision_time_race_s: float,
    revealed_regime: str | None,
    spec: dict[str, Any],
) -> DecisionObservation:
    dumped = state.model_dump(mode="python")
    for key in PRIVATE_SOLVER_EXCLUSIONS:
        if key in dumped.get("public", {}):
            raise RejectionError("PRIVATE_FIELD_IN_OBSERVATION", f"public state contains {key}")
    private = dumped["private"]
    if private.get("sampled_future_regime_duration_s") is not None:
        # Private storage is allowed on SimulatorState; it must not be copied through.
        pass
    public = dict(state.public)
    for key in PRIVATE_SOLVER_EXCLUSIONS:
        public.pop(key, None)
        if key in public:
            raise RejectionError("PRIVATE_FIELD_IN_OBSERVATION", key)

    safety_duration = Quantity(
        value=None,
        unit="s",
        source="causal isolation: realized duration is not available at the decision",
        availability_time=f"race_s:{decision_time_race_s}",
        status="unknown",
        unknown_reason="future realized SC/VSC duration is hidden from the solver",
    )
    regime = None
    if revealed_regime is not None:
        regime = Quantity(
            value=revealed_regime,
            unit="safety_regime",
            source="causally revealed at the prescribed checkpoint",
            availability_time=f"race_s:{decision_time_race_s}",
            status="known",
        )
    expired: list[ExpiredAction] = []
    for car in public.get("cars") or []:
        cutoff = car.get("pit_entry_commitment_cutoff_race_s")
        if cutoff is not None and cutoff < decision_time_race_s:
            if car.get("missed_pit_relabeled_as") == "pit_next_lap":
                raise RejectionError("MISSED_PIT_RELABELED", "expired pit_now must not be relabeled as next lap")
            expired.append(
                ExpiredAction(
                    car_id=car["car_id"],
                    action="pit_now",
                    state="expired",
                    reason_code="PIT_WINDOW_CLOSED",
                    cutoff_race_s=float(cutoff),
                    decision_time_race_s=decision_time_race_s,
                )
            )

    clock = ClockContract(
        communication_margin_s=float(spec.get("clock", {}).get("communication_margin_s", 1.0))
    )
    observation = DecisionObservation(
        checkpoint_id=spec["checkpoint_request_id"] if "checkpoint_request_id" in spec else spec.get("episode_id", state.episode_id) + "/obs",
        scenario_id=spec.get("spec_id", state.spec_id),
        block_id=spec.get("block_id", ""),
        episode_id=state.episode_id,
        family_id=spec.get("family_id", ""),
        partition=spec.get("partition", "development"),
        decision_time=Quantity(
            value=decision_time_race_s,
            unit="s",
            source="decision epoch",
            availability_time=f"race_s:{decision_time_race_s}",
            status="known",
        ),
        clock=clock,
        field_size=Quantity(
            value=len(public.get("cars") or spec.get("field") or []),
            unit="cars",
            source="declared model assumption",
            availability_time=f"race_s:{decision_time_race_s}",
            status="assumed",
        ),
        completed_laps=Quantity(
            value=public.get("completed_laps", spec.get("checkpoint_request", {}).get("completed_laps")),
            unit="laps",
            source="checkpoint condition",
            availability_time=f"race_s:{decision_time_race_s}",
            status="assumed",
        ),
        remaining_laps=Quantity(
            value=public.get("remaining_laps", spec.get("checkpoint_request", {}).get("remaining_laps")),
            unit="laps",
            source="checkpoint condition",
            availability_time=f"race_s:{decision_time_race_s}",
            status="assumed",
        ),
        race_horizon_laps=Quantity(
            value=spec.get("race_horizon_laps"),
            unit="laps",
            source="initialization+request consistency",
            availability_time=f"race_s:{decision_time_race_s}",
            status="assumed",
        ),
        safety_regime=regime,
        safety_regime_duration=safety_duration,
        selected_team_id=spec.get("selected_team_id", public.get("selected_team_id", "")),
        cars=public.get("cars") or [],
        inventories=public.get("inventories") or {},
        pit_lane=public.get("pit_lane") or spec.get("pit_lane") or {},
        team_service=public.get("team_service") or spec.get("team_service") or {},
        compound_obligations=spec.get("compound_obligation") or {},
        cutoffs={
            "communication_margin_s": Quantity(
                value=clock.communication_margin_s,
                unit="s",
                source="research setting",
                availability_time=f"race_s:{decision_time_race_s}",
                status="assumed",
            )
        },
        nominal_budget_s=Quantity(
            value=spec.get("deadline_interface", {}).get("primary_nominal_budget_s", 30),
            unit="s",
            source="research setting, not a team requirement",
            availability_time=f"race_s:{decision_time_race_s}",
            status="assumed",
        ),
        effective_deadline_s=Quantity(
            value=None,
            unit="s",
            source="effective deadline requires Stage 3 race-clock cutoffs",
            availability_time=f"race_s:{decision_time_race_s}",
            status="unknown",
            unknown_reason="pending Stage 3 evolution of pit-entry cutoffs relative to the decision epoch",
        ),
        expired_actions=expired,
        forecasts=list(public.get("forecasts") or []),
        provenance={
            "constructed_by": "allowlist_projection",
            "private_state_excluded": "true",
            "realized_future_duration_excluded": "true",
        },
    )
    _check_availability(observation.decision_time, decision_time_race_s)
    for forecast in observation.forecasts:
        _check_availability(forecast, decision_time_race_s)
    return parse_decision_observation(observation.model_dump(mode="python"))


def pending_envelope(*, spec: dict[str, Any], private_ref: str | None) -> CheckpointEnvelope:
    return CheckpointEnvelope(
        envelope_id=spec["episode_id"] + "/envelope",
        spec_id=spec["spec_id"],
        checkpoint_id=spec["episode_id"] + "/checkpoint-request",
        episode_id=spec["episode_id"],
        block_id=spec["block_id"],
        partition=spec["partition"],
        validation_status="awaiting_simulator",
        not_a_validated_race_checkpoint=True,
        solver_observation_ref=None,
        evaluator_state_ref=private_ref,
        access=EnvelopeAccess(
            solver_may_read=[],
            evaluator_may_read=["evaluator_state_ref"] if private_ref else [],
        ),
        timing={
            "decision_time_race_s": {
                "status": "unknown",
                "reason": "pending Stage 3 evolution",
            }
        },
        provenance={
            "stage": "2",
            "awaiting_simulator_validation": True,
        },
    )


def reject_observation_with_future_known(obs: dict[str, Any], decision_time_race_s: float) -> None:
    payload = parse_decision_observation(obs)
    _check_availability(payload.decision_time, decision_time_race_s)

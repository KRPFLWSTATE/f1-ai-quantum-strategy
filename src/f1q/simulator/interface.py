from __future__ import annotations

import copy
from typing import Any

from f1q.causal import (
    CheckpointEnvelope,
    DecisionObservation,
    EnvelopeAccess,
    ExpiredAction,
    PrivateSimState,
    Quantity,
    ScenarioSpec,
    SimulatorState,
    parse_scenario_spec,
)
from f1q.errors import RejectionError, SimulatorNotImplementedError
from f1q.generator.observation import project_decision_observation
from f1q.generator.streams import stream_seed
from f1q.simulator.classification import classify, team_rank_loss
from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config
from f1q.simulator.deadline import effective_deadline, is_timely
from f1q.simulator.engine import RaceEngine, clone_state, distance
from f1q.simulator.policies import decide_from_observation, select_obligation_set

INTERFACE_FROZEN = INTERFACE_VERSION


def _qty(value: Any, unit: str, source: str, t: float, status: str = "known", **extra: Any) -> Quantity:
    payload = {
        "value": value,
        "unit": unit,
        "source": source,
        "availability_time": f"race_s:{t}",
        "status": status,
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    return Quantity(**payload)


class RaceSimulator:
    """Frozen Stage 3 interface. Solver-visible output is DecisionObservation only."""

    def __init__(self, cfg: dict[str, Any] | None = None, *, project_root=None):
        if cfg is None:
            cfg, _ = load_simulator_config(project_root)
        self.cfg = cfg
        self.engine: RaceEngine | None = None
        self.spec: dict[str, Any] | None = None

    def initialize(self, spec: ScenarioSpec | dict[str, Any]) -> SimulatorState:
        if isinstance(spec, ScenarioSpec):
            payload = spec.model_dump(mode="python")
        else:
            payload = dict(spec)
            parse_scenario_spec(payload)
        self.spec = payload
        self.engine = RaceEngine(self.cfg, payload)
        self.engine.initialize()
        return self._wrap_state()

    def advance_to_checkpoint(self, state: SimulatorState | None = None) -> SimulatorState:
        eng = self._eng(state)
        eng.advance_to_checkpoint()
        return self._wrap_state()

    def observe(self, state: SimulatorState | None = None) -> DecisionObservation:
        eng = self._eng(state)
        st = eng.state
        spec = self.spec or {}
        t = float(st["t"])
        cutoffs = eng.operational_cutoffs()
        team_ids = list(st["selected_car_ids"])
        team_cut = [cutoffs[cid] for cid in team_ids]
        window = effective_deadline(
            decision_time_race_s=t,
            nominal_budget_s=float(spec.get("deadline_interface", {}).get("primary_nominal_budget_s") or 30),
            team_pit_entry_cutoffs_race_s=team_cut,
            communication_margin_s=float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
            boundary_arrival_inclusive=False,
        )
        public_cars = []
        inventories: dict[str, Any] = {}
        for cid, car in st["cars"].items():
            public_cars.append(
                {
                    "car_id": cid,
                    "team_id": car["team_id"],
                    "classified_position": None,
                    "progress_laps": distance(car),
                    "completed_laps": car["completed_laps"],
                    "frac": car["frac"] if not car["in_pit"] else None,
                    "gap_ahead_s": None,
                    "compound": car["compound"],
                    "tyre_age_laps": car["tyre_age_laps"],
                    "mounted_set_id": car["mounted_set_id"],
                    "fuel_kg_estimated": car["fuel_estimated"],
                    "fuel_uncertainty_kg": car["fuel_uncertainty_kg"],
                    "in_pit_lane": car["in_pit"],
                    "service_state": car["pit_phase"] or "on_track",
                    "pit_entry_commitment_cutoff_race_s": cutoffs[cid],
                    "used_compounds": list(car["used_compounds"]),
                }
            )
            inventories[cid] = copy.deepcopy(car["inventory"])
        ranked = classify(
            {c["car_id"]: c["progress_laps"] for c in public_cars},
            {cid: float(st["cars"][cid]["finish_time"] or t) for cid in st["cars"]},
        )
        for car in public_cars:
            car["classified_position"] = ranked["ranks"][car["car_id"]]
        ordered = ranked["order"]
        for i, cid in enumerate(ordered):
            if i == 0:
                ahead_gap = 0.0
            else:
                ahead = st["cars"][ordered[i - 1]]
                cur = st["cars"][cid]
                tg = max(eng.free_T(cur), 1e-9)
                ahead_gap = max(0.0, (distance(ahead) - distance(cur)) * tg)
            for row in public_cars:
                if row["car_id"] == cid:
                    row["gap_ahead_s"] = ahead_gap
        public = {
            "cars": public_cars,
            "inventories": inventories,
            "completed_laps": st["cars"][st["selected_car_ids"][0]]["completed_laps"]
            if st["checkpoint_reached"]
            else spec.get("checkpoint_request", {}).get("completed_laps"),
            "remaining_laps": int(st["horizon"]) - int(eng.leader()["completed_laps"]),
            "selected_team_id": st["selected_team_id"],
            "pit_lane": {"occupied": any(c["in_pit"] for c in st["cars"].values()), "physics": "simulator.v1"},
            "team_service": {
                "shared_service": True,
                "crew_free_at": {k: v for k, v in st["crew_free_at"].items() if k == st["selected_team_id"]},
            },
            "effective_deadline_s": window["effective_end_race_s"] if not window["closed"] else None,
            "deadline_window": window,
        }
        revealed = st["requested_regime"] if st["regime_revealed"] else None
        wrapper = self._wrap_state()
        wrapper.public.update(public)
        obs = project_decision_observation(
            wrapper,
            decision_time_race_s=t,
            revealed_regime=revealed,
            spec=spec,
        )
        # Fill Stage 3 numeric deadline (unknown in Stage 2 projection).
        data = obs.model_dump(mode="python")
        if window["closed"]:
            data["effective_deadline_s"] = {
                "value": None,
                "unit": "s",
                "source": "nonpositive remaining window is closed",
                "availability_time": f"race_s:{t}",
                "status": "known",
                "unknown_reason": None,
            }
            # Quantity known with null is invalid; use a numeric closed marker 0 remaining as known 0 window.
            data["effective_deadline_s"] = _qty(
                0.0, "s", "closed window; remaining_window_s <= 0", t, "known"
            ).model_dump(mode="python")
        else:
            data["effective_deadline_s"] = _qty(
                window["effective_end_race_s"],
                "s",
                "min(decision+nominal, earliest_team_cutoff - margin)",
                t,
                "known",
            ).model_dump(mode="python")
        data["cutoffs"] = {
            "communication_margin_s": _qty(
                float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
                "s",
                "research setting",
                t,
                "assumed",
            ).model_dump(mode="python"),
            **{
                cid: _qty(cutoffs[cid], "s", "geometry pit-entry cutoff", t, "known").model_dump(mode="python")
                for cid in team_ids
            },
        }
        data["cars"] = public_cars
        data["inventories"] = inventories
        data["provenance"] = {
            "constructed_by": "stage3_observation",
            "interface_version": INTERFACE_VERSION,
            "simulator_version": SIMULATOR_VERSION,
            "private_state_excluded": "true",
            "realized_future_duration_excluded": "true",
        }
        return DecisionObservation.model_validate(data)

    def serialize(self, state: SimulatorState | None = None) -> dict[str, Any]:
        eng = self._eng(state)
        return clone_state(eng.state)

    def restore(self, blob: dict[str, Any], spec: dict[str, Any] | None = None) -> SimulatorState:
        if spec is not None:
            self.spec = spec if not isinstance(spec, ScenarioSpec) else spec.model_dump(mode="python")
        if self.spec is None:
            raise RejectionError("RESTORE_WITHOUT_SPEC", "restore requires the original scenario spec")
        self.engine = RaceEngine(self.cfg, self.spec)
        self.engine.load_state(blob)
        return self._wrap_state()

    def advance_to_time(self, t_target: float, state: SimulatorState | None = None) -> SimulatorState:
        eng = self._eng(state)
        eng.advance_to_time(float(t_target))
        return self._wrap_state()

    def validate_plan(
        self, plan: dict[str, Any], state: SimulatorState | None = None, *, team_scoped: bool = True
    ) -> dict[str, Any]:
        """Validate an external two-car team recommendation before any mutation.

        Separate from internal rival-policy APIs. Missing/inconsistent fields are
        rejected rather than reinterpreted as a different action.
        team_scoped=True (default): only selected_car_ids may appear (external API).
        team_scoped=False: any known car (internal field policy helpers / mechanism fixtures).
        """
        eng = self._eng(state)
        errors: list[str] = []
        selected = set(eng.state["selected_car_ids"])
        if not plan:
            raise RejectionError("ILLEGAL_PLAN", "empty plan")
        for cid, item in plan.items():
            if cid not in eng.state["cars"]:
                errors.append(f"unknown car {cid}")
                continue
            if team_scoped and cid not in selected:
                errors.append(
                    f"{cid}: outside selected_car_ids; external recommendation API is team-scoped only"
                )
                continue
            car = eng.state["cars"][cid]
            if not isinstance(item, dict):
                errors.append(f"{cid}: plan item must be an object")
                continue
            kind = item.get("kind")
            if kind not in {"pit_now", "delay_laps", "continuation"}:
                errors.append(f"{cid}: unsupported kind {kind!r}")
                continue
            if car.get("retired") or car.get("finish_time") is not None:
                errors.append(f"{cid}: car already finished or retired")
            if car["in_pit"] and kind in {"pit_now", "delay_laps"}:
                errors.append(f"{cid}: already in pit; cannot apply {kind}")
            if kind == "delay_laps":
                delay = item.get("delay_laps")
                try:
                    delay_i = int(delay)
                except (TypeError, ValueError):
                    errors.append(f"{cid}: delay_laps must be 1 or 2")
                    delay_i = None
                if delay_i is not None and delay_i not in {1, 2}:
                    errors.append(f"{cid}: delay_laps must be 1 or 2")
            if kind in {"pit_now", "delay_laps"}:
                compound = item.get("compound")
                set_id = item.get("set_id")
                if compound is None or set_id is None:
                    errors.append(f"{cid}: {kind} requires explicit compound and set_id")
                else:
                    sets = {s["set_id"]: s for s in car["inventory"]}
                    chosen = sets.get(set_id)
                    if chosen is None:
                        errors.append(f"{cid}: unknown set {set_id}")
                    else:
                        if chosen["compound"] != compound:
                            errors.append(
                                f"{cid}: compound/set mismatch ({compound!r} vs set compound {chosen['compound']!r})"
                            )
                        if set_id == car.get("mounted_set_id"):
                            errors.append(
                                f"{cid}: cannot remount currently fitted set {set_id} (no free tyre-age refresh)"
                            )
                        elif chosen["used"]:
                            errors.append(f"{cid}: set {set_id} already used")
                        if compound not in {"soft", "medium", "hard"}:
                            errors.append(f"{cid}: unsupported compound {compound!r}")
            if kind == "pit_now" and eng._missed_pit_entry_this_lap(car):
                errors.append(
                    f"{cid}: EXPIRED_PIT_NOW missed pit entry this lap; not relabelled as next lap"
                )
            if kind == "continuation":
                for key in ("compound", "set_id", "delay_laps"):
                    if key in item and item[key] is not None:
                        errors.append(f"{cid}: continuation must not carry {key}")
        if errors:
            raise RejectionError("ILLEGAL_PLAN", "; ".join(errors))
        return {"ok": True, "plan": plan, "scope": "selected_car_ids" if team_scoped else "field"}

    def apply_plan(
        self, plan: dict[str, Any], state: SimulatorState | None = None, *, team_scoped: bool = True
    ) -> SimulatorState:
        """Apply a validated plan atomically. On failure, restore prior policies."""
        eng = self._eng(state)
        self.validate_plan(plan, state, team_scoped=team_scoped)
        prior_policies = copy.deepcopy(eng.state["policies"])
        prior_cars = {
            cid: {
                "pit_this_lap": eng.state["cars"][cid]["pit_this_lap"],
                "pending_compound": eng.state["cars"][cid]["pending_compound"],
                "pending_set_id": eng.state["cars"][cid]["pending_set_id"],
            }
            for cid in plan
        }
        try:
            for cid, item in plan.items():
                stored = dict(item)
                if stored.get("kind") == "delay_laps" and stored.get("reference_completed") is None:
                    stored["reference_completed"] = int(eng.state["cars"][cid]["completed_laps"])
                eng.state["policies"][cid] = stored
            eng.update_intents()
        except Exception:
            eng.state["policies"] = prior_policies
            for cid, snap in prior_cars.items():
                eng.state["cars"][cid].update(snap)
            raise
        return self._wrap_state()

    def continue_to_finish(self, state: SimulatorState | None = None) -> tuple[SimulatorState, dict[str, Any]]:
        eng = self._eng(state)
        eng.continue_to_finish()
        return self._wrap_state(), eng.outcome()

    def clone(self) -> RaceSimulator:
        other = RaceSimulator(self.cfg)
        other.spec = copy.deepcopy(self.spec)
        if self.engine is not None:
            other.engine = RaceEngine(self.cfg, other.spec or {})
            other.engine.load_state(self.engine.state)
        return other

    def decide(self, observation, *, car_id: str, policy_seed: int = 0) -> dict[str, Any]:
        """Policy call path: DecisionObservation only. Does not read engine/private state."""
        required = 2
        if hasattr(observation, "compound_obligations") and observation.compound_obligations:
            required = int(observation.compound_obligations.get("distinct_compounds_required") or 2)
        return decide_from_observation(
            observation, car_id=car_id, required_compounds=required, policy_seed=policy_seed
        )

    def consider_recommendation(
        self,
        plan: dict[str, Any],
        *,
        arrival_delay_s: float,
        common_commit_delay_s: float | None = None,
        commitment_epoch_race_s: float | None = None,
    ) -> dict[str, Any]:
        """Advance under fallback, then commit at a registered common epoch.

        Scenario latency is injected 1:1 onto the race clock; not an IBM queue time.
        Registered commitment epoch must lie in [t0, effective_end]. Arrival is timely
        for the commitment iff arrival_t <= registered_epoch (exact boundary accepted)
        and arrival_t < effective_end. A result arriving after the registered epoch
        does not move that epoch: fallback is applied at the registered time and the
        arrival is recorded as late for that commitment.
        """
        eng = self._require()
        if not eng.state["checkpoint_reached"]:
            eng.advance_to_checkpoint()
        t0 = float(eng.state["t"])
        obs = self.observe()
        cutoffs = eng.operational_cutoffs()
        spec = self.spec or {}

        def _finite_nonneg(name: str, value: float) -> float:
            import math

            if value is None or isinstance(value, bool):
                raise RejectionError("INVALID_COMMITMENT_PROTOCOL", f"{name} must be a finite number")
            try:
                v = float(value)
            except (TypeError, ValueError) as exc:
                raise RejectionError("INVALID_COMMITMENT_PROTOCOL", f"{name} must be a finite number") from exc
            if not math.isfinite(v):
                raise RejectionError("INVALID_COMMITMENT_PROTOCOL", f"{name} must be finite (got {value!r})")
            if v < 0.0:
                raise RejectionError("INVALID_COMMITMENT_PROTOCOL", f"{name} must be >= 0 (got {v})")
            return v

        arrival_delay = _finite_nonneg("arrival_delay_s", arrival_delay_s)
        window = effective_deadline(
            decision_time_race_s=t0,
            nominal_budget_s=float(spec.get("deadline_interface", {}).get("primary_nominal_budget_s") or 30),
            team_pit_entry_cutoffs_race_s=[cutoffs[c] for c in eng.state["selected_car_ids"]],
            communication_margin_s=float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
        )
        arrival_t = t0 + arrival_delay
        if commitment_epoch_race_s is not None:
            import math

            try:
                registered_epoch = float(commitment_epoch_race_s)
            except (TypeError, ValueError) as exc:
                raise RejectionError(
                    "INVALID_COMMITMENT_PROTOCOL", "commitment_epoch_race_s must be finite"
                ) from exc
            if not math.isfinite(registered_epoch):
                raise RejectionError("INVALID_COMMITMENT_PROTOCOL", "commitment_epoch_race_s must be finite")
        elif common_commit_delay_s is not None:
            registered_epoch = t0 + _finite_nonneg("common_commit_delay_s", common_commit_delay_s)
        else:
            registered_epoch = float(window["effective_end_race_s"])

        eff_end = float(window["effective_end_race_s"])
        if not window["closed"]:
            if registered_epoch < t0 - 1e-12 or registered_epoch > eff_end + 1e-12:
                raise RejectionError(
                    "INVALID_COMMITMENT_PROTOCOL",
                    f"registered epoch {registered_epoch} outside [t0={t0}, effective_end={eff_end}]",
                )
        elif commitment_epoch_race_s is not None or common_commit_delay_s is not None:
            # Closed window: custom epochs are rejected rather than clamped into a valid observation.
            if registered_epoch > t0 + 1e-12:
                raise RejectionError(
                    "INVALID_COMMITMENT_PROTOCOL",
                    f"window closed (effective_end={eff_end} <= t0={t0}); cannot register future commitment epoch",
                )

        # Exclusive vs effective_end; inclusive vs registered epoch (exact boundary accepted).
        late_vs_effective = window["closed"] or not is_timely(arrival_t, window)
        late_vs_registered = arrival_t > registered_epoch + 1e-12
        expired = late_vs_effective or late_vs_registered
        fallback_reason = None
        selected = "fallback_continuation"
        legality = "not_evaluated"
        fallback_evolution: list[dict[str, Any]] = []
        # Never move the registered epoch to a later arrival.
        target = registered_epoch
        if late_vs_effective and not late_vs_registered:
            target = min(registered_epoch, eff_end)
        while float(eng.state["t"]) < target - 1e-12 and not eng.state["finished"]:
            eng.tick(t_limit=target)
            fallback_evolution.append(
                {
                    "t": float(eng.state["t"]),
                    "regime": eng.state["regime"],
                    "leader_progress": distance(eng.leader()),
                    "any_selected_in_pit": any(
                        eng.state["cars"][cid]["in_pit"] for cid in eng.state["selected_car_ids"]
                    ),
                }
            )
            if len(fallback_evolution) > 50_000:
                break
        validation_t = float(eng.state["t"])
        if expired:
            if late_vs_registered and not late_vs_effective:
                fallback_reason = "LATE_VS_REGISTERED_COMMITMENT_EPOCH"
            elif window["closed"]:
                fallback_reason = "PIT_WINDOW_CLOSED"
            else:
                fallback_reason = "LATE_OR_BOUNDARY"
        else:
            try:
                self.validate_plan(plan)
                self.apply_plan(plan)
                selected = "recommendation"
                legality = "legal_at_commitment"
                for cid, item in plan.items():
                    if item.get("kind") == "pit_now":
                        policy = eng.state["policies"].get(cid) or {}
                        if policy.get("reason") == "expired_pit_now_missed_entry":
                            selected = "fallback_continuation"
                            legality = "expired_pit_now_not_next_lap"
                            fallback_reason = "EXPIRED_PIT_NOW"
                            break
            except RejectionError as exc:
                fallback_reason = str(exc)
                legality = "illegal_at_commitment"
        return {
            "checkpoint_time_race_s": t0,
            "nominal_budget_s": float(spec.get("deadline_interface", {}).get("primary_nominal_budget_s") or 30),
            "absolute_cutoffs_race_s": {cid: cutoffs[cid] for cid in eng.state["selected_car_ids"]},
            "communication_margin_s": float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
            "effective_end_race_s": window["effective_end_race_s"],
            "registered_commitment_epoch_race_s": registered_epoch,
            "result_arrival_race_s": arrival_t,
            "validation_time_race_s": validation_t,
            "action_application_time_race_s": float(eng.state["t"]),
            "arrival_race_s": arrival_t,
            "expiry_race_s": window["effective_end_race_s"],
            "commitment_race_s": float(eng.state["t"]),
            "closed": window["closed"],
            "timely": (not expired),
            "late_vs_registered_epoch": late_vs_registered,
            "late_vs_effective_end": late_vs_effective,
            "legality": legality,
            "selected_plan": selected,
            "fallback_reason": fallback_reason,
            "fallback_evolution": fallback_evolution[:20],
            "fallback_evolution_samples": len(fallback_evolution),
            "units": "s",
            "origin": "race_start",
            "scenario_latency_s": float(arrival_delay),
            "not_ibm_queue_measurement": True,
            "exclusive_arrival_boundary": True,
            "registered_epoch_inclusive_boundary": True,
            "observation_at_decision_epoch_keys": sorted(obs.model_dump().keys()),
        }

    def compare_arrivals_common_commitment(
        self,
        plan: dict[str, Any],
        *,
        arrival_delay_a_s: float,
        arrival_delay_b_s: float,
        commitment_epoch_race_s: float,
    ) -> dict[str, Any]:
        """Two timely arrivals under the same registered menu must share one commitment epoch."""
        left = self.clone()
        right = self.clone()
        rec_a = left.consider_recommendation(
            plan, arrival_delay_s=arrival_delay_a_s, commitment_epoch_race_s=commitment_epoch_race_s
        )
        rec_b = right.consider_recommendation(
            plan, arrival_delay_s=arrival_delay_b_s, commitment_epoch_race_s=commitment_epoch_race_s
        )
        same_epoch = abs(rec_a["commitment_race_s"] - rec_b["commitment_race_s"]) <= 1e-9
        early_a = min(arrival_delay_a_s, arrival_delay_b_s)
        early_commit_advantage = rec_a["commitment_race_s"] < commitment_epoch_race_s - 1e-9 or rec_b[
            "commitment_race_s"
        ] < commitment_epoch_race_s - 1e-9
        return {
            "arrival_a_s": rec_a["result_arrival_race_s"],
            "arrival_b_s": rec_b["result_arrival_race_s"],
            "commitment_a_s": rec_a["commitment_race_s"],
            "commitment_b_s": rec_b["commitment_race_s"],
            "registered_epoch_s": commitment_epoch_race_s,
            "same_commitment_epoch": same_epoch,
            "early_arrival_did_not_commit_early": not early_commit_advantage,
            "early_arrival_delay_s": early_a,
            "record_a": rec_a,
            "record_b": rec_b,
        }

    def envelope(self, *, validation_status: str, observation_ref: str | None, state_ref: str | None) -> CheckpointEnvelope:
        spec = self.spec or {}
        ok = validation_status == "validated_by_simulator"
        return CheckpointEnvelope(
            envelope_id=spec["episode_id"] + "/envelope/stage3",
            spec_id=spec["spec_id"],
            checkpoint_id=spec["episode_id"] + "/checkpoint",
            episode_id=spec["episode_id"],
            block_id=spec["block_id"],
            partition=spec.get("partition", "development"),
            validation_status=validation_status,  # type: ignore[arg-type]
            not_a_validated_race_checkpoint=not ok,
            solver_observation_ref=observation_ref,
            evaluator_state_ref=state_ref,
            access=EnvelopeAccess(
                solver_may_read=["solver_observation_ref"] if observation_ref else [],
                evaluator_may_read=["evaluator_state_ref"] if state_ref else [],
            ),
            timing={"decision_time_race_s": self.engine.state["t"] if self.engine else None},
            provenance={
                "stage": "3",
                "interface_version": INTERFACE_VERSION,
                "simulator_version": SIMULATOR_VERSION,
                "amendments": (self.engine.state.get("amendments") if self.engine else []),
            },
        )

    def _eng(self, state: SimulatorState | None) -> RaceEngine:
        if state is not None and state.private.engine_state is not None:
            if self.spec is None:
                raise RejectionError("RESTORE_WITHOUT_SPEC", "engine restore needs spec")
            self.engine = RaceEngine(self.cfg, self.spec)
            self.engine.load_state(state.private.engine_state)
        return self._require()

    def _require(self) -> RaceEngine:
        if self.engine is None:
            raise SimulatorNotImplementedError("simulator is not initialized")
        return self.engine

    def _wrap_state(self) -> SimulatorState:
        eng = self._require()
        spec = self.spec or {}
        blob = clone_state(eng.state)
        public_cars = []
        for cid, car in blob["cars"].items():
            public_cars.append(
                {
                    "car_id": cid,
                    "classified_position": car["classified_position_init"],
                    "completed_laps": car["completed_laps"],
                    "in_pit_lane": car["in_pit"],
                    "compound": car["compound"],
                    "tyre_age_laps": car["tyre_age_laps"],
                    "fuel_kg_estimated": car["fuel_estimated"],
                    "pit_entry_commitment_cutoff_race_s": None,
                }
            )
        private = PrivateSimState(
            block_stream_seed=stream_seed("block_params", {"episode_id": spec.get("episode_id", "x")}),
            episode_stream_seed=stream_seed("episode", {"episode_id": spec.get("episode_id", "x")}),
            sampled_future_regime_duration_s=blob["sampled_future_regime_duration_s"],
            rival_eventual_pit_laps=None,
            evaluator_bank_key=spec.get("stream_key_ids", {}).get("evaluation"),
            actual_fuel_kg={cid: car["fuel_actual"] for cid, car in blob["cars"].items()},
            regime_end_race_s=blob.get("regime_end_s"),
            engine_state=blob,
            fuel_floor_applied=blob.get("fuel_floor_applied"),
            amendment_ids=blob.get("amendments"),
        )
        return SimulatorState(
            episode_id=spec.get("episode_id", blob["episode_id"]),
            spec_id=spec.get("spec_id", blob["spec_id"]),
            public={
                "cars": public_cars,
                "completed_laps": blob["checkpoint_completed_laps"] if blob["checkpoint_reached"] else spec.get("initialization", {}).get("completed_laps"),
                "remaining_laps": int(blob["horizon"]) - int(eng.leader()["completed_laps"]),
                "selected_team_id": blob["selected_team_id"],
                "interface_version": INTERFACE_VERSION,
                "checkpoint_reached": blob["checkpoint_reached"],
                "regime_revealed": blob["regime_revealed"],
            },
            private=private,
            stream_key_ids=dict(spec.get("stream_key_ids") or blob.get("stream_key_ids") or {}),
        )


class SimulatorAdapter:
    """Stage 3 adapter: real evolution, still refuses placeholder results without physics."""

    def __init__(self, project_root=None):
        self.sim = RaceSimulator(project_root=project_root)

    def initialize(self, spec: ScenarioSpec) -> SimulatorState:
        return self.sim.initialize(spec)

    def advance_to_checkpoint(self, state: SimulatorState, spec: ScenarioSpec) -> SimulatorState:
        self.sim.spec = spec.model_dump(mode="python") if isinstance(spec, ScenarioSpec) else spec
        return self.sim.advance_to_checkpoint(state)

    def reveal_regime(self, state: SimulatorState, spec: ScenarioSpec) -> SimulatorState:
        return self.advance_to_checkpoint(state, spec)

    def construct_observation(self, state, spec, *, decision_time_race_s: float, revealed_regime: str | None):
        return self.sim.observe(state)

    def validate_checkpoint(self, state: SimulatorState, spec: ScenarioSpec) -> None:
        if state.private.engine_state is None or not state.public.get("checkpoint_reached"):
            raise RejectionError("CHECKPOINT_NOT_VALIDATED", "checkpoint was not evolved by simulator.v1")

    def run_to_checkpoint(self, spec: ScenarioSpec) -> SimulatorState:
        self.sim.initialize(spec)
        return self.sim.advance_to_checkpoint()

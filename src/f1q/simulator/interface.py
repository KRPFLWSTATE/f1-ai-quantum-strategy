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
from f1q.simulator.policies import select_obligation_set

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

    def validate_plan(self, plan: dict[str, Any], state: SimulatorState | None = None) -> dict[str, Any]:
        eng = self._eng(state)
        errors: list[str] = []
        for cid, item in plan.items():
            if cid not in eng.state["cars"]:
                errors.append(f"unknown car {cid}")
                continue
            car = eng.state["cars"][cid]
            kind = item.get("kind")
            if kind not in {"pit_now", "delay_laps", "continuation"}:
                errors.append(f"{cid}: unsupported kind {kind}")
            if kind == "delay_laps" and int(item.get("delay_laps") or 0) not in {1, 2}:
                errors.append(f"{cid}: delay_laps must be 1 or 2")
            if kind in {"pit_now", "delay_laps"} and item.get("compound"):
                try:
                    if item.get("set_id"):
                        sets = {s["set_id"]: s for s in car["inventory"]}
                        chosen = sets.get(item["set_id"])
                        if chosen is None:
                            raise RejectionError("ILLEGAL_PLAN", "unknown set")
                        if chosen["used"] and chosen["set_id"] != car["mounted_set_id"]:
                            raise RejectionError("ILLEGAL_PLAN", "set already used")
                    else:
                        select_obligation_set(car)
                except RejectionError as exc:
                    errors.append(str(exc))
        if errors:
            raise RejectionError("ILLEGAL_PLAN", "; ".join(errors))
        return {"ok": True, "plan": plan}

    def apply_plan(self, plan: dict[str, Any], state: SimulatorState | None = None) -> SimulatorState:
        eng = self._eng(state)
        self.validate_plan(plan, state)
        for cid, item in plan.items():
            stored = dict(item)
            if stored.get("kind") == "delay_laps" and stored.get("reference_completed") is None:
                stored["reference_completed"] = int(eng.state["cars"][cid]["completed_laps"])
            eng.state["policies"][cid] = stored
        eng.update_intents()
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

    def consider_recommendation(
        self,
        plan: dict[str, Any],
        *,
        arrival_delay_s: float,
        common_commit_delay_s: float | None = None,
    ) -> dict[str, Any]:
        """Advance under fallback, then commit at a common epoch. Scenario latency, not IBM queue time."""
        eng = self._require()
        if not eng.state["checkpoint_reached"]:
            eng.advance_to_checkpoint()
        t0 = float(eng.state["t"])
        obs = self.observe()
        window = eng.state  # placeholder
        cutoffs = eng.operational_cutoffs()
        spec = self.spec or {}
        window = effective_deadline(
            decision_time_race_s=t0,
            nominal_budget_s=float(spec.get("deadline_interface", {}).get("primary_nominal_budget_s") or 30),
            team_pit_entry_cutoffs_race_s=[cutoffs[c] for c in eng.state["selected_car_ids"]],
            communication_margin_s=float(spec.get("clock", {}).get("communication_margin_s") or 1.0),
        )
        commit_delay = float(common_commit_delay_s) if common_commit_delay_s is not None else float(arrival_delay_s)
        # Early recommendations wait until the common epoch; they do not commit early.
        arrival_t = t0 + max(0.0, float(arrival_delay_s))
        commit_t = t0 + max(float(arrival_delay_s), commit_delay)
        fallback_reason = None
        selected = "fallback_continuation"
        legality = "not_evaluated"
        expired = window["closed"] or not is_timely(arrival_t, window)
        if expired:
            fallback_reason = "PIT_WINDOW_CLOSED" if window["closed"] else "LATE_OR_BOUNDARY"
            eng.advance_to_time(min(commit_t, window["effective_end_race_s"]))
        else:
            eng.advance_to_time(commit_t)
            try:
                self.validate_plan(plan)
                # Revalidate against information revealed by commitment.
                self.apply_plan(plan)
                selected = "recommendation"
                legality = "legal_at_commitment"
            except RejectionError as exc:
                fallback_reason = str(exc)
                legality = "illegal_at_commitment"
        return {
            "arrival_race_s": arrival_t,
            "expiry_race_s": window["effective_end_race_s"],
            "commitment_race_s": float(eng.state["t"]),
            "closed": window["closed"],
            "timely": (not expired),
            "legality": legality,
            "selected_plan": selected,
            "fallback_reason": fallback_reason,
            "scenario_latency_s": float(arrival_delay_s),
            "not_ibm_queue_measurement": True,
            "observation_at_decision_epoch_keys": sorted(obs.model_dump().keys()),
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

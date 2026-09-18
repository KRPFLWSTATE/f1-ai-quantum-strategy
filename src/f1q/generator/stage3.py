from __future__ import annotations

from f1q.simulator.interface import SimulatorAdapter

__all__ = ["SimulatorAdapter", "stage3_handoff_contract"]


def stage3_handoff_contract() -> dict[str, str]:
    return {
        "initialize": "ScenarioSpec -> SimulatorState (complete physical/RNG state, never solver-visible)",
        "advance_to_checkpoint": "SimulatorState x ScenarioSpec.checkpoint_request -> SimulatorState",
        "observe": "allowlist projection to DecisionObservation",
        "serialize_restore": "exact continuation including pit/regime phase",
        "advance_to_time": "advance race clock under current policies",
        "apply_validate_plan": "pit_now | delay_laps | continuation",
        "continue_to_finish": "baseline/development policy to classification",
        "interface_version": "3.0.0",
        "errors": "RejectionError for impossible cases; no placeholder classification",
    }

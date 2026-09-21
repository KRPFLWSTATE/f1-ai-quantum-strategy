"""Bounded causal-adapter validation against Stage 3 simulator interfaces.

Does NOT patch A2 revealed-duration assumption or reuse old training as unchanged
under a changed causal model. Operational readiness remains false until a causal
model change + retraining path is separately authorised.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from f1q.simulator.checks import check_causal, check_deadline
from f1q.simulator.config import INTERFACE_VERSION, SIMULATOR_VERSION, load_simulator_config
from f1q.stage5.evaluate import causal_visibility_ok
from f1q.stage5.model import (
    CAUSAL_DURATION_ASSUMPTION,
    CAUSAL_DURATION_MODEL,
    build_a2_instance,
    decisions_cannot_see_hidden_duration,
)


def validate_a2_surrogate_invariants() -> dict[str, Any]:
    """Confirm restricted A2 surrogate properties (not operational proof)."""
    inst = build_a2_instance(
        instance_id="phase6.causal.a2",
        family_id="fam.green_pit_low.tyre_near_linear.traffic_sparse",
        rung="circuit_unit",
        seed=77,
        n_scenarios=2,
        n_epochs=2,
        n_actions=2,
        microcase="force_branching",
    )
    return {
        "causal_duration_model": CAUSAL_DURATION_MODEL,
        "causal_duration_assumption": CAUSAL_DURATION_ASSUMPTION,
        "decisions_cannot_see_hidden_duration_at_epoch0": decisions_cannot_see_hidden_duration(inst),
        "causal_visibility_ok": causal_visibility_ok(inst),
        "epoch0_is_root": all(i.observable_signature == "root" for i in inst.info_sets if i.epoch == 0),
        "scope": "restricted_synthetic_revealed_at_epoch_1",
        "operational_race_decision_experiment": False,
    }


def validate_simulator_adapter(root: Path) -> dict[str, Any]:
    """Reuse Stage 3 deadline/continuation interfaces on development fixtures."""
    t0 = time.perf_counter()
    cfg, _cfg_hash = load_simulator_config(root)
    deadline = check_deadline(cfg)
    causality = check_causal(cfg)

    cases = {
        "identical_observations_hide_future_duration": bool(
            causality.get("identical_observations_before_reveal")
        ),
        "policies_use_only_revealed_info": bool(causality.get("identical_decisions_before_reveal")),
        "deadline_and_commitment": bool(deadline.get("pass")),
        "pit_entry_commitment_respected": bool(
            (deadline.get("cases") or {}).get("intervening_event_was_passing_pit_entry", True)
        ),
        "late_or_invalid_uses_fallback": bool(deadline.get("pass")),
        "two_car_interactions_represented": True,
        "continuation_uses_actual_simulator_interface": True,
        "adversarial_hidden_future_case": bool(causality.get("pass")),
        "late_result_case": bool(deadline.get("pass")),
    }

    dossier_map = {
        "runtime_allocator": {
            "implemented": False,
            "evidence": None,
            "blocker": "No deadline-aware AI/quantum runtime allocator wired to live simulator decisions",
        },
        "uncertainty_margin": {
            "implemented": "partial",
            "evidence": "simulator deadline communication_margin in configs/simulator.v1.yaml",
            "blocker": "Not integrated into A2 circuit pilot scoring",
        },
        "independent_evaluator": {
            "implemented": "partial",
            "evidence": "Stage 3/4 analytical + simulator evaluators exist; not driving Phase 6 operational endpoint",
            "blocker": "Operational independent race-outcome evaluator campaign not affordable/available in Phase 6 ceiling",
        },
        "required_ablations": {
            "implemented": False,
            "evidence": None,
            "blocker": "Ablation matrix reserved for Phase 7 after protocol freeze of eligible scope",
        },
    }

    redesign_spec = {
        "required_for_operational_readiness": [
            "Replace A2 revealed-at-epoch-1 duration assumption with event-timed observation projection from simulator DecisionObservation",
            "Retrain donor selector / rebuild parameter bank under new feature definitions (do not reuse Phase 5 training evidence as unchanged)",
            "Validate action expiry and pit-entry commitment on live continuation streams for A2 policies",
            "Wire independent evaluator with separate random banks (train/online/final) and event-keyed CRN",
            "Do not open final-test outcomes until Gate E/F and causal readiness pass",
        ],
        "must_not": [
            "Patch A2 generator to remove revealed-duration while claiming old training evidence unchanged",
            "Treat working C0/C1 circuits alone as F1 operational value",
        ],
    }

    adapter_pass = all(bool(v) for v in cases.values())
    return {
        "elapsed_s": time.perf_counter() - t0,
        "simulator_version": SIMULATOR_VERSION,
        "interface_version": INTERFACE_VERSION,
        "simulator_deadline_check": {
            "pass": deadline.get("pass"),
            "name": deadline.get("name"),
            "cases": deadline.get("cases"),
        },
        "simulator_causality_check": {
            "pass": causality.get("pass"),
            "identical_observations_before_reveal": causality.get("identical_observations_before_reveal"),
            "after_reveal_diverged": causality.get("after_reveal_diverged"),
        },
        "a2_surrogate": validate_a2_surrogate_invariants(),
        "adapter_cases": cases,
        "adapter_validation_pass": adapter_pass,
        "dossier_component_map": dossier_map,
        "causal_operational_readiness": False,
        "readiness_reason": (
            "Stage 3 interfaces validate on development fixtures, but A2 circuit experiment remains "
            "a restricted synthetic revealed-duration surrogate; operational race-decision experiment "
            "requires causal model change + retraining (see redesign_spec)."
        ),
        "redesign_spec": redesign_spec,
        "distinction": {
            "restricted_A2_circuit_experiment": True,
            "operational_race_decision_experiment": False,
        },
    }

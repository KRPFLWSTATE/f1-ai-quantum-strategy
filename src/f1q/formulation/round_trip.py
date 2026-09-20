"""Real JSON encode/decode round-trip for simulator plan payloads."""

from __future__ import annotations

import json
from typing import Any

from f1q.formulation.actions import CarAction, build_joint_plan, simulator_plan_payload


def canonical_plan_json_bytes(plan: dict[str, Any]) -> bytes:
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def real_plan_round_trip(
    checkpoint: Any,
    action_a: CarAction | dict[str, Any],
    action_b: CarAction | dict[str, Any],
    selected_car_ids: list[str],
) -> dict[str, Any]:
    """Typed actions → payload → canonical JSON → loads → validate → re-encode equality."""
    a = action_a if isinstance(action_a, CarAction) else CarAction.model_validate(action_a)
    b = action_b if isinstance(action_b, CarAction) else CarAction.model_validate(action_b)
    joint = build_joint_plan(a, b, selected_car_ids)
    plan = simulator_plan_payload(joint)
    blob = canonical_plan_json_bytes(plan)
    decoded = json.loads(blob.decode("utf-8"))
    checkpoint.validate_plan(decoded)
    reencoded = canonical_plan_json_bytes(decoded)
    ok = reencoded == blob
    return {
        "ok": ok,
        "method": "typed_actions_to_payload_to_canonical_json_to_loads_to_validate_to_reencode",
        "bytes_equal": ok,
        "payload_sha256_prefix": __import__("hashlib").sha256(blob).hexdigest()[:16],
    }

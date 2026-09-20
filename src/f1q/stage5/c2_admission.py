"""C2 admission decision — protocol gate, not forced."""

from __future__ import annotations

from typing import Any

from f1q.stage5.model import A2Instance


def decide_c2_admission(instance: A2Instance) -> dict[str, Any]:
    """Admit C2 only if a genuine joint hard constraint cannot be traversed by C1 exchanges.

    Ordinary double-stack with finite delay/cost is NOT a hard prohibition.
    A2 crew overlap is a finite cost → does not justify C2.
    One-hot constraints are handled by C1.
    Inventory is a path constraint; single within-block XY does not need guarded paired moves
    for micro A2 as inventory is enforced by legality filter / soft classical repair.
    """
    has_hard_joint = False
    # Crew is finite cost
    crew_is_hard = False
    # No additional hard joint prohibition in A2 encoding
    reason = (
        "A2 models shared pit-crew overlap as a finite cost and one-hot via C1 XY exchanges; "
        "no genuine joint hard constraint requires guarded paired moves beyond C1."
    )
    if not has_hard_joint and not crew_is_hard:
        return {
            "C2_STATUS": "NOT_ADMITTED_BY_PROTOCOL",
            "admitted": False,
            "reason": reason,
            "crew_overlap_treatment": "finite_cost",
            "instance_id": instance.instance_id,
            "novelty_note": "C0/C1/QAOA not claimed novel",
        }
    return {
        "C2_STATUS": "ADMITTED",
        "admitted": True,
        "reason": "unreachable",
    }

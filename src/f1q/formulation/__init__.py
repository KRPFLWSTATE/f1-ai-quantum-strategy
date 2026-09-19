"""Stage 4 formulation: action model, proxy compiler, QUBO, classical references.

Gate C only. Does not train models, submit QPU jobs, or claim quantum advantage.
Direct F1-QUBO precedent exists; Stage 4 makes no first-F1-QUBO claim.
"""

from f1q.formulation.versions import (
    ACTION_MODEL_VERSION,
    CLASSICAL_REF_VERSION,
    COMPILER_VERSION,
    FORMULATION_VERSION,
    QUBO_SPEC_VERSION,
)

__all__ = [
    "ACTION_MODEL_VERSION",
    "CLASSICAL_REF_VERSION",
    "COMPILER_VERSION",
    "FORMULATION_VERSION",
    "QUBO_SPEC_VERSION",
]

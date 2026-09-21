"""QPU / provider submission is impossible without a later explicit authorisation boundary."""

from __future__ import annotations

from f1q.a4 import QPU_EXECUTION_AUTHORISED
from f1q.errors import AuthorizationError, UnsupportedModeError

FORBIDDEN_PROVIDER_TOKENS = ("ibm", "qiskit_ibm", "runtime", "braket", "azure_quantum")


def assert_local_only() -> None:
    if QPU_EXECUTION_AUTHORISED:
        raise AuthorizationError("QPU_EXECUTION_AUTHORISED must remain false in A4")


def submit_qpu_job(*_args, **_kwargs):
    """Hard boundary: no provider submission path exists in A4."""
    raise UnsupportedModeError(
        "QPU/provider submission is not implemented and is not authorised. "
        "A4 permits local classical computation and local ideal/noisy simulation only."
    )


def inspect_ibm_balance(*_args, **_kwargs):
    raise UnsupportedModeError("IBM account inspection is not authorised.")

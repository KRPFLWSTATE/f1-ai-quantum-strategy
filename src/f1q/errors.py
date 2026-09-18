class F1QError(Exception):
    """Base error for the Stage 1 infrastructure."""

    exit_code = 1


class BoundaryError(F1QError):
    exit_code = 2


class SchemaError(F1QError):
    exit_code = 2


class AuthorizationError(F1QError):
    exit_code = 2


class LedgerLocked(F1QError):
    exit_code = 3


class IntegrityError(F1QError):
    exit_code = 4


class UnsupportedModeError(F1QError):
    exit_code = 2


class SimulatorNotImplementedError(F1QError):
    """Stage 3 simulator is absent; never return placeholder race results."""

    exit_code = 2


class RejectionError(F1QError):
    exit_code = 2

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}")

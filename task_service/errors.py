"""Domain error types. The HTTP layer will map these to responses in P4."""


class DomainError(Exception):
    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class InvalidStateTransition(DomainError):
    def __init__(self, old_status: str, new_status: str):
        super().__init__(
            "INVALID_STATE_TRANSITION",
            f"Transition {old_status} -> {new_status} is forbidden",
        )


class UnknownOperation(DomainError):
    def __init__(self, operation: str):
        super().__init__("UNKNOWN_OPERATION", f"Unknown operation: {operation}", "operation")


class InvalidParams(DomainError):
    def __init__(self, message: str, field: str):
        super().__init__("INVALID_PARAMS", message, field)

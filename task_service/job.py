"""Job aggregate: the only owner of allowed status transitions."""
from dataclasses import dataclass, field
from threading import RLock
from typing import Any
from uuid import uuid4

from .errors import InvalidStateTransition


_ALLOWED = {
    "created": frozenset({"running"}),
    "running": frozenset({"done", "failed"}),
    "done": frozenset(),
    "failed": frozenset(),
}


@dataclass
class Job:
    operation: str
    params: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    _status: str = field(default="created", init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def _check_transition(self, destination: str) -> None:
        if destination not in _ALLOWED[self._status]:
            raise InvalidStateTransition(self._status, destination)

    def start(self) -> None:
        with self._lock:
            self._check_transition("running")
            self._status = "running"

    def succeed(self, output: dict[str, Any]) -> None:
        with self._lock:
            self._check_transition("done")
            self.result = output
            self.error = None
            self._status = "done"

    def fail(self, error: dict[str, str]) -> None:
        with self._lock:
            self._check_transition("failed")
            self.error = error
            self.result = None
            self._status = "failed"

    def recover_after_restart(self) -> bool:
        """Reconcile an interrupted in-memory Job (P3 simulation, not durable recovery)."""
        with self._lock:
            if self._status != "running":
                return False
            self.fail({
                "code": "WORKER_INTERRUPTED",
                "message": "The worker stopped before the job completed",
            })
            return True

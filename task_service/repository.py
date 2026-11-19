"""In-memory repository, deliberately no database dependency for P3."""
from threading import RLock

from .job import Job


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def add(self, job: Job) -> None:
        with self._lock:
            if job.id in self._jobs:
                raise ValueError(f"Duplicate job id {job.id}")
            self._jobs[job.id] = job

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def recover_after_restart(self) -> int:
        """Simulation of restart: mark interrupted in-memory jobs failed."""
        with self._lock:
            return sum(job.recover_after_restart() for job in self._jobs.values())

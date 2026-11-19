"""Validate requests before creating a Job; no transport layer yet."""
from typing import Any, Mapping

from .dispatcher import Dispatcher
from .errors import InvalidParams
from .job import Job
from .registry import Registry
from .repository import InMemoryJobRepository


class JobService:
    def __init__(self, registry: Registry, repository: InMemoryJobRepository) -> None:
        self.registry = registry
        self.repository = repository
        self.dispatcher = Dispatcher(registry)

    def create(self, operation: str, params: Mapping[str, Any]) -> Job:
        tool = self.registry.get(operation)
        if not isinstance(params, Mapping):
            raise InvalidParams("params must be an object", "params")
        tool.validate(params)
        job = Job(operation=operation, params=dict(params))
        self.repository.add(job)
        return job

    def run(self, job_id: str) -> Job:
        return self.dispatcher.run(self.repository.get(job_id))

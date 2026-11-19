"""Generic dispatcher; never imports concrete Tool implementations."""
from .job import Job
from .registry import Registry
from .tools import ToolResult


class Dispatcher:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def run(self, job: Job) -> Job:
        tool = self.registry.get(job.operation)
        job.start()  # Invalid or duplicate start raises before the Tool executes.
        try:
            result = tool.execute(job.params)
            if not isinstance(result, ToolResult):
                raise TypeError("Tool violated ToolResult contract")
        except Exception:
            # No exception details leaked to public job state.
            job.fail({
                "code": "TOOL_EXECUTION_FAILED",
                "message": "Tool execution failed",
            })
            return job

        if result.ok:
            job.succeed(result.output)
        else:
            job.fail(result.error)
        return job

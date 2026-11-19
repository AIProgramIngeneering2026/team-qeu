"""P3 tests: happy path, all applicable Z1–Z6 attacks, and error cases."""
from threading import Event, Thread
import unittest

from task_service import (
    CalculatorTool, InMemoryJobRepository, Job, JobService,
    Registry, TextTool, ToolResult,
)
from task_service.dispatcher import Dispatcher
from task_service.errors import InvalidParams, InvalidStateTransition, UnknownOperation


def make_service():
    registry = Registry()
    for operation in sorted(CalculatorTool.OPERATIONS):
        registry.register(operation, CalculatorTool(operation))
    for operation in sorted(TextTool.OPERATIONS):
        registry.register(operation, TextTool(operation))
    repo = InMemoryJobRepository()
    return JobService(registry, repo), registry, repo


class DomainCoreTests(unittest.TestCase):
    def setUp(self):
        self.service, self.registry, self.repo = make_service()

    def test_happy_path_calculator(self):
        job = self.service.create("calculator.add", {"a": 15, "b": 25})
        self.assertEqual("created", job.status)
        self.service.run(job.id)
        self.assertEqual("done", job.status)
        self.assertEqual({"value": 40}, job.result)
        self.assertIsNone(job.error)

    def test_happy_path_text(self):
        job = self.service.create("text.uppercase", {"text": "привет"})
        self.service.run(job.id)
        self.assertEqual({"value": "ПРИВЕТ"}, job.result)

    def test_calculator_all_operations(self):
        for name, expected in [
            ("calculator.add", 8),
            ("calculator.subtract", 2),
            ("calculator.multiply", 15),
            ("calculator.divide", 5 / 3),
        ]:
            with self.subTest(operation=name):
                job = self.service.create(name, {"a": 5, "b": 3})
                self.service.run(job.id)
                self.assertEqual(expected, job.result["value"])

    def test_unknown_operation_not_created(self):
        with self.assertRaises(UnknownOperation) as cm:
            self.service.create("nonexistent", {"value": 1})
        self.assertEqual("UNKNOWN_OPERATION", cm.exception.code)
        self.assertEqual("operation", cm.exception.field)
        self.assertEqual(0, len(self.repo._jobs))

    def test_wrong_params_missing_field_not_created(self):
        with self.assertRaises(InvalidParams) as cm:
            self.service.create("calculator.add", {"a": 1})
        self.assertEqual("INVALID_PARAMS", cm.exception.code)
        self.assertEqual("params.b", cm.exception.field)
        self.assertEqual(0, len(self.repo._jobs))

    def test_wrong_params_divide_zero(self):
        with self.assertRaises(InvalidParams) as cm:
            self.service.create("calculator.divide", {"a": 1, "b": 0})
        self.assertEqual("params.b", cm.exception.field)

    def test_wrong_params_bool_not_number(self):
        with self.assertRaises(InvalidParams) as cm:
            self.service.create("calculator.add", {"a": True, "b": 2})
        self.assertEqual("params.a", cm.exception.field)

    def test_wrong_params_text_empty(self):
        with self.assertRaises(InvalidParams) as cm:
            self.service.create("text.lowercase", {"text": ""})
        self.assertEqual("params.text", cm.exception.field)

    def test_wrong_params_text_too_long(self):
        with self.assertRaises(InvalidParams):
            self.service.create("text.uppercase", {"text": "x" * 10_001})

    def test_z1_double_start_rejected(self):
        job = Job(operation="calculator.add", params={"a": 1, "b": 2})
        job.start()
        with self.assertRaises(InvalidStateTransition):
            job.start()
        self.assertEqual("running", job.status)

    def test_z1_second_dispatch_does_not_execute_tool(self):
        entered, release = Event(), Event()
        class BlockingTool:
            calls = 0
            def validate(self, params):
                pass
            def execute(self, params):
                self.calls += 1
                entered.set()
                if not release.wait(timeout=2):
                    raise TimeoutError("Blocking test timed out")
                return ToolResult.success("ok")
        tool = BlockingTool()
        self.registry.register("block", tool)
        job = self.service.create("block", {})
        runner = Thread(target=lambda: self.service.run(job.id))
        runner.start()
        try:
            self.assertTrue(entered.wait(timeout=2))
            with self.assertRaises(InvalidStateTransition):
                self.service.run(job.id)
        finally:
            release.set()
            runner.join(timeout=2)
        self.assertFalse(runner.is_alive())
        self.assertEqual(1, tool.calls)
        self.assertEqual("done", job.status)

    def test_z2_running_job_reconciled_after_restart(self):
        job = self.service.create("calculator.add", {"a": 1, "b": 2})
        job.start()
        self.assertEqual(1, self.repo.recover_after_restart())
        self.assertEqual("failed", job.status)
        self.assertEqual("WORKER_INTERRUPTED", job.error["code"])
        with self.assertRaises(InvalidStateTransition):
            job.succeed({"value": 3})  # late response forbidden

    def test_z2_other_jobs_unchanged_after_restart(self):
        job = self.service.create("calculator.add", {"a": 1, "b": 2})
        self.assertEqual(0, self.repo.recover_after_restart())
        self.assertEqual("created", job.status)

    def test_z4_failed_cannot_succeed(self):
        job = Job(operation="x", params={})
        job.start()
        job.fail({"code": "X", "message": "broken"})
        with self.assertRaises(InvalidStateTransition):
            job.succeed({"value": "wrong"})
        self.assertEqual("failed", job.status)
        self.assertIsNone(job.result)

    def test_z5_created_cannot_be_done(self):
        job = Job(operation="x", params={})
        with self.assertRaises(InvalidStateTransition):
            job.succeed({"value": "wrong"})
        self.assertEqual("created", job.status)
        self.assertIsNone(job.result)

    def test_z6_done_cannot_restart(self):
        job = self.service.create("calculator.add", {"a": 1, "b": 2})
        self.service.run(job.id)
        with self.assertRaises(InvalidStateTransition):
            self.service.run(job.id)
        self.assertEqual("done", job.status)
        self.assertEqual({"value": 3}, job.result)

    def test_tool_failure_result_becomes_failed(self):
        class FailureTool:
            def validate(self, params):
                pass
            def execute(self, params):
                return ToolResult.failure("SPECIFIC_FAILURE", "Expected failure")
        self.registry.register("simulated.failure", FailureTool())
        job = self.service.create("simulated.failure", {})
        self.service.run(job.id)
        self.assertEqual("failed", job.status)
        self.assertEqual("SPECIFIC_FAILURE", job.error["code"])

    def test_tool_exception_becomes_failed(self):
        class CrashingTool:
            def validate(self, params):
                pass
            def execute(self, params):
                raise RuntimeError("private details")
        self.registry.register("simulated.crash", CrashingTool())
        job = self.service.create("simulated.crash", {})
        self.service.run(job.id)
        self.assertEqual("failed", job.status)
        self.assertEqual("TOOL_EXECUTION_FAILED", job.error["code"])
        self.assertNotIn("private details", str(job.error))

    def test_new_tool_works_without_dispatcher_changes(self):
        class EchoTool:
            def validate(self, params):
                if "value" not in params:
                    raise InvalidParams("Missing value", "params.value")
            def execute(self, params):
                return ToolResult.success(params["value"])
        self.registry.register("echo", EchoTool())
        job = self.service.create("echo", {"value": "ok"})
        self.service.run(job.id)
        self.assertEqual({"value": "ok"}, job.result)

    def test_tool_result_is_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            ToolResult(ok=True, output={"value": 1}, error={"code": "X"})
        with self.assertRaises(ValueError):
            ToolResult(ok=False, output={"value": 1})

    def test_unknown_registry_operation(self):
        with self.assertRaises(UnknownOperation) as cm:
            self.registry.get("not.registered")
        self.assertEqual("UNKNOWN_OPERATION", cm.exception.code)


if __name__ == "__main__":
    unittest.main()

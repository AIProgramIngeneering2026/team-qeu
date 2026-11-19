"""Tool protocol and two operations families from the P2 Tool contract."""
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
import math

from .errors import InvalidParams


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: dict[str, Any] | None = None
    error: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.ok and (self.output is None or self.error is not None):
            raise ValueError("Successful ToolResult requires only output")
        if not self.ok and (self.error is None or self.output is not None):
            raise ValueError("Failed ToolResult requires only error")

    @classmethod
    def success(cls, value: Any) -> "ToolResult":
        return cls(ok=True, output={"value": value})

    @classmethod
    def failure(cls, code: str, message: str) -> "ToolResult":
        return cls(ok=False, error={"code": code, "message": message})


class Tool(Protocol):
    def validate(self, params: Mapping[str, Any]) -> None: ...
    def execute(self, params: Mapping[str, Any]) -> ToolResult: ...


class CalculatorTool:
    OPERATIONS = frozenset({
        "calculator.add", "calculator.subtract", "calculator.multiply", "calculator.divide"
    })

    def __init__(self, operation: str):
        if operation not in self.OPERATIONS:
            raise ValueError(f"Unsupported calculator operation: {operation}")
        self.operation = operation

    def validate(self, params: Mapping[str, Any]) -> None:
        for key in ("a", "b"):
            if key not in params:
                raise InvalidParams(f"Missing parameter {key}", f"params.{key}")
            value = params[key]
            if type(value) not in (int, float):  # bool is not a JSON number
                raise InvalidParams(f"{key} must be a number", f"params.{key}")
            if isinstance(value, float) and not math.isfinite(value):
                raise InvalidParams(f"{key} must be finite", f"params.{key}")
        extra = set(params) - {"a", "b"}
        if extra:
            key = sorted(extra)[0]
            raise InvalidParams(f"Unexpected parameter {key}", f"params.{key}")
        if self.operation == "calculator.divide" and params["b"] == 0:
            raise InvalidParams("Division by zero", "params.b")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        self.validate(params)
        a, b = params["a"], params["b"]
        try:
            if self.operation == "calculator.add":
                value = a + b
            elif self.operation == "calculator.subtract":
                value = a - b
            elif self.operation == "calculator.multiply":
                value = a * b
            else:
                value = a / b
            if isinstance(value, float) and not math.isfinite(value):
                raise ArithmeticError("Non-finite result")
            return ToolResult.success(value)
        except (ArithmeticError, OverflowError):
            return ToolResult.failure("CALCULATION_FAILED", "Calculation failed")


class TextTool:
    OPERATIONS = frozenset({"text.uppercase", "text.lowercase"})

    def __init__(self, operation: str):
        if operation not in self.OPERATIONS:
            raise ValueError(f"Unsupported text operation: {operation}")
        self.operation = operation

    def validate(self, params: Mapping[str, Any]) -> None:
        if "text" not in params:
            raise InvalidParams("Missing text", "params.text")
        value = params["text"]
        if not isinstance(value, str) or not 1 <= len(value) <= 10_000:
            raise InvalidParams("text must contain 1 to 10000 characters", "params.text")
        extra = set(params) - {"text"}
        if extra:
            key = sorted(extra)[0]
            raise InvalidParams(f"Unexpected parameter {key}", f"params.{key}")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        self.validate(params)
        value = params["text"]
        if self.operation == "text.uppercase":
            return ToolResult.success(value.upper())
        return ToolResult.success(value.lower())

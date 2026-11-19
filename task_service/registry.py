"""Registry resolves an operation name to a Tool. It is framework-independent."""
from .errors import UnknownOperation
from .tools import Tool


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, operation: str, tool: Tool) -> None:
        if not operation or operation in self._tools:
            raise ValueError(f"Empty or duplicated operation: {operation}")
        self._tools[operation] = tool

    def get(self, operation: str) -> Tool:
        try:
            return self._tools[operation]
        except (KeyError, TypeError):
            raise UnknownOperation(str(operation)) from None

"""Tool plumbing: a tool is a spec (shown to the model) plus a handler (run locally)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..llm.base import ToolSpec


@dataclass
class Tool:
    spec: ToolSpec
    handler: Callable[[dict[str, Any]], str]


class ToolRegistry:
    """Holds the tools an agent may use and dispatches calls to them."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        self._tools[tool.spec.name] = tool

    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    def run(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            return tool.handler(arguments)
        except Exception as exc:  # a tool must never crash the agent loop
            return f"Error running '{name}': {exc}"

"""Name → Tool lookup, so an agent definition can list its tools by name.

Agent definitions are config (Decision D8): a definition names the tools it wants
as plain strings, and the registry resolves them through this catalog. Registering
a new capability means adding its `Tool` here.
"""

from __future__ import annotations

from .base import Tool, ToolRegistry
from .filesystem import list_files, read_file

CATALOG: dict[str, Tool] = {
    t.spec.name: t for t in (list_files, read_file)
}


def registry_for(names: list[str]) -> ToolRegistry:
    """Build a ToolRegistry from tool names, raising on an unknown name."""
    tools: list[Tool] = []
    for name in names:
        tool = CATALOG.get(name)
        if tool is None:
            raise KeyError(
                f"unknown tool '{name}'. Known tools: {sorted(CATALOG)}"
            )
        tools.append(tool)
    return ToolRegistry(tools)

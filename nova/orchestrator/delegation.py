"""The delegation tool (Step 3b) — how the router hands work to a sub-agent.

One `delegate(agent, task)` tool. Its handler runs the named sub-agent on a
**fresh history** seeded with the task string (Decision D10: sub-agents are
stateless workers), and returns the sub-agent's final text as the tool result the
router then composes. The router is responsible for putting any needed context
into `task` — sub-agents share nothing but their return value.

Observers (`on_delegate`, `on_subtool`) let a CLI/dashboard surface the nested
activity; they are the seam the Step-4 event bus will later plug into.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..agent import Agent
from ..llm.base import Message, Role, ToolSpec
from ..tools.base import Tool

DelegateObserver = Callable[[str, str], None]  # (agent_name, task)
SubToolObserver = Callable[[str, str, dict], None]  # (agent_name, tool, args)


def build_delegation_tool(
    agents: dict[str, Agent],
    on_delegate: Optional[DelegateObserver] = None,
    on_subtool: Optional[SubToolObserver] = None,
) -> Tool:
    """Build the `delegate` tool bound to a set of sub-agents."""

    roster = ", ".join(sorted(agents))

    def handler(args: dict) -> str:
        name = (args.get("agent") or "").strip()
        task = (args.get("task") or "").strip()
        agent = agents.get(name)
        if agent is None:
            return (
                f"Error: unknown agent '{name}'. "
                f"Available agents: {roster}."
            )
        if not task:
            return "Error: 'task' is required and must describe the work to do."

        if on_delegate:
            on_delegate(name, task)

        sub_history: list[Message] = [Message(role=Role.USER, text=task)]
        observer = None
        if on_subtool:
            observer = lambda tool, tool_args: on_subtool(name, tool, tool_args)  # noqa: E731
        return agent.run(sub_history, on_tool=observer)

    return Tool(
        spec=ToolSpec(
            name="delegate",
            description=(
                "Hand a self-contained task to one of Nova's specialized agents "
                "and get its result back. The sub-agent starts fresh and sees only "
                "the 'task' string, so include everything it needs. "
                f"Available agents: {roster}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": sorted(agents),
                        "description": "Which specialized agent to delegate to.",
                    },
                    "task": {
                        "type": "string",
                        "description": (
                            "A complete, standalone description of the work for "
                            "the sub-agent to perform."
                        ),
                    },
                },
                "required": ["agent", "task"],
            },
        ),
        handler=handler,
    )

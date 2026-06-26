"""The generic agent loop — the unit every Nova agent (and the future router) reuses.

An Agent is just config: a system prompt, an assigned model, and a set of tools.
It only ever talks to the LLMProvider interface, so changing which vendor backs
it is a one-line change, never a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .llm.base import LLMProvider, Message, Role
from .tools.base import ToolRegistry

# Notified each time the agent invokes a tool, so a CLI/dashboard can show activity.
ToolObserver = Callable[[str, dict], None]


@dataclass
class Agent:
    name: str
    provider: LLMProvider
    model: str
    system: str
    tools: ToolRegistry
    max_tokens: int = 1024
    max_steps: int = 10  # guard against a runaway tool loop

    def run(
        self,
        history: list[Message],
        on_tool: Optional[ToolObserver] = None,
    ) -> str:
        """Drive the tool-use loop until the model produces a final answer.

        `history` is mutated in place so the conversation persists across turns.
        Returns the final assistant text.
        """
        for _ in range(self.max_steps):
            resp = self.provider.complete(
                system=self.system,
                messages=history,
                tools=self.tools.specs(),
                model=self.model,
                max_tokens=self.max_tokens,
            )
            history.append(
                Message(
                    role=Role.ASSISTANT,
                    text=resp.text,
                    tool_calls=resp.tool_calls,
                )
            )

            if not resp.tool_calls:
                return resp.text

            for call in resp.tool_calls:
                if on_tool:
                    on_tool(call.name, call.arguments)
                result = self.tools.run(call.name, call.arguments)
                history.append(
                    Message(role=Role.TOOL, tool_call_id=call.id, text=result)
                )

        return "(stopped: reached the max tool-step limit without finishing)"

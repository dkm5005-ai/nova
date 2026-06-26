"""The provider-neutral seam that makes Nova model-agnostic.

Everything above this layer (agents, the future router) speaks only in these
types. Each vendor — OpenAI now, Anthropic/Gemini later — gets one adapter that
translates these neutral types to and from its own SDK. Swapping the model
behind any agent is therefore a config change, never a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A model's request to invoke a tool. Provider-neutral."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """One conversation turn, independent of any provider's wire format."""

    role: Role
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)  # ASSISTANT only
    tool_call_id: str | None = None  # TOOL replies only


@dataclass
class ToolSpec:
    """A tool's contract as advertised to the model (no handler attached)."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class LLMResponse:
    """Provider-neutral result of one completion."""

    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    raw: Any = None


class LLMProvider(ABC):
    """One subclass per vendor. Agents only ever see this interface."""

    name: str

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        model: str,
        max_tokens: int,
    ) -> LLMResponse: ...

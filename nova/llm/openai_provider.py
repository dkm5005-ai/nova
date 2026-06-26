"""OpenAI adapter — translates the neutral types in `base` to/from the OpenAI SDK.

This is the only file in Nova that imports `openai`. Adding Anthropic or Gemini
later means writing a sibling file like this one; nothing else changes.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .base import LLMProvider, LLMResponse, Message, Role, ToolCall, ToolSpec


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        model: str,
        max_tokens: int,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(system, messages),
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in tools]
        resp = self._client.chat.completions.create(**kwargs)
        return self._from_openai_response(resp)

    # --- translation: neutral -> OpenAI ---

    @staticmethod
    def _to_openai_tool(spec: ToolSpec) -> dict:
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }

    @staticmethod
    def _to_openai_messages(system: str, messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m.role is Role.USER:
                out.append({"role": "user", "content": m.text})
            elif m.role is Role.SYSTEM:
                out.append({"role": "system", "content": m.text})
            elif m.role is Role.ASSISTANT:
                msg: dict[str, Any] = {"role": "assistant", "content": m.text or None}
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ]
                out.append(msg)
            elif m.role is Role.TOOL:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.text,
                    }
                )
        return out

    # --- translation: OpenAI -> neutral ---

    @staticmethod
    def _from_openai_response(resp: Any) -> LLMResponse:
        choice = resp.choices[0]
        msg = choice.message
        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )
        return LLMResponse(
            text=msg.content or "",
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "stop",
            raw=resp,
        )

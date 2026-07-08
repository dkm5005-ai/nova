"""Anthropic adapter — translates the neutral types in `base` to/from the Anthropic SDK.

This is the only file in Nova that imports `anthropic`. It mirrors
`openai_provider.py`: same neutral interface, different wire format. Three shape
differences the adapter has to absorb:

- `system` is a top-level parameter, not a message in the list.
- Tools advertise their schema under `input_schema` (no `function` wrapper).
- The model speaks in content *blocks* (`text`, `tool_use`); tool results go
  back inside a `user` message as `tool_result` blocks.
"""

from __future__ import annotations

from typing import Any

import anthropic

from .base import LLMProvider, LLMResponse, Message, Role, ToolCall, ToolSpec


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

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
            "max_tokens": max_tokens,
            "messages": self._to_anthropic_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._to_anthropic_tool(t) for t in tools]
        resp = self._client.messages.create(**kwargs)
        return self._from_anthropic_response(resp)

    # --- translation: neutral -> Anthropic ---

    @staticmethod
    def _to_anthropic_tool(spec: ToolSpec) -> dict:
        return {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.parameters,
        }

    @staticmethod
    def _to_anthropic_messages(messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        pending_results: list[dict] = []

        def flush_results() -> None:
            # Consecutive tool results belong together in one user turn.
            if pending_results:
                out.append({"role": "user", "content": list(pending_results)})
                pending_results.clear()

        for m in messages:
            if m.role is Role.TOOL:
                pending_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.text,
                    }
                )
                continue

            flush_results()

            if m.role is Role.USER:
                out.append({"role": "user", "content": m.text})
            elif m.role is Role.ASSISTANT:
                if m.tool_calls:
                    blocks: list[dict] = []
                    if m.text:
                        blocks.append({"type": "text", "text": m.text})
                    for tc in m.tool_calls:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        )
                    out.append({"role": "assistant", "content": blocks})
                else:
                    out.append({"role": "assistant", "content": m.text})
            # SYSTEM messages are carried via the top-level `system` param, not here.

        flush_results()
        return out

    # --- translation: Anthropic -> neutral ---

    @staticmethod
    def _from_anthropic_response(resp: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "end_turn",
            raw=resp,
        )

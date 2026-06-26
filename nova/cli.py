"""Terminal chat for Nova — the simplest face on the agent core.

This is throwaway-friendly: once the React dashboard exists it will drive the
same Agent the same way. Run with `python -m nova.cli` (or `nova` if installed).
"""

from __future__ import annotations

import sys

from .agent import Agent
from .config import Settings
from .llm.base import Message, Role
from .llm.openai_provider import OpenAIProvider
from .tools.base import ToolRegistry
from .tools.filesystem import DEFAULT_TOOLS

SYSTEM_PROMPT = (
    "You are Nova, a helpful personal AI assistant running in your owner's terminal. "
    "You can inspect the project's files using your tools. Be concise and direct. "
    "When a tool would help you answer accurately, use it instead of guessing."
)

BANNER = "Nova — your assistant (type 'exit' or Ctrl-D to quit)"


def _show_tool(name: str, args: dict) -> None:
    arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"   · using {name}({arg_str})")


def main() -> int:
    settings = Settings.load()
    if not settings.openai_api_key:
        print(
            "Missing OPENAI_API_KEY. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return 1

    agent = Agent(
        name="Nova",
        provider=OpenAIProvider(api_key=settings.openai_api_key),
        model=settings.openai_model,
        system=SYSTEM_PROMPT,
        tools=ToolRegistry(DEFAULT_TOOLS),
        max_tokens=settings.max_tokens,
    )

    print(BANNER)
    print(f"(model: {settings.openai_model})\n")
    history: list[Message] = []

    while True:
        try:
            user = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return 0
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            print("bye.")
            return 0

        history.append(Message(role=Role.USER, text=user))
        answer = agent.run(history, on_tool=_show_tool)
        print(f"\nnova ▸ {answer}\n")


if __name__ == "__main__":
    raise SystemExit(main())

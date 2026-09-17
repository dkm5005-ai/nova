"""Terminal chat for Nova — the simplest face on the orchestrator.

This is throwaway-friendly: once the React dashboard exists it will drive the
same router the same way. Run with `python -m nova.cli` (or `nova` if installed).
"""

from __future__ import annotations

import sys

from .config import Settings
from .llm.base import Message, Role
from .orchestrator.router import build_router

BANNER = "Nova — your assistant (type 'exit' or Ctrl-D to quit)"


def _on_router_tool(name: str, args: dict) -> None:
    # The router's only tool is `delegate`; `_on_delegate` prints the nicer line,
    # so stay quiet here to avoid duplicating it.
    if name != "delegate":
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"   · router uses {name}({arg_str})")


def _on_delegate(agent: str, task: str) -> None:
    preview = task if len(task) <= 80 else task[:77] + "..."
    print(f"   → delegating to {agent}: {preview}")


def _on_subtool(agent: str, tool: str, args: dict) -> None:
    arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"      · {agent} uses {tool}({arg_str})")


def main() -> int:
    settings = Settings.load()
    try:
        router, agents = build_router(
            settings,
            on_delegate=_on_delegate,
            on_subtool=_on_subtool,
        )
    except RuntimeError as exc:
        print(f"{exc}\nCopy .env.example to .env and fill it in.", file=sys.stderr)
        return 1

    print(BANNER)
    print(
        f"(provider: {router.provider.name}, model: {router.model}, "
        f"agents: {', '.join(sorted(agents))})\n"
    )
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
        answer = router.run(history, on_tool=_on_router_tool)
        print(f"\nnova ▸ {answer}\n")


if __name__ == "__main__":
    raise SystemExit(main())

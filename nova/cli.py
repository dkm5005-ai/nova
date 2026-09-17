"""Terminal chat for Nova — the simplest face on the orchestrator.

This is throwaway-friendly: once the React dashboard exists it will drive the
same router the same way. Run with `python -m nova.cli` (or `nova` if installed).

Slash commands (type `/help`) let you inspect the multi-agent system from the
prompt; everything else is sent to the router, which delegates and answers.
"""

from __future__ import annotations

import sys

from .agent import Agent
from .config import Settings
from .llm.base import Message, Role
from .orchestrator.registry import DEFAULT_AGENTS, AgentDef
from .orchestrator.router import build_router

BANNER = "Nova — your assistant (type '/help' for commands, '/exit' to quit)"

# Role text lives on the AgentDef (config), not the built Agent, so keep a lookup
# for `/agents` to show what each specialist is for.
_ROLES: dict[str, str] = {d.name: d.role for d in DEFAULT_AGENTS}


def _tool_names(agent: Agent) -> list[str]:
    return [spec.name for spec in agent.tools.specs()]


def _print_help() -> None:
    print(
        "commands:\n"
        "  /help       show this help\n"
        "  /agents     list the specialist agents (model + tools)\n"
        "  /provider   show the router's backing provider and model\n"
        "  /reset      clear the conversation history\n"
        "  /exit       quit (also: /quit, exit, Ctrl-D)"
    )


def _print_agents(agents: dict[str, Agent]) -> None:
    print("agents:")
    for name in sorted(agents):
        agent = agents[name]
        tools = ", ".join(_tool_names(agent)) or "(none)"
        print(f"  {name} · {agent.provider.name}/{agent.model} · tools: {tools}")
        role = _ROLES.get(name)
        if role:
            print(f"      {role}")


def _print_provider(router: Agent) -> None:
    print(f"router runs on {router.provider.name}/{router.model}")


def main() -> int:
    settings = Settings.load()

    # Agents delegated to during the current turn (order-preserving, de-duped),
    # so we can attribute the answer after each turn. Cleared per turn; the
    # observers below close over this same list.
    turn_agents: list[str] = []

    def on_delegate(agent: str, task: str) -> None:
        if agent not in turn_agents:
            turn_agents.append(agent)
        preview = task if len(task) <= 80 else task[:77] + "..."
        print(f"   → delegating to {agent}: {preview}")

    def on_subtool(agent: str, tool: str, args: dict) -> None:
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"      · {agent} uses {tool}({arg_str})")

    def on_router_tool(name: str, args: dict) -> None:
        # The router's only tool is `delegate`; `on_delegate` prints the nicer
        # line, so stay quiet here to avoid duplicating it.
        if name != "delegate":
            arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
            print(f"   · router uses {name}({arg_str})")

    try:
        router, agents = build_router(
            settings, on_delegate=on_delegate, on_subtool=on_subtool
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

        # Slash commands (and the bare exit/quit words) never reach the router.
        if user.startswith("/") or user.lower() in {"exit", "quit"}:
            cmd = user.lower().lstrip("/")
            if cmd in {"exit", "quit"}:
                print("bye.")
                return 0
            if cmd == "help":
                _print_help()
            elif cmd == "agents":
                _print_agents(agents)
            elif cmd == "provider":
                _print_provider(router)
            elif cmd == "reset":
                history.clear()
                print("(conversation cleared)")
            else:
                print(f"unknown command '{user}'. Type /help.")
            print()
            continue

        history.append(Message(role=Role.USER, text=user))
        turn_agents.clear()
        try:
            answer = router.run(history, on_tool=on_router_tool)
        except KeyboardInterrupt:
            print("\n(cancelled)\n")
            # Drop the partial turn so history stays consistent for the next one.
            del history[-1]
            continue
        except Exception as exc:  # a bad API call must not kill the session
            print(f"\n⚠ error: {exc}\n", file=sys.stderr)
            del history[-1]
            continue

        who = ", ".join(turn_agents) if turn_agents else "answered directly"
        print(f"\nnova ▸ {answer}")
        print(f"   ({who})\n")


if __name__ == "__main__":
    raise SystemExit(main())

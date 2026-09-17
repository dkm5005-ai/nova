"""The router / orchestrator (Step 3c).

The router is *just another Agent* (principle 3): its one tool is `delegate`, and
its system prompt tells it to route real work to the best-suited specialist and
synthesize the results. It runs on `NOVA_PROVIDER` by default like any agent, but
nothing stops it running on a different vendor than the agents it coordinates.
"""

from __future__ import annotations

from typing import Optional

from ..agent import Agent
from ..config import Settings
from ..llm.factory import ProviderPool
from ..tools.base import ToolRegistry
from .delegation import DelegateObserver, SubToolObserver, build_delegation_tool
from .registry import AgentDef, DEFAULT_AGENTS, build_agents

ROUTER_NAME = "router"


def _system_prompt(defs: list[AgentDef]) -> str:
    roster = "\n".join(f"- {d.name}: {d.role}" for d in defs)
    return (
        "You are Nova, the owner's orchestrator. You coordinate a team of "
        "specialized agents and are the single voice that answers the owner.\n\n"
        "When a request needs real work, use the `delegate` tool to hand a "
        "self-contained task to the best-suited agent, then weave the results "
        "into one clear answer. Break a request into multiple delegations when it "
        "spans more than one specialty, and put everything an agent needs into its "
        "task — sub-agents start fresh and cannot see the conversation. For simple "
        "conversational replies you may answer directly without delegating.\n\n"
        "Your team:\n"
        f"{roster}"
    )


def build_router(
    settings: Settings,
    pool: Optional[ProviderPool] = None,
    defs: list[AgentDef] = DEFAULT_AGENTS,
    on_delegate: Optional[DelegateObserver] = None,
    on_subtool: Optional[SubToolObserver] = None,
) -> tuple[Agent, dict[str, Agent]]:
    """Build the router Agent and the team of sub-agents it delegates to.

    Returns (router, agents). The router is not in `agents`, so it cannot
    delegate to itself.
    """
    pool = pool or ProviderPool(settings)
    agents = build_agents(defs, pool)
    delegate = build_delegation_tool(
        agents, on_delegate=on_delegate, on_subtool=on_subtool
    )
    router = Agent(
        name=ROUTER_NAME,
        provider=pool.get(None),
        model=pool.model_for(None),
        system=_system_prompt(defs),
        tools=ToolRegistry([delegate]),
        max_tokens=settings.max_tokens,
    )
    return router, agents

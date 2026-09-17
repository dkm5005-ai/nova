"""Agent definitions as config (Step 3a, Decision D8).

An `AgentDef` is pure data: a role the router reads to decide where to send work,
a system prompt, an optional provider/model override, and the tools the agent may
use (by name). `build_agents` turns these definitions into live `Agent` objects,
sharing one provider client per vendor via the `ProviderPool`.

Adding an agent = adding an entry here. No subclasses, no new loop — the generic
`Agent` (nova/agent.py) backs every one of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..agent import Agent
from ..config import Settings
from ..llm.factory import ProviderPool
from ..tools.catalog import registry_for


@dataclass
class AgentDef:
    """Config for one specialized sub-agent."""

    name: str  # stable id the router delegates to, e.g. "files"
    role: str  # one line the router uses to choose this agent
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    provider: str | None = None  # None → fall back to NOVA_PROVIDER
    model: str | None = None  # None → the provider's configured default
    max_tokens: int = 1024


# Seed team. Kept honest to the tools that actually exist today: `files` inspects
# the project; `general` reasons and writes with no tools. More agents (research,
# email, calendar, …) arrive as their tools do.
DEFAULT_AGENTS: list[AgentDef] = [
    AgentDef(
        name="files",
        role="Inspects and explains this project's files, code, and structure.",
        system_prompt=(
            "You are Nova's files agent. You answer questions about this project "
            "by reading its files with your tools rather than guessing. Be precise "
            "and cite paths. Return a focused answer to the task you were given."
        ),
        tools=["list_files", "read_file"],
    ),
    AgentDef(
        name="general",
        role="General reasoning, writing, and questions that need no tools.",
        system_prompt=(
            "You are Nova's general agent. You handle reasoning, explanation, and "
            "writing tasks that do not require reading project files. Be concise "
            "and directly answer the task you were given."
        ),
        tools=[],
    ),
]


def build_agents(
    defs: list[AgentDef],
    pool: ProviderPool,
) -> dict[str, Agent]:
    """Instantiate `Agent`s from definitions, keyed by name."""
    agents: dict[str, Agent] = {}
    for d in defs:
        agents[d.name] = Agent(
            name=d.name,
            provider=pool.get(d.provider),
            model=d.model or pool.model_for(d.provider),
            system=d.system_prompt,
            tools=registry_for(d.tools),
            max_tokens=d.max_tokens,
        )
    return agents


def default_agents(settings: Settings) -> tuple[dict[str, Agent], list[AgentDef]]:
    """Convenience: build the seed team and return it with its definitions."""
    pool = ProviderPool(settings)
    return build_agents(DEFAULT_AGENTS, pool), DEFAULT_AGENTS

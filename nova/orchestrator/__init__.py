"""Orchestration: turn one agent into a coordinated team (Step 3).

`registry` defines the sub-agents as config, `delegation` gives the router a tool
to hand work to them, and `router` builds the top-level agent that does the
delegating. See docs/DESIGN.md §4.1 (Decision D10) for why this is an LLM router
over stateless sub-agents rather than an explicit state graph.
"""

from __future__ import annotations

from .delegation import build_delegation_tool
from .registry import AgentDef, DEFAULT_AGENTS, build_agents
from .router import build_router

__all__ = [
    "AgentDef",
    "DEFAULT_AGENTS",
    "build_agents",
    "build_delegation_tool",
    "build_router",
]

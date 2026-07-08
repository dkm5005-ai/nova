# Nova — Project Guide

> This file is the source of truth for what Nova is, how it's built, and how we
> work on it. Read it at the start of every session. Keep it current: when scope,
> architecture, or conventions change, update this file in the same change.
>
> **Design docs** (the thorough versions — keep in sync with this file):
> - `docs/DESIGN.md` — rationale, key decisions, domain model, architecture +
>   component + sequence diagrams, concurrency & security.
> - `docs/API.md` — backend API catalogue (REST + WebSocket event contract).
> - `docs/ROADMAP.md` — phased plan of execution with acceptance criteria.

## What Nova is

Nova is a **provider-agnostic, multi-agent personal AI assistant** — a "Jarvis"
for its owner. A top-level **router/orchestrator agent** receives a request and
delegates it to the right **specialized sub-agent** (Social, Sales, Research,
CRM, Email, Calendar, …). Agents do real work autonomously via tools.

The long-term shape (inspiration, not a spec):
- A backend "brain" that orchestrates many agents.
- A **React dashboard** front-end visualizing agents as a live radial graph
  (a glowing core surrounded by labeled agent nodes that light up when active),
  plus task/kanban and agent-status views.

## Core principles (do not violate without discussion)

1. **Provider-agnostic.** No agent is hardwired to a vendor. All model calls go
   through the `LLMProvider` interface (`nova/llm/base.py`). Each vendor gets one
   adapter file. Switching the model behind any agent is a **config change**, not
   a code change. Different agents may run on different vendors.
2. **Agents are config, not classes.** An agent = system prompt + assigned model
   + a set of tools. Reuse the one generic `Agent` loop (`nova/agent.py`).
3. **Router is just another agent** whose job is delegation. Routing strategy is
   a knob (LLM-based now; rule-based/hybrid possible later).
4. **Backend first, UI last.** The dashboard visualizes backend state — build the
   brain before the face. Never build UI for features that don't exist yet.
5. **One step at a time.** Each step must produce something runnable. Discuss the
   plan and confirm before building the next step. Prefer small, verifiable diffs.
6. **Tools never crash the loop.** Tool handlers return error strings, not
   exceptions. Filesystem/external tools are sandboxed/scoped by default.
7. **Avoid the lowest-common-denominator trap.** The provider interface covers
   the common 90%; expose vendor-specific powers (caching, structured output,
   long context) via optional capability flags when genuinely needed.

## Architecture

```
You ─► Orchestrator/Router (an Agent, any model)
          └─ delegates via tool-calls ─► specialized sub-agents (each: prompt+model+tools)
                                              └─ all model calls go through ─► LLMProvider
                                                                                 ├─ OpenAI    (built)
                                                                                 ├─ Anthropic (built)
                                                                                 └─ Gemini    (later)

Which provider backs the agent is chosen by `NOVA_PROVIDER` (openai | anthropic)
via `nova/llm/factory.py` — a config change, not a code change.
```

## Layout

```
nova/
  llm/
    base.py            # neutral types + LLMProvider interface (the seam)
    openai_provider.py # OpenAI adapter (only file that imports `openai`)
  tools/
    base.py            # Tool + ToolRegistry
    filesystem.py      # read-only, project-sandboxed file tools
  agent.py             # the generic agent tool-use loop
  config.py            # env/.env settings
  cli.py               # terminal chat (temporary face on the core)
```

## Roadmap / status

- [x] **Step 1** — provider seam + OpenAI adapter + generic agent + file tools + CLI
- [x] **Step 2** — Anthropic adapter + provider factory (`NOVA_PROVIDER` switch).
      Translation logic verified offline; pending a live test once an
      `ANTHROPIC_API_KEY` is available.
- [ ] **Step 3** — specialized agents + the router/orchestrator
- [ ] **Step 4** — shared state / memory + per-agent status (what the dashboard reads)
- [ ] **Step 5** — React dashboard (the agent-graph visualization)

## Conventions

- **Python ≥ 3.11**, standard library + minimal deps. Type hints everywhere.
- Dataclasses for plain data; `from __future__ import annotations` at file top.
- Keep modules small and single-purpose. Comments explain *why*, not *what*.
- New vendor = new file in `nova/llm/`; new capability = new tool in `nova/tools/`.
  Don't reach into a vendor SDK outside its adapter.

## Secrets

- Keys live in `.env` (gitignored). Never commit keys or print them.
- The user adds their own keys; don't ask them to paste a key into chat.
- `OPENAI_MODEL` (and future `*_MODEL`) selects the model per provider via env.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env        # then add your OpenAI key to .env
python -m nova.cli
```

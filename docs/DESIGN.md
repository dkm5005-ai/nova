# Nova — Design Document

> Companion to `CLAUDE.md` (the short source of truth). This doc is the *thorough*
> version: rationale, decisions, data model, and diagrams. Read `API.md` for the
> backend interface and `ROADMAP.md` for the execution plan.
>
> Status legend: **[DONE]** built & verified · **[NOW]** current step ·
> **[PLANNED]** designed, not built · **(Proposed)** decision awaiting your sign-off.

---

## 1. Purpose

Nova is a **provider-agnostic, multi-agent personal AI assistant** for a single
owner — a "Jarvis." A top-level **router/orchestrator** receives a request and
delegates it to the right **specialized sub-agent** (Research, Social, CRM,
Email, Calendar, …). Agents act autonomously through tools. A **React dashboard**
visualizes the live system as a radial agent graph + task board.

This document covers the whole intended system so we build toward a coherent
target, even though we implement it one verifiable step at a time.

---

## 2. Goals & non-goals

**Goals**
- **Provider-agnostic** — any agent can run on any vendor; switching is config.
- **Multi-agent** — a router delegates to specialized sub-agents that do real work.
- **Autonomous** — agents use tools in a loop until a task is done.
- **Observable** — every agent/tool/task transition emits an event the dashboard reads.
- **Personal / single-owner** — one user; local-first; not multi-tenant.
- **Incremental** — every step produces something runnable (see `ROADMAP.md`).

**Non-goals (for now)**
- Multi-tenant SaaS, accounts, billing.
- Mobile apps.
- Model fine-tuning / training.
- Heavy RAG / vector search (may come later as a tool).
- Production-grade auth/SSO (local-first until we expose Nova remotely).

---

## 3. Design principles

The seven in `CLAUDE.md` hold (provider-agnostic, agents-are-config, router-is-an-agent,
backend-first, one-step-at-a-time, tools-never-crash, no lowest-common-denominator).
This design adds three implementation principles:

8. **Events are the dashboard contract.** The UI never reaches into internals; it
   reads a stream of typed events (agent/task/tool transitions). Anything the
   dashboard shows must first exist as an event.
9. **Persistence behind a repository interface.** Storage starts as SQLite but is
   accessed only through repository interfaces, so swapping to Postgres later is
   a single-layer change.
10. **The CLI and the API drive the same core.** The orchestrator is UI-agnostic.
    The terminal (today) and the HTTP API (later) are two thin faces on one brain.

---

## 4. Key architectural decisions

Decisions marked **(Proposed)** are the ones I want your sign-off on before Step 3.

| # | Decision | Choice | Why | Alternatives considered |
|---|----------|--------|-----|-------------------------|
| D1 | Backend framework | **FastAPI + Uvicorn** *(Proposed)* | Async, first-class WebSockets, Pydantic models mirror our dataclasses, auto-generates the OpenAPI catalogue | Flask (no native async/WS), Django (too heavy), raw ASGI |
| D2 | Language split | **Python backend, React/TS frontend** | Already chosen; backend-first | All-TS (rejected: prefer Python for agent/integration work) |
| D3 | Persistence | **SQLite via repository interfaces** *(Proposed)* | Zero-setup, file-based, perfect for single-user; repo layer keeps Postgres a later swap | Postgres now (premature), JSON files (no queries), in-memory only (no history) |
| D4 | Concurrency | **asyncio API; sync agent loops run in worker threads** *(Proposed)* | Agents are I/O-bound; keeps the provider interface simple (sync SDKs) while the API stays responsive | Make providers async now (more work, premature), Celery/RQ queue (overkill for one user) |
| D5 | Live updates | **WebSocket fed by an in-process event bus** *(Proposed)* | The radial graph needs push updates; one WS channel is simplest | SSE (one-way, fine fallback), polling (laggy) |
| D6 | Routing strategy | **LLM-based delegation tools first** | Matches the Jarvis vision; flexible | Rule/keyword routing (cheaper, less flexible) — keep as a future knob |
| D7 | Auth | **None; bind to localhost** initially; **token auth before any remote exposure** *(Proposed)* | Personal, local-first; don't build SSO we don't need | API key/JWT now (premature) |
| D8 | Agent definitions | **Config/data, not subclasses** | One generic `Agent` loop; agents = prompt + model + tools | Class-per-agent (violates a core principle) |
| D9 | Task execution | **In-process background tasks** (asyncio tasks) with a task registry | Simple, observable; long agent runs don't block the API | External worker/queue (later, if scale demands) |

---

## 5. Domain model

The core entities the backend persists and the dashboard renders.

```
Agent (definition + live status)
  id, name, role, system_prompt, provider, model, tool_names[],
  status: idle | active | working | error, current_task_id?

Conversation
  id, title, created_at, message_ids[]

Message
  id, conversation_id, role: user|assistant|tool|system,
  text, tool_calls[], agent_id?, created_at

Task
  id, title, description, status: queued|running|blocked|done|failed,
  agent_id, parent_task_id?, conversation_id, result?, error?,
  created_at, updated_at

Event   (append-only activity stream; the dashboard contract)
  id, type, ts, data{...}        # see API.md for the type catalogue

MemoryEntry   (shared/persistent state across agents)
  key, value, scope: global | <agent_id>, updated_at

Tool   (runtime registry; exposed read-only for introspection)
  name, description, input_schema, owner_agents[]
```

Relationships (text ER):

```
Conversation 1───* Message
Conversation 1───* Task
Task        *───1 Agent            (assigned)
Task        0..1─* Task            (parent → subtasks, via delegation)
Agent       *───* Tool             (an agent is granted a set of tools)
Event        ─── references agent_id / task_id / conversation_id
MemoryEntry  ─── scoped to global or one agent
```

---

## 6. Architecture diagram

Layers top-to-bottom; arrows are "calls / depends on". The event bus is the
spine that feeds the dashboard.

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (React/TS)   radial agent graph · kanban board · chat       │   [PLANNED]
└───────────────▲──────────────────────────────────────▲────────────────┘
        REST (HTTP/JSON) │                              │ WebSocket (events)
┌───────────────┴──────────────────────────────────────┴────────────────┐
│  API LAYER  (FastAPI)                                                   │   [PLANNED]
│   REST routers (agents, chat, tasks, memory, tools) · WS event gateway  │
└───────────────▲──────────────────────────────────────▲────────────────┘
                │ submit request                        │ subscribe
┌───────────────┴────────────────────┐     ┌────────────┴────────────────┐
│  ORCHESTRATION                      │     │  EVENT BUS (in-process)      │   [PLANNED]
│   Router agent · Agent registry     │────►│  publish agent/task/tool     │
│   Delegation tool                   │     │  events to subscribers       │
└───────────────▲────────────────────┘     └────────────┬────────────────┘
                │ runs                                    │ persists history
┌───────────────┴────────────────────┐     ┌─────────────┴───────────────┐
│  AGENT RUNTIME                      │     │  STATE & MEMORY              │   [PLANNED]
│   generic Agent loop · ToolRegistry │     │  repositories: tasks,        │
│            [DONE]                    │     │  conversations, events,      │
└──────▲───────────────────▲─────────┘     │  memory  →  SQLite (swappable)│
       │ tools             │ model          └─────────────────────────────┘
┌──────┴────────┐   ┌──────┴──────────────────────────────────────────────┐
│  TOOLS        │   │  LLM PROVIDER LAYER   (the seam)            [DONE]    │
│  filesystem   │   │   factory → OpenAIProvider · AnthropicProvider ·     │
│  web/email/…  │   │             GeminiProvider(later)                    │
│  [partial]    │   └──────────────────────────▲──────────────────────────┘
└───────────────┘                              │ HTTPS
                              External LLM vendors  ·  external tool APIs
```

---

## 7. Component diagram

Module map with build status. New packages introduced by future steps are marked.

```
nova/
  llm/                                                  [DONE]
    base.py            neutral types + LLMProvider interface
    factory.py         build_provider(settings) → (provider, model)
    openai_provider.py · anthropic_provider.py
  tools/                                                [partial]
    base.py            Tool + ToolRegistry
    filesystem.py      read-only sandboxed file tools
    (web.py, email.py, calendar.py, crm.py, social.py …)   [PLANNED]
  agent.py             generic tool-use loop              [DONE]
  config.py            env/.env settings                  [DONE]
  cli.py               terminal face                      [DONE]

  orchestrator/                                          [Step 3 — NOW]
    registry.py        agent definitions (role→prompt+model+tools)
    router.py          builds the router Agent; routing strategy
    delegation.py      the delegate(agent, task) tool

  state/                                                 [Step 4]
    models.py          Task, Event, Conversation, Message dataclasses
    repositories.py    repo interfaces (TaskRepo, EventRepo, …)
    sqlite.py          SQLite implementations
    eventbus.py        in-process pub/sub

  memory/                                                [Step 4]
    store.py           MemoryStore (over a repo)
    tool.py            memory_read / memory_write tools

  api/                                                   [Step 5]
    app.py             FastAPI app factory
    deps.py            wiring (singletons: orchestrator, repos, bus)
    routers/agents.py · chat.py · tasks.py · memory.py · tools.py
    ws.py              /ws/events gateway (bridges event bus → WebSocket)

frontend/                                                [Step 5/6]
  React/TS dashboard (agent graph, kanban, chat)
```

Dependency rule: arrows point **downward only**. `api` depends on `orchestrator`,
`state`, `memory`; `orchestrator` depends on `agent`, `tools`, `state`; `agent`
depends on `llm`, `tools`. Nothing lower imports anything higher. This keeps the
core testable without the API and the API swappable without touching the brain.

---

## 8. Runtime flows

### 8.1 A request, delegated and observed (the core loop)

```
User ──POST /api/chat {message}──► API
  API → Orchestrator.handle(message, conversation)
    Router(Agent).run():
      LLM ─► tool_call: delegate(agent="research", task="find X")
        bus.publish(delegation: router → research, task_id)
        bus.publish(agent.status_changed: research = working)
        ResearchAgent.run(task):
          LLM ─► tool_call: web_search("X")
            bus.publish(tool.invoked: research, web_search)
            → result
          LLM ─► final text  (the research answer)
        bus.publish(task.updated: done) ; bus.publish(research = idle)
        return result to router
      LLM ─► final answer to the user
    persist conversation + task ; bus.publish(message.appended)
  API ◄── {conversation_id, task_id}
        (events streamed over /ws/events throughout)

Dashboard:  research node glows while working ·
            a task card moves queued → running → done ·
            chat shows the final answer
```

### 8.2 Event propagation

```
Agent / Orchestrator ──emit──► EventBus ──┬──► EventRepo (persist for history)
                                          └──► WS subscribers (live dashboard)
REST GET /api/events?after=cursor  ── replays persisted events (poll/fallback)
```

---

## 9. Concurrency & execution model

- The **API is async** (FastAPI/asyncio). A `POST /api/chat` schedules the
  orchestrator run as a **background task** and returns immediately with ids; the
  client watches `/ws/events` for progress. (Synchronous "wait for the answer"
  mode is also offered for the CLI/simple calls.)
- The **agent loop stays synchronous** (sync provider SDKs). Each agent run is
  executed in a **worker thread** (`anyio.to_thread` / executor) so it never
  blocks the event loop. *(Decision D4 — revisit async providers only if needed.)*
- A **task registry** tracks running background tasks so they can be listed,
  cancelled (`POST /api/tasks/{id}/cancel`), and surfaced as events.
- Concurrency limits (max parallel agent runs) are a config knob to bound cost.

---

## 10. Security & secrets

- **Secrets**: API keys live in `.env` (gitignored); never logged or returned by
  any endpoint. `GET /api/info` reports *which* providers are configured, never
  the keys.
- **Local-first**: the server binds to `127.0.0.1` by default. *(D7)*
- **Before any remote exposure**: add a single shared-token auth dependency on
  all `/api/*` routes and the WS handshake; document it; then allow non-local binds.
- **Tools stay sandboxed**: filesystem tools are project-scoped; outward-facing
  tools (email/social) must require explicit confirmation for irreversible
  actions (send/post/delete) before they're enabled.
- **Tools never crash the loop**: handlers return error strings (existing rule).

---

## 11. Target layout (end state)

See the component diagram (§7) for the package tree. Today `nova/llm`, `nova/tools`,
`nova/agent.py`, `nova/config.py`, `nova/cli.py` exist and are verified. `orchestrator/`,
`state/`, `memory/`, `api/`, and `frontend/` are introduced by Steps 3–6.
```

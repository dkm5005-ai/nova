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
| D10 | Orchestration model | **LLM router + stateless sub-agents; no explicit state graph** *(Proposed)* | Matches open-ended "do whatever I ask" Jarvis delegation you can't pre-draw; keeps the minimal seam and one generic `Agent` loop | LangGraph / explicit state-graph engine (borrow its ideas selectively, see §4.1) |
| D11 | Semantic memory | **Design the `SemanticMemory` + `EmbeddingProvider` seams now; build the engine in Step 4. Structured state stays in SQLite; vectors default to `sqlite-vec`, LanceDB the sanctioned upgrade** *(Proposed)* | Keeps memory swappable and provider-agnostic without building a store that has no consumer yet; one-file/local-first preserved until scale demands more | LanceDB now (a 2nd store before the 1st exists), hosted vector DB (breaks local-first, wrong scale), no seam / hardwire a vendor (breaks provider-agnostic) |

### 4.2 Semantic / embedding-based recall (D11)

**Question raised.** Should shared memory support semantic (embedding-based) recall,
and if so, is SQLite the right home — or LanceDB now?

**Two axes, kept separate.** "Vector memory" bundles two decisions:
1. **Where vectors live** (the store).
2. **Who computes embeddings** (the model) — an *provider* call, like a completion.

**Decision.**

- **Structured state stays in SQLite.** The domain model (§5) is relational (tasks,
  conversations, messages, events, key/value memory, with FKs). That is SQLite's
  job; a vector store is not a good home for it. So a vector engine is always an
  *addition*, never a replacement — adopting one means running **two** stores.
- **Design the seams now, build the engine in Step 4.** Introduce two interfaces:
  - `SemanticMemory` repo — `upsert(key, text, metadata)` / `search(query, k, filter)`.
  - `EmbeddingProvider` — sibling to `LLMProvider`; `embed(text) -> vector`. Keeps
    embeddings vendor-swappable (hosted e.g. OpenAI `text-embedding-3-*`, or local
    e.g. `sentence-transformers` for offline recall). This is the real long pole —
    it decides recall quality and whether memory works offline.
  Because both are behind interfaces (principle 9), choosing the engine later is a
  single-layer swap, and building it *now* — before an agent consumes it — would
  violate backend-first / one-step-at-a-time (Step 3, the orchestrator, isn't built).
- **Engine ladder.** Default **`sqlite-vec`** (vectors in the *same* SQLite file →
  one file, atomic fact+embedding writes, zero extra store). **LanceDB** is the
  sanctioned local upgrade when the vector layer outgrows it. **`pgvector`** is the
  convergence point *if/when* we adopt Postgres anyway (D3's stated later swap).
- **Not** a hosted vector DB (Pinecone/Weaviate/Milvus): built for approximate
  search over hundreds of millions of vectors across tenants — the opposite of a
  single-owner, local-first assistant. Wrong scale; breaks local-first.

**Relationship to the key/value `MemoryStore`.** Semantic memory *coexists* with the
scoped key/value store (§5 `MemoryEntry`) — it does not replace it. Key/value is for
exact facts (`owner.company`); semantic is for "what did I say about X?" recall. Both
sit behind the memory repository layer.

### 4.1 Orchestration: LLM-router vs. explicit-state-graph (D10)

**Question raised.** Do we need to pass explicit state between agents, à la LangGraph
(a typed `State` object threaded through a predefined graph of nodes)?

**Decision.** No — not now, and not the whole framework. Nova orchestrates by
**LLM-driven delegation**: the router *is* an agent, and it decides what runs next
by calling `delegate(agent, task)`. Sub-agents are **stateless workers** — each runs
its own generic `Agent` loop on a fresh history seeded with the task string, and
**returns its result as a string** that becomes a tool-result in the router's history.
The router holds the whole picture and composes multi-step work by feeding one
result into the next task. This keeps two core principles intact: the *minimal
provider seam* (nothing owns model calls but our adapters) and *agents-are-config,
one generic loop*.

**Two paradigms — why they differ.**

| | Our approach (LLM router) | LangGraph (explicit state graph) |
|---|---|---|
| Who picks the next step | The **model** (router reasons, calls `delegate()`) | **You** — edges in a predefined graph |
| State | Router history + shared memory (Step 4) | A typed `State` object merged through every node |
| Character | Emergent, flexible, agentic | Deterministic, auditable, testable |

**What explicit state genuinely buys you** (the reasons to reach for a graph engine),
and how Nova will absorb each *through its own seams* rather than adopt the framework:

- **Durable execution / resume after crash** → make `TaskRepo` (Step 4) store enough
  to replay a task; state lives in the repositories, not in-process strings.
- **Human-in-the-loop pause/approve** → *prioritized.* Already implied by "irreversible
  actions gated behind confirmation" (§10). A confirmation gate is a lightweight
  interrupt; persisted task state lets us pause and resume it.
- **Deterministic, repeatable routines** (e.g. a morning briefing) → add small
  **rule-based/hardcoded flows alongside** the router. Decision D6 already frames
  routing strategy as a knob (LLM now, rule-based later); D10 is consistent with it.
- **Bounded refine cycles, fan-out/fan-in, time-travel debugging** → deferred; add
  only when a concrete flow needs them.

**Shared state, when strings aren't enough.** Cross-agent state goes through the
Step-4 `MemoryStore` (`scope: global | <agent_id>`), *not* a new agent-to-agent
channel — because memory is observable (emits events the dashboard reads) and
persistent. A `conversation_id`-scoped **scratchpad/blackboard** (any agent on the
same task reads/writes a shared working set mid-task) is the one enhancement we'd
consider next — but only when a real flow proves string-passing + memory clumsy,
as a deliberate Step-4 addition, not speculatively.

**When we'd revisit.** If Nova evolves from conversational Jarvis into a **workflow
engine** — many long-running, repeatable, multi-step flows that must survive restarts
and pause for approval — that's the point to adopt LangGraph's patterns wholesale (or
the library itself). We are not there; starting there would violate backend-first and
one-step-at-a-time.

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
    embedding.py       EmbeddingProvider seam (embed text → vector)   [Step 4 — D11]
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
    store.py           MemoryStore (over a repo)          key/value, scoped
    tool.py            memory_read / memory_write tools
    semantic.py        SemanticMemory seam (upsert/search)   [D11 — engine later:
                       sqlite-vec default → LanceDB → pgvector; interface now]

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

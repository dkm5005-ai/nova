# Nova — Plan of Execution

> The phased build plan. Each phase ends in something **runnable and verified**.
> We do one phase at a time and confirm before starting the next (per `CLAUDE.md`).
> See `DESIGN.md` for the architecture and `API.md` for the target interface.

Status: **[x]** done · **[~]** in progress · **[ ]** planned.

---

## Phase 1 — Provider seam + agent core + CLI  **[x] DONE**

The foundation: model-agnostic provider interface, a generic agent loop, tools.

- [x] `llm/base.py` — neutral types + `LLMProvider` interface
- [x] `llm/openai_provider.py` — OpenAI adapter
- [x] `agent.py` — generic tool-use loop
- [x] `tools/` — `Tool` + registry; read-only sandboxed filesystem tools
- [x] `config.py`, `cli.py` — settings + terminal chat

**Verified:** multi-step tool use, error handling, sandbox enforcement, plain
chat, multi-turn memory.

---

## Phase 2 — Second provider (prove swappability)  **[x] DONE**

- [x] `llm/anthropic_provider.py` — Anthropic adapter
- [x] `llm/factory.py` — `NOVA_PROVIDER` switch (openai | anthropic)
- [x] Config + CLI wired to the factory

**Verified:** translation logic offline (incl. merged tool-results), OpenAI path
regression, graceful no-key failure. **Pending:** live Anthropic call (needs an
`ANTHROPIC_API_KEY`).

---

## Phase 3 — Orchestrator + specialized agents  **[x] DONE (backend, CLI-driven)**

Turn one agent into a coordinated team. **No HTTP yet** — proven in the terminal.

- [x] **3a. Agent registry** (`orchestrator/registry.py`) — agent definitions as
  config: role → system prompt + provider/model + tool set. Seeded `files` and
  `general` (tool-honest to what exists today); `ProviderPool` lets each agent run
  on a different vendor. Tools resolved by name via `tools/catalog.py`.
- [x] **3b. Delegation tool** (`orchestrator/delegation.py`) — the `delegate(agent,
  task)` tool runs a sub-agent on a **fresh history** (Decision D10) and returns its
  result string; observers surface nested activity (the future event-bus seam).
- [x] **3c. Router** (`orchestrator/router.py`) — an `Agent` whose only tool is
  `delegate`; LLM-based routing (Decision D6). Built with its team; can't self-delegate.
- [x] **3d. CLI wiring** — the terminal talks to the router; delegations and
  sub-agent tool use print as nested activity.

**Verified:** 14 offline checks (scripted stub provider) — router composes a final
answer from a delegated result, sub-agents run stateless on a fresh history, tool
results feed back, provider pool caches one client per vendor, registry wires
tools/models, and the error paths (unknown agent, empty task, unknown tool) all
return strings / raise as intended. **Pending:** a live end-to-end run once deps are
installed (`pip install -e .`).

**Acceptance:** in the terminal, a request like *"research X, then summarize the
files in this project"* visibly routes to the right sub-agents and returns a
combined answer. Each agent can run on a different provider.
*(Note: `research` awaits a web tool; today's seed proves routing with `files` +
`general`, e.g. "summarize nova/llm, then write a one-line tagline".)*

---

## Phase 4 — State, memory, and the event bus  **[ ] PLANNED (backend)**

Make the system persistent and observable — the data the dashboard will read.

- [ ] **4a. Domain models** (`state/models.py`) — Task, Conversation, Message, Event.
- [ ] **4b. Repositories + SQLite** (`state/repositories.py`, `state/sqlite.py`).
- [ ] **4c. Event bus** (`state/eventbus.py`) — in-process pub/sub; orchestrator
  and agents emit `agent.*` / `task.*` / `tool.*` events (see `API.md`).
- [ ] **4d. Memory** (`memory/`) — shared `MemoryStore` (scoped key/value) +
  `memory_read`/`memory_write` tools so agents persist facts across runs.
- [ ] **4e. Per-agent status tracking** driven off the event bus.
- [ ] **4f. Semantic-memory seams** (Decision D11) — define the `SemanticMemory`
  repo interface (`upsert`/`search`) and the `EmbeddingProvider` seam (sibling to
  `LLMProvider`). **Interfaces + a default engine only** (`sqlite-vec`, vectors in
  the same SQLite file); LanceDB/pgvector remain swap-later. Deferred until a real
  consumer exists — don't build a store nothing calls.

**Acceptance:** after a CLI session, tasks/conversations/events are queryable from
the store; agents can write and recall a fact via memory; an event log reflects
every agent/task/tool transition.

---

## Phase 5 — Backend API (FastAPI)  **[ ] PLANNED**

Expose the core over HTTP + WebSocket per `API.md`.

- [ ] **5a. App skeleton** (`api/app.py`, `api/deps.py`) — FastAPI, wiring,
  `/health`, `/api/info`; Swagger at `/docs`.
- [ ] **5b. Agents + tools routers** — `GET /api/agents`, `/api/agents/{id}`,
  `GET /api/tools`.
- [ ] **5c. Chat + tasks + conversations** — `POST /api/chat` (async + `?wait`),
  `/api/tasks*`, `/api/conversations*`, with agent runs in worker threads (D4).
- [ ] **5d. WebSocket** (`api/ws.py`) — `/ws/events` bridged to the event bus.
- [ ] **5e. Memory router** — `/api/memory*`.

**Acceptance:** drive Nova entirely over HTTP; watch live events on `/ws/events`;
the OpenAPI page documents every endpoint.

---

## Phase 6 — React dashboard  **[ ] PLANNED**

The face: the Apex-style radial agent graph + task board + chat, fed by Phase 5.

- [ ] **6a. App skeleton** — React/TS, API client, WS connection.
- [ ] **6b. Radial agent graph** — nodes from `/api/agents`; glow/edges from
  `agent.status_changed` + `delegation` events.
- [ ] **6c. Kanban + agent detail** — cards from `/api/tasks` + `task.*` events.
- [ ] **6d. Chat input** — `POST /api/chat`, streaming the conversation.

**Acceptance:** a live dashboard where issuing a request lights up the agent that
handles it and moves its task across the board — the video, but real.

---

## Cross-cutting (as needed, not a phase)

- **Security before remote exposure** — shared-token auth on `/api/*` + WS,
  non-local bind (Decision D7).
- **More tools** — web search, email, calendar, CRM, social — added per agent as
  capabilities are needed; outward/irreversible actions gated behind confirmation.
- **Tests** — grow alongside each phase (we already smoke + unit test the core).
- **Async providers / external task queue** — only if single-process concurrency
  becomes a real limit (Decision D4/D9).
```

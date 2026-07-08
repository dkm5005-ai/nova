# Nova — Backend API Catalogue

> The HTTP + WebSocket interface the React dashboard (and any client) uses to
> drive and observe the Nova backend. Built with FastAPI (Decision D1), which
> also serves a live, auto-generated version of this catalogue at `/docs`
> (Swagger UI) and `/openapi.json`.
>
> Status: **[PLANNED]** — this is the target contract for Step 5. It is published
> now so the orchestrator/state work (Steps 3–4) is built to satisfy it.
> Base path for application endpoints: `/api`. All bodies are JSON.

---

## Conventions

- **IDs** are opaque strings (e.g. `task_a1b2`, `agt_research`, `cnv_…`).
- **Timestamps** are ISO-8601 UTC strings.
- **Errors** use a consistent envelope and standard HTTP codes:
  ```json
  { "error": { "type": "not_found", "message": "task task_x not found" } }
  ```
  `400` validation · `404` not found · `409` conflict (e.g. cancel a finished task)
  · `500` internal. (Auth `401/403` arrive with Decision D7, pre-remote.)
- **Async by default**: actions that start agent work return ids immediately;
  progress arrives via `/ws/events`. Add `?wait=true` to block for the result
  where a synchronous response is convenient (CLI, simple scripts).

---

## REST endpoints

### System
| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/health` | Liveness probe | `{ "status": "ok" }` |
| GET | `/api/info` | Version, configured providers, agent count | `{ version, providers:["openai","anthropic"], agents: 5 }` |

### Agents — drive the radial graph
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/agents` | List agent definitions **+ live status** (graph nodes) | — | `[Agent]` |
| GET | `/api/agents/{id}` | One agent: prompt, model, tools, status, current task | — | `Agent` |
| POST | `/api/agents` | Define a new agent (config) | `AgentSpec` | `Agent` |
| PATCH | `/api/agents/{id}` | Update config — e.g. **swap the model/provider** | partial `AgentSpec` | `Agent` |

### Chat / orchestrator — the way in
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/chat` | Send a request to the router; starts orchestration | `{ message, conversation_id? }` | `{ conversation_id, task_id }` (or full answer if `?wait=true`) |
| GET | `/api/conversations` | List conversations | — | `[ConversationSummary]` |
| GET | `/api/conversations/{id}` | Full message trace | — | `Conversation` |

### Tasks — drive the kanban board
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/tasks` | List/filter tasks | `?status=&agent_id=` | `[Task]` |
| GET | `/api/tasks/{id}` | Task detail + subtasks + trace | — | `Task` |
| POST | `/api/tasks/{id}/cancel` | Stop a running task | — | `Task` |

### Memory — shared agent state
| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/memory` | List/query entries | `?scope=&prefix=` | `[MemoryEntry]` |
| GET | `/api/memory/{key}` | Read one | — | `MemoryEntry` |
| PUT | `/api/memory/{key}` | Upsert | `{ value, scope? }` | `MemoryEntry` |
| DELETE | `/api/memory/{key}` | Delete | — | `204` |

### Tools — introspection
| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/tools` | List registered tools + which agents own them | `[Tool]` |

### History / fallback
| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| GET | `/api/events` | Replay persisted events (poll fallback for WS) | `?after=<cursor>&limit=` → `[Event]` |

---

## WebSocket — live event stream

```
WS  /ws/events
```
Server → client, one JSON message per event. This is the **dashboard contract**:
the radial graph glows and the kanban moves purely off these events. (Optional
client → server messages for filtering come later; v1 sends all events.)

**Envelope**
```json
{ "id": "evt_…", "type": "agent.status_changed", "ts": "2026-06-26T18:00:00Z", "data": { … } }
```

**Event type catalogue**

| `type` | Fires when | `data` |
|--------|------------|--------|
| `agent.status_changed` | An agent changes state | `{ agent_id, status: "idle"\|"active"\|"working"\|"error", task_id? }` |
| `delegation` | Router hands a task to a sub-agent | `{ from_agent_id, to_agent_id, task_id }` |
| `task.created` | A task is created | `{ task_id, title, agent_id, status }` |
| `task.updated` | A task changes status | `{ task_id, status, result?, error? }` |
| `tool.invoked` | An agent calls a tool | `{ agent_id, task_id, tool, args_preview }` |
| `message.appended` | A message is added to a conversation | `{ conversation_id, role, text, agent_id? }` |
| `error` | A recoverable error is surfaced | `{ scope, message }` |

Maps to the dashboard: `agent.status_changed`/`delegation` → node glow + edges;
`task.*` → kanban cards; `message.appended` → chat; `tool.invoked` → activity feed.

---

## Schemas

```jsonc
// Agent  (definition + live status)
{
  "id": "agt_research",
  "name": "Research",
  "role": "Finds and synthesizes information from the web and files.",
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "tools": ["web_search", "read_file"],
  "status": "idle",               // idle | active | working | error
  "current_task_id": null
}

// AgentSpec  (create/update payload — config only)
{
  "name": "Research",
  "role": "…",
  "system_prompt": "You are Nova's research agent…",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "tools": ["web_search", "read_file"]
}

// Task
{
  "id": "task_a1b2",
  "title": "Find competitors for X",
  "description": "…",
  "status": "running",            // queued | running | blocked | done | failed
  "agent_id": "agt_research",
  "parent_task_id": null,         // set for delegated subtasks
  "conversation_id": "cnv_…",
  "result": null,
  "error": null,
  "created_at": "…", "updated_at": "…"
}

// Conversation / Message
{
  "id": "cnv_…", "title": "Competitor research", "created_at": "…",
  "messages": [
    { "id": "msg_…", "role": "user", "text": "find competitors for X", "created_at": "…" },
    { "id": "msg_…", "role": "assistant", "text": "…", "agent_id": "agt_router", "created_at": "…" }
  ]
}

// MemoryEntry
{ "key": "owner.company", "value": "Acme Engineering", "scope": "global", "updated_at": "…" }

// Tool
{ "name": "web_search", "description": "Search the web.", "input_schema": { … }, "owner_agents": ["agt_research"] }

// Event  (see WebSocket catalogue for `type` + `data`)
{ "id": "evt_…", "type": "task.updated", "ts": "…", "data": { "task_id": "task_a1b2", "status": "done" } }
```

---

## Build order (which step delivers what)

- **Step 3** makes the orchestrator + agents real (no HTTP yet) — exercised via CLI.
- **Step 4** adds `state/` + `memory/` + the event bus → tasks, conversations,
  events, and memory become persistent and queryable.
- **Step 5** stands up this API over that core: `/api/agents`, `/api/chat`,
  `/api/tasks`, `/api/memory`, `/api/tools`, and `/ws/events`, with Swagger at `/docs`.
- **Step 6** is the React dashboard consuming exactly these endpoints + events.
```

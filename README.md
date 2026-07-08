# Nova

A provider-agnostic, multi-agent personal AI assistant. Built one step at a time.

## Architecture (the plan)

Three layers keep Nova from being tied to any single AI vendor:

1. **Provider layer** (`nova/llm/`) — one neutral interface (`LLMProvider`), one
   adapter per vendor. OpenAI today; Anthropic and Gemini drop in as new files.
2. **Agents** (`nova/agent.py`) — an agent is just config: a system prompt, an
   assigned model, and a set of tools. It only talks to the provider interface,
   so changing its model is a config change, not a rewrite.
3. **Orchestrator / router** *(coming)* — a top-level agent that delegates each
   request to the right specialized sub-agent. Sub-agents can run on different
   vendors than the router.

A React dashboard (the "agent graph" visualization) will come last, reading the
agents' live state from the backend.

## Status

- [x] **Step 1** — provider seam + OpenAI adapter + generic agent + file tools + CLI
- [x] **Step 2** — Anthropic adapter + provider factory (`NOVA_PROVIDER` switch)
- [ ] Step 3 — specialized agents + the router
- [ ] Step 4 — shared state / memory + agent status
- [ ] Step 5 — React dashboard

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env        # then put your OpenAI key in .env
python -m nova.cli
```

Set `OPENAI_MODEL` in `.env` to any chat model your key can access (e.g.
`gpt-4o`, `gpt-4o-mini`, `gpt-4.1`).

# AI Company Health

**A simulated health insurer run entirely by AI agents, selling to a town of AI customers.**

50 AI employees across 12 departments run the company. 100 AI residents in a 3D town decide whether to buy from it. Nothing in the company's numbers is scripted: every sale, claim and cancellation comes from a decision a resident agent made.

> This is a simulation and a research project, not a real insurer. The numbers below are outputs of the simulation.

## What I'm seeing (35 simulated days)

| Result | Value |
|---|---|
| Policies in force | 20 → 46, with 0 cancellations |
| Market position | #1 fund in town, about 45% share |
| Customer satisfaction | NPS 100, every claim within its service target |
| Finances | About 20% margin, 54% loss ratio |
| Observability | 5,000+ model calls and 50M+ tokens, every run traced |
| Evaluations | 5 of 6 checks passed |

## How it works

```
                 ┌──────────────────────────── 3D UI (Three.js) ────────────────────────────┐
                 │   office · town · dashboards · documents · meetings · traces · evals     │
                 └───────────────▲──────────────────────────────────────────┬───────────────┘
                                 │ WebSocket events                          │ REST / chat
                 ┌───────────────┴──────────────────────────────────────────▼───────────────┐
                 │                         FastAPI bridge                                    │
                 └───────┬───────────────────────────┬───────────────────────────┬──────────┘
                         │                           │                           │
              company clock (daily)        LangGraph workflows           town loop (daily)
                         │                 daily · weekly · meetings      100 resident agents
                         ▼                           │                           │
                 SQLite company data  ◄── tools ── 50 ADK employee agents ── A2A ──┘
                 (KPIs, claims, files)        ▲          │ ask / hand off
                                              └── A2A ───┘
                                 every run → trace · fact-check · evaluation
```

1. **The town** generates demand. Each resident has a job, an income, a household, needs, friends and memories. When something happens (a premium notice, a life event, a friend's message, an ad), the resident's own agent compares funds, asks our staff questions, and buys, stays or cancels.
2. **The company** turns those decisions into data: sales, claims, call waits, revenue, margin.
3. **The employees** read that data with tools, meet, propose initiatives, challenge each other and decide, inside rules enforced in code.
4. **The quality layer** traces every run, fact-checks every published number and evaluates the agents against answers known from the data.

## The technology, and what each piece does here

### Google Agent Development Kit (ADK)
ADK is Google's framework for building agents: an LLM, a set of tools (plain Python functions) and session state.
**Here:** every employee and every resident is an ADK `LlmAgent`, all made in one place, the agent factory (`backend/src/hq/agents/factory.py`). The factory gives each agent four things:
- a persona: role, department and personality;
- long-term memory, injected into every call;
- live market context;
- the tools its role needs: KPIs, read-only SQL, documents, dashboards, A2A, hiring, app requests and more.

Agents answer by calling tools on live data, not from the model's memory.

### Vertex AI
Vertex AI is Google Cloud's managed platform for running generative models.
**Here:** the agents run on Gemini models through Vertex AI, authenticated with Application Default Credentials, so no API key is stored in the project. Two model tiers keep costs down: a fast tier for everyday agents and a stronger tier for the executives. Every call is metered per agent for tokens and cost.

### A2A (Agent2Agent protocol)
A2A is an open protocol that lets agents call each other as services, with tasks, messages and results.
**Here:** every employee is published as an A2A server at `/a2a/<agent-id>/`. Agents use it in two ways:
- **Consult:** ask a colleague a question and wait for the answer.
- **Hand off:** pass work to another department. This creates a task for the receiver, who runs it and reports back.

Both directions are logged and shown in the 3D office as messages flying between desks (`backend/src/hq/a2a/`).

### LangGraph
LangGraph is a library for stateful, multi-step workflows written as graphs, with parallel branches and checkpoints.
**Here:** it is the company's operating rhythm (`backend/src/hq/workflows/`):

| Workflow | When | What happens |
|---|---|---|
| Daily operations | Every day | Alerts are triaged and each one is investigated in parallel |
| Weekly strategy | Mondays | Seven departments propose in parallel, Risk and Finance challenge over A2A, and the CEO decides within budget |
| Weekly goals | Mondays | Last week's goals are reviewed and new ones set |
| App backlog | Tuesdays | IT works its backlog |
| Weekly report | Fridays | The report is published |
| Agenda meetings | When called | Each attendee builds a deck from data and presents it, and minutes are written |

### FastAPI and WebSockets
FastAPI is a Python web framework. WebSockets keep a live, two-way connection with the browser.
**Here:** FastAPI serves the UI, the REST API (`/docs`) and the A2A endpoints. A WebSocket streams every event to the 3D view as it happens: speech, walking, handoffs, documents, KPIs. That stream is what makes the agents' work visible and debuggable live.

### SQLite
SQLite is an embedded SQL database stored in a single file.
**Here:** it holds the company and town state: KPIs, sales, claims, residents, documents, memories, traces and the app backlog. Agents query it through a read-only SQL tool with a whitelist, row and CPU limits, and per-dataset access rights that the Data team grants.

### Three.js
Three.js is a JavaScript library for 3D graphics in the browser.
**Here:** it draws the 3-floor office with desks, meeting rooms and screens, and the town with houses, a hospital, a mall and residents coloured by their insurer. Agents walk to the boardroom only when a meeting is called, and present decks on the room screen (`frontend/js/`).

### Google Cloud (Compute Engine)
**Here:** the backend can run around the clock on a Compute Engine VM with no public IP, reached through an IAP SSH tunnel (`backend/deploy/deploy.sh`, `tunnel.sh`). An optional GPU VM renders the 3D office in the cloud and streams it to a laptop over WebRTC (`viewer.sh`).

### The quality layer: tracing, fact-checks, evaluations
This is the engineering that makes the agents trustworthy (`backend/src/hq/quality/`):

| Piece | What it does |
|---|---|
| Tracing | Every agent run is stored: prompt, each tool call with its arguments and result, reply, tokens, time and outcome. Shown under 📈 Ops → Traces. |
| Fact-check guardrail | Numbers in every published document are checked against the data. A mismatch is flagged, and the author agent remembers the correction. |
| Evaluations | Questions with answers known from the data (numbers, memory, compliance) are scored per agent. |
| LLM gate | Live chats go ahead of background work. Background calls are paced to stay within quota and back off after rate-limit errors. |
| Compliance in code | Pricing, marketing and privacy rules are enforced in code. A proposal that breaks a rule cannot be approved. |

### Offline mock LLM and tests
**Here:** without a cloud project the backend runs on a deterministic mock LLM (`backend/src/hq/llm/mock*.py`), so everything works offline and in CI. `pytest` covers the simulation, SQL safety, every workflow end to end, A2A, REST, WebSocket and the IT app backlog (73 tests).

## Run it

```bash
cd backend
uv sync                         # Python 3.12 virtual environment
cp .env.example .env            # choose Vertex AI, an API key, or nothing (offline mock)
uv run python -m hq             # open http://127.0.0.1:8787/
```

To use Vertex AI, set this in `backend/.env` (no secrets: run `gcloud auth application-default login` once):

```
HQ_USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=global
```

Tests:

```bash
cd backend && uv run pytest
```

## Project layout

```
backend/            Python backend: agents, A2A, workflows, company, town, quality, API (details in backend/README.md)
frontend/           the 3D UI (Three.js), served by the backend
docs/HQ-API.md      the UI ↔ backend event protocol
```

For the full design (agent factory, workflows, teams, the town, quality and the REST API), see [`backend/README.md`](backend/README.md).

## Known limits
- The simulation is synthetic and simplified. Do not use it for real pricing or financial decisions.
- Agent quality depends on the model. The offline mock uses transparent rules instead of reasoning.
- No single trace ID links a whole chain of handoffs yet; chains are linked through task IDs. A root trace ID with parent spans is the next step.

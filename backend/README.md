# AI Company Health – backend

A fictional **Australian private health insurer that also runs health services** (dental, optical, physio clinics, preventive programs),
run by 42 AI agents. A **synthetic data generator** produces a new day of sales, claims, service and staffing data, and the agents
(Google ADK on Gemini) analyse it, debate, decide strategies, and manage the team – then the simulation responds to what they decided.

| Layer | Technology | What it does |
|---|---|---|
| Agents | **Google ADK** `LlmAgent` on **Gemini** (Vertex AI or AI Studio; offline mock for tests) | One agent per leader/analyst in 10 departments, with tools to read data and propose / review / decide initiatives |
| Agent ↔ agent | **A2A protocol** (`a2a-sdk`, ADK `to_a2a`) | Reviewers question proposers, teams hand off work, each agent is served at `/a2a/<id>/` |
| Operating rhythm | **LangGraph** | Daily review, weekly strategy cycle, monthly review, annual premium round, team health review |
| Company & economy | SQLite (`hq/company`) | The company's numbers come only from the town agents' decisions (the old synthetic generator, `company/synthetic.py`, is kept for tests); initiatives change the numbers |
| Bridge | **FastAPI** | WebSocket/SSE to the 3D UI, REST API, serves the UI |

```
 3D UI ◄─ WebSocket ─► FastAPI ─► CompanyRunner (clock) ─► Company.advance() ─► daily data in SQLite  ─► KPIs, alerts
 (dashboard, agents)                  │                                              ▲ initiatives change the levers
                                      └► LangGraph workflows ─► ADK agents (Gemini) ─► tools ─► propose / review / decide
                                                                      ▲  A2A: consult, hand off ─┘
```

## Project structure

```
finance office/
├── frontend/                  the 3D UI (served by the backend at /ui/)
│   ├── index.html             markup only
│   ├── css/app.css            styles
│   └── js/                    one module per feature, joined in manifest.json order into /ui/app.js
│       ├── data.js            teams, rooms, colours (must match agents/roster.py – a test checks it)
│       ├── scene.js           renderer, camera, lights, sky, ground
│       ├── building.js        the HQ: floors, rooms, desks, screens, boards
│       ├── people.js          employees: characters, animation, commanded movement
│       ├── views.js           camera views, third-person, first-person room view
│       ├── panels.js          header, panels, details, meetings, task board, replay, palette, backend link
│       ├── company.js         company dashboard, live boards, work files, data access, floor map
│       ├── city.js            the city: avenue, mall, hospital, school, towers, the company's hospital & clinic
│       ├── town.js            Wattle Grove: residents, houses, plans, health visits, life events, person panels
│       ├── rooms.js           room records, @mention conversations, raise-hand; apps launcher
│       └── main.js            picking and the animation loop (loads last)
├── backend/
│   ├── src/hq/
│   │   ├── core/              config, event bus, world state (memory, conversations, room logs), services container,
│   │   │                      company clock (clock.py), room talk (rooms.py)
│   │   ├── agents/            EVERYTHING ABOUT AGENTS
│   │   │   ├── factory.py     ★ the agent factory: the one place every agent (employee or resident) is created
│   │   │   ├── roster.py      the org chart: departments, people, rooms; runtime hiring
│   │   │   ├── personas.py    who each agent is (employees and residents) and the prompt formats
│   │   │   ├── runtime.py     runs the agents the factory builds: tasks, chats, talks, enquiries, meetings
│   │   │   └── tools/         what agents can do: core.py (status, A2A, memory), business.py (KPIs, SQL, initiatives),
│   │   │                      work.py (files, dashboards, apps, data access, hiring, town), resident.py (residents' tools)
│   │   ├── llm/               model selection (models.py), Gemini wrapper with timeouts (guarded.py), token metering (usage.py),
│   │   │                      offline mock (mock.py, mock_biz.py)
│   │   ├── a2a/               every employee as an A2A server (host.py) and the A2A client (peers.py)
│   │   ├── company/           the insurer: products & rules (catalog.py, rules.py), initiatives, SQLite store,
│   │   │                      company.py (KPIs, decisions), economy.py (numbers from the town), synthetic.py (legacy)
│   │   ├── town/              Wattle Grove: residents & market (town.py), life (life.py), health care (health.py), town loop (loop.py)
│   │   ├── work/              work files & data access (files.py), downloads (render.py)
│   │   ├── workflows/         LangGraph: base.py, manager.py, operations.py (daily/weekly/monthly…), teams.py (meetings, reporting, IT…)
│   │   └── api/               FastAPI app, UI bridge (bridge.py), routes/ (agents.py, company.py, work.py)
│   ├── tests/                 61 tests
│   └── deploy/                deploy.sh (backend VM), tunnel.sh, viewer.sh + viewer/ (GPU cloud view)
├── docs/HQ-API.md             UI ↔ backend protocol
└── Open AI Company*.command   double-click launchers
```

## The agent factory (`hq/agents/factory.py`)

Every agent is made in one place, from the same parts:

| Part | Where | Notes |
|---|---|---|
| persona | `agents/personas.py` | who they are; residents also get personality, home, belongings, fund |
| context | `factory.market_block()` | employees see the real Wattle Grove market situation |
| memory | `core/world.py` (`remember`, `memories`) | their own long-term memory, injected on every call |
| model | `llm/models.py` | Gemini on Vertex AI (or the offline mock), token-metered per agent |
| toolsets | `agents/tools/*.py` | employees: `core` + `business` + `work` (each decides per role/department); residents: `resident` |

Kinds: **employee** (a work agent for workflows/A2A and a chat agent for you; rebuilt when People & Culture hires) and **resident**
(built fresh for each run so it sees its current life). `GET /api/factory` lists what exists and every employee's tools.
To add a kind of agent or give a role new abilities, change `factory.py` and the toolset modules.

## Run

```bash
cd backend
uv sync                         # Python 3.12 venv (ADK needs <3.14)
cp .env.example .env            # choose Vertex AI, an AI Studio key, or nothing (offline mock)
uv run python -m hq.doctor      # optional: verifies your Gemini setup with two tiny calls
uv run python -m hq             # http://127.0.0.1:8787  – open this URL, not the .html file
```

On first start it generates a year of history (a few seconds). Open **http://127.0.0.1:8787/**, then use the clock in the header:
**▶** runs the company (one simulated day every N seconds), **⏸** pauses, **+1 day** simulates the next day and lets the agents work on it.
Open **Company** for the dashboard (KPIs vs targets, charts, plans, the decisions board, team health, the strategy log).

### Gemini on Vertex AI

```
# backend/.env – no secrets, authentication is Application Default Credentials (gcloud auth application-default login)
HQ_USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=global
```
Everyday agents use `HQ_MODEL_FAST` (default `gemini-3.5-flash`); department heads and the executives use `HQ_MODEL_PRO`
(`gemini-3.1-pro-preview`). **Cost control:** each simulated day with agents on costs roughly 15–30 agent runs on a Monday (weekly strategy)
and 3–5 on other days; use `"agents": false` (or the "agents" tick box) to fast-forward data only, then switch agents back on.

## The legacy synthetic generator (`hq/company/synthetic.py`) – used only when `HQ_ECONOMY=synthetic` (tests)

* **Market model**: ~410,000 policies (~4% share). Plans use the real Australian structure: hospital **Gold / Silver / Bronze / Basic** tiers, extras,
  combined, ambulance, overseas visitors (OVHC) and students (OSHC); six sales channels; eight states; five age bands.
* **Daily generator** (`engine.py`): leads → conversion (price vs market elasticity, NPS, capacity) → sales by plan/state/channel/age; cancellations
  by reason; claims by type and state; claims **backlog and SLA** from team capacity; contact-centre **calls, wait time, abandonment, CSAT, NPS**;
  marketing and brand; staffing, engagement and attrition; premium revenue, benefits, expenses, margin. Deterministic per (seed, date).
* **Calendar realism**: weekday/weekend rhythm; pre-1-April rush and the **1 April premium round** (call spike, price shock, lapses); **tax-time June
  surge**; winter hospital claims and flu; extras peak Nov–Dec; random market events (competitor promos, comparison-site outages, media stories,
  web outages, hospital disputes).
* **Calibrated start**: loss ratio ≈ 86–87%, margin ≈ 2.5–3% (target 4%), net adds ≈ +60/day (target +120), engagement ≈ 70, service strained at peaks.
* **Storage** (`data/company.db`): `daily_kpi, daily_sales, daily_sales_age, daily_cancellations, daily_claims, daily_book, daily_leads, daily_team,
  events, products, initiatives, notes`. Agents can query it with a **read-only, whitelisted, row- and CPU-limited SQL tool**.

### How strategies change the business (`initiatives.py`)

Agents propose **initiatives**; each has a validated parameter set, an estimated cost and effect, and – once approved – a start date, a duration and a hidden
*realised* effect (so some bets under-deliver). Kinds: `marketing_campaign`, `promo_discount` (new joiners only), `new_product`, `hire`, `training`,
`wellbeing_program`, `automation`, `provider_deal`, `retention_program`, `preventive_program`, `broker_commission`. Effects flow into leads, conversion,
plan mix, cancellations, benefit cost, capacity, engagement and attrition. `evaluate_initiative` compares before/after, adjusted with last year's pattern
(difference-in-differences), against what was expected.

**Compliance rules** (`rules.py`) are enforced in code, not just in prompts: community rating (no targeting by health status / claims history), existing
members' prices change **only in the 1 April round** and within the approved industry cap, hospital tier rules, ASIC "no misleading claims", no marketing
to under-18s, Privacy Act, hiring-wave limits, and the **strategy budget** ($24M a year). A proposal that breaks a rule cannot be approved.

### Team maintenance

Each department has a simulated workforce (≈470 FTE) behind its 3D agents: **hiring lag** (5–8 weeks) and **ramp-up** (~2 months), business-as-usual
backfill, **utilisation → engagement → attrition** feedback, training and wellbeing programs, and automation. People & Culture agents watch utilisation,
engagement and attrition and propose hiring, training or wellbeing; Finance and the CEO decide.

## The agents' operating rhythm (`hq/workflows/operations.py`, LangGraph)

| Workflow | When | What happens |
|---|---|---|
| `daily_ops` | every simulated day | Data lead's brief → **triage** alerts → **one investigation per alert in parallel** (dynamic fan-out) → urgent decision if needed → Chief of Staff stand-up |
| `weekly_strategy` | Mondays | Weekly review → **7 departments propose in parallel** → **Risk & Compliance and Finance challenge in parallel** (questioning proposers over A2A) → CEO decides within budget → plan note |
| `monthly_review` | 1st | Evaluate initiatives (before/after) → board summary |
| `team_health` | 15th | Engagement/capacity review → people proposals → CFO review → CEO decision |
| `premium_round` | from mid-Feb | Actuary view → pricing proposal → compliance check → CFO decides (cap-checked) → member-comms prep |

Approved initiatives become delivery tasks on the board for their owners. Agents never walk to meeting rooms on their own; meetings happen only when a
workflow is started with `use_meetings`, when you summon agents, or in chat.

## Teams and their real work (`hq/work`, `hq/workflows/teams.py`)

| Team | What it does on the synthetic data |
|---|---|
| **Data & Actuarial** | Owns **data access**: every dataset (SQL table) has a sensitivity and a default audience; agents can only query what they may read (enforced in the SQLite authorizer). Others `request_data_access`; the Data team approves or rejects (least privilege). |
| **Reporting & Insights** (new) | Publishes **dashboards** (`create_dashboard`) and the **weekly report** every Friday. Every chart is a SQL query with the real rows stored. |
| **IT & Apps** (new) | Works an **app backlog** every Tuesday: any agent can ask for an app (`request_app`), the company's numbers raise requests on their own (membership milestones, claims SLA, call waits, cancellations or loss ratio off target), and CEO requests go on it too. The Head of IT ranks it (`prioritise_app_requests`), a developer builds the top item (`create_app(..., request_id)`: a sandboxed HTML page with the data injected), and the team that asked is told. Backlog: `GET /api/app-requests`. |
| **People & Culture** | **Hires real new AI agents** (`hire_agent`) for approved hiring initiatives or your requests: a new ADK agent with its own A2A endpoint and a new desk in the 3D office (max 8 per room); hires survive restarts. |
| **Department heads** | Manage their teams and take decisions; executives decide initiatives. |

**Meetings with an agenda**: pick people and a room in the *Meet* tab and write an agenda. Each attendee prepares a deck from the live data,
presents it on the meeting-room screen (with charts), then the Chief of Staff writes the minutes. **Work files** (reports, dashboards, decks, apps,
minutes) are listed per department and in *Company → Work files*; open them in the viewer and download as HTML, Markdown, CSV or **PowerPoint**.
Ask any team for work from its department panel (*Ask …*), or approve data access requests yourself.

REST: `GET /api/files[?dept=&kind=&meeting=]`, `GET /api/files/{id}`, `/view`, `/download?fmt=html|md|csv|pptx|json`, `GET /api/access`,
`POST /api/access/requests/{id}`, `GET /api/hires`, `POST /api/meetings/agenda`, `POST /api/requests`.

## The town: Wattle Grove (`hq/town`)

100 AI residents in 47 households on the island next to the office (bridge). Each has an age, suburb, job, income, household, needs,
personality and current cover, plus relations: family, friends, neighbours, and links to company employees. All of it is generated and seeded.
Five insurers compete: AI Company Health and four fictional competitors. Each simulated day, households with a reason (premium notice, tax time,
the Lifetime Health Cover deadline, a life event, a friend's message, an ad) run their own AI agent:
- `my_profile` and `my_feed`;
- `compare_insurers` (a comparison site priced for their household, rebate and LHC included) and `company_info` (live service numbers);
- `search_web` (Google Search through Gemini when available);
- `ask_employee` (a real conversation with your sales or care staff, recorded in that team's room);
- `message_someone`, then `buy_policy`, `keep_current_cover` or `cancel_cover`, and optionally `post_review`.

Marketing reads `get_town_insights` (aggregate only) and launches campaigns with `launch_town_campaign` on Wednesdays. The audience is checked in
code: suburb, age band and life stage are allowed; health status and under-18s are not. The 3D residents are coloured by insurer.

## Agent quality and observability (`hq/quality`)

| Piece | What it does | Where |
|---|---|---|
| Weekly goals | Every Monday the CEO reviews last week's goals (met / missed, what was tried), the lesson goes into the leaders' memories and a *Weekly goals review* document; then sets this week's measurable goals with `set_weekly_goals` (rule-based goals if none) | `quality/goals.py`, `workflows/quality.py` |
| Fact-check guardrail | Every published document's numbers (members, sales, loss ratio) are checked against the data; mismatches are flagged (⚠ in 📁 Documents), logged and remembered by the author | `quality/guard.py` |
| Memory | Recall by relevance to the current request (shared words + importance + recency); nightly digests fold old memories into a summary | `core/world.py` (`memories`, `memory_block`, `consolidate`) |
| Evaluations | Questions with answers known from the data (numbers, memory, compliance) scored per agent; 📈 Ops → Evaluations, `POST /api/evals/run`, `python -m hq.quality.evals` | `quality/evals.py` |
| Tracing | Every agent run: prompt, each tool call with arguments and result, tokens, time, outcome; 📈 Ops → Traces, `GET /api/traces` | `quality/traces.py` |
| Ops | Model calls/min, Vertex quota errors, queue, tokens and estimated cost (`HQ_PRICE_IN_PER_M`, `HQ_PRICE_OUT_PER_M`), errors by kind of work; `GET /api/ops` | `api/routes/quality.py` |
| LLM gate | Owner chats go before background work; background calls paced (`HQ_LLM_BACKGROUND_RPM`, default 30/min) and paused after 429s | `llm/guarded.py` |

**Realism.** Extras have annual limits per person (dental $800, optical $250, physio $500) and people new to private cover serve waiting periods
(2 months general, 12 months surgery and pregnancy; switchers keep what they served). Big gaps or refused claims can become Ombudsman complaints
(1-star reviews, lower NPS), and residents tell people they know about good and bad experiences. Rival funds respond weekly (offers, price cuts,
brand campaigns), mostly when they are losing members; their moves change the comparison site and are shown to our agents. All indicative.

**UI.** 🕒 Timeline replays the company day by day (KPIs + what happened). ❓ Tour is a guided walkthrough (shown once on first visit).
The header and side panels adapt to smaller screens.

## Rooms: records, conversations, raise-hand

Every room keeps a record (`room_log`): speech, presentations, enquiries, your messages. Open a room to read its conversation, its resources
(work files, and the decks and minutes of meetings held there) and to talk. Mention people with **@Name**: they raise a hand ✋ and speak
**one at a time** (you can move someone up ▶ or lower a hand ✕). Without a mention, the chair or the department head answers.
REST: `GET /api/rooms/{room}/log`, `POST /api/rooms/{room}/message`, `GET /api/town`, `/api/town/insights`, `/api/town/residents/{id}`, `POST /api/town/run`.

## UI ↔ backend

Backend → UI: the commands in `../docs/HQ-API.md` plus `biz_day` (KPIs, series, team, plans, alerts), `initiative`, `note`, `clock`, `approval_request`,
`resync_done`. UI → backend: `clock` (`start|pause|step|config`), `board_decision` (you approve/reject an initiative from the Decisions board), `chat`,
`summon`, `present_done`, `approval`.

## REST API (also `/docs`)

`/api/company/…` `snapshot · kpis · series · breakdown · forecast · products · team · alerts · events · notes · initiatives · clock` and
`POST /api/company/proposals` (the board can propose too), `POST /api/company/initiatives/{id}/decide` (board override), `POST /api/company/query` (read-only SQL).
Agents/tasks/A2A/workflows: `/api/agents/…`, `/api/tasks/…`, `/api/handoffs`, `/api/consult`, `/api/workflows/…`, `/api/a2a/…`, `/api/events…`.
`HQ_AUTH_TOKEN` protects REST, WebSocket and `/a2a/*`.

## Tests

```bash
uv run pytest      # 61 tests, ~15 s: simulation calibration and seasonality, determinism, SQL safety, initiative effects, compliance, premium round,
                   # every workflow end to end with the mock LLM, A2A, REST, WebSocket, roster ↔ UI parity
```

## Known limits

* The simulation is **synthetic and simplified**: elasticities and effects are plausible, not fitted to real data; do not use it for real pricing or
  financial decisions.
* With Gemini the agents reason for themselves; quality depends on the model. Offline mock mode uses transparent rules (`llm/mock_biz.py`) instead.
* State is in SQLite (company, initiatives, notes) and survives restarts; running workflows, chat sessions and the UI's task list are in memory.
* An agent works on one task at a time (a per-agent lock); parallel proposals therefore run in parallel across departments, not within one agent.

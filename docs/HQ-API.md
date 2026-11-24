# AI Company Health – UI ↔ backend protocol

Open `finance-hq-agents.html`. Agents stay at their desks until a command moves them.
Connect with the "Backend API" box in the UI, or load the page with `?ws=ws://localhost:8080`
(an `http(s)` URL is treated as Server-Sent Events). One JSON object, or an array of them, per message.

## Commands (backend → UI)
```json
{"type":"move","agent":"fpa.leo","room":"mr2","text":"Heading to review"}
{"type":"desk","agent":"fpa.leo"}
{"type":"status","agent":"fpa.leo","state":"working","text":"Rolling forecast v3"}
{"type":"say","agent":"fpa.leo","text":"Forecast ready","ms":3500}
{"type":"task","agent":"fpa.leo","title":"Rolling forecast v3","progress":40,"note":"Variance bridge","id":"t42","status":"doing"}
{"type":"meeting","room":"mr1","agents":["acct.helen","rep.grace"],"topic":"Close sync"}
{"type":"end_meeting","room":"mr1"}
{"type":"summon","agents":["fpa.leo","rep.grace"],"room":"mr2","topic":"Demo for the CFO","present":true}
{"type":"present","agent":"fpa.leo","slides":[{"title":"Forecast v3","bullets":["Revenue +4%","Opex flat"],"progress":60}]}
{"type":"visit","agent":"fpa.leo","target":"data.arjun","text":"Got a minute?"}
{"type":"handoff","from":"acct.helen","to":"rep.grace","item":"Trial balance pack"}
{"type":"chat_reply","agent":"fpa.leo","text":"Forecast is 60% done."}
{"type":"system","name":"erp","state":"ok","text":""}
{"type":"policy","autoHuddle":true}
```
* `state`: `idle | working | meeting | blocked | done | error`. Add `"now":true` to `status` to apply it immediately.
* Task `status`: `todo | doing | blocked | done` (drives the task board). A task with `progress` 100 is done.
* Commands for one agent run in order (queued).
* `summon` sends the agents to a room and, unless `present` is false, each presents in turn on the room screen.
* **Auto-huddle (off by default)**: when an agent becomes `blocked` or `error`, their lead (plus Security & Compliance for security-type
  issues or errors, and the relevant data, tax or treasury head) meet in a free meeting room until the agent is unblocked.
  Turn it on with the `policy` message or the checkbox in the Test controls.

## Events (UI → backend, when connected)
`hello` (agent and room lists), `arrived {agent,room}`, `select {agent}`, `state {agent,state}`,
`chat {agent,text}` (you chatted with an agent – answer with `chat_reply`), `summon {agents,room,topic}`.

## IDs
* Agent: `<dept>.<firstname>`, for example `cfo.priya`, `data.arjun`, `sec.isabel`.
* Departments: `cfo fpa rep data acct tre tax aud ir sec`. Shared rooms: `lob mr1 mr2 mr3 war brd`.
* Systems: `erp dw bank consol`.

## Browser console
`FinanceHQ.agents()`, `FinanceHQ.rooms()`, `FinanceHQ.move('fpa.leo','war')`, `FinanceHQ.summon([...],'mr1','topic')`,
`FinanceHQ.handoff(from,to,'item')`, `FinanceHQ.chat('fpa.leo','status?')`.

## Backend (Python: ADK + A2A + LangGraph)
`backend/` implements this protocol for real – see `backend/README.md`. Extra messages used with it:
* backend → UI: `{"type":"approval_request","run":"ab12","title":"…","summary":"…"}` shows Approve/Reject buttons;
  `{"type":"approval_resolved","run":"ab12","approved":true}` removes them.
* UI → backend: `{"type":"approval","run":"ab12","approved":true,"note":""}`, `{"type":"present_done","agent":"fpa.leo"}`.
* With a backend connected the UI no longer invents slides for "Call meeting": the backend sends `present` commands written by the agents.

## The synthetic health insurer (backend `hq/biz`)
The company is a fictional Australian health insurer with health services. Departments (room ids) → `exec sales mkt data claims care health people prod risk`,
agent ids are `<dept>.<firstname>` (e.g. `exec.priya` CEO, `claims.helen`, `risk.isabel`). Shared rooms: `lob mr1 mr2 mr3 war brd`.
Systems: `policy claims crm dw web pay`.

Extra backend → UI messages:
* `{"type":"biz_day","date":"2026-03-02","last":{…},"week":{…},"targets":{…},"series":{…},"team":{…},"products":[…],"dept_kpis":{…},"alerts":[…],"budget":{…}}` – one per simulated day (and on connect).
* `{"type":"initiative","initiative":{id,title,kind,status,proposer,dept,cost_est,compliance,reviews,…}}` – create/update on the decisions board.
* `{"type":"note","note":{id,date,author,kind,title,body}}` – strategy-log entry. `{"type":"clock",running,busy,date,seconds_per_day,agents}` – the company clock.
* `{"type":"resync_done"}` – marks the end of the state replayed to a (re)connected UI.

Extra UI → backend messages: `{"type":"clock","action":"start|pause|step|config","seconds_per_day":45,"agents":true,"days":1}` and
`{"type":"board_decision","id":"I3","approved":true,"note":""}`.

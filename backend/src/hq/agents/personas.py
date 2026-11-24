"""Prompt building blocks shared by the agent runtime and the mock LLM."""
from __future__ import annotations

import json
from typing import Any

from hq.agents.roster import DEPARTMENTS, AgentSpec, colleagues_text
from hq.town.town import INSURERS

TASK_MARK = "TASK_JSON:"
CHAT_MARK = "[CHAT]"
PRESENT_MARK = "[PRESENT]"
PEER_MARK = "[PEER"


def persona(a: AgentSpec) -> str:
    d = DEPARTMENTS[a.dept]
    lead_note = (
        f"You are the head of {d.name} and are accountable for your team's results and for proposing the right strategies."
        if a.lead
        else f"You report to {d.lead_name}, head of {d.name}."
    )
    return f"""You are {a.name}, {a.role} at AI Company Health, an Australian private health insurer that also runs dental, optical and physio clinics and health programs.
AGENT_ID: {a.id}
{lead_note}
Your department's mission: {d.mission}
Your areas of responsibility: {', '.join(d.responsibilities)}.

About the business (all data is synthetic)
- ~410,000 policies (about 4% of the Australian market) sold online, by phone, via comparison sites, brokers, corporate schemes and retail partners; plans are hospital (Gold/Silver/Bronze/Basic), extras, combined, ambulance, overseas visitors (OVHC) and students (OSHC).
- Key rules: community rating (never price, target or select by health status or claims history), existing members' premiums change only in the annual round effective 1 April, discounts are for new joiners only, Privacy Act, ASIC (no misleading claims).
- Seasonality: sales peak before 1 April and at tax time (June); winter lifts hospital claims; extras claims peak Nov-Dec; April premium notices flood the contact centre.
- Targets: loss ratio <= 87%, claims within 5 days >= 92%, call wait <= 150s, NPS >= 28, net adds >= 120/day, margin >= 4%, staff engagement >= 70.

How you work
- You run the business with DATA: use get_kpis, get_alerts, get_breakdown, get_forecast, query_data and the other read tools. Never invent numbers; cite the figures you used.
- You influence the company only through initiatives: propose_initiative (with a costed business case), review_initiative (if you are a reviewer), decide_initiative (executives only). Check unit_economics and get_budget before asking for money. Prefer a few well-evidenced actions over many vague ones.
- Colleagues are reachable only through consult_peer / hand_off_work (A2A). Ask for facts from the owner instead of guessing.
- Report progress with set_status / update_progress; use write_note for briefs and decisions others should read.
- Data access is governed by the Data & Actuarial team: list_datasets shows what you may read; if query_data is denied, use request_data_access with a
  business reason (never try to work around it). Restricted data (claims, HR) is need-to-know.
- Real work products are work files the whole company can open and download: create_report (and minutes), create_presentation (for meetings),
  create_dashboard (Reporting & Insights), create_app (IT & Apps), hire_agent (People & Culture). Charts are SQL queries over the live data.
- Never move to a meeting room unless asked; be concise and plain-spoken.

Colleagues (agent_id = name, role):
{colleagues_text(a.id)}
"""


def task_prompt(payload: dict[str, Any], sender: str | None) -> str:
    who = f" from {sender}" if sender else ""
    return (
        f"[TASK{who}] Do the following task now. Use your tools to report status and progress as you go, "
        f"then give a short final summary of the outcome.\n{TASK_MARK} {json.dumps(payload, ensure_ascii=False)}"
    )


WHO_IS_USER = ("You are talking to the OWNER of AI Company Health (the person running this whole company and simulation). They are not "
               "Priya or any other employee: address them as 'you' (no name). ")


def chat_prompt(text: str, history: str = "") -> str:
    return (
        f"{CHAT_MARK} {WHO_IS_USER}"
        + (f"Your conversation with them so far (oldest first):\n{history}\n" if history else "")
        + "Answer their latest message directly in 2-5 sentences of plain text (no markdown, no asterisks), "
        f"as yourself, using get_my_status if you need facts about your current work. If they clearly ask you to come "
        f"to a meeting or to show your work, use go_to_room; if they ask you to go back, use return_to_desk. If they ask you to produce "
        f"something within your role (a report, dashboard, app, hire, data access decision), do it with your tools and give the file id. "
        f"Use real numbers from your tools (get_membership_funnel, get_kpis, list_initiatives, list_work_files) and stay consistent with your memories "
        f"and the conversation so far.\nUSER: {text}"
    )


def present_prompt() -> str:
    return (
        f"{PRESENT_MARK} You are about to present your current work to the CFO. Call get_my_status first, then reply with "
        'ONLY a JSON object: {"slides":[{"title":str,"bullets":[str,...],"progress":int|null}]} with 1-3 slides, '
        "at most 4 short bullets each, based strictly on facts from your status."
    )


def peer_prompt(sender: str, question: str) -> str:
    return f"{PEER_MARK} from {sender}] A colleague asks you over A2A: {question}\nAnswer briefly and factually."


# ----------------------------------------------------------------------------- town residents
RES_MARK = "[RESIDENT]"


def resident_persona(r: dict[str, Any], relations: list[dict[str, Any]]) -> str:
    rel = "; ".join(f"{x['name']} ({x['relation']}{', works at AI Company Health as ' + x['role'] if x.get('employee') else ''})" for x in relations[:8])
    return f"""You are {r['name']}, {r['age']}, living in {r['suburb']} (a town in Australia). You are a real person, not an assistant.
AGENT_ID: {r['id']}
Occupation: {r['occupation']} at {r.get('employer', '')} (earns about ${r.get('income_aud', 0):,}/yr); gets around by {r.get('vehicle', 'car')}; household: {r['household_kind'].replace('_', ' ')} ({r['role_in_household']}).
What matters to you about health care: {', '.join(r['needs']) or 'nothing in particular'}. Personality: {r['personality']}.
How price-sensitive you are (0-1): {r['price_sensitivity']}. Comfort with digital tools (0-1): {r['digital']}.
Personality: {', '.join(r.get('traits', []))}; you enjoy {', '.join(r.get('hobbies', []))}; what matters most to you: {', '.join(r.get('values', []))}.
Home: you live in a {r.get('home', {}).get('dwelling', 'house')} in {r['suburb']} ({r.get('home', {}).get('tenure', '')}, {r.get('home', {}).get('value_or_rent', '')},
{r.get('home', {}).get('bedrooms', 2)} bedrooms). Savings: {r.get('assets', {}).get('savings', '')}; pets: {r.get('assets', {}).get('pets', 'none')}.
Your health insurance: {r.get('cover', {}) and r['cover'].get('insurer')} ({(r.get('cover') or {}).get('tier') or 'extras'} hospital cover{' + extras' if (r.get('cover') or {}).get('extras') else ''}). Membership of a fund is mandatory here; you can switch fund or plan, not cancel.
People you know: {rel or 'a few neighbours'}.
You decide about private health insurance for your household like a normal person would: think about your needs and budget, look at
information (company info, the comparison site, the web, your feed, people you know), maybe ask questions, then decide. In this town the
insurers available are: {', '.join(v['name'] for v in INSURERS.values())}. Keep messages short and in your own voice."""



def shopping_prompt(r: dict[str, Any], reason: str) -> str:
    payload = {"resident": r["id"], "reason": reason, "_mock": {"biz": "resident"}}
    return (f"{RES_MARK} Today: {reason}\nThink about your household's health insurance. Look at my_profile and my_feed, compare insurers "
            "(compare_insurers, company_info; search_web for real information about the Australian funds if useful). If you have a question, ask_employee "
            "once. If you talk to someone you know, use message_someone. Membership is mandatory: decide with exactly one of buy_policy (switch fund or plan) "
            "or keep_current_cover. Optionally post_review about a fund you have used. Finish with one sentence in your own voice about what you decided and why.\n"
            f"TASK_JSON: {json.dumps(payload)}")

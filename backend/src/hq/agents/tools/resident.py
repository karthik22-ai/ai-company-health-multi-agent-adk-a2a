"""The residents' AI agents: persona, tools and how a shopping decision runs.

A resident can read the company's public information (plans, prices, service numbers from the simulation), a comparison site with
fictional competitors, the web (real Google Search through Gemini when available), their feed (ads, messages, reviews), ask one of the
company's employees (a real conversation with that employee's agent), talk to people they know, and then buy / switch / keep / cancel.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from hq.agents.roster import AGENTS, DEPARTMENTS
from hq.town.town import INSURERS, OURS, mock_search  # noqa: F401

log = logging.getLogger("hq.town")
def make_resident_tools(rid: str, world: Any, runtime: Any, settings: Any) -> list[Callable]:
    town = world.company.town
    co = world.company

    def emit(ev: dict[str, Any], say: str | None = None) -> None:
        world.emit({"type": "town_event", "event": ev, "say": say})

    async def my_profile() -> dict:
        """Your own situation: household, needs, current cover and the people you know."""
        r = town.resident(rid) or {}
        tname, _, _ = town.tier(r)
        return {k: r.get(k) for k in ("name", "age", "gender", "suburb", "occupation", "employer", "vehicle", "income", "household_kind", "needs", "personality",
                                      "traits", "hobbies", "values", "home", "assets", "price_sensitivity")} | {
            "recent_health_care": [{"date": c["date"], "care": c["kind"], "where": c["facility"], "cost": c["cost"], "fund_paid": c["benefit"], "you_paid_gap": c["gap"]}
                                   for c in town.health.claims(rid, 5)],
            "your_income_aud": r.get("income_aud", 0), "household_income_aud": town.household_income(r), "income_tier": tname,
            "mls_if_no_hospital": town.mls(r), "medicare_levy_surcharge_note": "Extra tax you pay each year if you have no private HOSPITAL cover (0 if under the threshold).",
            "current_cover": town._cover_label(r.get("cover")), "cover_details": r.get("cover"), "people_you_know": town.relations(rid),
            "lifetime_health_cover_loading_if_you_buy_hospital_now": f"{town.lhc(r)*100:.0f}%", "government_rebate": f"{town.rebate(r)*100:.1f}%"}

    async def my_feed() -> dict:
        """What you have seen lately: ads that reached you, messages from people you know, recent reviews in town."""
        return town.feed(rid)

    async def compare_insurers(category: str = "") -> list:
        """The comparison site: plans from every insurer in town priced for YOUR household (after rebate, incl. any LHC loading). category: hospital, extras or combined (empty = all)."""
        rows = town.comparison(town.resident(rid))
        return [x for x in rows if not category or x["category"] == category][:30]

    async def company_info() -> dict:
        """AI Company Health's public information: plans, inclusions, waiting periods, and its live service numbers."""
        k = (co.kpi_window(28) or {}).get("current", {})
        lev = co.economy.levers() if getattr(co, "economy", None) else {}
        return {"insurer": "AI Company Health", "about": INSURERS[OURS]["note"], "member_perks": lev.get("perks", []),
                "new_member_discount": f"{lev.get('new_joiner_discount', 0)*100:.0f}%", "our_health_care": "AI Company Health Private Hospital and AI Company Health Clinic "
                "(dental, optical, physio, GP) in Wattle Grove: members pay no gap there.",
                "service": {"claims_paid_within_5_days_pct": round(k.get("claims_sla_pct", 0), 1), "average_call_wait_seconds": round(k.get("avg_wait_s", 0)),
                            "net_promoter_score": round(k.get("nps", 0))},
                "plans": [{x: p[x] for x in ("id", "name", "category", "tier", "monthly_price", "inclusions", "waiting", "description")}
                          for p in co.products_view() if p["active"] and p["category"] in ("hospital", "extras", "combined")]}

    async def search_web(query: str) -> dict:
        """Search the web (e.g. how Lifetime Health Cover works, reviews of an insurer, what extras cover)."""
        results = mock_search(query, town)
        if not settings.use_mock and settings.town_real_web:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client()
                resp = await asyncio.wait_for(client.aio.models.generate_content(
                    model=settings.model_fast,
                    contents=f"Search the web and answer in at most 5 short bullet points for an Australian consumer: {query}",
                    config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2)), 45)
                results = (resp.text or "")[:2500] + "\n(Insurers you can actually buy from in this town: " + ", ".join(v["name"] for v in INSURERS.values()) + ")"
            except Exception as e:  # noqa: BLE001 - fall back to the town's own information
                log.info("real web search failed (%s); using the town web", e)
        world.emit({"type": "town_event", "event": {"resident": rid, "kind": "web", "text": f"searched: {query[:80]}"}, "quiet": True})
        return {"query": query, "results": results}

    async def ask_employee(question: str, employee_id: str = "") -> dict:
        """Ask AI Company Health a question (phone/chat). If you personally know someone who works there you may ask them (employee_id)."""
        emp = employee_id if employee_id in AGENTS and AGENTS[employee_id].dept in ("sales", "care", "health", "prod", "mkt", "claims") else ""
        if not emp:
            known = [x["id"] for x in town.relations(rid) if x.get("employee") and AGENTS[x["id"]].dept in ("sales", "care")]
            emp = known[0] if known else ("sales.ana" if "sales.ana" in AGENTS else next(a.id for a in DEPARTMENTS["sales"].agents))
        r = town.resident(rid) or {}
        answer = await runtime.enquiry(emp, r, question)
        world.remember(rid, "talk", f"I asked {AGENTS[emp].name} at AI Company Health: {question[:150]} They said: {answer[:200]}", 0.6)
        world.remember(emp, "customer", f"{r.get('name', rid)} ({r.get('age')}, {r.get('suburb')}) asked: {question[:150]}", 0.5)
        world.convo(rid, emp, "enquiry", question, AGENTS[emp].dept)
        world.convo(emp, rid, "enquiry", answer, AGENTS[emp].dept)
        world.room_log(AGENTS[emp].dept, r.get("name", rid), "enquiry", question)
        world.room_log(AGENTS[emp].dept, emp, "enquiry", answer)
        world.say(emp, f"☎️ {r.get('name', rid).split()[0]}: {answer[:90]}", 4500)
        emit({"resident": rid, "kind": "enquiry", "text": f"asked {AGENTS[emp].name}: {question[:120]}", "employee": emp, "answer": answer[:300]})
        return {"employee": AGENTS[emp].name, "role": AGENTS[emp].role, "answer": answer}

    async def message_someone(resident_id: str, text: str) -> dict:
        """Tell someone you know (by their resident id from my_profile) what you think about health insurance."""
        res = town.message(rid, resident_id, text)
        if res.get("ok"):
            world.convo(rid, resident_id, "message", text)
            world.remember(resident_id, "talk", f"{(town.resident(rid) or {}).get('name', rid)} told me: {text[:200]}", 0.6)
            emit({"resident": rid, "kind": "message", "to": resident_id, "text": text[:200]}, f"💬 {text[:80]}")
        return res

    async def buy_policy(plan_id: str, reason: str) -> dict:
        """Buy (or switch to) a plan for your household. plan_id comes from compare_insurers. reason: why, in your own words."""
        ev = town.buy(rid, plan_id, reason)
        if "error" not in ev:
            world.remember(rid, "decision", ev["text"], 0.9)
            r = town.resident(rid) or {}
            ours = ev.get("insurer") == OURS
            emit(ev, f"🛒 {('Joined' if ev['kind'] != 'change_plan' else 'Changed to')} {INSURERS[ev['insurer']]['name']}")
            if ours:
                world.say("sales.leo", f"🎉 New member from town: {r.get('name', rid)}", 5000)
                world.log(f"🏘 {r.get('name', rid)} joined AI Company Health: {reason[:120]}")
        return ev

    async def keep_current_cover(reason: str) -> dict:
        """Decide to keep what you have (or to stay without cover). reason: why."""
        ev = town.keep(rid, reason)
        world.remember(rid, "decision", ev["text"], 0.6)
        emit(ev, "🤔 Keeping my current cover")
        return ev

    async def cancel_cover(reason: str) -> dict:
        """Cancel your household's private health insurance. reason: why."""
        ev = town.cancel(rid, reason)
        if "error" not in ev:
            emit(ev, "✂️ Cancelled my cover")
        return ev

    async def post_review(insurer_id: str, stars: int, text: str) -> dict:
        """Post a public review (1-5 stars) of an insurer you have experience with. insurer_id: aich, harbour, koala, bluegum or pacific."""
        res = town.review(rid, insurer_id, stars, text)
        if res.get("ok"):
            emit({"resident": rid, "kind": "review", "insurer": insurer_id, "text": f"{'★' * int(stars)} {text[:160]}"}, f"{'★' * int(stars)}")
        return res

    async def recall_memories(query: str = "") -> list:
        """Search your own memories (what happened in your life, what people told you, what you decided)."""
        return [{"date": m["sim_date"], "memory": m["text"]} for m in world.memories(rid, query, 10)]

    tools = [my_profile, my_feed, compare_insurers, company_info, search_web, ask_employee, message_someone, buy_policy, keep_current_cover,
             cancel_cover, post_review, recall_memories]
    mayor = town.life.mayor()
    if mayor and mayor["id"] == rid:
        async def get_town_needs() -> dict:
            """As chair of the town council: population, children, older residents, people without cars, what is built, and the options."""
            return town.life.needs()

        async def build_facility(kind: str, reason: str) -> dict:
            """Approve building ONE facility the town needs (kind from get_town_needs options). reason: why, citing the numbers."""
            f = town.life.build(kind, reason, rid, co.today)
            if "error" not in f:
                world.emit({"type": "town_life", "event": {"resident": rid, "kind": "facility", "text": f"The council approved {f['name']}: {reason[:160]}"}, "facility": f})
                world.remember(rid, "life", f"As council chair I approved building {f['name']} because {reason[:150]}", 0.9)
                world.log(f"🏗️ Wattle Grove council approved {f['name']}")
            return f
        tools += [get_town_needs, build_facility]
    return tools

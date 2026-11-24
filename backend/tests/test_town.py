"""The town: 100 residents with relations, a market with fictional competitors, residents deciding, Marketing campaigns, and room talk."""
import asyncio

import pytest

from hq.town.town import INSURERS


@pytest.fixture
async def co(svc):
    svc.company.ensure_history()
    return svc


async def run_flow(svc, name, params=None, timeout=90):
    run = await svc.workflows.start(name, params or {})
    return await svc.workflows.wait(run.id, timeout)


async def test_town_has_100_residents_households_relations_and_a_market(co):
    t = co.company.town
    rs = t.residents()
    assert len(rs) == 100 and len({r["household"] for r in rs}) >= 30
    covered = {(r.get("cover") or {}).get("insurer") for r in rs}
    assert None not in covered and len(covered) >= 5, "membership is mandatory; people are spread across the Australian funds"
    links = t.employee_contacts()
    assert len(links) >= 15, "residents know some of the company's employees"
    r = next(x for x in rs if x["age"] >= 35)
    late = dict(r, held_hospital_before=False)
    assert t.lhc(late) > 0, "Lifetime Health Cover loading applies to late joiners"
    cmp = t.comparison(r)
    assert {c["insurer"] for c in cmp} <= set(INSURERS) and {"aich", "medibank", "bupa", "hcf", "nib"} <= {c["insurer"] for c in cmp}
    assert all(c["monthly_price"] > 0 for c in cmp)
    teacher_free = [x for x in rs if not any(m.get("workplace") in ("school", "tafe") or m.get("occupation") == "Teacher" for m in t.household(x))]
    if teacher_free:
        assert "teachers" not in {c["insurer"] for c in t.comparison(teacher_free[0])}, "Teachers Health is a restricted fund"
    assert "mandatory" in t.cancel(rs[0]["id"], "x")["error"]
    rels = t.relations(rs[0]["id"])
    assert rels and all("relation" in x for x in rels)


async def test_residents_shop_ask_staff_and_decide(co):
    t = co.company.town
    q = co.bus.subscribe()
    picks = [r["id"] for r in t.residents() if r["age"] >= 25][:6]
    run = await run_flow(co, "town_day", {"residents": picks, "reason": "Your premium notice arrived."})
    assert run.status == "completed", run.error
    ev = co.company.store.rows("SELECT * FROM town_events")
    decided = {e["resident"] for e in ev if e["kind"] in ("buy", "switch", "keep", "change_plan")}
    assert decided == set(picks)
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    assert any(m.get("type") == "town_event" for m in msgs) and any(m.get("type") == "town" for m in msgs)
    if any(e["kind"] == "enquiry" for e in ev):
        assert co.world.room_history("sales") or co.world.room_history("care"), "enquiries are recorded in the employee's room"


async def test_marketing_campaign_respects_community_rating_and_reaches_people(co):
    t = co.company.town
    bad = t.launch_campaign("mkt.ben", "x", "Cover for people with chronic conditions", {"health": "chronic"}, "", 2)
    assert "community rating" in bad["error"]
    assert "under-18" in t.launch_campaign("mkt.ben", "x", "Teens", {"age_min": 15}, "", 2)["error"]
    run = await run_flow(co, "town_marketing")
    assert run.status == "completed", run.error
    camps = t.active_campaigns()
    assert camps and camps[0]["by_agent"].startswith("mkt.")
    reached = [r for r in t.residents() if t._targets(camps[0]["audience"], r)]
    assert reached and all(r["age"] >= 18 for r in reached)
    assert t.feed(reached[0]["id"])["ads_you_saw"]


async def test_room_talk_mentions_raise_hands_and_take_turns(co):
    w = co.world
    q = co.bus.subscribe()
    w.meeting("mr1", ["sales.leo", "claims.helen"], "Review", meeting_id="M-t", agenda="Net adds", organizer="sales.leo")
    await co.rooms.post("mr1", "@Helen what is the claims backlog? and @Leo how are sales?")
    for _ in range(100):
        await asyncio.sleep(0.05)
        if not co.rooms.queues.get("mr1") and co.rooms.workers["mr1"].done():
            break
    hist = w.room_history("mr1")
    speakers = [e["speaker"] for e in hist if e["kind"] == "speech"]
    assert speakers[:2] == ["claims.helen", "sales.leo"], "people speak one at a time in the order they were called"
    assert any(e["kind"] == "user" and "@Helen" in e["text"] for e in hist)
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    assert any(e.get("type") == "hand" and e.get("raised") for e in events) and any(e.get("type") == "speaking" for e in events)
    await co.rooms.post("sales", "What should we focus on this week?")      # department room: the head answers
    await co.rooms.workers["sales"]
    assert any(e["speaker"] == "sales.leo" and e["kind"] == "speech" for e in w.room_history("sales"))


async def test_jobs_pay_vehicles_and_australian_rebate_and_surcharge(co):
    t = co.company.town
    rs = t.residents()
    adults = [r for r in rs if r["age"] >= 18]
    assert all(r.get("employer") and r.get("workplace") and "income_aud" in r and r.get("vehicle") for r in adults)
    kids = [r for r in rs if r["age"] < 18]
    assert all(r["workplace"] == "school" for r in kids)
    rich = max(adults, key=lambda r: r["income_aud"])
    poor = min((r for r in adults if r["household_kind"] in ("single", "share_house")), key=lambda r: r["income_aud"])
    assert t.rebate(poor) > t.rebate(rich), "higher incomes get a smaller government rebate"
    if rich["household_kind"] in ("single", "share_house") and rich["income_aud"] > 101_000:
        assert t.mls(rich) > 0
    assert t.mls(poor) == 0, "low incomes pay no Medicare Levy Surcharge"
    snap = t.snapshot()
    assert "cover_reason" in snap["residents"][0] and snap["workplaces"]["mall"] == "Wattle Grove Mall"


async def test_conversations_and_token_usage_are_recorded_per_person(co):
    picks = [r["id"] for r in co.company.town.residents() if r["age"] >= 25][:6]
    await run_flow(co, "town_day", {"residents": picks})
    w = co.world
    u = w.usage(picks[0])
    assert u["total"]["calls"] > 0 and u["total"]["tokens"] > 0, "every model call is metered against the person who made it"
    enq = co.company.store.rows("SELECT * FROM convos WHERE channel='enquiry'")
    if enq:
        a, b = enq[0]["frm"], enq[0]["to_"]
        th = w.threads(a)
        assert any(x["other"] == b for x in th)
        assert len(w.thread(a, b)) >= 2, "question and answer are both in the thread"
    w.meeting("mr2", ["sales.leo"], "x", meeting_id="M-x", agenda="x", organizer="sales.leo")
    await co.rooms.post("mr2", "@Leo how are we tracking?")
    await co.rooms.workers["mr2"]
    assert any(x["other"] == "ceo" and x["channel"] == "meeting" for x in w.threads("sales.leo"))
    assert w.usage("sales.leo")["total"]["calls"] > 0


async def test_a_year_of_life_aging_births_deaths_move_ins_relationships_and_building(co):
    from datetime import date, timedelta
    t, life = co.company.town, co.company.town.life
    start = {r["id"]: r["age"] for r in t.residents()}
    assert all(r.get("gender") in ("female", "male", "non-binary") and r.get("birthday") for r in t.residents())
    kinds = {}
    d = date(2026, 3, 2)
    for i in range(365):
        for item in life.advance_day(d + timedelta(days=i)):
            kinds[item["event"]["kind"]] = kinds.get(item["event"]["kind"], 0) + 1
    assert kinds.get("birthday", 0) >= 80, "everyone has a birthday in a year"
    aged = [r for r in t.residents() if r["id"] in start and r["age"] == start[r["id"]] + 1]
    assert len(aged) >= 0.8 * len([r for r in t.residents() if r["id"] in start])
    assert kinds.get("death", 0) >= 1 and kinds.get("birth", 0) >= 1 and kinds.get("move_in", 0) >= 1 and kinds.get("friendship", 0) >= 10
    assert any(r.get("deceased") for r in t.all_residents()) and all(not r.get("deceased") for r in t.residents())
    assert life.advance_day(d + timedelta(days=10)) == [], "a day happens once"
    n = life.needs()
    f = life.rule_council(date(2027, 3, 1))
    if n["options"]:
        assert f and f["kind"] == n["options"][0]["kind"] and life.facilities()


async def test_memory_talk_and_council_with_the_mock(co):
    w, rt = co.world, co.runtime
    reply = await rt.talk("sales.leo", "What are you working on?")
    assert reply and any(m["kind"] == "talk" for m in w.memories("sales.leo"))
    assert "Your memories" in w.memory_block("sales.leo")
    r = co.company.town.residents()[5]["id"]
    rr = await rt.talk(r, "Hi, how is your health insurance going?")
    assert rr and w.thread(r, "ceo") and w.memories(r)
    mayor = co.company.town.life.mayor()["id"]
    await rt.resident_task(mayor, "[RESIDENT] You chair the council. Use get_town_needs and maybe build_facility.", "council")
    assert co.company.store.rows("SELECT * FROM town_events WHERE kind='facility'") or not co.company.town.life.needs()["options"]



async def test_the_company_runs_on_the_agents_health_care_claims_and_membership_levers(town_svc):
    from datetime import date
    s = town_svc
    co, town = s.company, s.company.town
    assert co.economy is not None and co.store.last_date() is None, "no synthetic history: the numbers start from the agents"
    ours = [r for r in town.residents() if r["cover"]["insurer"] == "aich"]
    member = ours[0] if ours else town.residents()[0]
    v = town.health.visit(member, "dental", co.today)
    if member["cover"]["insurer"] == "aich" and member["cover"].get("extras"):
        assert v["facility"] == "aich_clinic" and v["gap"] == 0, "members pay no gap at our own clinic"
    other = next(r for r in town.residents() if r["cover"]["insurer"] != "aich")
    town.buy(other["id"], next(c["plan_id"] for c in town.comparison(other) if c["insurer"] == "aich"), "test join")
    res = co.advance()
    k = res.kpi
    assert k["new_sales"] >= 1 and k["policies_in_force"] >= len(ours) + 1, "a resident joining is a sale"
    sales = co.sales()
    assert sales["sold"]["all_time"] >= 1 and sales["recent_sales"][0]["to"] == "AI Company Health" and sales["recent_sales"][0]["why"] == "test join"
    assert co.profile()["sales"]["sold"]["all_time"] == sales["sold"]["all_time"]
    assert k["premium_revenue"] > 0 and co.store.last_date() == res.date
    assert co.kpi_window(7)["current"]["policies_in_force"] == k["policies_in_force"]
    ini = co.propose("mkt.grace", "mkt", "promo_discount", "New member offer", "Test", {"discount_pct": 15, "weeks": 4, "products": ["hosp_silver"]})
    if "error" not in ini:
        assert ini["cost_est"] < 50_000, "initiative costs are scaled to the town"
        co.decide(ini["id"], "exec.priya", "approve", "go")
        for _ in range(16):
            co.advance()
        lev = co.economy.levers()
        newbie = next(r for r in town.residents() if r["cover"]["insurer"] != "aich")
        ours_price = [c for c in town.comparison(newbie) if c["insurer"] == "aich"]
        assert lev["new_joiner_discount"] > 0 and ours_price and "off for new members" in ours_price[0]["offer"]
    f = co.economy.funnel(28)
    assert f["joined_us"] >= 1 and "health_care" in f
    from hq.town.loop import day_plan
    plan = day_plan(town.residents()[0], date(2026, 3, 4), town)
    assert plan[0]["place"] == "home" and plan[-1]["place"] == "home" and len(plan) >= 3


async def test_claims_are_booked_at_real_frequency_and_old_days_are_rebooked(town_svc):
    """Town visits are accelerated for liveliness; the books count them at real frequency and pool very large claims (risk equalisation)."""
    from hq.town.health import ACCEL, POOL_CAP, booked
    assert booked(600) == 600 / ACCEL
    assert booked(POOL_CAP + 10_000) < (POOL_CAP + 10_000) / ACCEL / 2, "a big surgery does not wipe out a month of premiums"
    co, st = town_svc.company, town_svc.company.store
    member = next(r for r in co.town.residents() if r["cover"]["insurer"] == "aich")
    co.town.health.visit(member, "surgery", co.today)
    st.db.execute("INSERT INTO town_exposure VALUES (?, 2.0)", (co.today.isoformat(),))   # the day ran twice as long as planned
    k = co.advance().kpi
    assert abs(k["claims_incurred"] - co.town.health.booked_cost("aich", k["date"])) < 0.02 and booked(600, 2.0) == 600 / ACCEL / 2
    raw = sum(c["insurer_cost"] for c in st.rows("SELECT insurer_cost FROM town_claims WHERE date=? AND insurer='aich'", (k["date"],)))
    assert raw > 0
    # a database written with the old booking (full cost) is fixed once on start
    st.db.execute("UPDATE daily_kpi SET claims_incurred=?, loss_ratio=99 WHERE date=?", (raw, k["date"]))
    st.set_kv("claims_booking", "v1")
    co.economy.ensure()
    fixed = st.kpis(1, k["date"])[0]
    assert fixed["claims_incurred"] == k["claims_incurred"] and abs(fixed["loss_ratio"] - fixed["claims_incurred"] / fixed["premium_revenue"]) < 0.01 and st.get_kv("claims_booking") == "v3"

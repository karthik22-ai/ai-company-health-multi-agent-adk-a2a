import asyncio


async def test_agent_task_via_adk(svc):
    w = svc.world
    t = w.new_task("sales.leo", "Rolling forecast v3", "Update the forecast")
    text = await svc.runtime.run_task(t)
    assert w.tasks[t.id].status == "done"
    assert w.tasks[t.id].progress == 100
    assert "Completed" in text
    assert w.agents["sales.leo"].state == "done"


async def test_every_agent_has_an_a2a_card(svc):
    assert len(svc.cards) == 50
    card = svc.cards["risk.isabel"]
    assert "Isabel Moreno" in card.description


async def test_a2a_consult(svc):
    answer = await svc.peers.ask("sales.leo", "data.arjun", "Is the warehouse refreshed?")
    assert "Arjun" in answer, answer
    assert svc.peers.messages[0]["kind"] == "consult"


async def test_a2a_handoff(svc):
    t = await svc.peers.hand_off("claims.helen", "mkt.grace", "Trial balance pack", "Consolidate it")
    for _ in range(300):
        if svc.world.tasks[t.id].status in ("done", "failed"):
            break
        await asyncio.sleep(0.05)
    assert svc.world.tasks[t.id].status == "done", svc.world.tasks[t.id]
    assert svc.world.tasks[t.id].agent == "mkt.grace"

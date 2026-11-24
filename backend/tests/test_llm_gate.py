"""The model-call gate serves the owner's chats before queued background work."""
import asyncio

from hq.llm.guarded import _Gate


async def test_foreground_waiters_jump_the_queue():
    g, order = _Gate(1), []
    await g.acquire(1)                                   # a background call holds the only slot

    async def call(name, prio):
        await g.acquire(prio)
        order.append(name)
        g.release()

    tasks = [asyncio.create_task(call(f"bg{i}", 1)) for i in range(3)]
    await asyncio.sleep(0)
    tasks.append(asyncio.create_task(call("chat", 0)))
    await asyncio.sleep(0)
    g.release()
    await asyncio.gather(*tasks)
    assert order[0] == "chat" and order[1:] == ["bg0", "bg1", "bg2"] and g.free == 1

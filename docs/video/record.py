"""Record the video tour: drives the app in Chrome (Playwright), records the screen, and logs when each narration line starts.

Usage:  python record.py [base_url]        (the backend must be running; default http://localhost:8787)
Output: raw.webm (the screen) and timeline.json (narration start times, seconds from the start of the video)
"""
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
W, H = 1600, 900
DUR = {p.stem: wave.open(str(p)).getnframes() / 24000 for p in (HERE / "audio").glob("*.wav")}

# A visible cursor (headless recordings have none) that follows the mouse and pulses on click.
CURSOR = """
addEventListener('DOMContentLoaded',()=>{const c=document.createElement('div');c.id='demoCursor';
c.style.cssText='position:fixed;z-index:99999;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:#ffffffcc;border:2px solid #f5b942;box-shadow:0 2px 10px #0008;pointer-events:none;transition:transform .12s';
document.body.appendChild(c);addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px'},true);
addEventListener('mousedown',()=>c.style.transform='scale(.6)',true);addEventListener('mouseup',()=>c.style.transform='scale(1)',true)});
try{localStorage.setItem('hqTourDone','1')}catch(e){}
addEventListener('DOMContentLoaded',()=>{const st=document.createElement('style');st.textContent='body.focusmode #focusExit{display:none!important}';document.head.appendChild(st)});
"""


class Tour:
    def __init__(self, page):
        self.page, self.t0, self.log, self.mouse = page, time.monotonic(), [], (W / 2, H / 2)

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def say(self, key: str, wait: bool = False) -> float:
        """Start a narration line now; optionally wait until it has been spoken."""
        self.log.append({"key": key, "start": round(self.now(), 2), "dur": round(DUR[key], 2)})
        if wait:
            await asyncio.sleep(DUR[key] + .4)
        return DUR[key]

    async def until(self, key: str, extra: float = .5) -> None:
        """Wait until the narration line `key` has finished (+ a breath)."""
        e = next(x for x in reversed(self.log) if x["key"] == key)
        await asyncio.sleep(max(0.0, e["start"] + e["dur"] + extra - self.now()))

    async def js(self, code: str):
        return await self.page.evaluate(code)

    async def move(self, x: float, y: float, steps: int = 28) -> None:
        await self.page.mouse.move(x, y, steps=steps)
        self.mouse = (x, y)

    async def click(self, selector: str, text: str | None = None, pause: float = .35) -> None:
        loc = self.page.locator(selector, has_text=text) if text else self.page.locator(selector)
        if not await loc.count():
            print("skip click (not found):", selector, text)
            return
        loc = loc.first
        await loc.scroll_into_view_if_needed()
        b = await loc.bounding_box()
        if not b:
            print("skip click (hidden):", selector, text)
            return
        await self.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        await asyncio.sleep(pause)
        await self.page.mouse.down()
        await asyncio.sleep(.08)
        await self.page.mouse.up()


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True, args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal",
                                                                                 "--enable-unsafe-swiftshader"])
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                        record_video_dir=str(HERE / "rec"), record_video_size={"width": W, "height": H})
        await ctx.add_init_script(CURSOR)
        t0 = time.monotonic()
        page = await ctx.new_page()
        tour = Tour(page)
        tour.t0 = t0
        await page.goto(BASE + "/")
        await page.wait_for_function("typeof ws!=='undefined'&&ws&&ws.readyState===1&&TOWN&&TOWN.built", timeout=60000)
        await asyncio.sleep(2)
        t = tour

        # 1 intro: the building from outside, slowly rotating, panels hidden
        await t.js("setView('ext');controls.autoRotate=true;setFocusMode(true);document.querySelectorAll('.toast').forEach(x=>x.remove())")
        await asyncio.sleep(1.5)
        await t.say("intro")
        await t.until("intro")

        # 2 the town
        await t.js("setFocusMode(false);controls.autoRotate=false")
        await t.click('[data-a="town"]')
        await t.say("town")
        await asyncio.sleep(9)
        await t.js("controls.autoRotate=true")
        await t.until("town", .2)
        await t.js("controls.autoRotate=false")

        # 3 the office and one employee
        await t.js("clearFocus();setView('ext');showLeftTab('agents')")
        await asyncio.sleep(1.2)
        await t.say("office")
        await asyncio.sleep(3.5)
        await t.click(".col.l .row[data-agent]", "Leo Martins")
        await t.until("office", .3)

        # 4 talk to him (live Gemini)
        await t.say("chat_ask")
        await t.click("#tkIn")
        await page.keyboard.type("Hi Leo, how are sales going this month?", delay=55)
        await t.until("chat_ask", .2)
        await page.keyboard.press("Enter")
        await page.wait_for_function("PEOPLE['sales.leo']&&PEOPLE['sales.leo'].typing===false&&(PEOPLE['sales.leo'].ceo||[]).slice(-1)[0].frm!=='ceo'",
                                     timeout=120000, polling=500)
        await asyncio.sleep(4.5)                       # time to read the reply
        await t.say("chat_reply")
        await t.until("chat_reply", .4)

        # 5 memberships sold
        await t.js("clearFocus()")
        await t.say("sold")
        await t.click("#soldChip")
        await asyncio.sleep(5)
        await t.js("document.getElementById('profSales')&&document.querySelector('#profM .glass').scrollBy({top:260,behavior:'smooth'})")
        await t.until("sold", .4)
        await t.js("profM.classList.remove('on')")

        # 6 documents
        await t.click('[data-a="docs"]')
        await t.say("docs")
        await asyncio.sleep(5.5)
        await t.click("#docK button", "Presentations")
        await asyncio.sleep(2.5)
        await t.click("#docL [data-open]")
        await t.until("docs", 1.2)
        await t.js("typeof closeFile==='function'&&closeFile();docsM.classList.remove('on')")

        # 7 timeline
        await t.click('[data-a="timeline"]')
        await asyncio.sleep(1.5)
        await t.say("timeline")
        await t.click("#tlPlay")
        await t.until("timeline", .8)
        await t.js("tlStop();tlM.classList.remove('on')")

        # 8 ops: live, traces, one trace, goals, evaluations
        await t.click('[data-a="ops"]')
        await t.say("ops")
        await asyncio.sleep(5)
        await t.click("#opsTabs button", "Traces")
        await asyncio.sleep(2.2)
        await t.js("(()=>{const r=[...document.querySelectorAll('#opsB .trow')].find(x=>!x.textContent.includes('no tools'));r&&r.scrollIntoView({block:'center'})})()")
        await t.click("#opsB .trow:not(:has(.err))")
        await t.until("ops", .3)
        await t.click("#opsTabs button", "Goals")
        await t.say("goals")
        await asyncio.sleep(5.5)
        await t.click("#opsTabs button", "Evaluations")
        await t.until("goals", .4)
        await t.js("opsM.classList.remove('on')")

        # 9 outro
        await t.js("clearFocus();setView('ext');controls.autoRotate=true;setFocusMode(true);document.querySelectorAll('.toast').forEach(x=>x.remove())")
        await asyncio.sleep(1)
        await t.say("outro")
        await t.until("outro", 2.5)

        video = page.video
        close_at = t.now()
        await ctx.close()
        await browser.close()
        src = await video.path()
        Path(src).replace(HERE / "raw.webm")
        import imageio_ffmpeg, re, subprocess
        info = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(HERE / "raw.webm")], capture_output=True, text=True).stderr
        h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info).groups()
        offset = round(close_at - (int(h) * 3600 + int(m) * 60 + float(s)), 2)    # the video started this long after t0
        (HERE / "timeline.json").write_text(json.dumps({"video_offset": offset, "lines": t.log}, indent=1))
        print("video offset", offset)
        print("recorded", round(t.now(), 1), "s →", HERE / "raw.webm")


asyncio.run(main())

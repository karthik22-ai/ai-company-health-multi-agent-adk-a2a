"""Record the LinkedIn walkthrough: plain screen recording, first-person narration, results.

Usage:  python record.py [base_url]     (backend running with Gemini)
Output: raw.webm + timeline.json (narration start times; video offset)
"""
import asyncio
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import imageio_ffmpeg
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
W, H = 1600, 900
DUR = {p.stem: wave.open(str(p)).getnframes() / 24000 for p in (HERE / "audio").glob("*.wav")}

INIT = r"""
try{localStorage.setItem('hqTourDone','1')}catch(e){}
/* Demo mask: no model names, no project id, no rival fund names anywhere on screen (also inside live agent answers). */
(()=>{const RIV=[['Teachers Health','Rival Fund G'],['Australian Unity','Rival Fund H'],['Medibank','Rival Fund A'],['Bupa','Rival Fund B'],['HCF','Rival Fund C'],
  ['GMHBA','Rival Fund I'],['HBF','Rival Fund E'],['nib','Rival Fund D'],['ahm','Rival Fund F']];
  const fix=s=>{let o=s.replace(/Vertex AI · project-[^·]+ · [^·]+ · [\w.\-]+/g,'Vertex AI').replace(/project-[0-9a-f]{6,}[\w-]*/gi,'your project')
    .replace(/\bgemini[\w.\-]*/gi,'the model');for(const [a,b] of RIV)o=o.replace(new RegExp('\\b'+a+'\\b','g'),b);o=o.replace(/\(Australian rules\)/g,'(local rules)').replace(/\s*·\s*Australia\b/gi,'').replace(/\bAustralian\s+/gi,'').replace(/\bin Australia\b/gi,'');return o};window.__fix=fix;for(const k of ['fillText','strokeText']){const f0=CanvasRenderingContext2D.prototype[k];CanvasRenderingContext2D.prototype[k]=function(s,...a){return f0.call(this,typeof s==='string'?fix(s):s,...a)}};
  const walk=n=>{if(n.nodeType===3){const v=fix(n.nodeValue);if(v!==n.nodeValue)n.nodeValue=v;return}
    if(n.nodeType===1&&!/^(SCRIPT|STYLE)$/.test(n.tagName)){if(n.title)n.title=fix(n.title);if(n.placeholder)n.placeholder=fix(n.placeholder);n.childNodes.forEach(walk)}};
  addEventListener('DOMContentLoaded',()=>{walk(document.body);new MutationObserver(ms=>ms.forEach(m=>{m.addedNodes.forEach(walk);if(m.type==='characterData')walk(m.target)}))
    .observe(document.body,{childList:true,subtree:true,characterData:true})})})();
addEventListener('DOMContentLoaded',()=>{
  const st=document.createElement('style');st.textContent=`
  body.focusmode #focusExit{display:none!important}
  #demoCursor{position:fixed;z-index:99999;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:#ffffffcc;border:2px solid #f5b942;box-shadow:0 2px 10px #0008;pointer-events:none;transition:transform .12s}
  #cine{position:fixed;inset:0;z-index:99990;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;opacity:0;transition:opacity .9s ease;
        background:radial-gradient(ellipse at center,#0d1426f2 0%,#03050bff 75%);font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:#fff;text-align:center}
  #cine.on{opacity:1}#cine.soft{background:linear-gradient(180deg,#03050b00 0%,#03050bcc 35%,#03050bcc 65%,#03050b00 100%)}
  #cine .k{font-size:15px;letter-spacing:.55em;text-transform:uppercase;color:#f5b942;opacity:0;transform:translateY(8px);transition:all 1.1s ease .15s}
  #cine .t{font-size:64px;font-weight:700;letter-spacing:.42em;margin:14px 0 10px;opacity:0;transition:letter-spacing 2.6s cubic-bezier(.2,.7,.2,1),opacity 1.4s ease}
  #cine .s{font-size:22px;font-weight:300;color:#c9d2e6;letter-spacing:.06em;opacity:0;transform:translateY(10px);transition:all 1.2s ease .6s;max-width:1100px;line-height:1.45}
  #cine .f{position:absolute;bottom:64px;font-size:14px;letter-spacing:.3em;text-transform:uppercase;color:#8691ab;opacity:0;transition:opacity 1.2s ease 1.2s}
  #cine.on .k,#cine.on .s{opacity:1;transform:none}#cine.on .t{opacity:1;letter-spacing:.14em}#cine.on .f{opacity:1}
  .bars:before,.bars:after{content:'';position:fixed;left:0;right:0;height:62px;background:#000;z-index:99980;transition:height 1s ease}
  .bars:before{top:0}.bars:after{bottom:0}`;
  document.head.appendChild(st);
  const c=document.createElement('div');c.id='demoCursor';document.body.appendChild(c);
  addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px'},true);
  addEventListener('mousedown',()=>c.style.transform='scale(.6)',true);addEventListener('mouseup',()=>c.style.transform='scale(1)',true);
  const v=document.createElement('div');v.id='cine';v.innerHTML='<div class="k"></div><div class="t"></div><div class="s"></div><div class="f"></div>';document.body.appendChild(v);
  window.cine=(k,t,s,f,soft)=>{v.classList.remove('on');v.classList.toggle('soft',!!soft);void v.offsetWidth;
    v.querySelector('.k').textContent=k||'';v.querySelector('.t').textContent=t||'';v.querySelector('.s').textContent=s||'';v.querySelector('.f').textContent=f||'';
    requestAnimationFrame(()=>v.classList.add('on'))};
  window.cineOff=()=>v.classList.remove('on');
});
"""


class Tour:
    def __init__(self, page):
        self.page, self.t0, self.log = page, time.monotonic(), []

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def say(self, key: str, wait: bool = False) -> None:
        self.log.append({"key": key, "start": round(self.now(), 2), "dur": round(DUR[key], 2)})
        if wait:
            await asyncio.sleep(DUR[key] + .5)

    async def until(self, key: str, extra: float = .5) -> None:
        e = next(x for x in reversed(self.log) if x["key"] == key)
        await asyncio.sleep(max(0.0, e["start"] + e["dur"] + extra - self.now()))

    async def js(self, code: str):
        return await self.page.evaluate(code)

    async def card(self, k: str, t: str, s: str = "", f: str = "", hold: float = 3.2, soft: bool = False) -> None:
        await self.js(f"cine({json.dumps(k)},{json.dumps(t)},{json.dumps(s)},{json.dumps(f)},{json.dumps(soft)})")
        await asyncio.sleep(hold)
        await self.js("cineOff()")
        await asyncio.sleep(1.0)

    async def click(self, selector: str, text: str | None = None, pause: float = .35) -> bool:
        loc = self.page.locator(selector, has_text=text) if text else self.page.locator(selector)
        if not await loc.count():
            print("skip click (not found):", selector, text)
            return False
        loc = loc.first
        await loc.scroll_into_view_if_needed()
        b = await loc.bounding_box()
        if not b:
            print("skip click (hidden):", selector, text)
            return False
        await self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=26)
        await asyncio.sleep(pause)
        await self.page.mouse.down()
        await asyncio.sleep(.08)
        await self.page.mouse.up()
        return True

    async def type(self, selector: str, text: str) -> None:
        await self.click(selector)
        await self.page.keyboard.type(text, delay=38)

    async def scroll_to_text(self, container: str, text: str) -> None:
        await self.js(f"""(()=>{{const c=document.querySelector({json.dumps(container)});if(!c)return;
          const el=[...c.querySelectorAll('h3,b,small,div')].find(x=>x.textContent.trim().startsWith({json.dumps(text)}));
          if(el)el.scrollIntoView({{behavior:'smooth',block:'start'}})}})()""")


async def main() -> None:
    sales = json.loads(subprocess.run(["curl", "-s", f"{BASE}/api/company/sales?recent=5"], capture_output=True, text=True).stdout)
    res = sales["recent_sales"][0]
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True, args=["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal", "--enable-unsafe-swiftshader"])
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                        record_video_dir=str(HERE / "rec"), record_video_size={"width": W, "height": H})
        await ctx.add_init_script(INIT)
        t0 = time.monotonic()
        page = await ctx.new_page()
        page.on("pageerror", lambda e: print("PAGE ERROR:", str(e)[:300]))
        t = Tour(page)
        t.t0 = t0
        await page.goto(BASE + "/")
        for i in range(120):
            st = await page.evaluate("({ws:typeof ws!=='undefined'&&ws?ws.readyState:-1,town:typeof TOWN!=='undefined'&&!!TOWN.built})")
            if st["ws"] == 1 and st["town"]:
                break
            if i % 5 == 0:
                print("waiting for the app:", st)
            await asyncio.sleep(2)
        await t.js("setView('ext');controls.autoRotate=true;setFocusMode(true);document.querySelectorAll('.toast').forEach(x=>x.remove())")
        await asyncio.sleep(2.5)

        # intro: the building
        await t.say("intro")
        await t.until("intro", .4)
        await t.js("setFocusMode(false);controls.autoRotate=false")

        # the town and one resident
        await t.click('[data-a="town"]')
        await t.say("town")
        await asyncio.sleep(5)
        await t.js("controls.autoRotate=true")
        await t.until("town", .2)
        await t.js("controls.autoRotate=false")
        if not await t.click(f'.col.l [data-res="{res["resident"]}"]'):
            await t.js(f"selectResident({json.dumps(res['resident'])})")
        await asyncio.sleep(1.2)
        await t.say("resident")
        await asyncio.sleep(7)
        await t.js("(()=>{const d=document.getElementById('detail');const s=d.closest('.panel')||d;s.scrollBy({top:420,behavior:'smooth'})})()")
        await asyncio.sleep(6)
        await t.js("(()=>{const d=document.getElementById('detail');const s=d.closest('.panel')||d;s.scrollBy({top:520,behavior:'smooth'})})()")
        await t.until("resident", .4)

        # the office, Leo, tokens, live chat
        await t.js("clearFocus();setView('ext');showLeftTab('agents')")
        await asyncio.sleep(1)
        await t.say("office")
        await asyncio.sleep(4.5)
        await t.click(".col.l .row[data-agent]", "Leo Martins")
        await t.until("office", .4)
        await t.scroll_to_text("#detail", "AI usage")
        await asyncio.sleep(.6)
        await t.say("tokens")
        await t.until("tokens", .3)
        await t.scroll_to_text("#detail", "Talk to")
        await asyncio.sleep(.6)
        await t.say("chat_ask")
        await t.type("#tkIn", "Hi Leo, how are sales going this month?")
        await t.until("chat_ask", .2)
        await page.keyboard.press("Enter")
        await page.wait_for_function("PEOPLE['sales.leo']&&PEOPLE['sales.leo'].typing===false&&(PEOPLE['sales.leo'].ceo||[]).slice(-1)[0].frm!=='ceo'",
                                     timeout=240000, polling=500)
        await asyncio.sleep(4.5)
        await t.say("chat_reply")
        await t.until("chat_reply", .4)

        # a meeting
        await t.js("clearFocus();setView('ext')")
        await t.click("#ltabs button", "Meet")
        await asyncio.sleep(.6)
        await t.say("meet_call")
        await t.click("#mRoom")
        await page.select_option("#mRoom", "brd")
        await page.keyboard.press("Escape")
        await t.type("#mTopic", "Winning more members")
        await t.type("#mAgenda", "How do we win more young families this month? Each of you: one idea backed by our data.")
        for who in ("Grace", "Olivia", "Leo"):
            await t.page.fill("#mq", "")
            await t.type("#mq", who)
            await asyncio.sleep(.3)
            await t.click("#mList label", who)
        await t.until("meet_call", .2)
        await t.click("#mGo")
        await asyncio.sleep(1.5)
        await t.js("focusDept('brd')")
        await asyncio.sleep(1.5)
        await t.say("meet_walk")
        for i in range(400):       # fast-forwarded in the edit
            step = await t.js("fetch(API()+'/api/workflows/runs').then(r=>r.json()).then(L=>{const m=L.filter(x=>x.name==='meeting').pop();"
                              "return m?(m.steps.find(s=>s.node==='present'&&s.status==='running')?'present':m.status):'none'})")
            if step in ("present", "completed", "failed") or (step == "none" and i > 30):
                print("meeting:", step)
                break
            await asyncio.sleep(1.5)
        await asyncio.sleep(8)

        # results
        await t.js("clearFocus();showLeftTab('agents')")
        await t.click("#soldChip")
        await asyncio.sleep(.8)
        await t.say("results")
        await asyncio.sleep(8)
        await t.js("document.querySelector('#profM .glass').scrollBy({top:260,behavior:'smooth'})")
        await t.until("results", .3)
        await t.js("profM.classList.remove('on')")
        await t.click('[data-a="timeline"]')
        await asyncio.sleep(1)
        await t.say("kpis")
        await t.click("#tlPlay")
        await t.until("kpis", .8)
        await t.js("tlStop();tlM.classList.remove('on')")
        await t.click('[data-a="docs"]')
        await t.say("docs")
        await asyncio.sleep(5)
        await t.click("#docK button", "Presentations")
        await asyncio.sleep(3)
        await t.click("#docL [data-open]")
        await t.until("docs", 1.0)
        await t.js("typeof closeFile==='function'&&closeFile();docsM.classList.remove('on')")

        # under the hood
        await t.click('[data-a="ops"]')
        await t.say("ops")
        await asyncio.sleep(5)
        await t.click("#opsTabs button", "Traces")
        await asyncio.sleep(2.5)
        await t.click("#opsB .trow:not(:has(.err))")
        await t.until("ops", .4)
        await t.click("#opsTabs button", "Goals")
        await t.say("goals")
        await asyncio.sleep(6)
        await t.click("#opsTabs button", "Evaluations")
        await t.until("goals", .5)
        await t.js("opsM.classList.remove('on')")

        # outro
        await t.js("clearFocus();setView('ext');controls.autoRotate=true;setFocusMode(true);document.querySelectorAll('.toast').forEach(x=>x.remove())")
        await asyncio.sleep(.8)
        await t.say("outro")
        await t.until("outro", 3.0)

        video = page.video
        close_at = t.now()
        await ctx.close()
        await browser.close()
        Path(await video.path()).replace(HERE / "raw.webm")
        info = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(HERE / "raw.webm")], capture_output=True, text=True).stderr
        hh, mm, ss = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info).groups()
        offset = round(close_at - (int(hh) * 3600 + int(mm) * 60 + float(ss)), 2)
        (HERE / "timeline.json").write_text(json.dumps({"video_offset": offset, "lines": t.log}, indent=1))
        print("recorded", round(close_at, 1), "s; offset", offset)


asyncio.run(main())

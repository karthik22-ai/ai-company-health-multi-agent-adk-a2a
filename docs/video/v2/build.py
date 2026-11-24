"""Assemble the cinematic tour (v2): screen + voice at the logged times + music ducked under the voice + captions.
Long silent waits (live model work) are fast-forwarded so each lasts about 7 seconds.

Usage:  python build.py        Output: ai-company-health-cinematic.mp4, captions.srt
"""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
MUSIC = HERE.parent / "samples" / "music-sample.wav"
NO_CAPTION = {"cold1", "cold2", "final"}          # the title cards already show these words
lines = json.loads((HERE / "narration.json").read_text())["lines"]
tl = json.loads((HERE / "timeline.json").read_text())
off = tl.get("video_offset", 0.0)
log = [dict(e, start=e["start"] - off) for e in tl["lines"]]
start = max(0.0, log[0]["start"] - 3.0)
end = log[-1]["start"] + log[-1]["dur"] + 4.0

fast = []                                          # (from, to, factor) in raw-video time
for a, b in zip(log, log[1:]):
    f0, f1 = a["start"] + a["dur"] + 4.0, b["start"] - 7.0
    if f1 - f0 > 8.0:
        fast.append((f0, f1, max(4.0, (f1 - f0) / 7.0)))


def m(t: float) -> float:
    out = t - start
    for a, b, f in fast:
        if t > a:
            out -= (min(t, b) - a) * (1 - 1 / f)
    return out


def chunks(text: str, max_words: int = 10) -> list[str]:
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        words, cur = sent.split(), []
        for i, w in enumerate(words):
            cur.append(w)
            left = len(words) - i - 1
            if (len(cur) >= max_words and left > 2) or (len(cur) >= 4 and w[-1] in ",:;" and left > 3):
                out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
    return out


def ts(t: float, srt: bool = False) -> str:
    h, mi, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{mi:02d}:{int(s):02d},{int((s % 1) * 1000):03d}" if srt else f"{h}:{mi:02d}:{s:05.2f}"


events = []
for e in log:
    if e["key"] in NO_CAPTION:
        continue
    parts = chunks(lines[e["key"]])
    total_chars = sum(len(p) for p in parts) or 1
    t = m(e["start"])
    for p in parts:
        d = e["dur"] * len(p) / total_chars
        events.append((t, t + d - .05, p, "Cap"))
        t += d
for a, b, f in fast:
    events.append((m(a) + .3, m(b) - .2, f">> Fast-forward ({f:.0f}x): the agents are working live", "Ff"))
fin = next((e for e in log if e["key"] == "final"), None)
if fin:   # closing-card footer, drawn over the card (keeps the tech line exact)
    events.append((m(fin["start"]) - .9, m(end) - .05, "GOOGLE ADK  ·  VERTEX AI  ·  A2A  ·  LANGGRAPH  ·  GOOGLE CLOUD", "Foot"))
events.sort()

ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1600", "PlayResY: 900", "WrapStyle: 0", "", "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
       "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Cap,Helvetica Neue,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H9A0A0F1C,0,0,0,0,100,100,0.5,0,3,13,0,2,180,180,44,1",
       "Style: Foot,Helvetica Neue,17,&H00AB9186,&H00AB9186,&H000B0805,&H000B0805,0,0,0,0,100,100,4.6,0,3,16,0,2,180,180,64,1",
       "Style: Ff,Helvetica Neue,24,&H0042B9F5,&H0042B9F5,&H00000000,&H9A0A0F1C,1,0,0,0,100,100,1,0,3,10,0,8,180,180,90,1", "",
       "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
ass += [f"Dialogue: 0,{ts(a)},{ts(b)},{st},,0,0,0,,{'{\\fad(250,250)}'}{txt}" for a, b, txt, st in events]
(HERE / "captions.ass").write_text("\n".join(ass) + "\n")
(HERE / "captions.srt").write_text("\n".join(f"{i}\n{ts(a, True)} --> {ts(b, True)}\n{txt}\n"
                                             for i, (a, b, txt, st) in enumerate([e for e in events if e[3] == "Cap"], 1)))

total = m(end)
inputs, filt = ["-i", "raw.webm"], []
for i, e in enumerate(log, 1):
    inputs += ["-i", f"audio/{e['key']}.wav"]
    ms = int(max(0.0, m(e["start"])) * 1000)
    filt.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
n = len(log)
filt.append("".join(f"[a{i}]" for i in range(1, n + 1)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.2f},asplit=2[voice][key]")
mi = n + 1
inputs += ["-stream_loop", "-1", "-i", str(MUSIC)]
filt.append(f"[{mi}:a]aresample=48000,atrim=0:{total:.2f},volume=0.5,afade=t=in:d=3,afade=t=out:st={total - 5:.2f}:d=5[mus]")
filt.append("[mus][key]sidechaincompress=threshold=0.015:ratio=9:attack=30:release=700:makeup=1[duck]")
filt.append("[voice][duck]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aud]")
cuts, t = [], start
for a, b, f in fast:
    cuts += [(t, a, 1.0), (a, b, f)]
    t = b
cuts.append((t, end, 1.0))
filt.append(f"[0:v]split={len(cuts)}" + "".join(f"[s{i}]" for i in range(len(cuts))))
for i, (a, b, f) in enumerate(cuts):
    filt.append(f"[s{i}]trim=start={a:.2f}:end={b:.2f},setpts=(PTS-STARTPTS)/{f:.3f}[p{i}]")
filt.append("".join(f"[p{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0,fps=30,ass=captions.ass,"
            f"fade=t=in:d=1.2,fade=t=out:st={total - 1.5:.2f}:d=1.5,format=yuv420p[vid]")
cmd = [FF, "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[vid]", "-map", "[aud]", "-t", f"{total:.2f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "ai-company-health-cinematic.mp4"]
subprocess.run(cmd, cwd=HERE, check=True)
print("built", HERE / "ai-company-health-cinematic.mp4", f"{total:.1f}s", "fast:", [(round(a), round(b), round(f, 1)) for a, b, f in fast])

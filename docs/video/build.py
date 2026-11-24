"""Assemble the final video: screen recording + voice-over at the logged times + burned-in captions.

Usage:  python build.py          (after tts.py and record.py)
Output: ai-company-health-tour.mp4 and captions.srt (in this folder)
"""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
lines = json.loads((HERE / "narration.json").read_text())["lines"]
tl = json.loads((HERE / "timeline.json").read_text())
off = tl.get("video_offset", 0.0)                             # convert script time to video time
log = [dict(e, start=e["start"] - off) for e in tl["lines"]]
start = max(0.0, log[0]["start"] - 1.2)                       # cut the page loading
end = log[-1]["start"] + log[-1]["dur"] + 2.0
FAST = 8.0                                                    # long silent waits (e.g. a live Gemini answer) play at 8x
fast = []
for a, b in zip(log, log[1:]):
    gap_from, gap_to = a["start"] + a["dur"] + 4.0, b["start"] - 6.0
    if gap_to - gap_from > 6.0:
        fast.append((gap_from, gap_to))


def m(t: float) -> float:
    """Raw recording time -> time in the edited video."""
    out = t - start
    for a, b in fast:
        if t > a:
            out -= (min(t, b) - a) * (1 - 1 / FAST)
    return out


def chunks(text: str, max_words: int = 11) -> list[str]:
    """Caption-sized pieces, split at sentence and clause boundaries."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        words, cur = sent.split(), []
        for i, w in enumerate(words):
            cur.append(w)
            left = len(words) - i - 1
            if (len(cur) >= max_words and left > 2) or (len(cur) >= 5 and w[-1] in ",:;" and left > 3):
                out.append(" ".join(cur))
                cur = []
        if cur:
            out.append(" ".join(cur))
    return out


def ts(t: float, sep: str = ".") -> str:
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}" if sep == "." else f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


events = []
for e in log:
    parts = chunks(lines[e["key"]])
    total = sum(len(p) for p in parts) or 1
    t = m(e["start"])
    for p in parts:
        d = e["dur"] * len(p) / total
        events.append((t, t + d - .05, p))
        t += d

ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1600", "PlayResY: 900", "WrapStyle: 0", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
       "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Cap,Helvetica Neue,38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99101522,0,0,0,0,100,100,0,0,3,14,0,2,160,160,46,1", "",
       "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for a, b in fast:
    events.append((m(a) + .2, m(b) - .1, ">> Fast-forward (8x): Leo is answering live with Gemini"))
events.sort()
ass += [f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}" for a, b, txt in events]
(HERE / "captions.ass").write_text("\n".join(ass) + "\n")
(HERE / "captions.srt").write_text("\n".join(f"{i}\n{ts(a, ',')} --> {ts(b, ',')}\n{txt}\n" for i, (a, b, txt) in enumerate(events, 1)))

inputs, filt = ["-i", "raw.webm"], []
for i, e in enumerate(log, 1):
    inputs += ["-i", f"audio/{e['key']}.wav"]
    ms = int(max(0.0, m(e["start"])) * 1000)
    filt.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms},volume=1.0[a{i}]")
mix = "".join(f"[a{i}]" for i in range(1, len(log) + 1))
filt.append(f"{mix}amix=inputs={len(log)}:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[aud]")
cuts, t = [], start
for a, b in fast:
    cuts += [(t, a, 1.0), (a, b, FAST)]
    t = b
cuts.append((t, end, 1.0))
filt.append(f"[0:v]split={len(cuts)}" + "".join(f"[s{i}]" for i in range(len(cuts))))
for i, (a, b, f) in enumerate(cuts):
    filt.append(f"[s{i}]trim=start={a:.2f}:end={b:.2f},setpts=(PTS-STARTPTS)/{f}[p{i}]")
filt.append("".join(f"[p{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0,fps=30,ass=captions.ass,format=yuv420p[vid]")
total = m(end)
cmd = [FF, "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[vid]", "-map", "[aud]", "-t", f"{total:.2f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "ai-company-health-tour.mp4"]
subprocess.run(cmd, cwd=HERE, check=True)
print("built", HERE / "ai-company-health-tour.mp4", f"{total:.1f}s", "fast-forwarded:", [(round(a, 1), round(b, 1)) for a, b in fast])

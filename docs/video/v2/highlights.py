"""1-minute highlights cut from the cinematic tour (whole narration lines, crossfaded). Usage: python highlights.py"""
import subprocess
from pathlib import Path
import imageio_ffmpeg
HERE = Path(__file__).parent
SRC = "ai-company-health-cinematic.mp4"
X = 0.6                                    # crossfade seconds
import json
tl = json.loads((HERE / "timeline.json").read_text())
off = tl["video_offset"]
log = [dict(e, start=e["start"] - off) for e in tl["lines"]]
start = max(0.0, log[0]["start"] - 3.0)
fast = []
for a, b in zip(log, log[1:]):
    f0, f1 = a["start"] + a["dur"] + 4.0, b["start"] - 7.0
    if f1 - f0 > 8.0:
        fast.append((f0, f1, max(4.0, (f1 - f0) / 7.0)))


def m(t: float) -> float:                  # same mapping as build.py: raw recording time -> cinematic video time
    out = t - start
    for a, b, f in fast:
        if t > a:
            out -= (min(t, b) - a) * (1 - 1 / f)
    return out


L = {e["key"]: (m(e["start"]), m(e["start"]) + e["dur"]) for e in log}
END = m(log[-1]["start"] + log[-1]["dur"] + 4.0)
SEG = [(1.8, L["cold2"][1] + .5),                      # cold open: what if a company could run itself?
       (L["town"][0] - 1.5, L["town"][0] + 8.7),       # Wattle Grove: a hundred AI residents (first two sentences)
       (L["chat_reply"][0] - 1.0, L["chat_reply"][1] + .5),   # Leo's live answer
       (L["meet_walk"][0] - .5, L["meet_walk"][1] + .4),      # the team walks to the boardroom
       (L["ops"][0] - .5, L["ops"][1] + .4),                  # the engine room: calls, cost, tokens per agent
       (L["final"][0] - .7, END)]                             # closing card
inputs, f = [], []
for a, b in SEG:
    inputs += ["-ss", f"{a}", "-t", f"{b - a}", "-i", SRC]
v, au, t = "[0:v]", "[0:a]", SEG[0][1] - SEG[0][0]
for i in range(1, len(SEG)):
    f.append(f"{v}[{i}:v]xfade=transition=fade:duration={X}:offset={t - X:.2f}[v{i}]")
    f.append(f"{au}[{i}:a]acrossfade=d={X}[a{i}]")
    v, au = f"[v{i}]", f"[a{i}]"
    t += (SEG[i][1] - SEG[i][0]) - X
f.append(f"{v}fade=t=in:d=0.6,fade=t=out:st={t - 1.2:.2f}:d=1.2,format=yuv420p[vo]")
f.append(f"{au}afade=t=in:d=0.4,afade=t=out:st={t - 1.5:.2f}:d=1.5[ao]")
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(f), "-map", "[vo]", "-map", "[ao]",
                "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                "ai-company-health-highlights.mp4"], cwd=HERE, check=True)
print("built ai-company-health-highlights.mp4", round(t, 1), "s")

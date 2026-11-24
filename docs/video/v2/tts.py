"""Voice-over with Gemini TTS (Google Cloud Text-to-Speech, style prompt). Usage: python tts.py <project> [keys...]"""
import base64, json, subprocess, sys, urllib.request, wave
from pathlib import Path
here = Path(__file__).parent
cfg = json.loads((here / "narration.json").read_text())
project, only = sys.argv[1], set(sys.argv[2:])
token = subprocess.check_output([str(Path.home() / "google-cloud-sdk/bin/gcloud"), "auth", "print-access-token"], text=True).strip()
out = here / "audio"; out.mkdir(exist_ok=True)
for key, text in cfg["lines"].items():
    if only and key not in only:
        continue
    body = {"input": {"text": text, "prompt": cfg["style"]},
            "voice": {"languageCode": cfg["language"], "name": cfg["voice"], "modelName": cfg["model"]},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize", data=json.dumps(body).encode(),
                                         headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project, "Content-Type": "application/json"})
            audio = base64.b64decode(json.loads(urllib.request.urlopen(req, timeout=180).read())["audioContent"])
            break
        except Exception as e:  # noqa: BLE001
            print("retry", key, e)
    (out / f"{key}.wav").write_bytes(audio)
    with wave.open(str(out / f"{key}.wav")) as w:
        print(f"{key:12s} {w.getnframes() / w.getframerate():5.1f}s")

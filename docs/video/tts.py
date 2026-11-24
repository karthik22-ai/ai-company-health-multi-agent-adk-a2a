"""Generate the voice-over clips with Google Cloud Text-to-Speech (Chirp 3 HD). Usage: python tts.py <project>"""
import base64, json, subprocess, sys, urllib.request, wave
from pathlib import Path
here = Path(__file__).parent
cfg = json.loads((here / "narration.json").read_text())
project = sys.argv[1]
token = subprocess.check_output([str(Path.home() / "google-cloud-sdk/bin/gcloud"), "auth", "print-access-token"], text=True).strip()
out = here / "audio"; out.mkdir(exist_ok=True)
for key, text in cfg["lines"].items():
    body = {"input": {"text": text}, "voice": {"languageCode": "en-AU", "name": cfg["voice"]},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000, "speakingRate": 1.0}}
    req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project, "Content-Type": "application/json"})
    audio = base64.b64decode(json.loads(urllib.request.urlopen(req, timeout=120).read())["audioContent"])
    (out / f"{key}.wav").write_bytes(audio)
    with wave.open(str(out / f"{key}.wav")) as w:
        print(f"{key:12s} {w.getnframes() / w.getframerate():5.1f}s")

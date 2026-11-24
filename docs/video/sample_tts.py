import base64, json, os, subprocess, sys, urllib.request
from pathlib import Path
token = subprocess.check_output([str(Path.home() / "google-cloud-sdk/bin/gcloud"), "auth", "print-access-token"], text=True).strip()
P = os.environ.get("GOOGLE_CLOUD_PROJECT") or sys.exit("set GOOGLE_CLOUD_PROJECT")
TEXT = ("Fifty employees. Twelve departments. One building. And not a single human on the payroll. "
        "This is AI Company Health, an insurer run entirely by AI agents.")
STYLE = ("Narrate like a warm, confident documentary narrator. Natural, human pacing with small pauses, "
         "a hint of wonder on the striking lines, never robotic.")
def synth(name, voice, model=None, lang="en-US", prompt=None):
    body = {"input": {"text": TEXT, **({"prompt": prompt} if prompt else {})},
            "voice": {"languageCode": lang, "name": voice, **({"modelName": model} if model else {})},
            "audioConfig": {"audioEncoding": "MP3"}}
    req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize", data=json.dumps(body).encode(),
          headers={"Authorization": f"Bearer {token}", "x-goog-user-project": P, "Content-Type": "application/json"})
    try:
        a = base64.b64decode(json.loads(urllib.request.urlopen(req, timeout=120).read())["audioContent"])
        Path(f"samples/{name}.mp3").write_bytes(a); print("ok", name)
    except urllib.error.HTTPError as e:
        print("ERR", name, e.code, e.read()[:300])
for v in ["Charon", "Sulafat", "Algieba"]:
    synth(f"gemini-{v}", v, "gemini-2.5-pro-tts", "en-US", STYLE)
synth("gemini-Aoede-AU", "Aoede", "gemini-2.5-pro-tts", "en-AU", STYLE)

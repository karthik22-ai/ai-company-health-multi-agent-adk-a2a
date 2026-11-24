"""python -m hq.doctor  → checks your Vertex AI setup with ONE tiny Gemini call (a few tokens) before you start the backend."""
from __future__ import annotations

import sys

import google.auth

from hq.core.config import get_settings


def main() -> int:
    s = get_settings()
    print(f"LLM mode : {s.llm_label}")
    if s.use_mock:
        print("Mock mode – nothing to check. Set HQ_USE_VERTEX=true and GOOGLE_CLOUD_PROJECT in backend/.env to use Vertex AI.")
        return 0
    try:
        creds, adc_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    except Exception as e:  # noqa: BLE001
        print(f"✖ No Application Default Credentials: {e}\n  Run:  gcloud auth application-default login")
        return 1
    print(f"Credentials: {type(creds).__name__} (ADC default project: {adc_project})")
    from google import genai

    client = genai.Client()                       # picks up the GOOGLE_* env set by get_settings()
    for label, model in (("fast", s.model_fast), ("pro", s.model_pro)):
        try:
            r = client.models.generate_content(model=model, contents="Reply with the single word OK.")
            print(f"✔ {label:4} {model}: {(r.text or '').strip()[:40]!r}")
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0][:220]
            print(f"✖ {label:4} {model}: {msg}")
            if "NOT_FOUND" in str(e) or "404" in str(e):
                print("   → the model is not available in this location; try HQ_GCP_LOCATION=global or us-central1, or change HQ_MODEL_*")
            if "PERMISSION_DENIED" in str(e) or "403" in str(e):
                print("   → enable the Vertex AI API on the project and grant your account 'Vertex AI User'")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

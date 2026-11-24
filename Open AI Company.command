#!/bin/bash
# Double-click to open the AI Company. The backend runs all the time on the Google Cloud VM;
# this only opens a private SSH tunnel to it (if one isn't open yet) and then opens the app in your browser.
PROJECT="${GOOGLE_CLOUD_PROJECT:-$(grep -E '^GOOGLE_CLOUD_PROJECT=' "$(cd "$(dirname "$0")" && pwd)/backend/.env" | cut -d= -f2)}"   # read from backend/.env (not committed)
ZONE=australia-southeast1-b
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

if ! curl -s -m 3 http://localhost:8787/health >/dev/null; then
  echo "Starting the VM (if it was stopped) and opening the tunnel…"
  gcloud compute instances start ai-company-hq --zone "$ZONE" --project "$PROJECT" -q >/dev/null 2>&1
  ( while true; do
      gcloud compute ssh ai-company-hq --project "$PROJECT" --zone "$ZONE" --tunnel-through-iap -q -- -N \
        -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -o ExitOnForwardFailure=yes -L 8787:127.0.0.1:8787
      sleep 3
    done ) &
  for i in $(seq 1 60); do curl -s -m 2 http://localhost:8787/health >/dev/null && break; sleep 2; done
fi

if curl -s -m 3 http://localhost:8787/health >/dev/null; then
  open "http://localhost:8787/"
  echo "AI Company is open at http://localhost:8787/ – keep this window open while you use it."
  wait
else
  echo "Could not reach the backend. Check that you are logged in:  ~/google-cloud-sdk/bin/gcloud auth login"
  read -r -p "Press Enter to close…"
fi

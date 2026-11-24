#!/bin/bash
# Double-click to watch the AI Company drawn in the cloud: an NVIDIA L4 GPU VM renders the 3D office in Chrome and streams it
# to your browser as hardware H.264 video over WebRTC (Selkies). Your laptop only plays the video.
# Closing this window (or Ctrl+C) STOPS the GPU VM so it stops costing money.
PROJECT="${GOOGLE_CLOUD_PROJECT:-$(grep -E '^GOOGLE_CLOUD_PROJECT=' "$(cd "$(dirname "$0")" && pwd)/backend/.env" | cut -d= -f2)}"   # read from backend/.env (not committed)
ZONE=asia-southeast1-c
VM=ai-company-view
PWF="$(cd "$(dirname "$0")" && pwd)/backend/deploy/viewer/.view-password"
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

stop_vm(){ echo; echo "Stopping the GPU VM (no more GPU cost)…"; gcloud compute instances stop "$VM" --zone "$ZONE" --project "$PROJECT" -q --async >/dev/null 2>&1; echo "Stopped."; }
trap stop_vm EXIT

echo "Allowing only your current internet address through the firewall…"
MYIP=$(curl -s -m 8 https://checkip.amazonaws.com | tr -d '[:space:]')
[ -n "$MYIP" ] && gcloud compute firewall-rules update hq-view-allow --project "$PROJECT" --source-ranges "$MYIP/32" -q >/dev/null 2>&1

echo "Starting the GPU VM (about 1 minute)…"
gcloud compute instances start "$VM" --zone "$ZONE" --project "$PROJECT" -q >/dev/null 2>&1
IP=$(gcloud compute instances describe "$VM" --zone "$ZONE" --project "$PROJECT" --format "value(networkInterfaces[0].accessConfigs[0].natIP)")
for i in $(seq 1 90); do [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://$IP:8080/")" = 401 ] && break; sleep 2; done

if [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://$IP:8080/")" = 401 ]; then
  sleep 4   # let the office finish loading in the cloud Chrome
  open "http://hq:$(cat "$PWF")@$IP:8080/"
  echo "Cloud view is open in your browser (user: hq, password saved in backend/deploy/viewer/.view-password)."
  echo "Tip: use the browser's full-screen (Ctrl+Cmd+F) for the best picture."
  echo "Keep this window open while you watch. Close it (or press Ctrl+C) to stop the GPU VM."
  while true; do sleep 3600; done
else
  echo "Could not reach the cloud view. Check that you are logged in:  ~/google-cloud-sdk/bin/gcloud auth login"
  read -r -p "Press Enter to close (the GPU VM will be stopped)…"
fi

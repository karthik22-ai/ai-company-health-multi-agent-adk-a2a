#!/usr/bin/env bash
# Forward the VM's backend to http://localhost:8787 over SSH (nothing is exposed to the internet).
PROJECT="${1:?usage: ./tunnel.sh <project-id> [zone]}"; ZONE="${2:-australia-southeast1-b}"
if curl -s -m 3 http://localhost:8787/health >/dev/null; then
  echo "The tunnel is already open – just open http://localhost:8787/ in your browser."; exit 0
fi
echo "Opening the tunnel – keep this window open, then use http://localhost:8787/  (it reconnects by itself if it drops)"
while true; do
  gcloud compute ssh ai-company-hq --project "$PROJECT" --zone "$ZONE" --tunnel-through-iap -q -- -N \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -o ExitOnForwardFailure=yes -L 8787:127.0.0.1:8787
  echo "Tunnel dropped – reconnecting in 3 s (Ctrl+C to stop)"; sleep 3
done

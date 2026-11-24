#!/usr/bin/env bash
# Create the GPU "viewer" VM: it draws the AI Company 3D UI in Chrome on an NVIDIA T4 and streams it to your browser (noVNC),
# so your laptop only shows a video. No public IP: reach it with ../../Open AI Company (cloud view).command
#   ./viewer.sh <project-id>
set -euo pipefail
PROJECT="${1:?usage: ./viewer.sh <project-id>}"
VZONE="${VZONE:-asia-southeast1-c}"; GPU="${GPU:-nvidia-l4}"; VM="ai-company-view"; BZONE="australia-southeast1-b"; BVM="ai-company-hq"
DIR="$(cd "$(dirname "$0")" && pwd)"; SSH=(--tunnel-through-iap -q)
gcloud config set project "$PROJECT" >/dev/null
echo "== backend VM: expose the backend on the private network (port 8788, no public IP)"
gcloud compute ssh "$BVM" --zone "$BZONE" "${SSH[@]}" --command "bash -s" <<'R'
set -e
command -v socat >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq socat >/dev/null; }
sudo tee /etc/systemd/system/hq-internal.service >/dev/null <<'U'
[Unit]
Description=Expose the AI Company backend on the private VPC (port 8788)
After=hq.service
[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:8788,fork,reuseaddr TCP:127.0.0.1:8787
Restart=always
[Install]
WantedBy=multi-user.target
U
sudo systemctl daemon-reload && sudo systemctl enable --now hq-internal >/dev/null 2>&1 && systemctl is-active hq-internal
R
BIP="$(gcloud compute instances describe "$BVM" --zone "$BZONE" --format='value(networkInterfaces[0].networkIP)')"
URL="http://$BIP:8788"
if [ "$GPU" = nvidia-l4 ]; then MT=(--machine-type g2-standard-4); else MT=(--machine-type n1-standard-4 --accelerator "type=$GPU,count=1"); fi
echo "== GPU VM $VM (n1-standard-4 + $GPU, $VZONE)"
gcloud compute instances describe "$VM" --zone "$VZONE" >/dev/null 2>&1 || gcloud compute instances create "$VM" --zone "$VZONE" \
  ${MT[@]} --maintenance-policy TERMINATE \
  --image-family ubuntu-2204-lts --image-project ubuntu-os-cloud --boot-disk-size 50GB --no-address --no-service-account --no-scopes
echo "== waiting for SSH"; for i in $(seq 1 30); do gcloud compute ssh "$VM" --zone "$VZONE" "${SSH[@]}" --command true 2>/dev/null && break; sleep 6; done
gcloud compute scp "$DIR/viewer/setup-viewer.sh" "$VM:~/setup-viewer.sh" --zone "$VZONE" "${SSH[@]}"
echo "== phase 1: NVIDIA driver"
gcloud compute ssh "$VM" --zone "$VZONE" "${SSH[@]}" --command "bash ~/setup-viewer.sh 1"
gcloud compute instances reset "$VM" --zone "$VZONE" -q
echo "== waiting for reboot"; sleep 20; for i in $(seq 1 30); do gcloud compute ssh "$VM" --zone "$VZONE" "${SSH[@]}" --command true 2>/dev/null && break; sleep 6; done
echo "== phase 2: Xorg on the GPU, Chrome kiosk, VNC/noVNC"
gcloud compute ssh "$VM" --zone "$VZONE" "${SSH[@]}" --command "bash ~/setup-viewer.sh 2 $URL"
echo "== done. Open it with: \"Open AI Company (cloud view).command\""

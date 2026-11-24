#!/usr/bin/env bash
# Deploy the AI Company backend to a Compute Engine VM in YOUR Google Cloud project; Gemini runs through Vertex AI
# using the VM's own service account (no keys, no API key). The backend listens on 127.0.0.1 only: reach it with ./tunnel.sh.
#
#   gcloud auth login            # once, with the new Google account
#   ./deploy.sh <project-id> [zone] [machine-type]
set -euo pipefail
PROJECT="${1:?usage: ./deploy.sh <project-id> [zone] [machine-type]}"
ZONE="${2:-australia-southeast1-b}"
TYPE="${3:-e2-standard-2}"
VM="ai-company-hq"; SA="hq-backend"; SAMAIL="$SA@$PROJECT.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

gcloud config set project "$PROJECT" >/dev/null
echo "== enabling APIs (Vertex AI, Compute)"; gcloud services enable aiplatform.googleapis.com compute.googleapis.com iam.googleapis.com iap.googleapis.com
echo "== service account with Vertex AI access only"
gcloud iam service-accounts describe "$SAMAIL" >/dev/null 2>&1 || gcloud iam service-accounts create "$SA" --display-name "AI Company HQ backend"
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SAMAIL" --role roles/aiplatform.user --condition=None >/dev/null
REGION="${ZONE%-*}"; SSH=(--tunnel-through-iap)
echo "== private networking: IAP SSH rule + Cloud NAT (the VM has no public IP)"
gcloud compute firewall-rules describe allow-iap-ssh >/dev/null 2>&1 || gcloud compute firewall-rules create allow-iap-ssh --network default --allow tcp:22 --source-ranges 35.235.240.0/20
gcloud compute routers describe hq-router --region "$REGION" >/dev/null 2>&1 || gcloud compute routers create hq-router --network default --region "$REGION"
gcloud compute routers nats describe hq-nat --router hq-router --region "$REGION" >/dev/null 2>&1 || gcloud compute routers nats create hq-nat --router hq-router --region "$REGION" --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
echo "== VM $VM ($TYPE, $ZONE)"
gcloud compute instances describe "$VM" --zone "$ZONE" >/dev/null 2>&1 || gcloud compute instances create "$VM" --zone "$ZONE" --machine-type "$TYPE" \
  --image-family debian-12 --image-project debian-cloud --boot-disk-size 30GB --no-address --service-account "$SAMAIL" --scopes cloud-platform
echo "== packaging code"
TAR="$(mktemp -d)/hq.tgz"
tar -C "$ROOT" --exclude='backend/.venv' --exclude='backend/data' --exclude='__pycache__' --exclude='backend/.env' --exclude='.pytest_cache' \
    -czf "$TAR" frontend docs backend
echo "== waiting for SSH"; for i in $(seq 1 20); do gcloud compute ssh "$VM" --zone "$ZONE" "${SSH[@]}" --command true -q 2>/dev/null && break; sleep 6; done
gcloud compute scp "$TAR" "$VM:~/hq.tgz" --zone "$ZONE" "${SSH[@]}" -q
gcloud compute ssh "$VM" --zone "$ZONE" "${SSH[@]}" -q --command "bash -s" <<REMOTE
set -euo pipefail
sudo apt-get update -qq && sudo apt-get install -y -qq curl ca-certificates >/dev/null
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="\$HOME/.local/bin:\$PATH"
rm -f ~/hq/finance-hq-agents.html; mkdir -p ~/hq && tar -xzf ~/hq.tgz -C ~/hq && cd ~/hq/backend && mkdir -p data
printf 'HQ_USE_VERTEX=true\nGOOGLE_CLOUD_PROJECT=$PROJECT\nGOOGLE_CLOUD_LOCATION=global\nHQ_STEP_DELAY=1.0\nHQ_HOST=127.0.0.1\nHQ_SIM_AUTOSTART=true\nHQ_SIM_SECONDS_PER_DAY=120\n' > .env
uv sync
sudo tee /etc/systemd/system/hq.service >/dev/null <<UNIT
[Unit]
Description=AI Company HQ backend
After=network-online.target
[Service]
User=\$(whoami)
WorkingDirectory=\$HOME/hq/backend
ExecStart=\$HOME/hq/backend/.venv/bin/python -m hq
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable hq && sudo systemctl restart hq && sleep 8 && curl -s localhost:8787/health
REMOTE
echo; echo "== done. Open the UI with:  ./tunnel.sh $PROJECT $ZONE   then  http://localhost:8787"
echo "== stop billing when idle:  gcloud compute instances stop $VM --zone $ZONE"

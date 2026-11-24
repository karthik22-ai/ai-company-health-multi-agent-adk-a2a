#!/usr/bin/env bash
# Runs ON the GPU viewer VM. Phase 1: NVIDIA driver (then reboot). Phase 2: Xorg on the GPU, Chrome kiosk, VNC + noVNC (localhost only).
set -euo pipefail
PHASE="${1:?phase 1 or 2}"; BACKEND_URL="${2:-}"
export DEBIAN_FRONTEND=noninteractive
if [ "$PHASE" = 1 ]; then
  sudo rm -rf /var/lib/apt/lists/* && sudo apt-get update -qq   # some GCE images ship empty cached lists
  sudo apt-get install -y -qq ubuntu-drivers-common >/dev/null
  sudo apt-get install -y -qq "linux-modules-nvidia-535-server-$(uname -r | sed 's/^[0-9.-]*-//')" nvidia-driver-535-server >/dev/null 2>&1 || sudo apt-get install -y -qq nvidia-driver-535 >/dev/null
  exit 0
fi
# ---- phase 2 ----
sudo add-apt-repository -y universe >/dev/null 2>&1 || true
sudo apt-get update -qq
sudo apt-get install -y -qq xserver-xorg-core x11-xserver-utils openbox x11vnc novnc websockify curl \
  fonts-noto-core fonts-noto-color-emoji fonts-dejavu-core >/dev/null
if ! command -v google-chrome >/dev/null; then
  curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt-get install -y -qq /tmp/chrome.deb >/dev/null
fi
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
BUS=$(lspci | awk '/NVIDIA/{print $1; exit}' | awk -F'[:.]' '{printf "PCI:%d:%d:%d", strtonum("0x"$1), strtonum("0x"$2), $3}')
sudo tee /etc/X11/xorg.conf >/dev/null <<X
Section "Device"
  Identifier "nv"
  Driver "nvidia"
  BusID "$BUS"
  Option "AllowEmptyInitialConfiguration" "True"
EndSection
Section "Screen"
  Identifier "s"
  Device "nv"
  DefaultDepth 24
  SubSection "Display"
    Depth 24
    Virtual 1600 900
  EndSubSection
EndSection
Section "ServerLayout"
  Identifier "l"
  Screen "s"
EndSection
X
id viewer >/dev/null 2>&1 || sudo useradd -m -s /bin/bash viewer
echo "$BACKEND_URL" | sudo tee /etc/hq-backend-url >/dev/null
sudo tee /usr/local/bin/hq-session.sh >/dev/null <<'S'
#!/usr/bin/env bash
# Desktop session for the viewer: a tiny window manager and Chrome in kiosk mode on the AI Company UI (restarts if closed).
export DISPLAY=:0
xset s off -dpms 2>/dev/null || true
openbox &
URL="$(cat /etc/hq-backend-url)"
until curl -s -m 3 "$URL/health" >/dev/null; do sleep 3; done
while true; do
  google-chrome --kiosk --no-first-run --no-default-browser-check --disable-session-crashed-bubble --disable-infobars \
    --ignore-gpu-blocklist --use-gl=angle --use-angle=gl --enable-gpu-rasterization --enable-zero-copy --disable-gpu-driver-bug-workarounds --password-store=basic \
    --user-data-dir=/home/viewer/.chrome-hq "$URL/" || true
  sleep 2
done
S
sudo chmod +x /usr/local/bin/hq-session.sh
sudo tee /etc/systemd/system/hq-x.service >/dev/null <<'U'
[Unit]
Description=Xorg on the NVIDIA GPU (headless)
After=systemd-user-sessions.service
[Service]
ExecStart=/usr/lib/xorg/Xorg :0 -config /etc/X11/xorg.conf -nolisten tcp -ac vt7
Restart=always
[Install]
WantedBy=multi-user.target
U
sudo tee /etc/systemd/system/hq-session.service >/dev/null <<'U'
[Unit]
Description=AI Company in Chrome (kiosk)
After=hq-x.service
Requires=hq-x.service
[Service]
User=viewer
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 3
ExecStart=/usr/local/bin/hq-session.sh
Restart=always
[Install]
WantedBy=multi-user.target
U
sudo tee /etc/systemd/system/hq-vnc.service >/dev/null <<'U'
[Unit]
Description=VNC of the GPU display (localhost only)
After=hq-x.service
Requires=hq-x.service
[Service]
ExecStartPre=/bin/sleep 4
ExecStart=/usr/bin/x11vnc -display :0 -forever -shared -localhost -nopw -rfbport 5900 -noxdamage -xkb -quiet -threads
Restart=always
[Install]
WantedBy=multi-user.target
U
sudo tee /etc/systemd/system/hq-novnc.service >/dev/null <<'U'
[Unit]
Description=noVNC web client (localhost only)
After=hq-vnc.service
[Service]
ExecStart=/usr/bin/websockify --web /usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900
Restart=always
[Install]
WantedBy=multi-user.target
U
sudo systemctl daemon-reload
sudo systemctl enable hq-x hq-session hq-vnc hq-novnc >/dev/null 2>&1
sudo systemctl restart hq-x && sleep 3 && sudo systemctl restart hq-session hq-vnc hq-novnc
sleep 6; systemctl is-active hq-x hq-session hq-vnc hq-novnc

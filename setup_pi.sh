#!/usr/bin/env bash
# =============================================================================
# RetailIQ — Raspberry Pi Camera Bridge Setup
# Run once on a fresh Pi to install everything and auto-start on boot.
#
# One-liner install (run this on the Pi over SSH):
#   curl -fsSL https://raw.githubusercontent.com/hugoseligman-lang/retailiq/master/setup_pi.sh | bash
# =============================================================================
set -e

GREEN='\033[0;32m'; AMBER='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${AMBER}[setup]${NC} $*"; }
error() { echo -e "${RED}[setup]${NC} $*"; exit 1; }

echo ""
echo "  ██████╗ ███████╗████████╗ █████╗ ██╗██╗      ██╗ ██████╗ "
echo "  ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║██║      ██║██╔═══██╗"
echo "  ██████╔╝█████╗     ██║   ███████║██║██║      ██║██║   ██║"
echo "  ██╔══██╗██╔══╝     ██║   ██╔══██║██║██║      ██║██║▄▄ ██║"
echo "  ██║  ██║███████╗   ██║   ██║  ██║██║███████╗ ██║╚██████╔╝"
echo "  ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝╚═╝ ╚══▀▀═╝ "
echo "  Camera Bridge — Pi Setup"
echo ""

# ── 1. System update ──────────────────────────────────────────────────────────
info "Updating system packages..."
sudo apt-get update -y -q
sudo apt-get upgrade -y -q

# ── 2. System dependencies ────────────────────────────────────────────────────
info "Installing system dependencies..."
sudo apt-get install -y -q \
    git \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    curl \
    nano

# ── 3. Clone / update repo ────────────────────────────────────────────────────
REPO_DIR="$HOME/retailiq"
if [ -d "$REPO_DIR/.git" ]; then
    info "Updating existing repo at $REPO_DIR..."
    git -C "$REPO_DIR" pull --ff-only
else
    info "Cloning RetailIQ repo..."
    git clone https://github.com/hugoseligman-lang/retailiq.git "$REPO_DIR"
fi

cd "$REPO_DIR"

# ── 4. Python virtual environment ─────────────────────────────────────────────
# --system-site-packages lets the venv use the system-installed OpenCV
info "Creating Python virtual environment..."
python3 -m venv venv --system-site-packages
source venv/bin/activate

info "Installing Python packages..."
pip install -q --upgrade pip
pip install -q requests python-dotenv

# ── 5. cameras.json ───────────────────────────────────────────────────────────
if [ ! -f "$REPO_DIR/cameras.json" ]; then
    info "Creating cameras.json template (edit before starting)..."
    cat > "$REPO_DIR/cameras.json" << 'EOF'
{
  "vps_url": "https://cafe.meridianai.build",
  "bridge_secret": "REPLACE_WITH_BRIDGE_SECRET",
  "fps": 5,
  "cameras": {
    "front": {
      "name":    "Front Door",
      "mode":    "rtsp",
      "source":  "rtsp://REPLACE_FRONT_DOOR_IP:554/streaming/channels/0",
      "enabled": true
    },
    "back": {
      "name":    "Back Door",
      "mode":    "rtsp",
      "source":  "rtsp://REPLACE_BACK_DOOR_IP:554/streaming/channels/0",
      "enabled": true
    },
    "pos": {
      "name":    "POS Counter",
      "mode":    "rtsp",
      "source":  "rtsp://REPLACE_POS_IP:554/streaming/channels/0",
      "enabled": true
    }
  }
}
EOF
    warn "cameras.json created — you MUST fill in camera IPs and bridge_secret before starting."
else
    info "cameras.json already exists — skipping."
fi

# ── 6. Systemd service ────────────────────────────────────────────────────────
info "Installing systemd service (auto-start on boot)..."
WHOAMI=$(whoami)
sudo bash -c "cat > /etc/systemd/system/retailiq-bridge.service << EOF
[Unit]
Description=RetailIQ Camera Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${WHOAMI}
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/venv/bin/python ${REPO_DIR}/camera_bridge_multi.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable retailiq-bridge
info "Service installed and enabled on boot."

# ── 7. Update helper ──────────────────────────────────────────────────────────
cat > "$REPO_DIR/update_bridge.sh" << 'EOF'
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "[update] Pulling latest code..."
git pull
source venv/bin/activate
pip install -q requests python-dotenv
echo "[update] Restarting service..."
sudo systemctl restart retailiq-bridge
sudo systemctl status retailiq-bridge --no-pager
echo "[update] Done."
EOF
chmod +x "$REPO_DIR/update_bridge.sh"

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Setup complete!                            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Get the bridge secret from the VPS:"
echo "     ssh root@72.61.209.89 \"grep BRIDGE_SECRET /opt/retailiq/backend/.env\""
echo ""
echo "  2. Enable RTSP on each Eufy camera (Eufy app → camera → settings → Advanced → RTSP)"
echo "     Note the IP address shown for each camera"
echo ""
echo "  3. Edit cameras.json with the IPs and secret:"
echo "     nano ~/retailiq/cameras.json"
echo ""
echo "  4. Test manually first:"
echo "     cd ~/retailiq && source venv/bin/activate && python camera_bridge_multi.py"
echo ""
echo "  5. If all three cameras show 'Camera opened OK', start the service:"
echo "     sudo systemctl start retailiq-bridge"
echo ""
echo "  6. Watch live logs:"
echo "     sudo journalctl -fu retailiq-bridge"
echo ""
echo "  To update code later:"
echo "     ~/retailiq/update_bridge.sh"
echo ""

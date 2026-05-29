#!/usr/bin/env bash
# deploy_vps.sh — Deploy RetailIQ to a Hostinger Ubuntu VPS.
#
# Designed for: Ubuntu 22.04 LTS, root or sudo user.
# Safe to re-run (idempotent) — updates code and restarts on subsequent runs.
#
# Usage:
#   # First time — interactive (will prompt for config):
#   bash deploy_vps.sh
#
#   # Non-interactive (CI / re-deploy) — supply env vars:
#   GOOGLE_VISION_API_KEY=... ANTHROPIC_API_KEY=... \
#   DASHBOARD_PIN=1234 ADMIN_PASSWORD=mysecret \
#   CAMERA_MODE=rtsp CAMERA_SOURCE="rtsp://..." \
#   DOMAIN=cafe.meridianai.build \
#   bash deploy_vps.sh --yes
#
# What it does:
#   1. Installs system packages (Python, Node 20, nginx)
#   2. Clones / updates the RetailIQ repo from GitHub
#   3. Builds the React frontend (npm install && npm run build)
#   4. Installs Python deps in a virtualenv (headless OpenCV)
#   5. Writes /opt/retailiq/backend/.env
#   6. Configures nginx (separate server block — does NOT touch n8n)
#   7. Installs & starts the retailiq systemd service
#   8. Optionally sets up HTTPS via Let's Encrypt (certbot)

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLU}[INFO]${NC}  $*"; }
ok()    { echo -e "${GRN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YLW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }

# ── Constants ─────────────────────────────────────────────────────────────────
REPO="https://github.com/hugoseligman-lang/retailiq.git"
INSTALL_DIR="/opt/retailiq"
SERVICE="retailiq"
FLASK_PORT=5050
YES_FLAG=false
[[ "${1:-}" == "--yes" ]] && YES_FLAG=true

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "Run as root: sudo bash deploy_vps.sh"

echo ""
echo -e "${YLW}╔══════════════════════════════════════════╗${NC}"
echo -e "${YLW}║       RetailIQ VPS Deployment            ║${NC}"
echo -e "${YLW}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Gather config (interactive or from env) ───────────────────────────────────
prompt() {
  local var="$1" label="$2" default="${3:-}"
  if [[ -n "${!var:-}" ]]; then
    info "$label: ${!var}"
    return
  fi
  if $YES_FLAG; then
    [[ -n "$default" ]] && eval "$var='$default'" || die "$var is required (use env var)"
    return
  fi
  read -rp "  $label [$default]: " val
  eval "$var='${val:-$default}'"
}

prompt_secret() {
  local var="$1" label="$2"
  if [[ -n "${!var:-}" ]]; then
    info "$label: ***set***"
    return
  fi
  $YES_FLAG && die "$var is required (use env var)"
  read -rsp "  $label: " val; echo
  eval "$var='$val'"
}

echo "── Configuration ──────────────────────────────────"

prompt DOMAIN          "Domain name"                "cafe.meridianai.build"
prompt CAMERA_MODE     "Camera mode (webcam/rtsp/http/vps)"  "vps"

if [[ "${CAMERA_MODE:-vps}" != "vps" ]]; then
  prompt CAMERA_SOURCE "Camera source (index or URL)"  "0"
else
  CAMERA_SOURCE="${CAMERA_SOURCE:-}"
  info "Camera mode is VPS — camera_bridge.py pushes frames from the store"
fi

prompt DASHBOARD_PIN   "Dashboard PIN (4 digits; leave blank = no PIN)" ""
prompt ADMIN_PASSWORD  "Admin page password"        "$(openssl rand -hex 8)"
prompt BRIDGE_SECRET   "Bridge secret (camera_bridge auth; blank = no auth)" "$(openssl rand -hex 12)"
prompt STORE_NAME      "Store name"                 "My Cafe"
prompt STORE_LAT       "Store latitude"             "-33.8688"
prompt STORE_LON       "Store longitude"            "151.2093"
prompt STORE_STATE     "Store state (AU)"           "NSW"
prompt_secret GOOGLE_VISION_API_KEY "Google Vision API key"
prompt_secret ANTHROPIC_API_KEY     "Anthropic API key"

echo ""
echo "── Values ─────────────────────────────────────────"
echo "  Domain         : ${DOMAIN}"
echo "  Camera mode    : ${CAMERA_MODE}"
[[ "${CAMERA_MODE}" != "vps" ]] && echo "  Camera source  : ${CAMERA_SOURCE}"
echo "  Dashboard PIN  : ${DASHBOARD_PIN:-<none>}"
echo "  Admin password : ${ADMIN_PASSWORD}"
echo "  Bridge secret  : ${BRIDGE_SECRET}"
echo "  Store name     : ${STORE_NAME}"
echo ""

if ! $YES_FLAG; then
  read -rp "Proceed? [Y/n] " yn
  [[ "${yn,,}" == "n" ]] && die "Aborted."
fi

# ── 1. System packages ────────────────────────────────────────────────────────
info "[1/8] Installing system packages…"
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv \
  nginx curl git openssl \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
  2>/dev/null
ok "System packages installed"

# Node.js 20 (LTS) via NodeSource if not present / too old
if ! command -v node &>/dev/null || [[ $(node -e "process.stdout.write(process.version.slice(1).split('.')[0])") -lt 18 ]]; then
  info "Installing Node.js 20 LTS…"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
  apt-get install -y -qq nodejs 2>/dev/null
fi
ok "Node.js $(node --version)"

# ── 2. Clone / update repo ────────────────────────────────────────────────────
info "[2/8] Cloning / updating repo…"
if [[ -d "${INSTALL_DIR}/.git" ]]; then
  git -C "${INSTALL_DIR}" pull --ff-only
  ok "Repo updated"
else
  git clone "${REPO}" "${INSTALL_DIR}"
  ok "Repo cloned"
fi

# ── 3. Build frontend ─────────────────────────────────────────────────────────
info "[3/8] Building React frontend…"
cd "${INSTALL_DIR}/frontend"
npm install --silent
npm run build --silent
ok "Frontend built → ${INSTALL_DIR}/frontend/dist"

# ── 4. Python venv + deps ─────────────────────────────────────────────────────
info "[4/8] Installing Python dependencies…"
cd "${INSTALL_DIR}"
python3 -m venv .venv
# Install headless OpenCV for servers (no display required)
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet \
  flask==3.1.0 flask-cors==5.0.0 \
  anthropic requests python-dotenv holidays cloudscraper \
  numpy opencv-python-headless
ok "Python deps installed"

# ── 5. Write .env ─────────────────────────────────────────────────────────────
info "[5/8] Writing backend/.env…"
ENV_PATH="${INSTALL_DIR}/backend/.env"
cat > "${ENV_PATH}" <<EOF
# RetailIQ VPS configuration — generated by deploy_vps.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)

CAMERA_MODE=${CAMERA_MODE}
CAMERA_SOURCE=${CAMERA_SOURCE}

STORE_NAME=${STORE_NAME}
STORE_LAT=${STORE_LAT}
STORE_LON=${STORE_LON}
STORE_STATE=${STORE_STATE}

FLASK_HOST=127.0.0.1
FLASK_PORT=${FLASK_PORT}

GOOGLE_VISION_API_KEY=${GOOGLE_VISION_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

BRIDGE_SECRET=${BRIDGE_SECRET}
DASHBOARD_PIN=${DASHBOARD_PIN}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
chmod 600 "${ENV_PATH}"
ok ".env written (mode 600)"

# ── 6. nginx config ───────────────────────────────────────────────────────────
info "[6/8] Configuring nginx…"
NGINX_CONF="/etc/nginx/sites-available/retailiq"
cat > "${NGINX_CONF}" <<'NGINX'
# RetailIQ — generated by deploy_vps.sh
# This block is self-contained and does NOT interfere with n8n on port 5678.
server {
    listen 80;
    listen [::]:80;
    server_name DOMAIN_PLACEHOLDER;

    root DIST_PLACEHOLDER;
    index index.html;

    # ── MJPEG live stream — disable buffering for real-time video ──
    location /api/stream {
        proxy_pass         http://127.0.0.1:FLASK_PORT_PLACEHOLDER;
        proxy_buffering    off;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        chunked_transfer_encoding on;
    }

    # ── API proxy ──────────────────────────────────────────────────
    location /api/ {
        proxy_pass         http://127.0.0.1:FLASK_PORT_PLACEHOLDER;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    # ── SPA fallback — /admin and all other routes → index.html ───
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

# Substitute placeholders
sed -i \
  -e "s|DOMAIN_PLACEHOLDER|${DOMAIN}|g" \
  -e "s|DIST_PLACEHOLDER|${INSTALL_DIR}/frontend/dist|g" \
  -e "s|FLASK_PORT_PLACEHOLDER|${FLASK_PORT}|g" \
  "${NGINX_CONF}"

# Enable site (remove default if it's still there)
ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/retailiq
[[ -f /etc/nginx/sites-enabled/default ]] && rm -f /etc/nginx/sites-enabled/default || true

# Test and reload
nginx -t 2>/dev/null && systemctl reload nginx
ok "nginx configured for ${DOMAIN}"

# ── 7. systemd service ────────────────────────────────────────────────────────
info "[7/8] Installing systemd service…"
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=RetailIQ Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}/backend
ExecStart=${INSTALL_DIR}/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE}"
systemctl restart "${SERVICE}"

# Wait a moment and confirm it's up
sleep 3
if systemctl is-active --quiet "${SERVICE}"; then
  ok "retailiq service is running"
else
  warn "Service may not have started — check: journalctl -fu retailiq"
fi

# ── 8. Done ───────────────────────────────────────────────────────────────────
info "[8/8] Deployment complete!"
PUBLIC_IP=$(curl -sf --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')

echo ""
echo -e "${GRN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GRN}║  RetailIQ is live!                                       ║${NC}"
echo -e "${GRN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Dashboard : ${YLW}http://${DOMAIN}${NC}  (or http://${PUBLIC_IP} before DNS)"
echo -e "  Admin     : ${YLW}http://${DOMAIN}/admin${NC}"
echo -e "  Health    : ${YLW}http://${DOMAIN}/api/health${NC}"
echo ""
echo "  Dashboard PIN  : ${DASHBOARD_PIN:-<none>}"
echo "  Admin password : ${ADMIN_PASSWORD}"
echo ""
if [[ "${CAMERA_MODE}" == "vps" ]]; then
  echo "  ── Camera bridge .env (put next to camera_bridge.py at the store) ──"
  echo "  VPS_URL=http://${PUBLIC_IP}:80"
  echo "  BRIDGE_SECRET=${BRIDGE_SECRET}"
  echo ""
fi
echo "  ── Next steps ──────────────────────────────────────────────────"
echo "  1. Point DNS:  cafe.meridianai.build  A  ${PUBLIC_IP}"
echo "  2. HTTPS:      certbot --nginx -d ${DOMAIN}"
echo "  3. View logs:  journalctl -fu ${SERVICE}"
echo "  4. Update:     bash ${INSTALL_DIR}/update_vps.sh"
echo ""

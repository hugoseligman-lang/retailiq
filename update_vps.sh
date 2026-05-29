#!/usr/bin/env bash
# update_vps.sh — Pull latest code and restart RetailIQ on the VPS.
# Run as root: bash /opt/retailiq/update_vps.sh

set -euo pipefail
INSTALL_DIR="/opt/retailiq"

echo "[update] Pulling latest code…"
git -C "${INSTALL_DIR}" pull --ff-only

echo "[update] Rebuilding frontend…"
cd "${INSTALL_DIR}/frontend"
npm install --silent
npm run build --silent

echo "[update] Installing any new Python deps…"
"${INSTALL_DIR}/.venv/bin/pip" install --quiet \
  flask flask-cors anthropic requests python-dotenv holidays cloudscraper \
  numpy opencv-python-headless

echo "[update] Restarting service…"
systemctl restart retailiq
sleep 2
systemctl is-active retailiq && echo "[update] retailiq is running" || echo "[update] WARN: check journalctl -fu retailiq"

echo "[update] Done."

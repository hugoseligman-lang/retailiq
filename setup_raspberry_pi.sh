#!/bin/bash
# setup_raspberry_pi.sh — Install RetailIQ on a Raspberry Pi (or any Linux box)
# Run once: bash setup_raspberry_pi.sh
# After running, RetailIQ starts automatically on boot and restarts on crash.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
SERVICE_NAME="retailiq"
RUN_USER="$(whoami)"

echo "==> Installing RetailIQ backend dependencies..."
# Use headless OpenCV on Pi (no GUI libs needed)
sed 's/opencv-python==/opencv-python-headless==/g' \
    "$BACKEND/requirements.txt" > /tmp/requirements_pi.txt
pip3 install -r /tmp/requirements_pi.txt --break-system-packages 2>/dev/null \
    || pip3 install -r /tmp/requirements_pi.txt

echo "==> Creating systemd service at /etc/systemd/system/${SERVICE_NAME}.service"
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=RetailIQ Retail Analytics Backend
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${BACKEND}
ExecStart=$(which python3) main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo ""
echo "==> RetailIQ installed as a system service."
echo "    Status:   sudo systemctl status retailiq"
echo "    Logs:     sudo journalctl -u retailiq -f"
echo "    Stop:     sudo systemctl stop retailiq"
echo "    Disable:  sudo systemctl disable retailiq"
echo ""
echo "==> Dashboard available at: http://$(hostname -I | awk '{print $1}'):5050"
echo "    Access this URL from any device on the same WiFi network."

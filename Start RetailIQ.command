#!/bin/bash
# macOS launcher — double-click to start RetailIQ with auto-restart watchdog
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

pip3 install -r requirements.txt -q 2>/dev/null

# Open browser after 3 seconds
(sleep 3 && open http://localhost:5050) &

# Watchdog loop — restart backend on crash
echo "RetailIQ starting (watchdog active — do not close this window)..."
while true; do
    echo "[$(date '+%H:%M:%S')] Starting backend..."
    python3 main.py
    echo "[$(date '+%H:%M:%S')] Backend stopped. Restarting in 5 seconds..."
    sleep 5
done

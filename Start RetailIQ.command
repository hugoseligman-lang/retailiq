#!/bin/bash
# macOS launcher — double-click to start RetailIQ
cd "$(dirname "$0")/backend"
pip3 install -r requirements.txt -q 2>/dev/null
python3 main.py &
sleep 3
open http://localhost:5050

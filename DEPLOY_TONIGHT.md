# RetailIQ — Deploy Tonight (Dukes Green Café)

## ARCHITECTURE OVERVIEW (read this first)

```
Café (your MacBook on Dukes Green Cafe WiFi)
  └── camera_bridge_multi.py
       ├── RTSP → Eufy Camera 1 (Front Door, ~192.168.x.x)
       ├── RTSP → Eufy Camera 2 (Back Door, ~192.168.x.x)
       └── RTSP → Eufy Camera 3 (POS Counter, ~192.168.x.x)
            ↓ POST JPEG frames over internet
VPS (72.61.209.89)
  └── RetailIQ backend (Flask + multi_tracker.py)
       └── nginx → cafe.meridianai.build
```

**KEY POINT:** Eufy cameras are on local WiFi (192.168.x.x).
The VPS CANNOT connect to them directly.
Your MacBook bridges the gap — it must stay connected to café WiFi while running.

---

## STEP 1 — DEPLOY TO VPS TONIGHT

### 1a. SSH into the VPS
```bash
ssh root@72.61.209.89
```

### 1b. Run the deployment script
```bash
curl -fsSL https://raw.githubusercontent.com/hugoseligman-lang/retailiq/master/deploy_vps.sh | bash
```

When prompted, enter:
- **Domain**: `cafe.meridianai.build`
- **Camera mode**: `vps`  ← cameras are pushed from your MacBook
- **Dashboard PIN**: `1234`  ← or whatever you want
- **Admin password**: choose something memorable
- **Bridge secret**: copy and save this — you'll need it for cameras.json
- **Google Vision API key**: your key
- **Anthropic API key**: your key
- **Store name**: `Dukes Green Cafe`

### 1c. Verify the backend is running
```bash
curl http://72.61.209.89/api/health
# Expected: {"status": "ok"}
```

### 1d. Check logs if anything looks wrong
```bash
journalctl -fu retailiq
```

---

## STEP 2 — SET UP DNS

In your Hostinger DNS panel:
```
A    cafe    72.61.209.89    TTL: 300
```
Wait 5–10 minutes, then:
```bash
curl http://cafe.meridianai.build/api/health
```

### 2b. (Optional) Add HTTPS
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d cafe.meridianai.build
```

---

## STEP 3 — SET UP YOUR MACBOOK FOR TOMORROW

### 3a. Install bridge dependencies on your MacBook
```bash
# In Terminal on your Mac
pip3 install opencv-python requests python-dotenv
```

### 3b. Get the bridge secret from the VPS
```bash
ssh root@72.61.209.89 "grep BRIDGE_SECRET /opt/retailiq/backend/.env"
```

### 3c. Create cameras.json on your MacBook
In the retailiq folder on your Mac, create `cameras.json`.
You'll fill in the actual camera IPs tomorrow morning (after enabling RTSP on each Eufy camera).

Template (save this for tomorrow):
```json
{
  "vps_url": "http://cafe.meridianai.build",
  "bridge_secret": "PASTE_BRIDGE_SECRET_HERE",
  "fps": 5,
  "cameras": {
    "front": { "name": "Front Door", "mode": "rtsp", "source": "rtsp://REPLACE_WITH_CAMERA1_IP:554/streaming/channels/0", "enabled": true },
    "back":  { "name": "Back Door",  "mode": "rtsp", "source": "rtsp://REPLACE_WITH_CAMERA2_IP:554/streaming/channels/0", "enabled": true },
    "pos":   { "name": "POS Counter","mode": "rtsp", "source": "rtsp://REPLACE_WITH_CAMERA3_IP:554/streaming/channels/0", "enabled": true }
  }
}
```

---

## TOMORROW MORNING — SETUP SEQUENCE

### T+0 min: Arrive at café, connect MacBook to WiFi
```
Network: Dukes Green Cafe
Password: Watson15$
```

### T+5 min: Enable RTSP on each Eufy camera

**For EACH camera (front door, back door, POS counter):**

1. Open the **Eufy Security** app on your phone
2. Tap the camera you want to configure
3. Tap the **gear icon** (Settings) → top right
4. Tap **"Advanced settings"** or **"Video Quality"**
5. Find **"RTSP Stream"** and toggle it **ON**
6. Note the camera's local IP address shown on screen
   (or check your router's connected devices list)

**Eufy RTSP URL format:**
```
rtsp://<camera-ip>:554/streaming/channels/0
```

### T+15 min: Find camera IPs
Option A — Check Eufy app Settings → About Device → IP address  
Option B — Check router admin page (192.168.1.1 or 192.168.0.1) → Connected Devices  
Option C — Run the scanner:
```bash
cd ~/path/to/retailiq
python camera_bridge_multi.py --scan
# This scans the local network for RTSP devices
```

### T+20 min: Fill in cameras.json
```json
{
  "vps_url": "http://cafe.meridianai.build",
  "bridge_secret": "YOUR_SECRET",
  "fps": 5,
  "cameras": {
    "front": { "name": "Front Door",  "mode": "rtsp", "source": "rtsp://192.168.1.101:554/streaming/channels/0", "enabled": true },
    "back":  { "name": "Back Door",   "mode": "rtsp", "source": "rtsp://192.168.1.102:554/streaming/channels/0", "enabled": true },
    "pos":   { "name": "POS Counter", "mode": "rtsp", "source": "rtsp://192.168.1.103:554/streaming/channels/0", "enabled": true }
  }
}
```

### T+25 min: Test VLC first (confirm RTSP works before starting bridge)
```
File → Open Network → rtsp://192.168.1.101:554/streaming/channels/0
```
If VLC shows video — RTSP is working. If not, see "Troubleshooting RTSP" below.

### T+30 min: Start the camera bridge
```bash
cd ~/path/to/retailiq
python camera_bridge_multi.py
```

Expected output:
```
[bridge] Config loaded from cameras.json
[bridge] Checking VPS health … OK
[bridge:front] Starting — rtsp / rtsp://192.168.1.101:554/...
[bridge:back]  Starting — rtsp / rtsp://192.168.1.102:554/...
[bridge:pos]   Starting — rtsp / rtsp://192.168.1.103:554/...
[bridge:front] Camera opened OK
[bridge:back]  Camera opened OK
[bridge:pos]   Camera opened OK
```

### T+35 min: Open dashboard and verify
Open **https://cafe.meridianai.build** on your phone.
- Enter your 4-digit PIN
- Top of Section 1 shows: **Camera Feeds — 3/3 live**
- Each camera shows green dot + "live"

### T+40 min: Set entrance lines
Go to **⚙ Calibrate** in the top-right
- For Front Door camera: drag the entrance line across the doorway
- For Back Door camera: same
- POS camera: no line needed (uses headcount mode)

### T+45 min: Open for business
Tap **"Open for Business"** in the green bar at the top.
The system starts counting. You're live.

---

## FALLBACK — IF RTSP DOESN'T WORK

### Fallback 1: Try different RTSP URL formats
Some Eufy cameras use different paths:
```
rtsp://<ip>:554/streaming/channels/0
rtsp://<ip>:554/streaming/channels/1
rtsp://<ip>:8554/
rtsp://admin:password@<ip>:554/stream1
```

### Fallback 2: HTTP snapshot mode
If RTSP fails, change `mode` to `http` and use the camera's snapshot URL:
```json
"front": { "mode": "http", "source": "http://192.168.1.101/Streaming/channels/1/picture" }
```

### Fallback 3: Phone as camera
If all else fails, install **IP Camera Lite** on a spare phone, place it at the door, and use:
```json
"front": { "mode": "http", "source": "http://192.168.1.200:8080/shot.jpg" }
```
(IP Camera Lite shows its stream URL on the app's main screen.)

---

## UPDATING CAMERA URLS REMOTELY

If you need to change a camera URL without going to the café:

**Option A: Admin panel** (cafe.meridianai.build/admin)
- Admin → Camera Configuration → update URL → Save & Restart

**Option B: SSH**
```bash
ssh root@72.61.209.89
nano /opt/retailiq/backend/.env
# Edit CAMERA_SOURCE if needed
systemctl restart retailiq
```

**Note:** Camera URLs for the bridge script are in `cameras.json` on your MacBook,
not on the VPS. The VPS just receives frames — it doesn't know the camera URLs.

---

## VERIFY EVERYTHING IS WORKING

### VPS side:
```bash
# Check service status
systemctl status retailiq

# Watch live logs
journalctl -fu retailiq

# Check camera feed status
curl http://localhost:5050/api/cameras/status | python3 -m json.tool
```

### Bridge side (your MacBook):
The bridge console shows status every 10 seconds:
```
[bridge] Status at 09:15:42
  [front ] streaming      ok= 2847  err=   0  last_ok=2s ago
  [back  ] streaming      ok= 2843  err=   0  last_ok=2s ago
  [pos   ] streaming      ok= 2851  err=   0  last_ok=2s ago
```

---

## AFTER THE PILOT — LEAVE IT RUNNING ALL DAY

Leave your MacBook:
- Plugged into power
- Screen lock disabled (System Settings → Lock Screen → Never)
- Terminal window with bridge running visible

The VPS runs 24/7 — only the MacBook bridge needs to stay at the café.

If the bridge crashes, restart it:
```bash
python camera_bridge_multi.py
```

---

## EMAIL ALERTS SETUP (optional)

To receive an email if all cameras go offline:

1. Create a Gmail App Password:
   - Google Account → Security → 2-Step Verification → App passwords
   - App: Mail, Device: Mac → Generate
   - Copy the 16-character password

2. SSH into VPS and add to .env:
```bash
ssh root@72.61.209.89
nano /opt/retailiq/backend/.env
# Add these lines:
ALERT_EMAIL_TO=hugo@meridianai.build
ALERT_EMAIL_FROM=your-gmail@gmail.com
ALERT_EMAIL_PASS=your-16-char-app-password
systemctl restart retailiq
```

---

## QUICK REFERENCE

| What                       | Where                                              |
|----------------------------|----------------------------------------------------|
| Dashboard                  | https://cafe.meridianai.build                     |
| Admin panel                | https://cafe.meridianai.build/admin               |
| VPS health check           | https://cafe.meridianai.build/api/health          |
| Camera status API          | https://cafe.meridianai.build/api/cameras/status  |
| Merged counts API          | https://cafe.meridianai.build/api/tracker/merged  |
| VPS logs                   | ssh root@72.61.209.89 → journalctl -fu retailiq  |
| Update VPS code            | ssh root@72.61.209.89 → bash /opt/retailiq/update_vps.sh |
| Bridge config              | cameras.json on your MacBook                       |
| Restart bridge             | python camera_bridge_multi.py (on MacBook)        |

"""
camera_bridge_multi.py — Runs on a device at the store (MacBook, Pi, laptop).
Captures from multiple cameras simultaneously and pushes each feed to the VPS.

!! IMPORTANT — NETWORKING !!
Eufy cameras have LOCAL IP addresses (192.168.x.x).
The VPS cannot reach them directly — this bridge must run on a device
on the SAME WiFi network as the cameras.

Quick start (tomorrow morning):
  1. Connect your MacBook to "Dukes Green Cafe" WiFi
  2. Edit cameras.json with each camera's local IP
  3. python camera_bridge_multi.py
  4. Watch the console — each camera shows "OK" when frames are flowing

Configure via cameras.json (see cameras.json.example) or environment variables.
"""

import base64
import json
import os
import sys
import threading
import time
from pathlib import Path

import cv2
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "cameras.json"
EXAMPLE_FILE = Path(__file__).parent / "cameras.json.example"

DEFAULT_CONFIG = {
    "vps_url":       "http://72.61.209.89",
    "bridge_secret": "",
    "fps":           5,
    "cameras": {
        "front": {
            "name":    "Front Door",
            "mode":    "rtsp",
            "source":  "rtsp://CAMERA_1_IP:554/streaming/channels/0",
            "enabled": True
        },
        "back": {
            "name":    "Back Door",
            "mode":    "rtsp",
            "source":  "rtsp://CAMERA_2_IP:554/streaming/channels/0",
            "enabled": True
        },
        "pos": {
            "name":    "POS / Counter",
            "mode":    "rtsp",
            "source":  "rtsp://CAMERA_3_IP:554/streaming/channels/0",
            "enabled": True
        }
    }
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        print(f"[bridge] Config loaded from {CONFIG_FILE}")
        return cfg

    # Write example and use defaults
    with open(EXAMPLE_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"[bridge] No cameras.json found — created {EXAMPLE_FILE}")
    print("[bridge] Copy it to cameras.json and fill in your camera IPs, then re-run.")

    # Check for environment variable overrides
    cfg = dict(DEFAULT_CONFIG)
    cfg["vps_url"]       = os.getenv("VPS_URL", cfg["vps_url"])
    cfg["bridge_secret"] = os.getenv("BRIDGE_SECRET", cfg["bridge_secret"])
    cfg["fps"]           = float(os.getenv("BRIDGE_FPS", cfg["fps"]))
    for role in ("front", "back", "pos"):
        mode_key = f"CAMERA_{role.upper()}_MODE"
        src_key  = f"CAMERA_{role.upper()}_SOURCE"
        if os.getenv(mode_key):
            cfg["cameras"][role]["mode"]   = os.getenv(mode_key)
        if os.getenv(src_key):
            cfg["cameras"][role]["source"] = os.getenv(src_key)
    return cfg


# ── Per-camera worker ──────────────────────────────────────────────────────────

class CameraWorker:
    RECONNECT_DELAY = 30   # seconds before retry after failure

    def __init__(self, role: str, camera_cfg: dict, vps_url: str,
                 secret: str, fps: float):
        self.role    = role
        self.name    = camera_cfg.get("name", role)
        self.mode    = camera_cfg.get("mode", "rtsp").lower()
        self.source  = camera_cfg.get("source", "")
        self.enabled = camera_cfg.get("enabled", True)

        self.vps_url    = vps_url.rstrip("/")
        self.ingest_url = f"{self.vps_url}/api/ingest-frame/{role}"
        self.headers    = {
            "X-Bridge-Secret": secret,
            "Content-Type":    "image/jpeg",
        }
        self.frame_delay = 1.0 / max(float(fps), 0.1)

        self._stop      = threading.Event()
        self._thread    = None
        self._ok_count  = 0
        self._err_count = 0
        self._last_ok   = 0.0
        self._status    = "idle"

    def start(self):
        if not self.enabled:
            print(f"[bridge:{self.role}] Disabled — skipping")
            return
        self._thread = threading.Thread(target=self._run, name=f"bridge-{self.role}", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def status_line(self) -> str:
        age = time.time() - self._last_ok if self._last_ok else None
        age_str = f"{age:.0f}s ago" if age else "never"
        return (f"  [{self.role:6s}] {self._status:12s}  "
                f"ok={self._ok_count:5d}  err={self._err_count:4d}  last_ok={age_str}")

    def _run(self):
        print(f"[bridge:{self.role}] Starting — {self.mode} / {self.source}")
        while not self._stop.is_set():
            try:
                if self.mode in ("rtsp", "webcam"):
                    self._run_cv2()
                elif self.mode == "http":
                    self._run_http_snapshot()
                elif self.mode == "eufy":
                    self._run_eufy_snapshot()
                else:
                    print(f"[bridge:{self.role}] Unknown mode '{self.mode}' — defaulting to rtsp")
                    self.mode = "rtsp"
            except Exception as e:
                self._status   = "error"
                self._err_count += 1
                print(f"[bridge:{self.role}] Unhandled error: {e}")

            if not self._stop.is_set():
                print(f"[bridge:{self.role}] Reconnecting in {self.RECONNECT_DELAY}s…")
                self._stop.wait(self.RECONNECT_DELAY)

    def _run_cv2(self):
        """Capture via OpenCV (RTSP or webcam)."""
        src = int(self.source) if str(self.source).isdigit() else self.source
        if sys.platform == "win32" and str(self.source).isdigit():
            cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(src)

        if not cap.isOpened():
            self._status = "no_camera"
            print(f"[bridge:{self.role}] Cannot open: {self.source}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
        print(f"[bridge:{self.role}] Camera opened OK")
        self._status = "connected"

        fail = 0
        while not self._stop.is_set():
            t0 = time.time()
            ret, frame = cap.read()

            if not ret:
                fail += 1
                if fail >= 15:
                    print(f"[bridge:{self.role}] Lost feed after {fail} failures")
                    cap.release()
                    return
                time.sleep(0.1)
                continue

            fail = 0
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                self._send(buf.tobytes())

            elapsed = time.time() - t0
            sleep   = self.frame_delay - elapsed
            if sleep > 0:
                time.sleep(sleep)

        cap.release()

    def _run_http_snapshot(self):
        """Periodically fetch a JPEG snapshot from an HTTP URL."""
        self._status = "connecting"
        print(f"[bridge:{self.role}] HTTP snapshot mode — {self.source}")
        while not self._stop.is_set():
            t0 = time.time()
            try:
                r = requests.get(self.source, timeout=6, stream=False)
                r.raise_for_status()
                ctype = r.headers.get("Content-Type", "")
                if "multipart" in ctype:
                    # MJPEG stream — grab one frame
                    jpeg = self._extract_mjpeg_frame(r)
                else:
                    jpeg = r.content
                if jpeg:
                    self._send(jpeg)
                    self._status = "streaming"
            except Exception as e:
                self._status = "error"
                self._err_count += 1
                print(f"[bridge:{self.role}] HTTP error: {e}")
                time.sleep(self.RECONNECT_DELAY)
                return

            elapsed = time.time() - t0
            sleep   = self.frame_delay - elapsed
            if sleep > 0:
                time.sleep(sleep)

    def _extract_mjpeg_frame(self, response) -> bytes | None:
        buf = b""
        for chunk in response.iter_content(65536):
            buf += chunk
            start = buf.find(b"\xff\xd8")
            end   = buf.find(b"\xff\xd9")
            if start != -1 and end != -1 and end > start:
                return buf[start:end + 2]
            if len(buf) > 1_000_000:
                break
        return None

    def _run_eufy_snapshot(self):
        """
        Eufy local HTTP snapshot fallback.
        Many Eufy cameras expose:  http://[ip]/Streaming/channels/1/picture
        Falls back to RTSP if that URL 404s.
        """
        snap_url = f"http://{self.source}/Streaming/channels/1/picture"
        print(f"[bridge:{self.role}] Trying Eufy local snapshot: {snap_url}")
        # Try once to confirm it works, then loop
        try:
            r = requests.get(snap_url, timeout=5)
            if r.status_code == 200:
                self.source  = snap_url
                self.mode    = "http"
                print(f"[bridge:{self.role}] Eufy local snapshot working — switching to http mode")
                self._run_http_snapshot()
                return
        except Exception:
            pass
        # Fall through to RTSP
        print(f"[bridge:{self.role}] Eufy snapshot not available — trying RTSP instead")
        self.source = f"rtsp://{self.source}:554/streaming/channels/0"
        self.mode   = "rtsp"
        self._run_cv2()

    def _send(self, jpeg_bytes: bytes) -> bool:
        try:
            r = requests.post(self.ingest_url, data=jpeg_bytes,
                              headers=self.headers, timeout=5)
            if r.status_code == 200:
                self._ok_count  += 1
                self._last_ok    = time.time()
                self._status     = "streaming"
                return True
            else:
                self._err_count += 1
                print(f"[bridge:{self.role}] VPS returned {r.status_code}")
        except requests.exceptions.ConnectionError:
            self._err_count += 1
            if self._err_count % 30 == 1:
                print(f"[bridge:{self.role}] VPS unreachable (attempt {self._err_count})")
        except Exception as e:
            self._err_count += 1
            print(f"[bridge:{self.role}] Send error: {e}")
        self._status = "send_error"
        return False


# ── Camera discovery helpers ───────────────────────────────────────────────────

def find_eufy_cameras_on_network() -> list[str]:
    """
    Scan the local network for Eufy cameras by checking common ports.
    Returns list of IPs that respond on port 554 (RTSP).
    This is a best-effort scan — not guaranteed to find all cameras.
    """
    import socket
    import ipaddress

    print("[discovery] Scanning local network for RTSP devices on port 554…")
    # Get local subnet
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    # Assume /24 subnet
    network = str(ipaddress.ip_network(local_ip + "/24", strict=False))
    found = []

    def check(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            if s.connect_ex((ip, 554)) == 0:
                found.append(ip)
                print(f"[discovery]   Found RTSP device at {ip}")
            s.close()
        except Exception:
            pass

    threads = []
    for host in ipaddress.ip_network(network).hosts():
        t = threading.Thread(target=check, args=(str(host),), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=0.5)

    print(f"[discovery] Scan complete — found {len(found)} RTSP device(s): {found}")
    return found


# ── Status display ─────────────────────────────────────────────────────────────

def _status_loop(workers: list[CameraWorker]):
    while True:
        time.sleep(10)
        print(f"\n[bridge] Status at {time.strftime('%H:%M:%S')}")
        for w in workers:
            print(w.status_line())
        print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()

    if not CONFIG_FILE.exists():
        print("\n[bridge] Edit cameras.json then run again. Exiting.")
        sys.exit(1)

    vps_url = cfg.get("vps_url", "http://localhost:5050")
    secret  = cfg.get("bridge_secret", os.getenv("BRIDGE_SECRET", ""))
    fps     = float(cfg.get("fps", 5))
    cameras = cfg.get("cameras", {})

    if not cameras:
        print("[bridge] No cameras configured in cameras.json. Exiting.")
        sys.exit(1)

    # Verify VPS is reachable
    print(f"[bridge] Checking VPS health at {vps_url}/api/health …")
    try:
        r = requests.get(f"{vps_url}/api/health", timeout=5)
        if r.status_code == 200:
            print("[bridge] VPS is reachable — OK")
        else:
            print(f"[bridge] VPS returned {r.status_code} — continuing anyway")
    except Exception as e:
        print(f"[bridge] WARNING: Cannot reach VPS ({e}). Check VPS_URL and network.")
        print("[bridge] Will retry sending frames anyway — VPS may come online shortly.")

    # Start workers
    workers = []
    for role, cam_cfg in cameras.items():
        if role == "office":
            print(f"[bridge] Skipping camera '{role}' (office — ignored per config)")
            continue
        w = CameraWorker(role, cam_cfg, vps_url, secret, fps)
        workers.append(w)
        w.start()

    if not workers:
        print("[bridge] No active cameras to run. Exiting.")
        sys.exit(1)

    enabled = [w.role for w in workers if w.enabled]
    print(f"\n[bridge] Running {len(enabled)} camera(s): {enabled}")
    print("[bridge] Press Ctrl+C to stop.\n")

    # Status printer in background
    t = threading.Thread(target=_status_loop, args=(workers,), daemon=True)
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[bridge] Stopping…")
        for w in workers:
            w.stop()
        sys.exit(0)


if __name__ == "__main__":
    # If --scan flag passed, discover cameras first
    if "--scan" in sys.argv:
        ips = find_eufy_cameras_on_network()
        if ips:
            print("\nRTSP URLs to try:")
            for ip in ips:
                print(f"  rtsp://{ip}:554/streaming/channels/0")
        sys.exit(0)

    main()

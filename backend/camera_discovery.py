"""
camera_discovery.py — network RTSP scan + camera test utilities.
Runs as a background thread; callers poll get_scan_state() for progress.
"""

import socket
import threading
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

CREDENTIALS = [
    ("admin",  "admin"),
    ("admin",  "12345"),
    ("admin",  "password"),
    ("admin",  ""),
    ("root",   "root"),
    ("root",   "admin"),
    ("",       ""),
]

RTSP_PATHS = ["/stream", "/live", "/video", "/cam", "/channel1", "/h264", "/stream1", "/1", "/"]
RTSP_PORTS = [554, 8554]


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_local_subnet() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:3])
    except Exception:
        return "192.168.1"


def port_open(ip: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:
        return False


def frame_to_b64(frame) -> str | None:
    if frame is None or not CV2_OK:
        return None
    try:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
        return base64.b64encode(buf).decode()
    except Exception:
        return None


def try_rtsp(url: str, timeout: float = 3.0) -> str | None:
    if not CV2_OK:
        return None
    try:
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
        if not cap.isOpened():
            cap.release()
            return None
        ret, frame = cap.read()
        cap.release()
        return frame_to_b64(frame) if ret else None
    except Exception:
        return None


# ── Per-host discovery ────────────────────────────────────────────────────────

def _probe_host(ip: str, results: list, lock: threading.Lock):
    for port in RTSP_PORTS:
        if not port_open(ip, port):
            continue
        for user, pw in CREDENTIALS:
            creds = f"{user}:{pw}@" if user else ""
            for path in RTSP_PATHS[:6]:
                url = f"rtsp://{creds}{ip}:{port}{path}"
                frame = try_rtsp(url, timeout=2.5)
                if frame:
                    with lock:
                        results.append({
                            "id":     len(results) + 1,
                            "name":   f"Camera {ip}",
                            "mode":   "rtsp",
                            "source": url,
                            "ip":     ip,
                            "frame":  frame,
                            "status": "connected",
                        })
                    return   # stop after first success on this host


# ── Background scan ───────────────────────────────────────────────────────────

_state: dict = {"running": False, "done": True, "progress": 0, "total": 254, "results": []}
_lock = threading.Lock()


def _run_scan(state: dict):
    subnet = get_local_subnet()
    hosts  = [f"{subnet}.{i}" for i in range(1, 255)]
    results, rl = [], threading.Lock()
    done_count  = [0]

    def probe(ip):
        _probe_host(ip, results, rl)
        with rl:
            done_count[0] += 1
            state["progress"] = done_count[0]
            state["results"]  = list(results)

    with ThreadPoolExecutor(max_workers=50) as ex:
        futs = [ex.submit(probe, ip) for ip in hosts]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception:
                pass

    state["running"] = False
    state["done"]    = True
    state["results"] = list(results)


def start_scan():
    global _state
    _state = {"running": True, "done": False, "progress": 0, "total": 254, "results": []}
    threading.Thread(target=_run_scan, args=(_state,), daemon=True).start()


def get_scan_state() -> dict:
    return dict(_state)


# ── Single-camera test ────────────────────────────────────────────────────────

def test_camera(mode: str, source: str) -> dict:
    if not CV2_OK:
        return {"ok": False, "error": "OpenCV not installed"}
    try:
        if mode == "webcam":
            idx = int(source) if str(source).isdigit() else 0
            cap = cv2.VideoCapture(idx)
        elif mode in ("rtsp", "http"):
            cap = cv2.VideoCapture(source)
        else:
            return {"ok": False, "error": f"Unknown mode: {mode}"}

        if not cap.isOpened():
            cap.release()
            return {"ok": False, "error": "Could not open camera"}

        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return {"ok": False, "error": "No frame received"}

        h, w = frame.shape[:2]
        return {"ok": True, "frame": frame_to_b64(frame), "width": w, "height": h}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def capture_frame(mode: str, source: str) -> str | None:
    r = test_camera(mode, source)
    return r.get("frame") if r.get("ok") else None

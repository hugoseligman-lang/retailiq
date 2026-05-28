"""
camera_bridge.py — Runs at the store. Captures frames from a local camera
and POSTs them to the RetailIQ VPS backend.

Usage:
  python camera_bridge.py

Configure with environment variables or a .env file in this directory:
  VPS_URL        URL of the VPS backend, e.g. http://1.2.3.4:5050
  BRIDGE_SECRET  Must match BRIDGE_SECRET on the VPS (can be empty for local pilots)
  CAMERA_MODE    webcam | rtsp | http  (default: webcam)
  CAMERA_SOURCE  Camera index or URL  (default: 0)
  BRIDGE_FPS     Frames per second to send  (default: 5)
"""

import base64
import os
import sys
import time

import cv2
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

VPS_URL       = os.getenv("VPS_URL", "http://localhost:5050").rstrip("/")
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")
CAMERA_MODE   = os.getenv("CAMERA_MODE", "webcam").lower()
_src          = os.getenv("CAMERA_SOURCE", "0")
CAMERA_SOURCE = int(_src) if _src.isdigit() else _src
BRIDGE_FPS    = float(os.getenv("BRIDGE_FPS", "5"))

INGEST_URL    = VPS_URL + "/api/ingest-frame"
FRAME_DELAY   = 1.0 / max(BRIDGE_FPS, 0.1)
HEADERS       = {"X-Bridge-Secret": BRIDGE_SECRET, "Content-Type": "image/jpeg"}


def _open_cap():
    if CAMERA_MODE == "webcam":
        src = CAMERA_SOURCE
        if sys.platform == "win32":
            cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(src)
        else:
            cap = cv2.VideoCapture(src)
    else:
        cap = cv2.VideoCapture(str(CAMERA_SOURCE))

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def _send(jpeg_bytes: bytes) -> bool:
    try:
        r = requests.post(INGEST_URL, data=jpeg_bytes, headers=HEADERS, timeout=5)
        return r.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"[bridge] send error: {e}")
        return False


def run():
    print(f"[bridge] Starting — VPS: {VPS_URL}  camera: {CAMERA_MODE}/{CAMERA_SOURCE}  fps: {BRIDGE_FPS}")
    cap = _open_cap()
    if not cap.isOpened():
        print("[bridge] ERROR: cannot open camera")
        return

    fail_count = 0
    MAX_FAILS  = 30
    send_fail  = 0

    while True:
        t0 = time.time()

        ret, frame = cap.read()
        if not ret:
            fail_count += 1
            if fail_count >= MAX_FAILS:
                print("[bridge] Camera lost — reconnecting...")
                cap.release()
                for delay in [2, 5, 10, 30]:
                    time.sleep(delay)
                    cap = _open_cap()
                    if cap.isOpened():
                        fail_count = 0
                        print("[bridge] Camera reconnected")
                        break
            time.sleep(0.1)
            continue

        fail_count = 0
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            continue

        jpeg = buf.tobytes()
        sent = _send(jpeg)
        if sent:
            send_fail = 0
        else:
            send_fail += 1
            if send_fail == 1 or send_fail % 30 == 0:
                print(f"[bridge] VPS unreachable (attempt {send_fail}) — retrying...")

        elapsed = time.time() - t0
        sleep   = FRAME_DELAY - elapsed
        if sleep > 0:
            time.sleep(sleep)


if __name__ == "__main__":
    run()

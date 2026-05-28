"""
Camera abstraction supporting 4 modes:
  webcam  — USB camera via OpenCV (CAMERA_SOURCE = integer index)
  rtsp    — IP/CCTV camera via RTSP URL
  http    — HTTP MJPEG/snapshot stream (e.g. phone IP camera app)
  arlo    — Arlo camera snapshot via pyaarlo library
"""
import cv2
import requests
from config import CAMERA_MODE, CAMERA_SOURCE, ARLO_EMAIL, ARLO_PASSWORD, ARLO_DEVICE


def _frame_from_cv2(source) -> bytes | None:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[camera] Cannot open: {source}")
        return None
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ok else None


def _frame_from_http(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=6, stream=True)
        r.raise_for_status()
        # If it's an MJPEG stream, grab the first JPEG frame
        content_type = r.headers.get("Content-Type", "")
        if "multipart" in content_type:
            for chunk in r.iter_content(chunk_size=65536):
                # Find JPEG start/end markers
                start = chunk.find(b"\xff\xd8")
                end   = chunk.find(b"\xff\xd9")
                if start != -1 and end != -1:
                    return chunk[start:end + 2]
        else:
            return r.content
    except Exception as e:
        print(f"[camera] HTTP fetch error: {e}")
    return None


def _frame_from_arlo() -> bytes | None:
    """Get a snapshot from the active Arlo session (set up via onboarding)."""
    try:
        import base64
        import arlo_camera as ac
        session = ac.get_active_session()
        if not session:
            print("[camera] No active Arlo session — complete Arlo setup in onboarding first")
            return None
        if not session.cameras:
            print("[camera] No Arlo cameras found in active session")
            return None
        # Use ARLO_DEVICE name if configured, otherwise use first camera
        cam = (
            next((c for c in session.cameras
                  if ARLO_DEVICE and ARLO_DEVICE.lower() in c["name"].lower()),
                 session.cameras[0])
        )
        b64 = session.get_snapshot_b64(cam["id"])
        return base64.b64decode(b64) if b64 else None
    except Exception as e:
        print(f"[camera] Arlo error: {e}")
    return None


def capture_frame() -> bytes | None:
    mode = CAMERA_MODE.lower()
    if mode == "webcam":
        return _frame_from_cv2(CAMERA_SOURCE)
    elif mode == "rtsp":
        return _frame_from_cv2(CAMERA_SOURCE)
    elif mode == "http":
        return _frame_from_http(CAMERA_SOURCE)
    elif mode == "arlo":
        return _frame_from_arlo()
    else:
        print(f"[camera] Unknown mode: {mode}")
        return None

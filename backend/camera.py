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
    try:
        import pyaarlo
        ar = pyaarlo.PyArlo(username=ARLO_EMAIL, password=ARLO_PASSWORD,
                            tfa_type="SMS", tfa_source="console")
        cameras = ar.cameras
        cam = next((c for c in cameras if ARLO_DEVICE.lower() in c.name.lower()), None)
        if cam is None:
            print(f"[camera] Arlo device '{ARLO_DEVICE}' not found")
            return None
        snapshot_url = cam.get_snapshot()
        if snapshot_url:
            r = requests.get(snapshot_url, timeout=10)
            return r.content if r.ok else None
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

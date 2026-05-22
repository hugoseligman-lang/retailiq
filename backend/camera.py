import cv2
from config import CAMERA_SOURCE


def capture_frame() -> bytes | None:
    """
    Opens the camera, grabs a single frame, and returns it as JPEG bytes.
    Returns None if capture fails.
    """
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    if not cap.isOpened():
        print(f"[camera] Failed to open source: {CAMERA_SOURCE}")
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("[camera] Failed to read frame")
        return None

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        print("[camera] Failed to encode frame as JPEG")
        return None

    return buffer.tobytes()

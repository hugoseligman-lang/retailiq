"""
frame_buffer.py — Thread-safe buffer for frames pushed from a remote camera bridge.

When CAMERA_MODE=vps the camera bridge (camera_bridge.py) POSTs JPEG frames
to POST /api/ingest-frame. This module holds the most recent frame so
detector.py and tracker.py can process it without a local camera.
"""
import threading
import time

_lock        = threading.Lock()
_frame: bytes | None = None
_last_push   = 0.0


def push(frame_bytes: bytes):
    global _frame, _last_push
    with _lock:
        _frame     = frame_bytes
        _last_push = time.time()


def get() -> bytes | None:
    with _lock:
        return _frame


def is_fresh(max_age: float = 30.0) -> bool:
    """True if a frame was received within the last max_age seconds."""
    with _lock:
        return _frame is not None and (time.time() - _last_push) < max_age


def age_seconds() -> float:
    with _lock:
        return time.time() - _last_push if _frame is not None else float("inf")

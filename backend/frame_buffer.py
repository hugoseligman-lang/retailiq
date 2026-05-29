"""
frame_buffer.py — Thread-safe per-camera frame buffer.

push(frame_bytes, camera="default")  — called by /api/ingest-frame
get(camera="default")                — called by detector.py
is_fresh(camera="default", max_age)  — staleness check
age_seconds(camera="default")        — seconds since last push
camera_status()                      — dict of all camera ages / freshness

Backward-compatible: push(bytes) and get() without camera= still work
exactly as before for single-camera deployments.
"""
import threading
import time

_lock    = threading.Lock()
_DEFAULT = "default"

# {camera_role: {"frame": bytes, "last_push": float}}
_buffers: dict[str, dict] = {}

# Legacy single-buffer aliases kept for backward compat
_frame_legacy: bytes | None = None
_last_push_legacy: float = 0.0


def push(frame_bytes: bytes, camera: str = _DEFAULT) -> None:
    global _frame_legacy, _last_push_legacy
    with _lock:
        _buffers[camera] = {"frame": frame_bytes, "last_push": time.time()}
        if camera == _DEFAULT:
            _frame_legacy     = frame_bytes
            _last_push_legacy = time.time()


def get(camera: str = _DEFAULT) -> bytes | None:
    with _lock:
        slot = _buffers.get(camera)
        if slot:
            return slot["frame"]
        # fallback to legacy single-buffer
        return _frame_legacy


def is_fresh(camera: str = _DEFAULT, max_age: float = 30.0) -> bool:
    """True if a frame was received within the last max_age seconds."""
    with _lock:
        slot = _buffers.get(camera)
        if slot:
            return (time.time() - slot["last_push"]) < max_age
        if camera == _DEFAULT and _frame_legacy is not None:
            return (time.time() - _last_push_legacy) < max_age
        return False


def age_seconds(camera: str = _DEFAULT) -> float:
    with _lock:
        slot = _buffers.get(camera)
        if slot:
            return time.time() - slot["last_push"]
        if camera == _DEFAULT and _frame_legacy is not None:
            return time.time() - _last_push_legacy
        return float("inf")


def camera_status() -> dict:
    """Return freshness info for every camera that has ever received a frame."""
    with _lock:
        now = time.time()
        return {
            cam: {
                "age_seconds": round(now - slot["last_push"], 1),
                "fresh":       (now - slot["last_push"]) < 60,
            }
            for cam, slot in _buffers.items()
        }

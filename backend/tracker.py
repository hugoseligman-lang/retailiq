"""
tracker.py — Real-time person tracking with entrance-line crossing detection.

Supports two operating modes:
  local  — opens a camera directly (webcam, RTSP, or HTTP stream)
  vps    — no local camera; frames are pushed via process_frame() from
           /api/ingest-frame (sent by camera_bridge.py at the store)

Tracks per session:
  entries             : crossed the line going in  (top->bottom)
  exits               : crossed the line going out (bottom->top)
  passersby           : appeared but left without crossing
  in_store            : net people currently inside
  staff_in_store      : staff who have explicitly checked in
  customers_in_store  : in_store - staff_in_store
  conversion_rate     : entries / (entries + passersby) x 100%

Counting only increments while _counting_active is True.
Call pause_counting() / resume_counting() to control this (store open/close).
"""

import cv2
import sys
import threading
import time
import numpy as np
from collections import OrderedDict

from config import CAMERA_MODE, CAMERA_SOURCE

# ── Shared state ──────────────────────────────────────────────────────────────
_lock             = threading.Lock()
_line_y           = 0.55
_counts           = {"entries": 0, "exits": 0, "passersby": 0, "in_store": 0}
_staff_in_store   = 0
_counting_active  = True    # False when store is "closed"
_last_frame       = None    # latest annotated JPEG bytes
_running          = False
_stop_evt         = threading.Event()

# ── Centroid tracker state ────────────────────────────────────────────────────
_next_id     = 0
_objects     = OrderedDict()
_disappeared = OrderedDict()
_side        = {}
_did_cross   = set()

MAX_GONE = 12
MAX_DIST = 90

# ── HOG detector (lazy-initialised, shared across calls) ─────────────────────
_hog = None


def _get_hog():
    global _hog
    if _hog is None:
        _hog = cv2.HOGDescriptor()
        _hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return _hog


# ── Camera open ───────────────────────────────────────────────────────────────

def _open_capture():
    mode = CAMERA_MODE.lower()
    if mode in ("arlo", "vps"):
        return None

    if mode == "webcam":
        src = int(CAMERA_SOURCE) if str(CAMERA_SOURCE).isdigit() else 0
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


# ── Centroid tracking helpers ─────────────────────────────────────────────────

def _register(centroid, line_y_px):
    global _next_id
    oid = _next_id
    _next_id += 1
    _objects[oid]     = centroid
    _disappeared[oid] = 0
    _side[oid] = "above" if centroid[1] < line_y_px else "below"


def _deregister(oid):
    if oid not in _did_cross and _counting_active:
        with _lock:
            _counts["passersby"] += 1
    _did_cross.discard(oid)
    _side.pop(oid, None)
    del _objects[oid]
    del _disappeared[oid]


def _update_tracker(rects, fh):
    line_y_px = int(_line_y * fh)

    if not rects:
        for oid in list(_disappeared):
            _disappeared[oid] += 1
            if _disappeared[oid] > MAX_GONE:
                _deregister(oid)
        return

    centroids = [(int(x + w / 2), int(y + h / 2)) for x, y, w, h in rects]

    if not _objects:
        for c in centroids:
            _register(c, line_y_px)
        return

    oids  = list(_objects)
    ocens = list(_objects.values())

    D = np.zeros((len(ocens), len(centroids)))
    for i, (ox, oy) in enumerate(ocens):
        for j, (cx, cy) in enumerate(centroids):
            D[i, j] = np.hypot(ox - cx, oy - cy)

    rows = D.min(axis=1).argsort()
    cols = D.argmin(axis=1)[rows]

    used_r, used_c = set(), set()
    for r, c in zip(rows, cols):
        if r in used_r or c in used_c or D[r, c] > MAX_DIST:
            continue

        oid     = oids[r]
        prev_cy = _objects[oid][1]
        new_cy  = centroids[c][1]
        _objects[oid]     = centroids[c]
        _disappeared[oid] = 0

        prev_side = "above" if prev_cy < line_y_px else "below"
        new_side  = "above" if new_cy  < line_y_px else "below"
        if prev_side != new_side and _counting_active:
            with _lock:
                if new_side == "below":
                    _counts["entries"]  += 1
                    _counts["in_store"] += 1
                else:
                    _counts["exits"]    += 1
                    _counts["in_store"] = max(0, _counts["in_store"] - 1)
            _did_cross.add(oid)
        _side[oid] = new_side

        used_r.add(r)
        used_c.add(c)

    for i, oid in enumerate(oids):
        if i not in used_r:
            _disappeared[oid] += 1
            if _disappeared[oid] > MAX_GONE:
                _deregister(oid)

    for j, c in enumerate(centroids):
        if j not in used_c:
            _register(c, line_y_px)


# ── Per-frame processing (shared by local loop and VPS push mode) ─────────────

def _process_one_frame(frame: np.ndarray) -> None:
    """Detect people, update tracker state, encode annotated JPEG to _last_frame."""
    global _last_frame

    fh, fw = frame.shape[:2]
    line_y_px = int(_line_y * fh)

    small    = cv2.resize(frame, (320, 240))
    rects_s, _ = _get_hog().detectMultiScale(
        small, winStride=(8, 8), padding=(4, 4), scale=1.05
    )
    rects = [(x*2, y*2, w*2, h*2) for x, y, w, h in rects_s] if len(rects_s) else []

    _update_tracker(rects, fh)

    with _lock:
        c     = dict(_counts)
        staff = _staff_in_store

    # ── Draw overlays ──────────────────────────────────────────────────────────

    for (x, y, bw, bh) in rects:
        cy     = y + bh // 2
        colour = (40, 220, 40) if cy > line_y_px else (40, 220, 220)
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), colour, 2)
        cv2.circle(frame, (x + bw // 2, cy), 5, colour, -1)

    cv2.line(frame, (0, line_y_px), (fw, line_y_px), (0, 220, 255), 2)
    cv2.putText(frame, "v ENTER", (fw // 2 - 48, line_y_px + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)
    cv2.putText(frame, "^ EXIT",  (fw // 2 - 40, line_y_px - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)

    if not _counting_active:
        cv2.putText(frame, "CLOSED", (12, fh - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 2)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (fw, 56), (15, 15, 15), -1)
    frame = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

    total     = c["entries"] + c["passersby"]
    conv      = round(c["entries"] / total * 100) if total else 0
    customers = max(0, c["in_store"] - staff)

    stats = [
        ("Customers", str(customers)),
        ("Entries",   str(c["entries"])),
        ("Exits",     str(c["exits"])),
        ("Passersby", str(c["passersby"])),
        ("Conv",      f"{conv}%"),
    ]
    if staff:
        stats.append(("Staff", str(staff)))

    for i, (label, val) in enumerate(stats):
        x0 = 10 + i * 108
        cv2.putText(frame, label, (x0, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)
        cv2.putText(frame, val,   (x0, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
    if ok:
        with _lock:
            _last_frame = buf.tobytes()


# ── Local camera loop ─────────────────────────────────────────────────────────

def _loop():
    global _running

    cap = _open_capture()
    if cap is None or not cap.isOpened():
        print(f"[tracker] ERROR: cannot open camera (mode={CAMERA_MODE} source={CAMERA_SOURCE})")
        _running = False
        return

    print(f"[tracker] Started (mode={CAMERA_MODE} source={CAMERA_SOURCE})")
    fail_count = 0
    MAX_FAILS  = 30

    while not _stop_evt.is_set():
        ret, frame = cap.read()

        if not ret:
            fail_count += 1
            if fail_count >= MAX_FAILS:
                print("[tracker] Camera disconnected — reconnecting...")
                cap.release()
                for delay in [2, 5, 10, 30]:
                    time.sleep(delay)
                    cap = _open_capture()
                    if cap and cap.isOpened():
                        fail_count = 0
                        print("[tracker] Camera reconnected")
                        break
                    print(f"[tracker] Reconnect failed — retrying in {delay*2}s...")
                else:
                    while not _stop_evt.is_set():
                        time.sleep(30)
                        cap = _open_capture()
                        if cap and cap.isOpened():
                            fail_count = 0
                            print("[tracker] Camera reconnected (long wait)")
                            break
            else:
                time.sleep(0.05)
            continue

        fail_count = 0
        _process_one_frame(frame)
        time.sleep(0.04)   # ~25 fps

    cap.release()
    _running = False
    print("[tracker] Stopped")


# ── Public API ────────────────────────────────────────────────────────────────

def start():
    global _running
    if _running:
        return
    _stop_evt.clear()
    _running = True

    if CAMERA_MODE.lower() in ("arlo", "vps"):
        mode_label = "Arlo (snapshot via detector.py)" if CAMERA_MODE.lower() == "arlo" else "VPS (frames via /api/ingest-frame)"
        print(f"[tracker] {mode_label} — no local camera loop")
        return

    threading.Thread(target=_loop, daemon=True).start()


def stop():
    _stop_evt.set()


def process_frame(frame_bytes: bytes):
    """VPS mode: process a JPEG frame sent by the remote camera bridge."""
    try:
        arr   = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            _process_one_frame(frame)
    except Exception as e:
        print(f"[tracker] process_frame error: {e}")


def set_line(y_frac: float):
    global _line_y
    _line_y = max(0.1, min(0.9, float(y_frac)))


def reset():
    global _counts, _next_id, _objects, _disappeared, _side, _did_cross
    with _lock:
        _counts = {"entries": 0, "exits": 0, "passersby": 0, "in_store": 0}
    _objects.clear()
    _disappeared.clear()
    _side.clear()
    _did_cross.clear()


def pause_counting():
    global _counting_active
    _counting_active = False


def resume_counting():
    global _counting_active
    _counting_active = True


def staff_in():
    global _staff_in_store
    with _lock:
        _staff_in_store += 1


def staff_out():
    global _staff_in_store
    with _lock:
        _staff_in_store = max(0, _staff_in_store - 1)


def get_staff_count() -> int:
    with _lock:
        return _staff_in_store


def get_counts() -> dict:
    with _lock:
        c     = dict(_counts)
        staff = _staff_in_store
    total = c["entries"] + c["passersby"]
    c["conversion_rate"]    = round(c["entries"] / total * 100) if total else 0
    c["staff_in_store"]     = staff
    c["customers_in_store"] = max(0, c["in_store"] - staff)
    c["counting_active"]    = _counting_active
    c["line_y"]             = _line_y
    c["running"]            = _running
    return c


def get_frame() -> bytes | None:
    with _lock:
        return _last_frame

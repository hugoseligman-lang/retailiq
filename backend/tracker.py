"""
tracker.py — Real-time person tracking with entrance-line crossing detection.

Uses OpenCV's built-in HOG person detector (offline, no API key needed).
Generates annotated MJPEG frames and tracks:
  - entries   : crossed the line going into the store (top→bottom)
  - exits     : crossed the line going out (bottom→top)
  - passersby : appeared in frame but left without crossing
  - in_store  : net people currently inside
  - conversion rate : entries / (entries + passersby) × 100 %
"""

import cv2
import threading
import time
import numpy as np
from collections import OrderedDict

# ── Shared state ──────────────────────────────────────────────────────────────
_lock         = threading.Lock()
_line_y       = 0.55          # entrance line Y as fraction of frame height
_counts       = {"entries": 0, "exits": 0, "passersby": 0, "in_store": 0}
_last_frame   = None           # latest annotated JPEG bytes
_running      = False
_stop_evt     = threading.Event()

# ── Simple centroid tracker ───────────────────────────────────────────────────
_next_id      = 0
_objects      = OrderedDict()  # id → (cx, cy)
_disappeared  = OrderedDict()  # id → frames missing
_side         = {}             # id → "above" | "below"  (side at last frame)
_did_cross    = set()          # ids that have already crossed the line

MAX_GONE   = 12    # frames before an object is deregistered
MAX_DIST   = 90    # pixel distance threshold for assignment


def _register(centroid, line_y_px):
    global _next_id
    oid = _next_id
    _next_id += 1
    _objects[oid]     = centroid
    _disappeared[oid] = 0
    _side[oid] = "above" if centroid[1] < line_y_px else "below"
    return oid


def _deregister(oid):
    global _counts
    if oid not in _did_cross:
        with _lock:
            _counts["passersby"] += 1
    _did_cross.discard(oid)
    _side.pop(oid, None)
    del _objects[oid]
    del _disappeared[oid]


def _update_tracker(rects, fh):
    global _counts
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

    # Distance matrix
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

        # Crossing check
        prev_side = "above" if prev_cy < line_y_px else "below"
        new_side  = "above" if new_cy  < line_y_px else "below"
        if prev_side != new_side:
            with _lock:
                if new_side == "below":           # entering
                    _counts["entries"]  += 1
                    _counts["in_store"] += 1
                else:                             # exiting
                    _counts["exits"]    += 1
                    _counts["in_store"] = max(0, _counts["in_store"] - 1)
            _did_cross.add(oid)
        _side[oid] = new_side

        used_r.add(r)
        used_c.add(c)

    # Unmatched existing → increment disappeared
    for i, oid in enumerate(oids):
        if i not in used_r:
            _disappeared[oid] += 1
            if _disappeared[oid] > MAX_GONE:
                _deregister(oid)

    # Unmatched new centroids → new objects
    for j, c in enumerate(centroids):
        if j not in used_c:
            _register(c, line_y_px)


# ── Tracking loop ─────────────────────────────────────────────────────────────

def _loop():
    global _last_frame, _running

    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)   # CAP_DSHOW is faster on Windows
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)              # fallback
    if not cap.isOpened():
        print("[tracker] ERROR: cannot open webcam 0")
        _running = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("[tracker] Webcam opened — streaming at 640×480")

    while not _stop_evt.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        fh, fw = frame.shape[:2]
        line_y_px = int(_line_y * fh)

        # Detect on half-size frame for speed
        small = cv2.resize(frame, (320, 240))
        rects_s, _ = hog.detectMultiScale(
            small, winStride=(8, 8), padding=(4, 4), scale=1.05
        )
        rects = [(x*2, y*2, w*2, h*2) for x, y, w, h in rects_s] if len(rects_s) else []

        _update_tracker(rects, fh)

        with _lock:
            c = dict(_counts)

        # ── Draw overlays ──────────────────────────────────────────────────

        # Bounding boxes + centroids
        for (x, y, bw, bh) in rects:
            cy = y + bh // 2
            colour = (40, 220, 40) if cy > line_y_px else (40, 220, 220)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), colour, 2)
            cv2.circle(frame, (x + bw // 2, cy), 5, colour, -1)

        # Entrance line with arrows indicating direction
        cv2.line(frame, (0, line_y_px), (fw, line_y_px), (0, 220, 255), 2)
        cv2.putText(frame, "v ENTER", (fw // 2 - 48, line_y_px + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)
        cv2.putText(frame, "^ EXIT",  (fw // 2 - 40, line_y_px - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)

        # Top stats bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (fw, 56), (15, 15, 15), -1)
        frame = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

        total      = c["entries"] + c["passersby"]
        conv       = round(c["entries"] / total * 100) if total else 0
        in_store   = max(0, c["in_store"])

        stats = [
            ("In Store",    str(in_store)),
            ("Entries",     str(c["entries"])),
            ("Exits",       str(c["exits"])),
            ("Passersby",   str(c["passersby"])),
            ("Conversion",  f"{conv}%"),
        ]
        for i, (label, val) in enumerate(stats):
            x0 = 12 + i * 128
            cv2.putText(frame, label, (x0, 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160, 160, 160), 1)
            cv2.putText(frame, val, (x0, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if ok:
            with _lock:
                _last_frame = buf.tobytes()

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
    threading.Thread(target=_loop, daemon=True).start()


def stop():
    _stop_evt.set()


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


def get_counts() -> dict:
    with _lock:
        c = dict(_counts)
    total = c["entries"] + c["passersby"]
    c["conversion_rate"] = round(c["entries"] / total * 100) if total else 0
    c["line_y"] = _line_y
    c["running"] = _running
    return c


def get_frame() -> bytes | None:
    with _lock:
        return _last_frame

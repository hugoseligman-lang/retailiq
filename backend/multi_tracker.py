"""
multi_tracker.py — Class-based HOG person tracker supporting multiple independent
camera instances. Each CameraTracker is a fully self-contained tracker.

Two modes:
  crossing  — centroid tracking with entrance-line crossing (front / back doors)
  queue     — simple HOG headcount in-frame; emits queue events (POS counter)

Usage:
    from multi_tracker import CameraTracker
    front = CameraTracker("front", mode="crossing", line_y=0.55)
    pos   = CameraTracker("pos",   mode="queue")

    front.process_frame(jpeg_bytes)   # call on every received frame
    print(front.get_counts())
"""

import cv2
import threading
import time
import numpy as np
from collections import OrderedDict

MAX_GONE = 14
MAX_DIST = 90

# Queue mode settings
QUEUE_THRESHOLD    = 2      # min people for a queue event
QUEUE_DWELL_SECS   = 30     # seconds people must be present before event fires


class CameraTracker:
    """Thread-safe HOG tracker for one camera role."""

    def __init__(self, role: str, mode: str = "crossing", line_y: float = 0.55):
        """
        role : human label — "front", "back", "pos", etc.
        mode : "crossing" | "queue"
        """
        self.role = role
        self.mode = mode

        self._lock    = threading.Lock()
        self._line_y  = max(0.1, min(0.9, float(line_y)))

        # Counts
        self._counts  = {"entries": 0, "exits": 0, "passersby": 0,
                         "in_store": 0, "queue_length": 0, "queue_events": 0}
        self._staff   = 0
        self._counting_active = True
        self._last_frame: bytes | None = None
        self._last_frame_ts: float = 0.0
        self._frame_count: int = 0

        # Centroid tracker state (crossing mode only)
        self._next_id    = 0
        self._objects    = OrderedDict()   # id -> (cx, cy)
        self._disappeared = OrderedDict()  # id -> frames_since_seen
        self._side       = {}              # id -> "above"|"below"
        self._did_cross  = set()

        # Queue mode state
        self._queue_start: float | None = None  # when queue first appeared

        self._hog = None

    # ── HOG init ──────────────────────────────────────────────────────────────

    def _get_hog(self):
        if self._hog is None:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        return self._hog

    # ── Public API ────────────────────────────────────────────────────────────

    def process_frame(self, frame_bytes: bytes) -> None:
        """Decode JPEG, run HOG, update state. Thread-safe."""
        try:
            arr   = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                if self.mode == "queue":
                    self._process_queue_frame(frame)
                else:
                    self._process_crossing_frame(frame)
        except Exception as e:
            print(f"[tracker:{self.role}] process_frame error: {e}")

    def get_counts(self) -> dict:
        with self._lock:
            c = dict(self._counts)
            staff = self._staff
        total = c["entries"] + c["passersby"]
        c["conversion_rate"]    = round(c["entries"] / total * 100) if total else 0
        c["staff_in_store"]     = staff
        c["customers_in_store"] = max(0, c["in_store"] - staff)
        c["counting_active"]    = self._counting_active
        c["line_y"]             = self._line_y
        c["running"]            = True
        c["role"]               = self.role
        c["mode"]               = self.mode
        c["frame_age"]          = round(time.time() - self._last_frame_ts, 1) if self._last_frame_ts else None
        return c

    def get_frame(self) -> bytes | None:
        with self._lock:
            return self._last_frame

    def reset(self) -> None:
        with self._lock:
            self._counts = {"entries": 0, "exits": 0, "passersby": 0,
                            "in_store": 0, "queue_length": 0, "queue_events": 0}
        self._objects.clear()
        self._disappeared.clear()
        self._side.clear()
        self._did_cross.clear()
        self._queue_start = None

    def set_line(self, y_frac: float) -> None:
        self._line_y = max(0.1, min(0.9, float(y_frac)))

    def pause_counting(self) -> None:
        self._counting_active = False

    def resume_counting(self) -> None:
        self._counting_active = True

    def staff_in(self) -> None:
        with self._lock:
            self._staff += 1

    def staff_out(self) -> None:
        with self._lock:
            self._staff = max(0, self._staff - 1)

    # ── Crossing mode ─────────────────────────────────────────────────────────

    def _process_crossing_frame(self, frame: np.ndarray) -> None:
        fh, fw = frame.shape[:2]
        line_y_px = int(self._line_y * fh)

        # Detect at half size for speed
        small     = cv2.resize(frame, (320, 240))
        rects_s, _ = self._get_hog().detectMultiScale(
            small, winStride=(8, 8), padding=(4, 4), scale=1.05
        )
        rects = [(x*2, y*2, w*2, h*2) for x, y, w, h in rects_s] if len(rects_s) else []

        self._update_centroid_tracker(rects, fh)

        # Annotate frame
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

        if not self._counting_active:
            cv2.putText(frame, "CLOSED", (12, fh - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 2)

        # Overlay stats bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (fw, 52), (15, 15, 15), -1)
        frame   = cv2.addWeighted(overlay, 0.65, frame, 0.35, 0)

        with self._lock:
            c = dict(self._counts)
        stats = [
            (self.role.upper(), ""),
            ("In",   str(c["in_store"])),
            ("In/Out", f"{c['entries']}/{c['exits']}"),
            ("Pass",  str(c["passersby"])),
        ]
        for i, (lbl, val) in enumerate(stats):
            x0 = 8 + i * 96
            cv2.putText(frame, lbl, (x0, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160, 160, 160), 1)
            if val:
                cv2.putText(frame, val, (x0, 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.64, (255, 255, 255), 2)

        self._encode_frame(frame)

    def _update_centroid_tracker(self, rects: list, fh: int) -> None:
        line_y_px = int(self._line_y * fh)

        if not rects:
            for oid in list(self._disappeared):
                self._disappeared[oid] += 1
                if self._disappeared[oid] > MAX_GONE:
                    self._deregister(oid)
            return

        centroids = [(int(x + w / 2), int(y + h / 2)) for x, y, w, h in rects]

        if not self._objects:
            for c in centroids:
                self._register(c, line_y_px)
            return

        oids  = list(self._objects)
        ocens = list(self._objects.values())

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

            oid      = oids[r]
            prev_cy  = self._objects[oid][1]
            new_cy   = centroids[c][1]
            self._objects[oid]      = centroids[c]
            self._disappeared[oid]  = 0

            prev_side = "above" if prev_cy < line_y_px else "below"
            new_side  = "above" if new_cy  < line_y_px else "below"
            if prev_side != new_side and self._counting_active:
                with self._lock:
                    if new_side == "below":
                        self._counts["entries"]  += 1
                        self._counts["in_store"] += 1
                    else:
                        self._counts["exits"]    += 1
                        self._counts["in_store"] = max(0, self._counts["in_store"] - 1)
                self._did_cross.add(oid)
            self._side[oid] = new_side

            used_r.add(r)
            used_c.add(c)

        for i, oid in enumerate(oids):
            if i not in used_r:
                self._disappeared[oid] += 1
                if self._disappeared[oid] > MAX_GONE:
                    self._deregister(oid)

        for j, c in enumerate(centroids):
            if j not in used_c:
                self._register(c, line_y_px)

    def _register(self, centroid, line_y_px):
        oid = self._next_id
        self._next_id += 1
        self._objects[oid]      = centroid
        self._disappeared[oid]  = 0
        self._side[oid] = "above" if centroid[1] < line_y_px else "below"

    def _deregister(self, oid):
        if oid not in self._did_cross and self._counting_active:
            with self._lock:
                self._counts["passersby"] += 1
        self._did_cross.discard(oid)
        self._side.pop(oid, None)
        del self._objects[oid]
        del self._disappeared[oid]

    # ── Queue mode ────────────────────────────────────────────────────────────

    def _process_queue_frame(self, frame: np.ndarray) -> None:
        fh, fw = frame.shape[:2]

        small     = cv2.resize(frame, (320, 240))
        rects_s, _ = self._get_hog().detectMultiScale(
            small, winStride=(8, 8), padding=(4, 4), scale=1.05
        )
        rects = [(x*2, y*2, w*2, h*2) for x, y, w, h in rects_s] if len(rects_s) else []
        count = len(rects)

        # Queue event logic
        now = time.time()
        if count >= QUEUE_THRESHOLD:
            if self._queue_start is None:
                self._queue_start = now
            elif (now - self._queue_start) >= QUEUE_DWELL_SECS and self._counting_active:
                with self._lock:
                    self._counts["queue_events"] += 1
                self._queue_start = None   # reset — count next dwell separately
        else:
            self._queue_start = None

        with self._lock:
            self._counts["queue_length"] = count
            self._counts["in_store"]     = count  # queue = headcount in zone

        # Annotate
        for (x, y, bw, bh) in rects:
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (40, 160, 255), 2)
            cv2.circle(frame, (x + bw // 2, y + bh // 2), 5, (40, 160, 255), -1)

        colour = (0, 80, 255) if count >= QUEUE_THRESHOLD else (40, 200, 40)
        cv2.putText(frame, f"QUEUE: {count}", (12, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2)
        cv2.putText(frame, "POS / Counter", (12, fh - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)

        self._encode_frame(frame)

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _encode_frame(self, frame: np.ndarray) -> None:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            with self._lock:
                self._last_frame    = buf.tobytes()
                self._last_frame_ts = time.time()
            self._frame_count += 1


# ── Registry helpers (used by api.py) ─────────────────────────────────────────

_registry: dict[str, CameraTracker] = {}
_reg_lock  = threading.Lock()


def get(role: str) -> CameraTracker:
    """Get or create a CameraTracker for the given role."""
    with _reg_lock:
        if role not in _registry:
            mode = "queue" if role == "pos" else "crossing"
            _registry[role] = CameraTracker(role, mode=mode)
        return _registry[role]


def all_trackers() -> dict[str, CameraTracker]:
    with _reg_lock:
        return dict(_registry)


def merged_counts() -> dict:
    """
    Aggregate counts across all active cameras:
      entries / exits / in_store  = front + back (not pos)
      passersby / conversion      = front only
      queue_length / queue_events = pos only
    """
    trackers = all_trackers()
    if not trackers:
        return {}

    door_cams  = [t for r, t in trackers.items() if r != "pos"]
    front      = trackers.get("front")
    pos        = trackers.get("pos")

    entries    = sum(t.get_counts()["entries"]   for t in door_cams)
    exits      = sum(t.get_counts()["exits"]     for t in door_cams)
    in_store   = sum(t.get_counts()["in_store"]  for t in door_cams)
    passersby  = front.get_counts()["passersby"] if front else 0

    pos_c       = pos.get_counts() if pos else {}
    queue_len   = pos_c.get("queue_length",  0)
    queue_evts  = pos_c.get("queue_events",  0)

    total = entries + passersby
    result = {
        "entries":          entries,
        "exits":            exits,
        "in_store":         in_store,
        "passersby":        passersby,
        "queue_length":     queue_len,
        "queue_events":     queue_evts,
        "conversion_rate":  round(entries / total * 100) if total else 0,
        "counting_active":  any(t.get_counts()["counting_active"] for t in trackers.values()),
        "running":          True,
        "line_y":           front.get_counts()["line_y"] if front else 0.55,
        "staff_in_store":   sum(t._staff for t in door_cams),
        "customers_in_store": max(0, in_store - sum(t._staff for t in door_cams)),
        "cameras": {
            role: {
                "running":        True,
                "mode":           t.mode,
                "frame_age":      t.get_counts()["frame_age"],
                "entries":        t.get_counts().get("entries", 0),
                "exits":          t.get_counts().get("exits",   0),
                "in_store":       t.get_counts()["in_store"],
                "queue_length":   t.get_counts().get("queue_length", 0),
            }
            for role, t in trackers.items()
        },
    }
    return result

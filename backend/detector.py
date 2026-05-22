import time
import threading
from datetime import datetime
from camera import capture_frame
from vision_api import detect_people
from supabase_db import insert_detection
from config import CAPTURE_INTERVAL

_stop_event = threading.Event()


def _run_loop():
    print("[detector] Detection loop started")
    while not _stop_event.is_set():
        try:
            frame = capture_frame()
            if frame is None:
                print("[detector] No frame — skipping cycle")
                time.sleep(CAPTURE_INTERVAL)
                continue

            result = detect_people(frame)
            insert_detection(
                result["people_count"],
                result["zone_left"],
                result["zone_center"],
                result["zone_right"],
            )

            ts = datetime.utcnow().strftime("%H:%M:%S")
            print(
                f"[{ts}] people={result['people_count']} "
                f"L={result['zone_left']} C={result['zone_center']} R={result['zone_right']}"
            )

        except Exception as exc:
            print(f"[detector] Error: {exc}")

        time.sleep(CAPTURE_INTERVAL)

    print("[detector] Detection loop stopped")


def start(daemon: bool = True):
    t = threading.Thread(target=_run_loop, daemon=daemon)
    t.start()
    return t


def stop():
    _stop_event.set()

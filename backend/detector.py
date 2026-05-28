import time
import threading
from datetime import datetime, date
from camera import capture_frame
from vision_api import detect_people
import database as db
import weather as wx
import frame_buffer
from config import CAPTURE_INTERVAL, CAMERA_MODE

_stop   = threading.Event()
_latest = {}
_lock   = threading.Lock()
_last_date = date.today()
_last_weather_fetch = 0
_current_weather = {}
WEATHER_INTERVAL = 1800  # refresh weather every 30 min


def get_latest() -> dict:
    with _lock:
        return dict(_latest)


def get_current_weather() -> dict:
    return dict(_current_weather)


def _maybe_refresh_weather():
    global _last_weather_fetch, _current_weather
    now = time.time()
    if now - _last_weather_fetch > WEATHER_INTERVAL:
        w = wx.fetch_current()
        if w:
            _current_weather = w
            db.insert_weather(w)
            _last_weather_fetch = now


def _maybe_midnight_rollover():
    global _last_date
    today = date.today()
    if today != _last_date:
        print(f"[detector] Midnight rollover: {_last_date} → {today}")
        dow = _last_date.weekday()
        try:
            import holidays as hols
            from config import STORE_STATE
            au = hols.Australia(state=STORE_STATE, years=_last_date.year)
            is_hol = _last_date in au
        except Exception:
            is_hol = False
        db.midnight_rollover(dow, is_hol)
        _last_date = today


def _run():
    print("[detector] Detection loop started")
    while not _stop.is_set():
        try:
            _maybe_midnight_rollover()
            _maybe_refresh_weather()

            # VPS mode: use the frame pushed by the remote camera bridge.
            # Local mode: capture from the configured camera.
            if CAMERA_MODE.lower() == "vps":
                if not frame_buffer.is_fresh(max_age=60):
                    time.sleep(1)
                    continue
                frame = frame_buffer.get()
            else:
                frame = capture_frame()
            if frame is None:
                print("[detector] No frame")
                time.sleep(CAPTURE_INTERVAL)
                continue

            result = detect_people(frame, _current_weather)
            db.insert_detection(result)

            result["last_updated"] = datetime.utcnow().isoformat() + "Z"
            result["weather"] = _current_weather
            with _lock:
                _latest.update(result)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"in={result['people_count']} pass={result['passerby_count']} "
                  f"queue={result['queue_length']} zone={result['busiest_zone']}")

        except Exception as e:
            print(f"[detector] Error: {e}")

        time.sleep(CAPTURE_INTERVAL)

    print("[detector] Stopped")


def start(daemon=True):
    t = threading.Thread(target=_run, daemon=daemon)
    t.start()
    return t


def stop():
    _stop.set()

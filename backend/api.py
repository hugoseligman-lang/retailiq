import json
import os
import threading
import time
import requests as req
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import detector
import database as db
import daily_summary as ds
import ai_insights as ai
import chat_handler
import camera_discovery as cam_disc
import scene_analysis as scene_ai
import arlo_camera as arlo_cam
import tracker
from config import STORE_NAME

app = Flask(__name__)
CORS(app)

DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))


# ── Live ──────────────────────────────────────────────────────────────────

@app.route("/api/live")
def live():
    data = detector.get_latest()
    data["weather"] = detector.get_current_weather()
    return jsonify(data)


# ── Today stats ───────────────────────────────────────────────────────────

@app.route("/api/today")
def today():
    return jsonify(db.get_today_stats())


# ── Traffic chart ─────────────────────────────────────────────────────────

@app.route("/api/traffic")
def traffic():
    from datetime import date, timedelta
    overlay = request.args.get("overlay", "none")

    # Today's hourly data
    today_data = db.get_hourly_today()

    # Build full 24-hour grid for today
    today_map = {r["hour"]: r for r in today_data}
    today_full = []
    for h in range(24):
        key = f"{h:02d}"
        if key in today_map:
            today_full.append(today_map[key])
        else:
            today_full.append({"hour": key, "avg_count": 0, "peak_count": 0,
                                "passersby": 0, "max_queue": 0,
                                "weather_temp": None, "weather_code": None})

    result = {"today": today_full}

    if overlay != "none":
        offsets = {"yesterday": 1, "last_week": 7, "last_month": 30}
        offset  = offsets.get(overlay, 0)
        if offset:
            target = (date.today() - timedelta(days=offset)).isoformat()
            hist   = db.get_hourly_for_date(target)
            hist_map = {r["hour"]: r for r in hist}
            hist_full = []
            for h in range(24):
                key = f"{h:02d}"
                hist_full.append(hist_map.get(key, {
                    "hour": key, "avg_people": 0, "max_people": 0,
                    "weather_temp": None, "weather_code": None
                }))
            result["overlay"] = hist_full
            result["overlay_label"] = overlay.replace("_", " ").title()

    return jsonify(result)


# ── Heatmap ───────────────────────────────────────────────────────────────

@app.route("/api/heatmap")
def heatmap():
    period = request.args.get("period", "today")
    return jsonify(db.get_heatmap_data(period))


# ── Weather ───────────────────────────────────────────────────────────────

@app.route("/api/weather")
def weather():
    return jsonify(detector.get_current_weather())


# ── AI Insights ───────────────────────────────────────────────────────────

@app.route("/api/insights")
def insights():
    row = db.get_latest_insight()
    if not row:
        return jsonify({"patterns": [], "anomalies": [], "comparisons": {}, "alerts": []})
    try:
        return jsonify(json.loads(row["content"]))
    except Exception:
        return jsonify({"alerts": [row.get("content", "")]})


@app.route("/api/insights/refresh", methods=["POST"])
def refresh_insights():
    content = ai.generate_hourly_insights()
    try:
        return jsonify(json.loads(content))
    except Exception:
        return jsonify({"alerts": [content]})


# ── Daily summary ─────────────────────────────────────────────────────────

@app.route("/api/summary")
def summary():
    return jsonify(db.get_daily_summary())


@app.route("/api/summary/generate", methods=["POST"])
def generate_summary():
    text = ds.generate()
    return jsonify({"summary": text})


# ── Chat ─────────────────────────────────────────────────────────────────

@app.route("/api/chat/history")
def chat_history():
    return jsonify(db.get_chat_history(100))


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    msg  = (body.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    reply = chat_handler.send_message(msg)
    return jsonify({"reply": reply})


# ── Notes ─────────────────────────────────────────────────────────────────

@app.route("/api/notes", methods=["POST"])
def add_note():
    body = request.get_json(force=True)
    content = (body.get("content") or "").strip()
    if not content:
        return jsonify({"error": "empty"}), 400
    db.insert_note(content, source="note")
    return jsonify({"ok": True})


# ── Calibration ──────────────────────────────────────────────────────────────

# Live-test shared state (in-memory, one test at a time)
_live_test = {"running": False, "type": None, "events": [], "elapsed": 0, "duration": 30}
_live_test_lock = threading.Lock()


@app.route("/api/calibration/scan/start", methods=["POST"])
def calib_scan_start():
    if cam_disc.get_scan_state().get("running"):
        return jsonify({"ok": False, "error": "Scan already running"})
    cam_disc.start_scan()
    return jsonify({"ok": True})


@app.route("/api/calibration/scan/status")
def calib_scan_status():
    state = cam_disc.get_scan_state()
    return jsonify({
        "running":  state["running"],
        "done":     state["done"],
        "progress": state["progress"],
        "total":    state["total"],
        "results":  state["results"],
    })


@app.route("/api/calibration/camera/test", methods=["POST"])
def calib_camera_test():
    body   = request.get_json(force=True) or {}
    mode   = body.get("mode", "webcam")
    source = str(body.get("source", "0"))
    result = cam_disc.test_camera(mode, source)
    return jsonify(result)


@app.route("/api/calibration/camera/add", methods=["POST"])
def calib_camera_add():
    body   = request.get_json(force=True) or {}
    name   = body.get("name", "Camera")
    mode   = body.get("mode", "webcam")
    source = str(body.get("source", "0"))
    width  = int(body.get("width", 1920))
    height = int(body.get("height", 1080))
    cam_id = db.add_camera(name, mode, source, width, height)
    return jsonify({"ok": True, "camera_id": cam_id})


@app.route("/api/calibration/cameras")
def calib_cameras():
    cameras = db.get_cameras()
    for c in cameras:
        c["zones"]         = db.get_zones(c["id"])
        c["entrance_line"] = db.get_entrance_line(c["id"])
        c["queue_config"]  = db.get_queue_config(c["id"])
    return jsonify(cameras)


@app.route("/api/calibration/camera/<int:cam_id>", methods=["DELETE"])
def calib_camera_delete(cam_id):
    db.delete_camera(cam_id)
    return jsonify({"ok": True})


@app.route("/api/calibration/analyse/<int:cam_id>", methods=["POST"])
def calib_analyse(cam_id):
    cameras = db.get_cameras()
    cam = next((c for c in cameras if c["id"] == cam_id), None)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    frame = cam_disc.capture_frame(cam["mode"], cam["source"])
    if not frame:
        return jsonify({"error": "Could not capture frame from camera"}), 400

    analysis = scene_ai.analyse_scene(frame)
    if "error" in analysis:
        return jsonify({"error": analysis["error"]}), 500

    return jsonify({"ok": True, "analysis": analysis, "frame": frame})


@app.route("/api/calibration/zones/save", methods=["POST"])
def calib_zones_save():
    body      = request.get_json(force=True) or {}
    camera_id = body.get("camera_id")
    zones     = body.get("zones", [])
    if not camera_id:
        return jsonify({"error": "camera_id required"}), 400
    db.save_zones(camera_id, zones)
    return jsonify({"ok": True})


@app.route("/api/calibration/entrance/save", methods=["POST"])
def calib_entrance_save():
    body      = request.get_json(force=True) or {}
    camera_id = body.get("camera_id")
    line      = body.get("line")
    if not camera_id or not line:
        return jsonify({"error": "camera_id and line required"}), 400
    db.save_entrance_line(camera_id, line)
    return jsonify({"ok": True})


@app.route("/api/calibration/queue/save", methods=["POST"])
def calib_queue_save():
    body      = request.get_json(force=True) or {}
    camera_id = body.get("camera_id")
    db.save_queue_config(camera_id, body.get("min_people", 2), body.get("min_dwell_seconds", 30))
    return jsonify({"ok": True})


@app.route("/api/calibration/cross-reference", methods=["POST"])
def calib_cross_ref():
    body = request.get_json(force=True) or {}
    ids  = body.get("camera_ids", [])
    if len(ids) < 2:
        return jsonify({"error": "Need at least 2 camera IDs"}), 400

    cameras = {c["id"]: c for c in db.get_cameras()}
    cam1 = cameras.get(ids[0])
    cam2 = cameras.get(ids[1])
    if not cam1 or not cam2:
        return jsonify({"error": "Camera not found"}), 404

    f1 = cam_disc.capture_frame(cam1["mode"], cam1["source"])
    f2 = cam_disc.capture_frame(cam2["mode"], cam2["source"])
    if not f1 or not f2:
        return jsonify({"error": "Could not capture frames from both cameras"}), 400

    result = scene_ai.cross_reference(f1, f2)
    if "error" not in result:
        import json as _json
        db.save_camera_relationship(ids[0], ids[1], _json.dumps(result))

    return jsonify({"ok": True, "result": result, "frames": [f1, f2]})


# ── Live calibration tests ────────────────────────────────────────────────────

def _run_live_test(test_type: str, camera_id: int, duration: int):
    """Background thread for queue / entrance live tests."""
    global _live_test
    start  = time.time()
    prev_count = None
    queue_start = None
    q_cfg = db.get_queue_config(camera_id)

    with _live_test_lock:
        _live_test = {"running": True, "type": test_type, "events": [], "elapsed": 0, "duration": duration}

    while time.time() - start < duration:
        elapsed = time.time() - start
        det = db.get_latest_detection()
        count = det.get("people_count", 0) if det else 0

        events = []

        if test_type == "queue":
            threshold = q_cfg.get("min_people", 2)
            dwell     = q_cfg.get("min_dwell_seconds", 30)
            if count >= threshold:
                if queue_start is None:
                    queue_start = time.time()
                elif time.time() - queue_start >= dwell:
                    events.append({
                        "t": round(elapsed, 1),
                        "type": "queue_event",
                        "count": count,
                        "msg": f"Queue of {count} people (≥{dwell}s)"
                    })
                    queue_start = None  # reset after recording
            else:
                queue_start = None

        elif test_type == "entrance":
            if prev_count is not None and count != prev_count:
                diff = count - prev_count
                events.append({
                    "t": round(elapsed, 1),
                    "type": "entry" if diff > 0 else "exit",
                    "delta": abs(diff),
                    "msg": f"{'Entry' if diff > 0 else 'Exit'} ×{abs(diff)}"
                })
            prev_count = count

        with _live_test_lock:
            _live_test["elapsed"] = round(elapsed, 1)
            _live_test["events"].extend(events)

        time.sleep(2)

    with _live_test_lock:
        _live_test["running"] = False


@app.route("/api/calibration/test/start", methods=["POST"])
def calib_test_start():
    body      = request.get_json(force=True) or {}
    test_type = body.get("type", "queue")  # "queue" | "entrance"
    camera_id = body.get("camera_id", 1)
    duration  = int(body.get("duration", 30))

    with _live_test_lock:
        if _live_test.get("running"):
            return jsonify({"error": "A test is already running"}), 400

    t = threading.Thread(target=_run_live_test, args=(test_type, camera_id, duration), daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/calibration/test/status")
def calib_test_status():
    with _live_test_lock:
        return jsonify(dict(_live_test))


@app.route("/api/calibration/data")
def calib_data():
    return jsonify(db.get_calibration_summary())


@app.route("/api/calibration/complete", methods=["POST"])
def calib_complete():
    db.set_config("calibration_complete", "true")
    return jsonify({"ok": True})


# ── Setup / onboarding ────────────────────────────────────────────────────

@app.route("/api/setup/status")
def setup_status():
    return jsonify({"setup_complete": db.is_setup_complete()})


@app.route("/api/setup", methods=["POST"])
def setup():
    data = request.get_json(force=True) or {}
    for key, value in data.items():
        if value is not None and str(value).strip():
            db.set_config(key, str(value))
    return jsonify({"ok": True})


@app.route("/api/setup/geocode")
def setup_geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    try:
        r = req.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 10, "language": "en", "format": "json"},
            timeout=5,
        )
        return jsonify(r.json())
    except Exception:
        return jsonify({"results": []})


# ── Live tracker (webcam + HOG + line crossing) ───────────────────────────────

def _mjpeg_generator():
    """Yield MJPEG frames for the /api/stream endpoint."""
    while True:
        frame = tracker.get_frame()
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(0.04)


@app.route("/api/stream")
def video_stream():
    """MJPEG live stream from the tracker."""
    tracker.start()   # idempotent — starts only if not already running
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/tracker/counts")
def tracker_counts():
    tracker.start()
    return jsonify(tracker.get_counts())


@app.route("/api/tracker/line", methods=["POST"])
def tracker_set_line():
    body = request.get_json(force=True) or {}
    y = body.get("y", 0.55)
    tracker.set_line(y)
    return jsonify({"ok": True, "line_y": tracker.get_counts()["line_y"]})


@app.route("/api/tracker/reset", methods=["POST"])
def tracker_reset():
    tracker.reset()
    return jsonify({"ok": True})


@app.route("/api/staff/in", methods=["POST"])
def staff_checkin():
    tracker.start()
    tracker.staff_in()
    return jsonify({"ok": True, "staff_in_store": tracker.get_staff_count()})


@app.route("/api/staff/out", methods=["POST"])
def staff_checkout():
    tracker.start()
    tracker.staff_out()
    return jsonify({"ok": True, "staff_in_store": tracker.get_staff_count()})


@app.route("/api/staff/count")
def staff_count():
    return jsonify({"staff_in_store": tracker.get_staff_count()})


# ── Arlo camera auth ──────────────────────────────────────────────────────

@app.route("/api/arlo/connect", methods=["POST"])
def arlo_connect():
    """
    Start Arlo login. Returns {session_id, needs_2fa, cameras?}.
    If needs_2fa is true, call /api/arlo/verify next.
    """
    data  = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip()
    pw    = (data.get("password") or "").strip()
    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400
    try:
        result = arlo_cam.login(email, pw)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/arlo/verify", methods=["POST"])
def arlo_verify():
    """Submit 2FA code. Returns {cameras: [...]}."""
    data       = request.get_json(force=True) or {}
    session_id = data.get("session_id", "")
    code       = data.get("code", "")
    if not session_id or not code:
        return jsonify({"error": "session_id and code required"}), 400
    try:
        result = arlo_cam.submit_2fa(session_id, code)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/arlo/snapshot/<session_id>/<device_id>")
def arlo_snapshot(session_id, device_id):
    """Return a live snapshot from an Arlo camera as base64 JPEG."""
    frame = arlo_cam.get_snapshot(session_id, device_id)
    if not frame:
        return jsonify({"error": "No snapshot available"}), 503
    return jsonify({"frame": frame})


# ── Meta ─────────────────────────────────────────────────────────────────

@app.route("/api/config")
def config_info():
    cfg = db.get_all_config()
    return jsonify({
        "store_name":    cfg.get("store_name") or STORE_NAME,
        "setup_complete": db.is_setup_complete(),
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ── SPA static serving (for local installs: python main.py → localhost:5050) ─

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if path.startswith("api/"):
        return jsonify({"error": "not found"}), 404
    if not os.path.exists(DIST):
        return jsonify({"info": "frontend not built — run npm run build in retailiq/frontend"}), 200
    target = os.path.join(DIST, path)
    if path and os.path.exists(target) and not os.path.isdir(target):
        return send_from_directory(DIST, path)
    return send_from_directory(DIST, "index.html")

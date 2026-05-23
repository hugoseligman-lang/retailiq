import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import detector
import database as db
import daily_summary as ds
import ai_insights as ai
import chat_handler
from config import STORE_NAME

app = Flask(__name__)
CORS(app)


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


# ── Meta ─────────────────────────────────────────────────────────────────

@app.route("/api/config")
def config_info():
    return jsonify({"store_name": STORE_NAME})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

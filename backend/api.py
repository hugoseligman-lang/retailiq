from flask import Flask, jsonify
from flask_cors import CORS
import detector
import database as db

app = Flask(__name__)
CORS(app)


@app.route("/api/live")
def live():
    """Current people count and zone breakdown."""
    return jsonify(detector.get_latest_result())


@app.route("/api/hourly")
def hourly():
    """Hourly traffic breakdown for today."""
    rows = db.get_hourly_today()
    # Fill in all 24 hours so the chart always has a full x-axis
    hourly_map = {r["hour"]: r for r in rows}
    full = []
    for h in range(24):
        key = f"{h:02d}"
        if key in hourly_map:
            full.append(hourly_map[key])
        else:
            full.append({"hour": key, "peak_count": 0, "avg_count": 0, "samples": 0})
    return jsonify(full)


@app.route("/api/zones")
def zones():
    """Aggregated zone totals for today."""
    return jsonify(db.get_zone_totals_today())


@app.route("/api/stats")
def stats():
    """Today's summary stats: peak count, total detections, peak hour."""
    return jsonify(db.get_stats_today())


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

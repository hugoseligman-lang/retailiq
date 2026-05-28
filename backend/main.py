"""
RetailIQ — full backend entry point.
Starts: camera detector, hourly AI insights scheduler, daily summary scheduler, Flask API.
"""
import signal
import sys
import threading
import time
from datetime import datetime

import database as db
import detector
import ai_insights
import daily_summary
from api import app
from config import FLASK_HOST, FLASK_PORT, DAY_END_TIME


def _scheduler():
    last_insight_hour = -1
    summary_generated_today = None

    while True:
        now = datetime.now()
        # Hourly insights — fire at the top of each hour
        if now.hour != last_insight_hour:
            try:
                ai_insights.generate_hourly_insights()
            except Exception as e:
                print(f"[scheduler] Insights error: {e}")
            last_insight_hour = now.hour

        # Daily summary — fire at DAY_END_TIME once per day
        hh, mm = map(int, DAY_END_TIME.split(":"))
        if now.hour == hh and now.minute == mm and summary_generated_today != now.date():
            try:
                daily_summary.generate()
                summary_generated_today = now.date()
            except Exception as e:
                print(f"[scheduler] Daily summary error: {e}")

        time.sleep(30)


def handle_shutdown(sig, frame):
    print("\n[main] Shutting down...")
    detector.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("[main] Initialising database...")
    db.init_db()

    print("[main] Starting camera detector...")
    detector.start(daemon=True)

    print("[main] Starting scheduler (insights + summary)...")
    t = threading.Thread(target=_scheduler, daemon=True)
    t.start()

    print(f"[main] API server -> http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)

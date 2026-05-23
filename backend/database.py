import sqlite3
import json
from datetime import date, datetime, timedelta
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        -- Raw detections (today only — reset at midnight)
        CREATE TABLE IF NOT EXISTS detections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
            people_count    INTEGER NOT NULL DEFAULT 0,
            passerby_count  INTEGER NOT NULL DEFAULT 0,
            zone_left       INTEGER NOT NULL DEFAULT 0,
            zone_center     INTEGER NOT NULL DEFAULT 0,
            zone_right      INTEGER NOT NULL DEFAULT 0,
            queue_length    INTEGER NOT NULL DEFAULT 0,
            busiest_zone    TEXT,
            weather_temp    REAL,
            weather_code    INTEGER
        );

        -- Historical (aggregated 30-min buckets, 12-month retention)
        CREATE TABLE IF NOT EXISTS historical (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE NOT NULL,
            hour            INTEGER NOT NULL,
            bucket          INTEGER NOT NULL,   -- 0 or 30 (minute)
            avg_people      REAL DEFAULT 0,
            max_people      INTEGER DEFAULT 0,
            total_passersby INTEGER DEFAULT 0,
            avg_zone_left   REAL DEFAULT 0,
            avg_zone_center REAL DEFAULT 0,
            avg_zone_right  REAL DEFAULT 0,
            max_queue       INTEGER DEFAULT 0,
            avg_queue       REAL DEFAULT 0,
            queue_events    INTEGER DEFAULT 0,
            weather_temp    REAL,
            weather_code    INTEGER,
            day_of_week     INTEGER,
            is_holiday      INTEGER DEFAULT 0
        );

        -- Weather observations
        CREATE TABLE IF NOT EXISTS weather (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            code        INTEGER,
            condition   TEXT,
            wind_speed  REAL,
            precipitation REAL,
            humidity    REAL
        );

        -- Store owner notes + chat context
        CREATE TABLE IF NOT EXISTS store_notes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            content   TEXT NOT NULL,
            source    TEXT DEFAULT 'note'
        );

        -- Chat message history
        CREATE TABLE IF NOT EXISTS chat_messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL
        );

        -- AI insights (hourly pattern analysis)
        CREATE TABLE IF NOT EXISTS ai_insights (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            content      TEXT NOT NULL
        );

        -- Daily AI summaries
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         DATE NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            summary      TEXT NOT NULL
        );
        """)
        conn.commit()


# ── Detections ─────────────────────────────────────────────────────────────

def insert_detection(d: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO detections
               (people_count, passerby_count, zone_left, zone_center, zone_right,
                queue_length, busiest_zone, weather_temp, weather_code)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["people_count"], d["passerby_count"], d["zone_left"],
             d["zone_center"], d["zone_right"], d["queue_length"],
             d["busiest_zone"], d.get("weather_temp"), d.get("weather_code"))
        )
        conn.commit()


def get_latest_detection():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM detections ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


def get_today_stats():
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)            AS total_readings,
                MAX(people_count)   AS peak_people,
                SUM(passerby_count) AS total_passersby,
                AVG(people_count)   AS avg_people,
                MAX(queue_length)   AS longest_queue,
                AVG(CASE WHEN queue_length > 0 THEN queue_length END) AS avg_queue,
                SUM(CASE WHEN queue_length >= ? THEN 1 ELSE 0 END) AS queue_events
            FROM detections
        """, (2,)).fetchone()

        # Peak 30-min window
        peak_row = conn.execute("""
            SELECT
                strftime('%H', timestamp)                     AS hour,
                CASE WHEN CAST(strftime('%M',timestamp) AS INTEGER) < 30
                     THEN 0 ELSE 30 END                       AS bucket,
                AVG(people_count)                             AS avg_p
            FROM detections
            GROUP BY hour, bucket
            ORDER BY avg_p DESC
            LIMIT 1
        """).fetchone()

        # Total unique visitors (in-store)
        visit_row = conn.execute("""
            SELECT SUM(people_count) AS total_visitors FROM detections
        """).fetchone()

        # Zone dwell estimates (person-seconds per zone)
        zone_row = conn.execute("""
            SELECT
                AVG(zone_left)   AS avg_left,
                AVG(zone_center) AS avg_center,
                AVG(zone_right)  AS avg_right
            FROM detections
        """).fetchone()

    stats = dict(row) if row else {}
    stats["peak_window"] = f"{peak_row['hour']}:{str(peak_row['bucket']).zfill(2)}" if peak_row and peak_row["hour"] else "N/A"
    stats["total_visitors"] = int(visit_row["total_visitors"] or 0)
    stats["avg_zone_left"]   = round(float(zone_row["avg_left"]   or 0), 1)
    stats["avg_zone_center"] = round(float(zone_row["avg_center"] or 0), 1)
    stats["avg_zone_right"]  = round(float(zone_row["avg_right"]  or 0), 1)

    total = stats["total_visitors"] + int(stats.get("total_passersby") or 0)
    stats["conversion_rate"] = round(stats["total_visitors"] / total * 100, 1) if total > 0 else 0
    return stats


def get_hourly_today():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%H', timestamp)  AS hour,
                AVG(people_count)          AS avg_count,
                MAX(people_count)          AS peak_count,
                SUM(passerby_count)        AS passersby,
                MAX(queue_length)          AS max_queue,
                weather_temp, weather_code
            FROM detections
            GROUP BY hour
            ORDER BY hour
        """).fetchall()
    return [dict(r) for r in rows]


def get_hourly_for_date(target_date: str):
    """Used for chart overlays (yesterday, last week, last month)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT hour, avg_people, max_people, total_passersby,
                   max_queue, weather_temp, weather_code
            FROM historical
            WHERE date = ?
            ORDER BY hour, bucket
        """, (target_date,)).fetchall()
    return [dict(r) for r in rows]


def get_heatmap_data(period: str):
    """Return zone sums for today / this week / this month."""
    if period == "today":
        with get_conn() as conn:
            row = conn.execute("""
                SELECT SUM(zone_left)   AS left_total,
                       SUM(zone_center) AS center_total,
                       SUM(zone_right)  AS right_total
                FROM detections
            """).fetchone()
        return dict(row) if row else {}
    else:
        if period == "week":
            cutoff = (date.today() - timedelta(days=7)).isoformat()
        else:
            cutoff = (date.today() - timedelta(days=30)).isoformat()
        with get_conn() as conn:
            row = conn.execute("""
                SELECT SUM(avg_zone_left)   AS left_total,
                       SUM(avg_zone_center) AS center_total,
                       SUM(avg_zone_right)  AS right_total
                FROM historical
                WHERE date >= ?
            """, (cutoff,)).fetchone()
        return dict(row) if row else {}


# ── Midnight reset ──────────────────────────────────────────────────────────

def midnight_rollover(day_of_week: int, is_holiday: bool):
    """Aggregate today's detections into historical, then clear today."""
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO historical
                (date, hour, bucket,
                 avg_people, max_people, total_passersby,
                 avg_zone_left, avg_zone_center, avg_zone_right,
                 max_queue, avg_queue, queue_events,
                 weather_temp, weather_code, day_of_week, is_holiday)
            SELECT
                DATE(timestamp)                                            AS date,
                CAST(strftime('%H', timestamp) AS INTEGER)                AS hour,
                CASE WHEN CAST(strftime('%M',timestamp) AS INTEGER) < 30
                     THEN 0 ELSE 30 END                                   AS bucket,
                AVG(people_count), MAX(people_count), SUM(passerby_count),
                AVG(zone_left), AVG(zone_center), AVG(zone_right),
                MAX(queue_length), AVG(queue_length),
                SUM(CASE WHEN queue_length >= 2 THEN 1 ELSE 0 END),
                AVG(weather_temp), MAX(weather_code),
                ?, ?
            FROM detections
            WHERE DATE(timestamp) = ?
            GROUP BY date, hour, bucket
        """, (day_of_week, 1 if is_holiday else 0, today))

        # Delete detections older than today
        conn.execute("DELETE FROM detections WHERE DATE(timestamp) < DATE('now')")

        # Prune historical older than 12 months
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        conn.execute("DELETE FROM historical WHERE date < ?", (cutoff,))
        conn.commit()


# ── Weather ─────────────────────────────────────────────────────────────────

def insert_weather(w: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO weather (temperature, code, condition, wind_speed, precipitation, humidity)
               VALUES (?,?,?,?,?,?)""",
            (w.get("temperature"), w.get("code"), w.get("condition"),
             w.get("wind_speed"), w.get("precipitation"), w.get("humidity"))
        )
        conn.commit()


def get_current_weather():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM weather ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


# ── Notes / Chat ────────────────────────────────────────────────────────────

def insert_note(content: str, source: str = "note"):
    with get_conn() as conn:
        conn.execute("INSERT INTO store_notes (content, source) VALUES (?,?)", (content, source))
        conn.commit()


def get_notes_since(days: int):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM store_notes WHERE timestamp >= ? ORDER BY timestamp",
            (cutoff,)
        ).fetchall()
    return [dict(r) for r in rows]


def insert_chat(role: str, content: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO chat_messages (role, content) VALUES (?,?)", (role, content))
        conn.commit()


def get_chat_history(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


# ── AI insights ─────────────────────────────────────────────────────────────

def insert_insight(content: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO ai_insights (content) VALUES (?)", (content,))
        conn.commit()


def get_latest_insight():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ai_insights ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


def insert_daily_summary(summary: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_summaries (date, summary) VALUES (DATE('now'),?)", (summary,)
        )
        conn.commit()


def get_daily_summary():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_summaries ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


# ── Historical summaries for AI context ─────────────────────────────────────

def get_history_summary(days: int = 7):
    """Return per-day aggregates for AI context."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT date,
                   AVG(avg_people)      AS avg_people,
                   MAX(max_people)      AS peak_people,
                   SUM(total_passersby) AS passersby,
                   MAX(max_queue)       AS peak_queue,
                   SUM(queue_events)    AS queue_events,
                   AVG(weather_temp)    AS avg_temp,
                   day_of_week, is_holiday
            FROM historical
            WHERE date >= ?
            GROUP BY date
            ORDER BY date
        """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]

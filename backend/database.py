import sqlite3
from datetime import datetime, date
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP,
                people_count INTEGER NOT NULL,
                zone_left    INTEGER NOT NULL DEFAULT 0,
                zone_center  INTEGER NOT NULL DEFAULT 0,
                zone_right   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def insert_detection(people_count: int, zone_left: int, zone_center: int, zone_right: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO detections (people_count, zone_left, zone_center, zone_right) VALUES (?, ?, ?, ?)",
            (people_count, zone_left, zone_center, zone_right),
        )
        conn.commit()


def get_latest():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM detections ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {"people_count": 0, "zone_left": 0, "zone_center": 0, "zone_right": 0}


def get_hourly_today():
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%H', timestamp) AS hour,
                   MAX(people_count)         AS peak_count,
                   AVG(people_count)         AS avg_count,
                   COUNT(*)                  AS samples
            FROM detections
            WHERE DATE(timestamp) = ?
            GROUP BY hour
            ORDER BY hour
            """,
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_zone_totals_today():
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT SUM(zone_left)   AS total_left,
                   SUM(zone_center) AS total_center,
                   SUM(zone_right)  AS total_right
            FROM detections
            WHERE DATE(timestamp) = ?
            """,
            (today,),
        ).fetchone()
    return dict(row) if row else {"total_left": 0, "total_center": 0, "total_right": 0}


def get_stats_today():
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT strftime('%M', timestamp) || strftime('%H', timestamp)) AS total_visitors,
                   MAX(people_count) AS peak_count
            FROM detections
            WHERE DATE(timestamp) = ?
            """,
            (today,),
        ).fetchone()

        peak_hour_row = conn.execute(
            """
            SELECT strftime('%H', timestamp) AS hour, AVG(people_count) AS avg_count
            FROM detections
            WHERE DATE(timestamp) = ?
            GROUP BY hour
            ORDER BY avg_count DESC
            LIMIT 1
            """,
            (today,),
        ).fetchone()

        total_row = conn.execute(
            "SELECT SUM(people_count) AS total FROM detections WHERE DATE(timestamp) = ?",
            (today,),
        ).fetchone()

    stats = {
        "peak_count": row["peak_count"] or 0,
        "total_detections": total_row["total"] or 0,
        "peak_hour": f"{peak_hour_row['hour']}:00" if peak_hour_row and peak_hour_row["hour"] else "N/A",
    }
    return stats

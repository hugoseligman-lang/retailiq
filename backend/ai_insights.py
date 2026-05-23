"""Hourly AI insights — runs once per hour, analyses last 7 days."""
import json
import anthropic
import database as db
from weather import condition_label
from config import STORE_NAME, CLAUDE_MODEL, ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = f"""You are a retail analytics AI for {STORE_NAME}.
You analyse foot traffic data, queue patterns, zone usage, and store owner notes to surface
actionable insights. Be specific, concise, and always reference the actual data.
Format your response as JSON with these keys:
  patterns     — array of strings (recurring patterns identified)
  anomalies    — array of strings (anything >25% above/below average for its time slot)
  comparisons  — object with keys: today_vs_yesterday, vs_last_week, vs_last_month, rainy_vs_sunny
  alerts       — array of strings (urgent items needing attention)
"""


def generate_hourly_insights() -> str:
    history = db.get_history_summary(7)
    notes   = db.get_notes_since(7)
    today   = db.get_today_stats()
    hourly  = db.get_hourly_today()
    weather = db.get_current_weather()

    history_text = "\n".join([
        f"  {r['date']} (dow={r['day_of_week']}, holiday={r['is_holiday']}): "
        f"avg={r['avg_people']:.1f}, peak={r['peak_people']}, passersby={r['passersby']}, "
        f"queue_events={r['queue_events']}, temp={r['avg_temp']}"
        for r in history
    ]) or "  No historical data yet."

    notes_text = "\n".join([f"  [{n['timestamp']}] {n['content']}" for n in notes]) or "  None."

    hourly_text = "\n".join([
        f"  {h['hour']}:00 — avg={h['avg_count']:.1f}, peak={h['peak_count']}, "
        f"passersby={h['passersby']}, queue={h['max_queue']}"
        for h in hourly
    ]) or "  No hourly data yet."

    user_msg = f"""Analyse this retail traffic data and return JSON insights.

TODAY'S STATS:
  Visitors: {today.get('total_visitors',0)}
  Passersby: {today.get('total_passersby',0)}
  Conversion rate: {today.get('conversion_rate',0)}%
  Peak window: {today.get('peak_window','N/A')}
  Longest queue: {today.get('longest_queue',0)}
  Queue events: {today.get('queue_events',0)}

TODAY'S HOURLY BREAKDOWN:
{hourly_text}

LAST 7 DAYS DAILY SUMMARY:
{history_text}

CURRENT WEATHER: {weather.get('condition','unknown')}, {weather.get('temperature','?')}°C

STORE OWNER NOTES (last 7 days):
{notes_text}

Flag any hour-slot anomalies where today's count differs >25% from the average for that slot
across the last 7 days. Identify recurring queue times, dead zones, and conversion patterns."""

    resp = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    content = resp.content[0].text
    # Validate JSON — if invalid, wrap it
    try:
        json.loads(content)
    except Exception:
        content = json.dumps({"patterns": [], "anomalies": [], "comparisons": {}, "alerts": [content]})

    db.insert_insight(content)
    print("[insights] Hourly analysis complete")
    return content

"""Hourly AI insights — runs once per hour, analyses last 7 days."""
import json
import re
import anthropic
import database as db
from config import STORE_NAME, CLAUDE_MODEL, ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = f"""You are a retail analytics AI for {STORE_NAME}, a café.

Your job is to analyse real foot traffic data and give the owner genuinely useful insights.
Only comment on metrics where you actually have data — do not fabricate comparisons or patterns
if the data doesn't exist yet. If it's early days with little data, say so plainly and focus
on what you CAN see.

Rules:
- Never output markdown, code blocks, or backticks — return raw JSON only
- Only include a key if you have something real to say about it
- Be specific and direct — talk like a smart business analyst, not a generic AI
- For a café: think about morning rush, lunch peak, queue at POS, weather impact on walk-ins

Return a JSON object with these keys (omit any key you have nothing useful to say):
  summary      — string: 2-3 sentence plain-English overview of what the data shows right now
  patterns     — array of strings: real recurring patterns you can identify from the data
  anomalies    — array of strings: hours where today deviates >25% from the same-slot average
  zone_analysis — string: what the zone activity distribution tells us about customer behaviour
  alerts       — array of strings: only genuinely urgent items (queue backing up, data gap, etc)
  weather_note  — string: only if weather is meaningfully affecting traffic today
"""


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences Claude sometimes wraps around JSON."""
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*',     '', text)
    text = re.sub(r'\s*```$',     '', text)
    return text.strip()


def generate_hourly_insights() -> str:
    history = db.get_history_summary(7)
    notes   = db.get_notes_since(7)
    today   = db.get_today_stats()
    hourly  = db.get_hourly_today()
    weather = db.get_current_weather()

    has_history = len(history) > 0
    has_hourly  = any(h.get('avg_count', 0) > 0 for h in hourly)

    history_text = "\n".join([
        f"  {r['date']} (dow={r['day_of_week']}, holiday={r['is_holiday']}): "
        f"visitors={r.get('avg_people',0):.1f}, peak={r.get('peak_people',0)}, "
        f"queue_events={r.get('queue_events',0)}, temp={r.get('avg_temp','?')}°C"
        for r in history
    ]) if has_history else "  No historical data yet — system just started."

    notes_text = "\n".join([
        f"  [{n['timestamp']}] {n['content']}" for n in notes
    ]) if notes else "  None."

    hourly_text = "\n".join([
        f"  {h['hour']}:00 — visitors={h['avg_count']:.1f}, peak={h['peak_count']}, "
        f"passersby={h['passersby']}, queue={h['max_queue']}"
        for h in hourly if h.get('avg_count', 0) > 0 or h.get('peak_count', 0) > 0
    ]) if has_hourly else "  No visitor data recorded yet today."

    # Zone activity
    live = db.get_latest_snapshot() if hasattr(db, 'get_latest_snapshot') else {}
    zone_left   = live.get('zone_left', 0)   if live else 0
    zone_center = live.get('zone_center', 0) if live else 0
    zone_right  = live.get('zone_right', 0)  if live else 0
    zone_total  = zone_left + zone_center + zone_right
    if zone_total > 0:
        zone_text = (f"  Left={zone_left} ({zone_left/zone_total*100:.0f}%), "
                     f"Centre={zone_center} ({zone_center/zone_total*100:.0f}%), "
                     f"Right={zone_right} ({zone_right/zone_total*100:.0f}%)")
    else:
        zone_text = "  No zone data yet."

    user_msg = f"""Analyse this café traffic data. Only comment on what you can actually see.

TODAY SO FAR:
  Visitors in: {today.get('total_visitors', 0)}
  Passersby (didn't enter): {today.get('total_passersby', 0)}
  Conversion rate: {today.get('conversion_rate', 0):.1f}%
  Peak window: {today.get('peak_window', 'none yet')}
  Queue events today: {today.get('queue_events', 0)}
  Longest queue seen: {today.get('longest_queue', 0)} people

HOURLY BREAKDOWN (hours with activity only):
{hourly_text}

ZONE DISTRIBUTION (where in-frame people appear):
{zone_text}

WEATHER NOW: {weather.get('condition', 'unknown')}, {weather.get('temperature', '?')}°C,
  precipitation={weather.get('precipitation', 0)}mm, wind={weather.get('wind_speed', '?')}km/h

LAST 7 DAYS:
{history_text}

OWNER NOTES:
{notes_text}

Analyse what you can actually see. If there's limited data because the system just started,
say that and focus on the real-time snapshot. Be a useful analyst, not a generic AI."""

    resp = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = _strip_markdown(resp.content[0].text)

    # Validate — if Claude still returned non-JSON, wrap summary
    try:
        json.loads(raw)
        content = raw
    except Exception:
        content = json.dumps({
            "summary": raw[:500] if len(raw) < 500 else "Analysis generated — see alerts for details.",
            "alerts":  [raw] if len(raw) < 800 else []
        })

    db.insert_insight(content)
    print("[insights] Hourly analysis complete")
    return content

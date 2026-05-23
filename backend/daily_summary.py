"""End-of-day AI summary — generated at DAY_END_TIME or on demand."""
import anthropic
import database as db
from config import STORE_NAME, CLAUDE_MODEL, ANTHROPIC_API_KEY
from datetime import date

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = f"""You are a retail analytics AI summarising the trading day for {STORE_NAME}.
Write a clear, readable end-of-day summary formatted with these sections (use these exact headings):

**Today's Headline**
One sentence capturing the day.

**What Went Well**
2-3 bullet points.

**What Needs Attention**
2-3 bullet points.

**Recommended Actions**
Numbered list, specific and actionable based on the store's actual data.

**Weather Impact**
How today's weather influenced traffic or conversion.

**Trend Watch**
One or two emerging patterns worth monitoring this week.

Reference any store owner notes where relevant (e.g. "Following your window display change this morning...").
Be specific with numbers. Do not use jargon."""


def generate(today_stats: dict | None = None) -> str:
    stats   = today_stats or db.get_today_stats()
    hourly  = db.get_hourly_today()
    history = db.get_history_summary(30)
    notes   = db.get_notes_since(1)
    weather = db.get_current_weather()

    history_text = "\n".join([
        f"  {r['date']}: avg={r['avg_people']:.1f}, peak={r['peak_people']}, "
        f"passersby={r['passersby']}, queue_events={r['queue_events']}"
        for r in history
    ]) or "  No historical data."

    notes_text = "\n".join([f"  [{n['timestamp']}] {n['content']}" for n in notes]) or "  None today."

    hourly_text = "\n".join([
        f"  {h['hour']}:00 — avg {h['avg_count']:.1f} people, peak {h['peak_count']}, "
        f"queue {h['max_queue']}"
        for h in hourly
    ]) or "  No hourly data."

    user_msg = f"""Generate today's end-of-day retail summary for {STORE_NAME}.

TODAY ({date.today().strftime('%A %d %B %Y')}):
  Visitors: {stats.get('total_visitors', 0)}
  Passersby: {stats.get('total_passersby', 0)}
  Conversion rate: {stats.get('conversion_rate', 0)}%
  Peak 30-min window: {stats.get('peak_window', 'N/A')}
  Longest queue: {stats.get('longest_queue', 0)} people
  Queue events: {stats.get('queue_events', 0)}
  Avg zone traffic — Left: {stats.get('avg_zone_left', 0)}, Centre: {stats.get('avg_zone_center', 0)}, Right: {stats.get('avg_zone_right', 0)}

HOURLY BREAKDOWN:
{hourly_text}

LAST 30 DAYS CONTEXT:
{history_text}

WEATHER TODAY: {weather.get('condition', 'unknown')}, {weather.get('temperature', '?')}°C

STORE OWNER NOTES TODAY:
{notes_text}"""

    resp = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    summary = resp.content[0].text
    db.insert_daily_summary(summary)
    print("[daily_summary] Generated")
    return summary

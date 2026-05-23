"""Chat with store AI analyst — full context, persistent history."""
import anthropic
import database as db
from config import STORE_NAME, CLAUDE_MODEL, ANTHROPIC_API_KEY
from datetime import date

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = f"""You are a knowledgeable retail analyst for {STORE_NAME}. You know this store's data
inside out — its traffic patterns, busiest zones, queue behaviours, conversion rates, and the
owner's notes about events, changes, and constraints.

Rules:
- Always refer to the store's actual data. Use specific numbers.
- When the owner mentions a constraint (e.g. "can't add staff at lunch"), acknowledge it and
  propose alternative solutions using the data (layout changes, signage, promotions, timing shifts).
- Be practical and concise. No filler text.
- If asked why something happened, correlate with weather, day of week, notes, or known events.
- Messages are timestamped — use them for temporal context.
"""


def _build_context() -> str:
    stats   = db.get_today_stats()
    hourly  = db.get_hourly_today()
    history = db.get_history_summary(30)
    notes   = db.get_notes_since(14)
    weather = db.get_current_weather()

    history_text = "\n".join([
        f"  {r['date']}: avg_people={r['avg_people']:.1f}, peak={r['peak_people']}, "
        f"passersby={r['passersby']}, queue_events={r['queue_events']}, temp={r['avg_temp']}"
        for r in history
    ]) or "  No history yet."

    notes_text = "\n".join([
        f"  [{n['timestamp']}] {n['content']}"
        for n in notes
    ]) or "  No notes."

    hourly_text = "\n".join([
        f"  {h['hour']}:00 — avg {h['avg_count']:.1f} in-store, peak {h['peak_count']}"
        for h in hourly
    ]) or "  No hourly data yet."

    return f"""=== STORE CONTEXT ===
Store: {STORE_NAME}
Today: {date.today().strftime('%A %d %B %Y')}
Current weather: {weather.get('condition', '?')}, {weather.get('temperature', '?')}°C

TODAY'S STATS:
  Visitors: {stats.get('total_visitors', 0)} | Passersby: {stats.get('total_passersby', 0)}
  Conversion: {stats.get('conversion_rate', 0)}% | Peak window: {stats.get('peak_window', 'N/A')}
  Queue events: {stats.get('queue_events', 0)} | Longest queue: {stats.get('longest_queue', 0)}

TODAY HOURLY:
{hourly_text}

30-DAY HISTORY:
{history_text}

STORE OWNER NOTES (last 14 days):
{notes_text}
=== END CONTEXT ==="""


def send_message(user_text: str) -> str:
    # Save user message as a note and to chat history
    db.insert_note(user_text, source="chat")
    db.insert_chat("user", user_text)

    # Build messages for API — inject context as first user turn
    history = db.get_chat_history(limit=60)
    context = _build_context()

    messages = []
    # Prepend context to the very first user message
    for i, m in enumerate(history):
        if i == 0 and m["role"] == "user":
            messages.append({"role": "user", "content": f"{context}\n\n{m['content']}"})
        else:
            messages.append({"role": m["role"], "content": m["content"]})

    # If history is empty (shouldn't be since we just inserted), add context
    if not messages:
        messages = [{"role": "user", "content": f"{context}\n\n{user_text}"}]

    resp = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=SYSTEM,
        messages=messages,
    )
    reply = resp.content[0].text
    db.insert_chat("assistant", reply)
    return reply

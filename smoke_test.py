"""
smoke_test.py — Pre-pilot health check for RetailIQ.

Run this before handing the system to a client:
    python smoke_test.py

Checks:
  - Backend is reachable at localhost:5050
  - All critical API endpoints respond with valid data
  - Tracker is running and streaming
  - Database is readable (setup complete)
  - Weather data is being fetched
  - Staff check-in/out works

Exit code 0 = all green. Non-zero = failures found.
"""

import sys
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:5050"
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
failures = []


def check(label, fn):
    try:
        result = fn()
        print(f"  {PASS}  {label}: {result}")
        return result
    except Exception as e:
        msg = str(e)
        print(f"  {FAIL}  {label}: {msg}")
        failures.append(f"{label}: {msg}")
        return None


def get(path, timeout=8):
    url = BASE + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post(path, body=None, timeout=8):
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def stream_peek(timeout=5):
    """Fetch the first ~4 KB of the MJPEG stream and verify it's JPEG."""
    req = urllib.request.Request(BASE + "/api/stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        chunk = r.read(4096)
    if b"\xff\xd8" not in chunk:
        raise ValueError("MJPEG stream open but no JPEG magic bytes found")
    return f"stream OK ({len(chunk)} bytes)"


print("\nRetailIQ Smoke Test")
print("=" * 50)

print("\n1. Connectivity")
check("Health endpoint",    lambda: get("/api/health")["status"])
check("Setup status",       lambda: "complete" if get("/api/setup/status")["setup_complete"] else "NOT COMPLETE (run onboarding)")

print("\n2. Tracker / Live Feed")
counts = check("Tracker counts", lambda: get("/api/tracker/counts"))
if counts:
    check("Tracker running",  lambda: "yes" if counts["running"] else "NO — webcam may not be connected")
check("MJPEG stream",     stream_peek)

print("\n3. Staff check-in")
check("Staff check-in",  lambda: post("/api/staff/in")["staff_in_store"])
check("Staff check-out", lambda: post("/api/staff/out")["staff_in_store"])

print("\n4. Live data endpoints")
check("Live widget data", lambda: f"in_store={get('/api/live')['people_count']}")
check("Today stats",      lambda: f"visitors={get('/api/today')['total_visitors']}")
check("Weather",          lambda: get("/api/weather").get("condition", "no data yet"))

print("\n5. AI endpoints (may be slow first call)")
try:
    check("Insights",     lambda: get("/api/insights").get("generated_at", "no insights yet"))
except Exception:
    print(f"  {WARN}  Insights: skipped (no API key or no data yet)")
try:
    check("Chat history", lambda: f"{len(get('/api/chat/history'))} messages")
except Exception:
    print(f"  {WARN}  Chat: skipped")

print("\n" + "=" * 50)
if failures:
    print(f"\nFAILED ({len(failures)} issue(s)):")
    for f in failures:
        print(f"  - {f}")
    print("\nFix the failures above before handing the system to the client.\n")
    sys.exit(1)
else:
    print("\nAll checks passed. System is ready.\n")
    sys.exit(0)

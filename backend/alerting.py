"""
alerting.py — Email alerts when all camera feeds go dead.

Configure in .env:
  ALERT_EMAIL_TO   = hugo@meridianai.build
  ALERT_EMAIL_FROM = retailiq.alerts@gmail.com  (or any Gmail address)
  ALERT_EMAIL_PASS = <Gmail App Password>        (not your normal password)

To create a Gmail App Password:
  Google Account → Security → 2-Step Verification → App passwords
  Select "Mail" and generate a 16-character password.

Alert fires when ALL cameras have been offline for > ALERT_THRESHOLD_SECS.
After firing, waits ALERT_COOLDOWN_SECS before sending another alert.
"""

import os
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import frame_buffer

ALERT_TO        = os.getenv("ALERT_EMAIL_TO",   "hugo@meridianai.build")
ALERT_FROM      = os.getenv("ALERT_EMAIL_FROM", "")
ALERT_PASS      = os.getenv("ALERT_EMAIL_PASS", "")
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD_SECS", "120"))  # 2 min all cameras dead
ALERT_COOLDOWN  = int(os.getenv("ALERT_COOLDOWN_SECS",  "1800")) # max 1 alert per 30 min

_last_alert = 0.0
_lock       = threading.Lock()
_thread     = None
_stop_evt   = threading.Event()


def _can_send() -> bool:
    return bool(ALERT_FROM and ALERT_PASS)


def send_alert(subject: str, body: str) -> bool:
    """Send an email alert. Returns True on success."""
    if not _can_send():
        print(f"[alerting] Email not configured — would have sent: {subject}")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = ALERT_FROM
        msg["To"]      = ALERT_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(ALERT_FROM, ALERT_PASS)
            server.send_message(msg)

        print(f"[alerting] Alert sent → {ALERT_TO}: {subject}")
        return True
    except Exception as e:
        print(f"[alerting] Failed to send alert: {e}")
        return False


def _watch():
    """Background thread — monitors frame_buffer and fires alerts."""
    global _last_alert
    print("[alerting] Camera watchdog started")

    while not _stop_evt.is_set():
        time.sleep(30)
        try:
            status = frame_buffer.camera_status()
            if not status:
                # No cameras have ever pushed frames — don't alert yet
                continue

            all_stale = all(not v["fresh"] for v in status.values())
            if not all_stale:
                continue

            # All cameras are stale — check threshold
            worst_age = max(v["age_seconds"] for v in status.values())
            if worst_age < ALERT_THRESHOLD:
                continue

            with _lock:
                now = time.time()
                if now - _last_alert < ALERT_COOLDOWN:
                    continue
                _last_alert = now

            camera_lines = "\n".join(
                f"  {cam}: last frame {v['age_seconds']:.0f}s ago"
                for cam, v in status.items()
            )
            subject = "[RetailIQ] All cameras offline"
            body = (
                f"All RetailIQ camera feeds have been offline for >{ALERT_THRESHOLD}s.\n\n"
                f"Camera status:\n{camera_lines}\n\n"
                f"Check that camera_bridge_multi.py is still running at the café.\n"
                f"If the bridge crashed, restart it:\n"
                f"  cd /path/to/retailiq && python camera_bridge_multi.py\n"
            )
            send_alert(subject, body)

        except Exception as e:
            print(f"[alerting] Watchdog error: {e}")

    print("[alerting] Camera watchdog stopped")


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_evt.clear()
    _thread = threading.Thread(target=_watch, daemon=True, name="alerting")
    _thread.start()


def stop():
    _stop_evt.set()

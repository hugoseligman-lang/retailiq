"""
arlo_camera.py — Arlo cloud camera integration.

Flow:
  1. login(email, password) → {session_id, needs_2fa}
  2. if needs_2fa: submit_2fa(session_id, code) → {cameras}
  3. capture_snapshot(session_id, device_id) → base64 JPEG

Sessions persist for the server lifetime; pyaarlo saves auth tokens to disk
so re-starts after the first login don't need 2FA again.
"""

import threading
import time
import base64
import uuid
import queue
import builtins
import os
import io
import logging
from pathlib import Path

try:
    import pyaarlo
    PYAARLO_OK = True
except ImportError:
    PYAARLO_OK = False

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

# ── Session store ─────────────────────────────────────────────────────────────

_sessions: dict[str, "ArloSession"] = {}
_session_lock = threading.Lock()

# Storage dir for pyaarlo auth tokens (persisted across server restarts)
STORAGE_DIR = Path(os.path.dirname(__file__)) / ".arlo_state"
STORAGE_DIR.mkdir(exist_ok=True)

# Global lock so only one Arlo login runs at a time (avoids input() conflicts)
_login_lock = threading.Lock()


class ArloSession:
    def __init__(self, session_id: str, email: str, password: str):
        self.session_id  = session_id
        self.email       = email
        self.password    = password
        self.ar          = None
        self.cameras: list = []
        self.status      = "connecting"   # connecting | needs_2fa | connected | error
        self.error: str  = ""
        self._tfa_q      = queue.Queue()
        self._ready      = threading.Event()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── Login thread ──────────────────────────────────────────────────────────

    def _run(self):
        if not PYAARLO_OK:
            self.status = "error"
            self.error  = "pyaarlo not installed — run: pip install pyaarlo"
            self._ready.set()
            return

        # Serialise logins to avoid input() conflicts across sessions
        with _login_lock:
            orig_input = builtins.input

            def _fake_input(prompt=""):
                """Called by pyaarlo when 2FA code is needed."""
                self.status = "needs_2fa"
                self._ready.set()          # unblock the caller
                try:
                    code = self._tfa_q.get(timeout=300)  # 5-min window
                    return code
                except queue.Empty:
                    raise RuntimeError("Timed out waiting for 2FA code")

            builtins.input = _fake_input
            try:
                storage = str(STORAGE_DIR / self.email.replace("@", "_"))
                self.ar = pyaarlo.PyArlo(
                    username=self.email,
                    password=self.password,
                    tfa_type="EMAIL",
                    tfa_source="cli",
                    wait_for_initial_update=True,
                    storage_dir=storage,
                    save_state=True,       # ← persists tokens; no 2FA on restart
                )
                if self.ar.is_connected:
                    self.cameras = self._list_cameras()
                    self.status  = "connected"
                else:
                    self.status = "error"
                    self.error  = "Could not connect to Arlo — check credentials"
            except Exception as exc:
                self.status = "error"
                self.error  = str(exc)
            finally:
                builtins.input = orig_input
                self._ready.set()

    def _list_cameras(self) -> list:
        if not self.ar:
            return []
        return [
            {
                "id":    d.device_id,
                "name":  d.name,
                "model": getattr(d, "model_id", "Arlo"),
            }
            for d in self.ar.cameras
        ]

    # ── 2FA submission ────────────────────────────────────────────────────────

    def submit_2fa(self, code: str):
        """Inject the OTP code and wait for login to complete."""
        self._tfa_q.put(code.strip())
        # Reset ready event so we wait for login to finish
        self._ready.clear()
        self._ready.wait(timeout=30)

    # ── Snapshot capture ──────────────────────────────────────────────────────

    def get_snapshot_b64(self, device_id: str) -> str:
        """Request a fresh snapshot from Arlo and return as base64 JPEG."""
        if not self.ar or self.status != "connected":
            return ""
        cam = next((d for d in self.ar.cameras if d.device_id == device_id), None)
        if not cam:
            return ""
        try:
            # Request a new snapshot capture
            cam.request_snapshot()
            time.sleep(3)   # give Arlo time to upload

            img_url = cam.last_image
            if not img_url or not REQUESTS_OK:
                return ""
            resp = _req.get(img_url, timeout=10)
            if resp.ok:
                return base64.b64encode(resp.content).decode()
        except Exception as exc:
            log.warning("Arlo snapshot error: %s", exc)
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

def login(email: str, password: str) -> dict:
    """
    Start an Arlo login.
    Returns {'session_id', 'needs_2fa': bool, 'cameras': list|None}
    """
    session_id = uuid.uuid4().hex[:12]
    session = ArloSession(session_id, email, password)
    with _session_lock:
        _sessions[session_id] = session

    # Wait up to 8 s to see if it connects without 2FA (cached token path)
    session._ready.wait(timeout=8)

    if session.status == "connected":
        return {"session_id": session_id, "needs_2fa": False, "cameras": session.cameras}
    if session.status == "needs_2fa":
        return {"session_id": session_id, "needs_2fa": True, "cameras": None}
    if session.status == "error":
        raise RuntimeError(session.error or "Arlo login failed")
    # Still connecting after timeout — assume 2FA is incoming
    return {"session_id": session_id, "needs_2fa": True, "cameras": None}


def submit_2fa(session_id: str, code: str) -> dict:
    """
    Submit the 2FA code for a pending session.
    Returns {'cameras': [...]}
    """
    session = _sessions.get(session_id)
    if not session:
        raise RuntimeError("Session not found or expired — please reconnect")
    session.submit_2fa(code)
    if session.status == "connected":
        return {"cameras": session.cameras}
    raise RuntimeError(session.error or "2FA verification failed")


def get_cameras(session_id: str) -> list:
    session = _sessions.get(session_id)
    return session.cameras if session and session.status == "connected" else []


def get_snapshot(session_id: str, device_id: str) -> str:
    """Returns base64 JPEG or empty string."""
    session = _sessions.get(session_id)
    return session.get_snapshot_b64(device_id) if session else ""


def get_active_session() -> "ArloSession | None":
    """Returns the most recent connected session (used by the detector loop)."""
    with _session_lock:
        for s in reversed(list(_sessions.values())):
            if s.status == "connected":
                return s
    return None

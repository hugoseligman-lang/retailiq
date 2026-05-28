"""
arlo_camera.py — Direct Arlo REST implementation with RSA password encryption.

Arlo's API requires the password to be RSA-encrypted using a public key fetched
from their server before login. This replaces pyaarlo (which has a broken 2FA
handler in v0.8.0.19) while keeping the same public API surface.

Flow:
  1. login(email, password)        → {session_id, needs_2fa, cameras?}
  2. submit_2fa(session_id, code)  → {cameras}
  3. get_snapshot(session_id, device_id) → base64 JPEG
"""

import base64, json, logging, os, threading, time, uuid
from pathlib import Path

log = logging.getLogger(__name__)

AUTH_BASE = "https://ocapi-app.arlo.com"
API_BASE  = "https://myapi.arlo.com"

STATE_DIR = Path(os.path.dirname(__file__)) / ".arlo_state"
STATE_DIR.mkdir(exist_ok=True)

_sessions: dict = {}
_lock = threading.Lock()

# Camera device types recognised as cameras
_CAMERA_TYPES = {
    "arloq", "arloss", "arloqs", "arlobaby",
    "arlopro", "arlopro2", "arlopro3", "arlopro4", "arlopro5",
    "arloessential", "arloessential2", "arloultra", "arloultra2",
    "arlo", "arlovms3030", "arlovmc2030", "arloavd1001",
}

# ── RSA password encryption ───────────────────────────────────────────────────

def _make_scraper():
    try:
        import cloudscraper
        return cloudscraper.create_scraper()
    except Exception:
        import requests
        return requests.Session()


def _encrypt_password(password: str, pub_key_hex: str, exponent) -> str:
    """
    RSA-encrypt the password using Arlo's public key (hex-encoded modulus).
    Falls back to plaintext if pycryptodome is unavailable.
    """
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher   import PKCS1_v1_5
        n   = int(pub_key_hex, 16)
        e   = int(exponent)
        key = RSA.construct((n, e))
        enc = PKCS1_v1_5.new(key).encrypt(password.encode("utf-8"))
        return base64.b64encode(enc).decode("utf-8")
    except Exception as exc:
        log.warning("RSA encrypt failed (%s) — using plaintext", exc)
        return password


# ── Session ───────────────────────────────────────────────────────────────────

class ArloSession:
    def __init__(self, session_id: str, email: str, password: str):
        self.session_id         = session_id
        self.email              = email
        self.password           = password
        self.token: str         = ""
        self.user_id: str       = ""
        self.factor_id: str     = ""
        self.factor_auth_code: str = ""
        self.cameras: list      = []
        self.status             = "idle"   # idle|needs_2fa|connected|error
        self.error              = ""
        self.sc                 = _make_scraper()
        self._state_file = STATE_DIR / (
            email.replace("@", "_").replace(".", "_") + ".json"
        )

    # ── Request helpers ───────────────────────────────────────────────────────

    def _h(self, extra: dict | None = None) -> dict:
        h = {
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/120.0.0.0 Safari/537.36",
            "Content-Type":  "application/json",
            "Accept":        "application/json, text/plain, */*",
            "Origin":        "https://my.arlo.com",
            "Referer":       "https://my.arlo.com/",
            "auth-version":  "2",
            "Source":        "arloCamWeb",
            "schemaVersion": "1",
        }
        if self.token:
            h["Authorization"] = self.token
        if extra:
            h.update(extra)
        return h

    def _post(self, url: str, body: dict, timeout: int = 15) -> dict:
        r = self.sc.post(url, json=body, headers=self._h(), timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {"meta": {"code": r.status_code, "message": r.text[:200]}}

    def _get(self, url: str, params=None, extra=None, timeout: int = 15) -> dict:
        r = self.sc.get(url, params=params, headers=self._h(extra), timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {}

    # ── Saved-session restore ─────────────────────────────────────────────────

    def try_restore(self) -> bool:
        if not self._state_file.exists():
            return False
        try:
            data = json.loads(self._state_file.read_text())
            self.token   = data.get("token", "")
            self.user_id = data.get("user_id", "")
            if not self.token:
                return False
            body = self._get(f"{API_BASE}/hmsweb/users/devices")
            if body.get("success"):
                self.cameras = self._parse_cameras(body.get("data", []))
                self.status  = "connected"
                log.info("Arlo: restored session for %s (%d cameras)",
                         self.email, len(self.cameras))
                return True
        except Exception as exc:
            log.warning("Arlo restore failed: %s", exc)
        self.token = ""
        return False

    # ── Login step 1: email + RSA-encrypted password ──────────────────────────

    def start_login(self):
        try:
            # Fetch RSA public key
            nonce = str(int(time.time() * 1000))
            kr = self._get(
                f"{AUTH_BASE}/api/getFactors",
                params={"data": json.dumps({"factorNonce": nonce})},
            )
            kd = kr.get("data") or {}
            pub_key  = kd.get("pubKey",  "")
            exponent = kd.get("exponent", 65537)

            # Encrypt password
            enc_pw = _encrypt_password(self.password, pub_key, exponent) \
                     if pub_key else self.password

            # Login
            body = self._post(
                f"{AUTH_BASE}/api/auth",
                {"email": self.email, "password": enc_pw},
            )
            meta = body.get("meta", {})
            code = meta.get("code", 0)

            if code == 401:
                self.status = "error"
                self.error  = "Incorrect password — please check and try again."
                return

            if code not in (200, 0, None) and code != 400:
                self.status = "error"
                self.error  = meta.get("message", f"Login error {code}")
                return

            data = body.get("data") or {}
            self.token   = data.get("token", "")
            self.user_id = data.get("userId", "")

            factors = data.get("factors") or []
            if factors:
                # Prefer EMAIL factor
                factor = next(
                    (f for f in factors
                     if str(f.get("factorType", "")).upper() == "EMAIL"),
                    factors[0],
                )
                self.factor_id = factor.get("factorId", "")
                self._send_2fa_code()
                self.status = "needs_2fa"
            else:
                self._finalise()

        except Exception as exc:
            self.status = "error"
            self.error  = str(exc)

    # ── 2FA: fire the email / SMS ─────────────────────────────────────────────

    def _send_2fa_code(self):
        try:
            r = self._post(
                f"{AUTH_BASE}/api/startAuth",
                {"factorId": self.factor_id},
            )
            self.factor_auth_code = (r.get("data") or {}).get("factorAuthCode", "")
        except Exception as exc:
            log.warning("Arlo: could not send 2FA: %s", exc)

    # ── 2FA: verify the code the user types ───────────────────────────────────

    def verify_2fa(self, code: str):
        try:
            body = self._post(
                f"{AUTH_BASE}/api/finishAuth",
                {
                    "factorAuthCode": self.factor_auth_code,
                    "otp":            code.strip(),
                },
            )
            meta = body.get("meta", {})
            if meta.get("code") not in (200, 0, None):
                self.status = "error"
                self.error  = meta.get("message", "Invalid code — please try again.")
                return
            data = body.get("data") or {}
            if data.get("token"):
                self.token = data["token"]
            self._finalise()
        except Exception as exc:
            self.status = "error"
            self.error  = str(exc)

    # ── Finalise: fetch devices and save token ────────────────────────────────

    def _finalise(self):
        try:
            body = self._get(f"{API_BASE}/hmsweb/users/devices")
            if body.get("success"):
                self.cameras = self._parse_cameras(body.get("data", []))
            self._state_file.write_text(
                json.dumps({"token": self.token, "user_id": self.user_id})
            )
            self.status = "connected"
            log.info("Arlo: connected as %s, %d cameras",
                     self.email, len(self.cameras))
        except Exception as exc:
            self.status = "error"
            self.error  = str(exc)

    # ── Parse device list ─────────────────────────────────────────────────────

    def _parse_cameras(self, devices: list) -> list:
        out = []
        for d in devices:
            dt = d.get("deviceType", "").lower().replace(" ", "").replace("-", "")
            if (dt in _CAMERA_TYPES
                    or "camera" in dt
                    or ("arlo" in dt and dt not in ("arlobasestation", "arlobridge"))):
                if d.get("deviceId"):
                    out.append({
                        "id":    d["deviceId"],
                        "name":  d.get("deviceName", "Arlo Camera"),
                        "model": d.get("deviceType", "Arlo"),
                    })
        return out

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def get_snapshot_b64(self, device_id: str) -> str:
        if not self.token:
            return ""
        try:
            import requests as _req
            from datetime import datetime, timedelta
            today    = datetime.utcnow().strftime("%Y%m%d")
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")
            body = self._get(
                f"{API_BASE}/hmsweb/users/library",
                params={"dateFrom": week_ago, "dateTo": today},
            )
            for item in (body.get("data") or []):
                if item.get("deviceId") == device_id:
                    url = (item.get("presignedThumbnailUrl")
                           or item.get("presignedContentUrl"))
                    if url:
                        resp = _req.get(url, timeout=12)
                        if resp.ok:
                            return base64.b64encode(resp.content).decode()
        except Exception as exc:
            log.warning("Arlo snapshot error: %s", exc)
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

def login(email: str, password: str) -> dict:
    session_id = uuid.uuid4().hex[:12]
    session    = ArloSession(session_id, email, password)
    with _lock:
        _sessions[session_id] = session

    if session.try_restore():
        return {"session_id": session_id, "needs_2fa": False,
                "cameras": session.cameras}

    session.start_login()

    if session.status == "connected":
        return {"session_id": session_id, "needs_2fa": False,
                "cameras": session.cameras}
    if session.status == "needs_2fa":
        return {"session_id": session_id, "needs_2fa": True, "cameras": None}

    raise RuntimeError(session.error or "Arlo login failed")


def submit_2fa(session_id: str, code: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise RuntimeError("Session not found — please reconnect")
    session.verify_2fa(code)
    if session.status == "connected":
        return {"cameras": session.cameras}
    raise RuntimeError(session.error or "2FA verification failed")


def get_cameras(session_id: str) -> list:
    session = _sessions.get(session_id)
    return session.cameras if session and session.status == "connected" else []


def get_snapshot(session_id: str, device_id: str) -> str:
    session = _sessions.get(session_id)
    return session.get_snapshot_b64(device_id) if session else ""


def get_active_session() -> "ArloSession | None":
    with _lock:
        for s in reversed(list(_sessions.values())):
            if s.status == "connected":
                return s
    return None

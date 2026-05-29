/**
 * PinGate — wraps the app and blocks access until the correct 4-digit PIN
 * is entered. Auth state lives in localStorage with a 7-day expiry.
 * Skipped entirely when the backend reports pin_required = false.
 */
import { useEffect, useState, useRef } from "react";
import { api } from "../api";

const TOKEN_KEY  = "iq_token";
const TOKEN_EXP  = "iq_token_exp";
const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000;

export default function PinGate({ children }) {
  const [ready,   setReady]   = useState(false);   // done checking stored token
  const [authed,  setAuthed]  = useState(false);
  const [required, setRequired] = useState(false);

  // Check stored session on mount
  useEffect(() => {
    api.authRequired()
      .then(r => {
        if (!r.pin_required) { setAuthed(true); setRequired(false); setReady(true); return; }
        setRequired(true);
        const token = localStorage.getItem(TOKEN_KEY);
        const exp   = parseInt(localStorage.getItem(TOKEN_EXP) || "0", 10);
        if (token && Date.now() < exp) {
          // Verify token is still valid (backend may have restarted)
          api.authVerify(token)
            .then(v => { setAuthed(v.ok); setReady(true); })
            .catch(() => { setReady(true); });
        } else {
          setReady(true);
        }
      })
      .catch(() => {
        // Backend unreachable — let through, API calls will show offline state
        setAuthed(true); setReady(true);
      });
  }, []);

  function handleSuccess(token) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXP, String(Date.now() + SEVEN_DAYS));
    setAuthed(true);
  }

  if (!ready) return (
    <div className="pin-shell">
      <div className="pin-card">
        <div className="pin-logo"><span>Retail</span>IQ</div>
        <p style={{ color: "var(--muted)", fontSize: "0.78rem", textAlign: "center" }}>Connecting…</p>
      </div>
    </div>
  );

  if (!required || authed) return children;

  return <PinScreen onSuccess={handleSuccess} />;
}


function PinScreen({ onSuccess }) {
  const [digits,  setDigits]  = useState(["", "", "", ""]);
  const [error,   setError]   = useState(false);
  const [loading, setLoading] = useState(false);
  const refs = [useRef(), useRef(), useRef(), useRef()];

  useEffect(() => { refs[0].current?.focus(); }, []);

  function handleKey(i, e) {
    const val = e.target.value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[i] = val;
    setDigits(next);
    setError(false);

    if (val && i < 3) refs[i + 1].current?.focus();

    // Auto-submit when all four filled
    if (val && i === 3) {
      const pin = [...next.slice(0, 3), val].join("");
      if (pin.length === 4) submit(pin);
    }
  }

  function handleKeyDown(i, e) {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      refs[i - 1].current?.focus();
    }
    if (e.key === "Enter") {
      const pin = digits.join("");
      if (pin.length === 4) submit(pin);
    }
  }

  async function submit(pin) {
    if (loading) return;
    setLoading(true);
    try {
      const r = await api.verifyPin(pin);
      if (r.ok) {
        onSuccess(r.token);
      } else {
        setError(true);
        setDigits(["", "", "", ""]);
        setTimeout(() => refs[0].current?.focus(), 50);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  const pin = digits.join("");

  return (
    <div className="pin-shell">
      <div className="pin-card">
        <div className="pin-logo"><span>Retail</span>IQ</div>
        <p className="pin-title">Enter your PIN to continue</p>

        <div className="pin-inputs">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={refs[i]}
              className={`pin-digit ${error ? "pin-digit-error" : ""}`}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={e => handleKey(i, e)}
              onKeyDown={e => handleKeyDown(i, e)}
              disabled={loading}
              autoComplete="off"
            />
          ))}
        </div>

        {error && <p className="pin-error">Incorrect PIN — try again</p>}

        <button
          className="pin-submit"
          onClick={() => pin.length === 4 && submit(pin)}
          disabled={pin.length < 4 || loading}
        >
          {loading ? "Checking…" : "Unlock"}
        </button>

        <p className="pin-hint">
          Access restricted to authorised users.
        </p>
      </div>
    </div>
  );
}

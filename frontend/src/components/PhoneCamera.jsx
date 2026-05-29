/**
 * PhoneCamera — turns any phone browser into a live camera stream.
 *
 * Open  cafe.meridianai.build/camera  on the phone, pick a role,
 * tap Stream. The phone sends JPEG frames directly to the VPS backend.
 * No app, no laptop, no bridge script needed.
 *
 * Auth: uses the session token already stored in localStorage from the
 * PIN login — no extra password needed.
 */
import { useEffect, useRef, useState, useCallback } from "react";

const ROLES = [
  { value: "front", label: "Front Door",  icon: "🚪", desc: "Entry/exit counting" },
  { value: "back",  label: "Back Door",   icon: "🚪", desc: "Entry/exit counting" },
  { value: "pos",   label: "POS Counter", icon: "🛒", desc: "Queue detection" },
];

const DEFAULT_FPS   = 5;
const JPEG_QUALITY  = 0.72;

function getBase() {
  try { return localStorage.getItem("iq_backend") || "/api"; } catch { return "/api"; }
}
function getToken() {
  try { return localStorage.getItem("iq_token") || ""; } catch { return ""; }
}

export default function PhoneCamera() {
  const [role,      setRole]      = useState("front");
  const [streaming, setStreaming] = useState(false);
  const [framesSent, setFrames]  = useState(0);
  const [fps,        setFps]     = useState(DEFAULT_FPS);
  const [facing,    setFacing]   = useState("environment"); // rear camera
  const [status,   setStatus]    = useState("idle");        // idle|streaming|error|no_camera
  const [errMsg,   setErrMsg]    = useState("");
  const [lastOk,   setLastOk]    = useState(null);          // timestamp of last successful send

  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const streamRef  = useRef(null);
  const timerRef   = useRef(null);
  const wakeLockRef = useRef(null);
  const sendingRef = useRef(false);  // prevent overlapping sends

  // ── Camera lifecycle ──────────────────────────────────────────────────────

  const startCamera = useCallback(async () => {
    // Stop any existing stream first
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    const constraints = {
      video: {
        facingMode: facing,
        width:  { ideal: 640 },
        height: { ideal: 480 },
        frameRate: { max: 30 },
      },
      audio: false,
    };
    const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
    streamRef.current = mediaStream;
    if (videoRef.current) {
      videoRef.current.srcObject = mediaStream;
      await videoRef.current.play();
    }
  }, [facing]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  // Restart camera when facing direction changes
  useEffect(() => {
    if (streaming) startCamera().catch(e => console.warn("flip camera error", e));
  }, [facing]);

  // ── Frame capture + send ─────────────────────────────────────────────────

  const sendFrame = useCallback(async () => {
    if (sendingRef.current) return;
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    sendingRef.current = true;
    try {
      const w = video.videoWidth  || 640;
      const h = video.videoHeight || 480;
      canvas.width  = w;
      canvas.height = h;
      canvas.getContext("2d").drawImage(video, 0, 0, w, h);

      const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", JPEG_QUALITY));
      if (!blob) return;

      const url     = `${getBase()}/ingest-frame/${role}`;
      const token   = getToken();
      const r = await fetch(url, {
        method:  "POST",
        headers: {
          "Content-Type":    "image/jpeg",
          "X-Session-Token": token,
        },
        body: blob,
      });

      if (r.ok) {
        setFrames(n => n + 1);
        setLastOk(new Date());
        setStatus("streaming");
      } else if (r.status === 403) {
        setErrMsg("Auth failed — re-open the dashboard and log in first.");
        setStatus("error");
        stopStreaming();
      }
    } catch (e) {
      // Network error — don't stop, just log
      console.warn("send error:", e.message);
      setStatus("error");
      setErrMsg(`Send error: ${e.message} — retrying…`);
      setTimeout(() => setStatus("streaming"), 3000);
    } finally {
      sendingRef.current = false;
    }
  }, [role]);

  // ── Start / stop streaming ────────────────────────────────────────────────

  async function startStreaming() {
    setErrMsg("");
    try {
      await startCamera();
    } catch (e) {
      setStatus("no_camera");
      setErrMsg(e.name === "NotAllowedError"
        ? "Camera permission denied — tap 'Allow' when the browser asks."
        : `Camera error: ${e.message}`);
      return;
    }

    // Keep screen on
    try {
      if ("wakeLock" in navigator) {
        wakeLockRef.current = await navigator.wakeLock.request("screen");
      }
    } catch { /* not critical */ }

    const interval = Math.round(1000 / fps);
    timerRef.current = setInterval(sendFrame, interval);
    setStreaming(true);
    setStatus("streaming");
    setFrames(0);
  }

  function stopStreaming() {
    clearInterval(timerRef.current);
    stopCamera();
    if (wakeLockRef.current) {
      wakeLockRef.current.release().catch(() => {});
      wakeLockRef.current = null;
    }
    setStreaming(false);
    setStatus("idle");
  }

  // Cleanup on unmount
  useEffect(() => () => { clearInterval(timerRef.current); stopCamera(); }, []);

  // Re-register send interval when fps or role changes mid-stream
  useEffect(() => {
    if (!streaming) return;
    clearInterval(timerRef.current);
    timerRef.current = setInterval(sendFrame, Math.round(1000 / fps));
  }, [fps, role, sendFrame]);

  // ── Derived UI state ──────────────────────────────────────────────────────

  const ageText = lastOk
    ? (() => {
        const s = Math.round((Date.now() - lastOk.getTime()) / 1000);
        return s < 2 ? "just now" : `${s}s ago`;
      })()
    : null;

  const roleLabel = ROLES.find(r => r.value === role)?.label || role;
  const roleIcon  = ROLES.find(r => r.value === role)?.icon  || "📷";

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="pcam-shell">

      {/* ── Header ── */}
      <div className="pcam-header">
        <div className="pcam-logo"><span>Retail</span>IQ</div>
        <a href="/" className="pcam-back">← Dashboard</a>
      </div>

      {/* ── Video viewfinder ── */}
      <div className="pcam-viewfinder">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="pcam-video"
        />
        <canvas ref={canvasRef} className="pcam-canvas" />

        {/* Status overlay */}
        {streaming && (
          <div className="pcam-vid-overlay">
            <span className="pcam-live-badge">
              <span className="pcam-live-dot" /> LIVE
            </span>
            <span className="pcam-frame-count">{framesSent} frames</span>
          </div>
        )}

        {/* Role label on video */}
        <div className="pcam-role-badge">
          {roleIcon} {roleLabel}
        </div>

        {/* Flip camera button */}
        <button
          className="pcam-flip-btn"
          onClick={() => setFacing(f => f === "environment" ? "user" : "environment")}
          title="Flip camera"
        >
          🔄
        </button>
      </div>

      {/* ── Controls ── */}
      <div className="pcam-controls">

        {/* Role selector */}
        <div className="pcam-role-row">
          {ROLES.map(r => (
            <button
              key={r.value}
              className={`pcam-role-btn ${role === r.value ? "pcam-role-active" : ""}`}
              onClick={() => setRole(r.value)}
              disabled={streaming}
            >
              <span className="pcam-role-icon">{r.icon}</span>
              <span className="pcam-role-name">{r.label}</span>
              <span className="pcam-role-desc">{r.desc}</span>
            </button>
          ))}
        </div>

        {/* FPS slider */}
        {!streaming && (
          <div className="pcam-fps-row">
            <span className="pcam-fps-label">Speed</span>
            <input
              type="range" min={1} max={10} value={fps}
              onChange={e => setFps(Number(e.target.value))}
              className="pcam-fps-slider"
            />
            <span className="pcam-fps-val">{fps} fps</span>
          </div>
        )}

        {/* Error message */}
        {errMsg && <p className="pcam-error">{errMsg}</p>}

        {/* Last OK timestamp */}
        {streaming && ageText && (
          <p className="pcam-ack">Last received by VPS: {ageText}</p>
        )}

        {/* Main action button */}
        <button
          className={`pcam-stream-btn ${streaming ? "pcam-btn-stop" : "pcam-btn-start"}`}
          onClick={streaming ? stopStreaming : startStreaming}
        >
          {streaming ? "⏹ Stop" : "▶ Start Streaming"}
        </button>

        {/* Dashboard link */}
        {streaming && (
          <a href="/" className="pcam-dashboard-link">
            View live dashboard →
          </a>
        )}

      </div>

      {/* ── How to use ── */}
      {!streaming && (
        <div className="pcam-help">
          <p><strong>How to use:</strong></p>
          <ol>
            <li>Select the camera role (which doorway this phone covers)</li>
            <li>Prop the phone up pointing at the entrance — screen facing outward</li>
            <li>Tap <strong>Start Streaming</strong></li>
            <li>Leave the screen on and browser open — it streams all day</li>
            <li>Open the <a href="/">dashboard</a> on another device to see counts</li>
          </ol>
        </div>
      )}

    </div>
  );
}

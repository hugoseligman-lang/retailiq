/**
 * CalibrationWizard — 7-step AI-powered setup modal.
 * Steps: Discovery → Scene Analysis → Zone Editor →
 *        Multi-Camera → Queue Cal → Entrance Cal → Summary
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api";
import ZoneEditor from "./calibration/ZoneEditor";

const STEPS = [
  { id: "discovery",    label: "Camera Discovery"   },
  { id: "analysis",     label: "Scene Analysis"     },
  { id: "zones",        label: "Zone Editor"        },
  { id: "multicam",     label: "Multi-Camera"       },
  { id: "queue",        label: "Queue Calibration"  },
  { id: "entrance",     label: "Entrance Counting"  },
  { id: "summary",      label: "Save & Confirm"     },
];

const CAMERA_MODE_LABELS = { webcam: "USB Webcam", rtsp: "IP Camera", http: "Web Stream", arlo: "Arlo" };

// ── Utility ──────────────────────────────────────────────────────────────────

function ConfidenceBadge({ v }) {
  const pct = Math.round((v || 0) * 100);
  const cls = pct >= 80 ? "conf-high" : pct >= 60 ? "conf-mid" : "conf-low";
  return <span className={`calib-conf ${cls}`}>{pct}%{pct < 60 ? " ⚠" : ""}</span>;
}

function Spinner({ label }) {
  return <div className="calib-spinner-row"><div className="calib-spinner" />{label && <span>{label}</span>}</div>;
}

// Build zone list from Claude analysis JSON
function analysisToZones(analysis) {
  const zones = [];
  let id = 1;

  const addZone = (src, type, label) => {
    if (!src || src.confidence === 0) return;
    zones.push({ id: id++, zone_type: type, label, confidence: src.confidence || 0.8,
      x1_pct: src.x1, y1_pct: src.y1, x2_pct: src.x2, y2_pct: src.y2 });
  };

  addZone(analysis.entrance_zone,      "entrance",      "Entrance");
  addZone(analysis.counter_queue_zone, "counter_queue", "Counter / Queue");
  (analysis.seating_zones || []).forEach((z, i) => addZone(z, "seating", z.label || `Seating ${i + 1}`));
  (analysis.suggested_zones || []).forEach(z => addZone(z, z.zone_type || "custom", z.label || "Zone"));

  return zones;
}

function analysisToEntranceLine(analysis) {
  const l = analysis.entrance_line || analysis.recommended_counting_line;
  if (!l) return null;
  return { x1_pct: l.x1, y1_pct: l.y1, x2_pct: l.x2, y2_pct: l.y2,
    entry_direction: l.entry_direction || "left_to_right" };
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CalibrationWizard({ onClose }) {
  const [stepIdx,   setStepIdx]   = useState(0);
  const step = STEPS[stepIdx].id;

  // ── Camera discovery state ─────────────────────────────────────────────────
  const [scanning,        setScanning]        = useState(false);
  const [scanProgress,    setScanProgress]    = useState(0);
  const [discovered,      setDiscovered]      = useState([]);
  const [manualMode,      setManualMode]      = useState("webcam");
  const [manualSource,    setManualSource]    = useState("0");
  const [manualName,      setManualName]      = useState("");
  const [testingManual,   setTestingManual]   = useState(false);
  const [manualTestFrame, setManualTestFrame] = useState(null);
  const [manualError,     setManualError]     = useState("");
  const [registeredCams,  setRegisteredCams]  = useState([]);  // saved to DB
  const scanPoll = useRef(null);

  // ── Analysis state ─────────────────────────────────────────────────────────
  const [analysisResults, setAnalysisResults] = useState({});  // { camId: { analysis, frame } }
  const [analysing,       setAnalysing]       = useState(null); // camId being analysed
  const [analysisError,   setAnalysisError]   = useState("");

  // ── Zone editor state ──────────────────────────────────────────────────────
  const [activeCamIdx,  setActiveCamIdx]  = useState(0);
  const [zonesByCam,    setZonesByCam]    = useState({});      // { camId: zones[] }
  const [linesByCam,    setLinesByCam]    = useState({});      // { camId: line }

  // ── Multi-camera state ─────────────────────────────────────────────────────
  const [crossRefResult, setCrossRefResult] = useState(null);
  const [crossRefFrames, setCrossRefFrames] = useState([]);
  const [crossRefLoading, setCrossRefLoading] = useState(false);

  // ── Queue test state ───────────────────────────────────────────────────────
  const [queueCamId,   setQueueCamId]    = useState(null);
  const [queueMin,     setQueueMin]      = useState(2);
  const [queueDwell,   setQueueDwell]    = useState(30);
  const [testRunning,  setTestRunning]   = useState(false);
  const [testEvents,   setTestEvents]    = useState([]);
  const [testElapsed,  setTestElapsed]   = useState(0);
  const [testDuration, setTestDuration]  = useState(30);
  const testPoll = useRef(null);

  // ── Entrance test state ────────────────────────────────────────────────────
  const [entranceCamId, setEntranceCamId] = useState(null);
  const [flipDir,       setFlipDir]       = useState(false);

  // ── Saving ─────────────────────────────────────────────────────────────────
  const [saving,   setSaving]   = useState(false);
  const [saveOk,   setSaveOk]   = useState(false);
  const [saveError, setSaveError] = useState("");

  // ── Load existing cameras on mount ────────────────────────────────────────
  useEffect(() => {
    api.calibCameras().then(cams => {
      setRegisteredCams(cams);
      const zb = {}, lb = {};
      cams.forEach(c => {
        zb[c.id] = (c.zones || []).map((z, i) => ({ ...z, id: i + 1 }));
        lb[c.id] = c.entrance_line || null;
      });
      setZonesByCam(zb);
      setLinesByCam(lb);
      if (cams.length > 0) {
        setQueueCamId(cams[0].id);
        setEntranceCamId(cams[0].id);
      }
    }).catch(() => {});
  }, []);

  // ── STEP 1: CAMERA DISCOVERY ───────────────────────────────────────────────

  function startScan() {
    setScanning(true);
    setDiscovered([]);
    api.calibScanStart().catch(() => {});
    scanPoll.current = setInterval(async () => {
      try {
        const s = await api.calibScanStatus();
        setScanProgress(Math.round((s.progress / s.total) * 100));
        if (s.results?.length) setDiscovered(s.results);
        if (s.done) {
          clearInterval(scanPoll.current);
          setScanning(false);
        }
      } catch {}
    }, 1500);
  }

  useEffect(() => () => clearInterval(scanPoll.current), []);

  async function testManual() {
    setTestingManual(true);
    setManualError("");
    setManualTestFrame(null);
    try {
      const r = await api.calibTestCamera(manualMode, manualSource);
      if (r.ok) setManualTestFrame(r.frame);
      else setManualError(r.error || "Connection failed");
    } catch { setManualError("Could not reach backend"); }
    finally { setTestingManual(false); }
  }

  async function addManualCamera() {
    if (!manualTestFrame) { setManualError("Test the connection first"); return; }
    const name = manualName || `${CAMERA_MODE_LABELS[manualMode]} ${registeredCams.length + 1}`;
    const r = await api.calibAddCamera({ name, mode: manualMode, source: manualSource });
    if (r.ok) {
      const fresh = await api.calibCameras();
      setRegisteredCams(fresh);
      setManualTestFrame(null);
      setManualSource("0");
      setManualName("");
    }
  }

  async function addDiscoveredCamera(cam) {
    const r = await api.calibAddCamera({ name: cam.name, mode: cam.mode, source: cam.source });
    if (r.ok) {
      const fresh = await api.calibCameras();
      setRegisteredCams(fresh);
    }
  }

  async function removeCamera(id) {
    await api.calibDeleteCamera(id);
    setRegisteredCams(prev => prev.filter(c => c.id !== id));
  }

  // ── STEP 2: SCENE ANALYSIS ─────────────────────────────────────────────────

  async function analyseCamera(camId) {
    setAnalysing(camId);
    setAnalysisError("");
    try {
      const r = await api.calibAnalyse(camId);
      if (r.ok) {
        setAnalysisResults(prev => ({ ...prev, [camId]: r }));
        const zones = analysisToZones(r.analysis);
        const line  = analysisToEntranceLine(r.analysis);
        setZonesByCam(prev => ({ ...prev, [camId]: zones }));
        setLinesByCam(prev => ({ ...prev, [camId]: line }));
      } else {
        setAnalysisError(r.error || "Analysis failed");
      }
    } catch (e) { setAnalysisError(String(e)); }
    finally { setAnalysing(null); }
  }

  async function analyseAll() {
    for (const cam of registeredCams) {
      await analyseCamera(cam.id);
    }
  }

  // ── STEP 4: MULTI-CAMERA ───────────────────────────────────────────────────

  async function runCrossRef() {
    if (registeredCams.length < 2) return;
    setCrossRefLoading(true);
    try {
      const r = await api.calibCrossRef(registeredCams.slice(0, 2).map(c => c.id));
      if (r.ok) { setCrossRefResult(r.result); setCrossRefFrames(r.frames || []); }
    } catch {}
    finally { setCrossRefLoading(false); }
  }

  // ── STEPS 5 & 6: LIVE TESTS ────────────────────────────────────────────────

  async function startTest(type) {
    const camId   = type === "queue" ? queueCamId : entranceCamId;
    const dur     = type === "queue" ? 30 : 60;
    setTestRunning(true);
    setTestEvents([]);
    setTestElapsed(0);
    setTestDuration(dur);

    if (type === "queue") {
      await api.calibSaveQueue(camId, { min_people: queueMin, min_dwell_seconds: queueDwell });
    }

    await api.calibTestStart(type, camId, dur);

    testPoll.current = setInterval(async () => {
      try {
        const s = await api.calibTestStatus();
        setTestElapsed(s.elapsed || 0);
        setTestEvents(s.events || []);
        if (!s.running) { clearInterval(testPoll.current); setTestRunning(false); }
      } catch {}
    }, 1000);
  }

  useEffect(() => () => clearInterval(testPoll.current), []);

  function flipEntranceDirection(camId) {
    setLinesByCam(prev => {
      const l = prev[camId];
      if (!l) return prev;
      const dirs = ["left_to_right", "right_to_left", "bottom_to_top", "top_to_bottom"];
      const idx  = (dirs.indexOf(l.entry_direction) + 1) % dirs.length;
      return { ...prev, [camId]: { ...l, entry_direction: dirs[idx] } };
    });
    setFlipDir(f => !f);
  }

  // ── STEP 7: SAVE ──────────────────────────────────────────────────────────

  async function saveAll() {
    setSaving(true);
    setSaveError("");
    try {
      for (const cam of registeredCams) {
        const zones = zonesByCam[cam.id] || [];
        const line  = linesByCam[cam.id];
        await api.calibSaveZones(cam.id, zones);
        if (line) await api.calibSaveEntrance(cam.id, line);
      }
      await api.calibComplete();
      setSaveOk(true);
    } catch (e) { setSaveError(String(e)); }
    finally { setSaving(false); }
  }

  // ── Navigation ─────────────────────────────────────────────────────────────

  const activeCam = registeredCams[activeCamIdx] || null;

  function canNext() {
    if (step === "discovery") return registeredCams.length > 0;
    if (step === "analysis")  return registeredCams.every(c => analysisResults[c.id]);
    return true;
  }

  function next() { setStepIdx(i => Math.min(i + 1, STEPS.length - 1)); }
  function back() { setStepIdx(i => Math.max(i - 1, 0)); }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="cw-overlay">
      <div className="cw-modal">

        {/* Sidebar */}
        <div className="cw-sidebar">
          <div className="cw-sidebar-logo"><span>Retail</span>IQ</div>
          <div className="cw-sidebar-title">Setup & Calibration</div>
          <nav className="cw-steps">
            {STEPS.map((s, i) => (
              <button
                key={s.id}
                className={`cw-step-btn ${i === stepIdx ? "cw-step-active" : ""} ${i < stepIdx ? "cw-step-done" : ""}`}
                onClick={() => setStepIdx(i)}
              >
                <span className="cw-step-num">{i < stepIdx ? "✓" : i + 1}</span>
                <span className="cw-step-label">{s.label}</span>
              </button>
            ))}
          </nav>
          {onClose && (
            <button className="cw-close-btn" onClick={onClose} title="Close">✕ Close</button>
          )}
        </div>

        {/* Main */}
        <div className="cw-main">
          <div className="cw-content">

            {/* ── Step 1: Discovery ─────────────────────────────────────── */}
            {step === "discovery" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Camera Discovery</h2>
                <p className="cw-step-sub">Scan the local network for IP cameras, or add yours manually.</p>

                {/* Scan */}
                <div className="cw-panel">
                  <div className="cw-panel-title">Network Scan</div>
                  <p className="cw-note">Tries common RTSP ports (554, 8554) and default credentials automatically.</p>
                  {scanning ? (
                    <>
                      <div className="cw-progress-bar"><div className="cw-progress-fill" style={{ width: `${scanProgress}%` }} /></div>
                      <span className="cw-muted">{scanProgress}% scanned — {discovered.length} found so far</span>
                    </>
                  ) : (
                    <button className="cw-btn cw-primary" onClick={startScan}>Start Network Scan</button>
                  )}

                  {discovered.length > 0 && (
                    <div className="cw-cam-grid">
                      {discovered.map((cam, i) => (
                        <div key={i} className="cw-cam-thumb">
                          {cam.frame && <img src={`data:image/jpeg;base64,${cam.frame}`} alt="cam" />}
                          <div className="cw-cam-info">
                            <div className="cw-cam-name">{cam.name}</div>
                            <div className="cw-cam-url">{cam.source}</div>
                            <button className="cw-btn cw-sm" onClick={() => addDiscoveredCamera(cam)}>+ Add</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Manual add */}
                <div className="cw-panel">
                  <div className="cw-panel-title">Add Camera Manually</div>
                  <div className="cw-form-row">
                    <select className="cw-input" value={manualMode} onChange={e => { setManualMode(e.target.value); setManualSource(e.target.value === "webcam" ? "0" : ""); }}>
                      <option value="webcam">USB Webcam</option>
                      <option value="rtsp">IP Camera (RTSP)</option>
                      <option value="http">Web Stream (HTTP)</option>
                    </select>
                    <input className="cw-input cw-input-grow" placeholder={manualMode === "webcam" ? "Camera index (0)" : manualMode === "rtsp" ? "rtsp://admin:admin@192.168.1.x:554/stream" : "http://192.168.1.x:8080/video"}
                      value={manualSource} onChange={e => setManualSource(e.target.value)} />
                    <input className="cw-input" placeholder="Name (optional)" value={manualName} onChange={e => setManualName(e.target.value)} />
                    <button className="cw-btn" onClick={testManual} disabled={testingManual}>
                      {testingManual ? "Testing…" : "Test"}
                    </button>
                    {manualTestFrame && <button className="cw-btn cw-primary" onClick={addManualCamera}>+ Add Camera</button>}
                  </div>
                  {manualError && <div className="cw-error">{manualError}</div>}
                  {manualTestFrame && (
                    <div className="cw-test-frame">
                      <img src={`data:image/jpeg;base64,${manualTestFrame}`} alt="test frame" />
                      <span className="cw-success-tag">✓ Connected</span>
                    </div>
                  )}
                </div>

                {/* Registered cameras */}
                {registeredCams.length > 0 && (
                  <div className="cw-panel">
                    <div className="cw-panel-title">Registered Cameras ({registeredCams.length})</div>
                    {registeredCams.map(cam => (
                      <div key={cam.id} className="cw-reg-cam">
                        <span className="cw-cam-dot" />
                        <span className="cw-reg-name">{cam.name}</span>
                        <span className="cw-muted">{CAMERA_MODE_LABELS[cam.mode]} · {cam.source}</span>
                        <button className="cw-btn cw-sm cw-danger" onClick={() => removeCamera(cam.id)}>Remove</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── Step 2: Scene Analysis ────────────────────────────────── */}
            {step === "analysis" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">AI Scene Analysis</h2>
                <p className="cw-step-sub">Claude Vision analyses each camera frame to detect zones, entrance lines, and potential issues.</p>

                {analysisError && <div className="cw-error">{analysisError}</div>}

                <div className="cw-analyse-actions">
                  <button className="cw-btn cw-primary" onClick={analyseAll} disabled={!!analysing}>
                    {analysing ? <Spinner label="Analysing…" /> : "Analyse All Cameras"}
                  </button>
                </div>

                {registeredCams.map(cam => {
                  const res = analysisResults[cam.id];
                  const a   = res?.analysis;
                  return (
                    <div key={cam.id} className="cw-panel cw-analysis-panel">
                      <div className="cw-panel-header">
                        <div className="cw-panel-title">{cam.name}</div>
                        <button className="cw-btn cw-sm" onClick={() => analyseCamera(cam.id)} disabled={analysing === cam.id}>
                          {analysing === cam.id ? "Analysing…" : "Analyse"}
                        </button>
                      </div>

                      {!res && !analysing && <p className="cw-muted">Not yet analysed</p>}
                      {analysing === cam.id && <Spinner label="Sending frame to Claude Vision…" />}

                      {res && !a?.error && (
                        <div className="cw-analysis-results">
                          <div className="cw-analysis-frame">
                            <img src={`data:image/jpeg;base64,${res.frame}`} alt="analysed frame" />
                          </div>
                          <div className="cw-analysis-meta">
                            <div className="cw-meta-row"><span>Lighting</span><span className={a.lighting_quality === "poor" ? "conf-low" : "conf-high"}>{a.lighting_quality}</span></div>
                            <div className="cw-meta-row"><span>Camera height</span><span>{a.camera_height_estimate}</span></div>
                            <div className="cw-meta-row"><span>Camera angle</span><span>{a.camera_angle_estimate}</span></div>
                            <div className="cw-meta-row"><span>Entrance zone</span><ConfidenceBadge v={a.entrance_zone?.confidence} /></div>
                            <div className="cw-meta-row"><span>Queue zone</span><ConfidenceBadge v={a.counter_queue_zone?.confidence} /></div>
                            {(a.occlusion_issues || []).map((iss, i) => (
                              <div key={i} className="cw-occlusion-warning">⚠ {iss}</div>
                            ))}
                          </div>
                        </div>
                      )}
                      {a?.error && <div className="cw-error">{a.error}</div>}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── Step 3: Zone Editor ───────────────────────────────────── */}
            {step === "zones" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Zone Editor</h2>
                <p className="cw-step-sub">Drag zones to reposition, pull corners to resize. Click a zone to select it.</p>

                {/* Camera tabs */}
                {registeredCams.length > 1 && (
                  <div className="cw-cam-tabs">
                    {registeredCams.map((cam, i) => (
                      <button key={cam.id} className={`cw-cam-tab ${i === activeCamIdx ? "cw-cam-tab-active" : ""}`} onClick={() => setActiveCamIdx(i)}>
                        {cam.name}
                      </button>
                    ))}
                  </div>
                )}

                {activeCam && (
                  <ZoneEditor
                    frameB64={analysisResults[activeCam.id]?.frame || null}
                    frameWidth={activeCam.width || 1920}
                    frameHeight={activeCam.height || 1080}
                    zones={zonesByCam[activeCam.id] || []}
                    entranceLine={linesByCam[activeCam.id] || null}
                    onZonesChange={zones => setZonesByCam(prev => ({ ...prev, [activeCam.id]: zones }))}
                    onEntranceLineChange={line => setLinesByCam(prev => ({ ...prev, [activeCam.id]: line }))}
                  />
                )}

                {!activeCam && <p className="cw-muted">No cameras registered. Go back to Step 1.</p>}

                {/* Low-confidence warnings */}
                {activeCam && (zonesByCam[activeCam.id] || []).filter(z => (z.confidence || 1) < 0.6).map(z => (
                  <div key={z.id} className="cw-warn-banner">
                    ⚠ Zone "{z.label}" has low confidence ({Math.round((z.confidence || 0) * 100)}%) — please review its position manually.
                  </div>
                ))}
              </div>
            )}

            {/* ── Step 4: Multi-Camera ──────────────────────────────────── */}
            {step === "multicam" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Multi-Camera Cross-Reference</h2>
                {registeredCams.length < 2 ? (
                  <p className="cw-muted">Only one camera registered — this step is optional. Click Continue to proceed.</p>
                ) : (
                  <>
                    <p className="cw-step-sub">Claude Vision compares pairs of camera frames to detect overlapping areas and build a unified store map.</p>
                    <button className="cw-btn cw-primary" onClick={runCrossRef} disabled={crossRefLoading}>
                      {crossRefLoading ? <Spinner label="Comparing cameras…" /> : "Run Cross-Reference"}
                    </button>

                    {crossRefFrames.length === 2 && (
                      <div className="cw-xref-frames">
                        {crossRefFrames.map((f, i) => (
                          <div key={i} className="cw-xref-frame">
                            <div className="cw-muted" style={{ fontSize: "0.7rem", marginBottom: 6 }}>
                              {registeredCams[i]?.name || `Camera ${i + 1}`}
                            </div>
                            <img src={`data:image/jpeg;base64,${f}`} alt={`cam${i + 1}`} />
                          </div>
                        ))}
                      </div>
                    )}

                    {crossRefResult && !crossRefResult.error && (
                      <div className="cw-panel">
                        <div className="cw-panel-title">Analysis Results</div>
                        <div className="cw-xref-result">
                          <div className="cw-meta-row"><span>Overlap detected</span><span className={crossRefResult.overlap_detected ? "conf-high" : "conf-low"}>{crossRefResult.overlap_detected ? `Yes (${Math.round((crossRefResult.overlap_confidence || 0) * 100)}%)` : "No"}</span></div>
                          {crossRefResult.spatial_relationship && <div className="cw-meta-row"><span>Relationship</span><span>{crossRefResult.spatial_relationship}</span></div>}
                          {crossRefResult.camera1_coverage && <div className="cw-meta-row"><span>Camera 1 covers</span><span>{crossRefResult.camera1_coverage}</span></div>}
                          {crossRefResult.camera2_coverage && <div className="cw-meta-row"><span>Camera 2 covers</span><span>{crossRefResult.camera2_coverage}</span></div>}
                          {(crossRefResult.shared_landmarks || []).length > 0 && (
                            <>
                              <div className="cw-panel-title" style={{ marginTop: 14 }}>Shared Landmarks</div>
                              {crossRefResult.shared_landmarks.map((lm, i) => (
                                <div key={i} className="cw-landmark">{lm.description}</div>
                              ))}
                            </>
                          )}
                        </div>
                      </div>
                    )}
                    {crossRefResult?.error && <div className="cw-error">{crossRefResult.error}</div>}
                  </>
                )}
              </div>
            )}

            {/* ── Step 5: Queue Calibration ─────────────────────────────── */}
            {step === "queue" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Queue Detection Calibration</h2>
                <p className="cw-step-sub">Set the threshold and run a 30-second test to confirm queue detection is working.</p>

                {registeredCams.length > 1 && (
                  <div className="cw-field">
                    <label>Camera</label>
                    <select className="cw-input" value={queueCamId || ""} onChange={e => setQueueCamId(Number(e.target.value))}>
                      {registeredCams.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                )}

                <div className="cw-two-col">
                  <div className="cw-field">
                    <label>Minimum people to trigger queue</label>
                    <input className="cw-input cw-input-sm" type="number" min={1} max={20} value={queueMin} onChange={e => setQueueMin(Number(e.target.value))} />
                  </div>
                  <div className="cw-field">
                    <label>Minimum dwell time (seconds)</label>
                    <input className="cw-input cw-input-sm" type="number" min={5} max={300} value={queueDwell} onChange={e => setQueueDwell(Number(e.target.value))} />
                  </div>
                </div>

                <button className="cw-btn cw-primary" onClick={() => startTest("queue")} disabled={testRunning}>
                  {testRunning ? `Testing… (${Math.round(testElapsed)}/${testDuration}s)` : "Run 30-Second Test"}
                </button>

                {testRunning && (
                  <div className="cw-progress-bar"><div className="cw-progress-fill" style={{ width: `${(testElapsed / testDuration) * 100}%` }} /></div>
                )}

                <LiveTestEvents events={testEvents} type="queue" />
              </div>
            )}

            {/* ── Step 6: Entrance Counting ─────────────────────────────── */}
            {step === "entrance" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Entrance Counting Calibration</h2>
                <p className="cw-step-sub">Run a 60-second live test. Each person crossing the entrance line shows as an event. Flip direction if entries and exits are reversed.</p>

                {registeredCams.length > 1 && (
                  <div className="cw-field">
                    <label>Camera</label>
                    <select className="cw-input" value={entranceCamId || ""} onChange={e => setEntranceCamId(Number(e.target.value))}>
                      {registeredCams.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                )}

                {entranceCamId && linesByCam[entranceCamId] && (
                  <div className="cw-meta-row">
                    <span>Current entry direction</span>
                    <span>{linesByCam[entranceCamId]?.entry_direction?.replace(/_/g, " ")}</span>
                    <button className="cw-btn cw-sm" onClick={() => flipEntranceDirection(entranceCamId)}>Flip Direction</button>
                  </div>
                )}

                <button className="cw-btn cw-primary" onClick={() => startTest("entrance")} disabled={testRunning}>
                  {testRunning ? `Testing… (${Math.round(testElapsed)}/${testDuration}s)` : "Run 60-Second Test"}
                </button>

                {testRunning && (
                  <div className="cw-progress-bar"><div className="cw-progress-fill" style={{ width: `${(testElapsed / 60) * 100}%` }} /></div>
                )}

                <LiveTestEvents events={testEvents} type="entrance" />
              </div>
            )}

            {/* ── Step 7: Summary & Save ────────────────────────────────── */}
            {step === "summary" && (
              <div className="cw-step-body">
                <h2 className="cw-step-h">Save & Confirm</h2>
                <p className="cw-step-sub">Review your calibration and activate live monitoring.</p>

                {saveOk ? (
                  <div className="cw-save-success">
                    <div className="cw-done-check">✓</div>
                    <h3>Calibration saved successfully</h3>
                    <p>{registeredCams.length} camera{registeredCams.length !== 1 ? "s" : ""} configured · {Object.values(zonesByCam).flat().length} zones mapped · {Object.values(linesByCam).filter(Boolean).length} entrance line{Object.values(linesByCam).filter(Boolean).length !== 1 ? "s" : ""} set</p>
                    {onClose && <button className="cw-btn cw-primary" onClick={onClose}>Enter Live Monitoring →</button>}
                  </div>
                ) : (
                  <>
                    {registeredCams.map(cam => {
                      const zones = zonesByCam[cam.id] || [];
                      const line  = linesByCam[cam.id];
                      return (
                        <div key={cam.id} className="cw-panel">
                          <div className="cw-panel-title">{cam.name}</div>
                          <div className="cw-summary-grid">
                            <span>Mode</span>       <span>{CAMERA_MODE_LABELS[cam.mode]}</span>
                            <span>Zones</span>      <span>{zones.length} zone{zones.length !== 1 ? "s" : ""}: {zones.map(z => z.label).join(", ") || "none"}</span>
                            <span>Entrance line</span><span>{line ? `${line.entry_direction.replace(/_/g, " ")} ✓` : "Not set"}</span>
                            <span>Queue config</span><span>≥{queueMin} people for ≥{queueDwell}s</span>
                          </div>
                          <div className="cw-summary-re-run">
                            <button className="cw-btn cw-sm" onClick={() => { setActiveCamIdx(registeredCams.indexOf(cam)); setStepIdx(2); }}>Re-run Zone Editor</button>
                            <button className="cw-btn cw-sm" onClick={() => setStepIdx(4)}>Re-run Queue Test</button>
                            <button className="cw-btn cw-sm" onClick={() => setStepIdx(5)}>Re-run Entrance Test</button>
                          </div>
                        </div>
                      );
                    })}

                    {saveError && <div className="cw-error">{saveError}</div>}

                    <button className="cw-btn cw-primary cw-lg" onClick={saveAll} disabled={saving || registeredCams.length === 0}>
                      {saving ? <Spinner label="Saving calibration…" /> : "Save & Start Live Monitoring →"}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Footer navigation */}
          {!saveOk && (
            <div className="cw-footer">
              <button className="cw-btn cw-ghost" onClick={back} disabled={stepIdx === 0}>← Back</button>
              <span className="cw-step-counter">{stepIdx + 1} / {STEPS.length}</span>
              {stepIdx < STEPS.length - 1 ? (
                <button className="cw-btn cw-primary" onClick={next} disabled={!canNext()}>
                  Continue →
                </button>
              ) : (
                <span />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Live test events feed ────────────────────────────────────────────────────

function LiveTestEvents({ events, type }) {
  const ref = useRef(null);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [events]);

  if (!events.length) return (
    <div className="cw-events-empty">Events will appear here during the test…</div>
  );

  return (
    <div className="cw-events" ref={ref}>
      {events.map((ev, i) => (
        <div key={i} className={`cw-event ${ev.type}`}>
          <span className="cw-event-time">{ev.t}s</span>
          <span className={`cw-event-icon ${ev.type === "entry" ? "ev-entry" : ev.type === "exit" ? "ev-exit" : "ev-queue"}`}>
            {ev.type === "entry" ? "→" : ev.type === "exit" ? "←" : "⏳"}
          </span>
          <span>{ev.msg}</span>
        </div>
      ))}
    </div>
  );
}

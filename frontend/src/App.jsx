import { useEffect, useMemo, useState } from "react";
import AlertFeed from "./components/AlertFeed";
import ClipModal from "./components/ClipModal";
import Controls from "./components/Controls";
import LiveFeed from "./components/LiveFeed";
import LiveStatus from "./components/LiveStatus";
import RecordingReview from "./components/RecordingReview";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function readJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

export default function App() {
  const [sourceMode, setSourceMode] = useState("camera");
  const [cameraIndex, setCameraIndex] = useState("0");
  const [rtspUrl, setRtspUrl] = useState("");
  const [status, setStatus] = useState({
    running: false,
    uptime_seconds: 0,
    alert_count: 0,
    source: null,
    people_count: 0,
    last_heuristic_reason: "monitoring",
    last_classifier_reason: "No concern detected.",
    last_classifier_severity: "none",
  });
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const headline = useMemo(() => {
    if (status.running) {
      return "Monitoring is active. EyeQ is scoring scenes, buffering evidence, and ready to escalate.";
    }
    return "Monitoring is offline. Start a live stream to begin abuse-risk detection and clip preservation.";
  }, [status.running]);

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      try {
        const data = await readJson(`${API_BASE}/status`);
        if (!cancelled) {
          setStatus(data);
          setErrorMessage("");
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
        }
      }
    }

    async function loadAlerts() {
      try {
        const data = await readJson(`${API_BASE}/alerts?limit=50`);
        if (!cancelled) {
          setAlerts(data);
          setErrorMessage("");
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error.message);
        }
      }
    }

    loadStatus();
    loadAlerts();

    const statusTimer = window.setInterval(loadStatus, 5000);
    const alertsTimer = window.setInterval(loadAlerts, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(statusTimer);
      window.clearInterval(alertsTimer);
    };
  }, []);

  async function handleStart() {
    setBusy(true);
    setErrorMessage("");
    try {
      const payload =
        sourceMode === "rtsp"
          ? { rtsp_url: rtspUrl.trim() }
          : { camera_index: Number.parseInt(cameraIndex, 10) || 0 };
      const nextStatus = await readJson(`${API_BASE}/stream/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus(nextStatus);
    } catch (error) {
      let message = error.message;
      if (message.includes("Unable to open video source")) {
        message =
          `${message}. Try camera index 1, or switch to RTSP if your webcam is busy or blocked by macOS permissions.`;
      }
      setErrorMessage(message);
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    setBusy(true);
    setErrorMessage("");
    try {
      const nextStatus = await readJson(`${API_BASE}/stream/stop`, { method: "POST" });
      setStatus(nextStatus);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <section className="panel overflow-hidden">
        <div className="grid gap-6 px-6 py-8 lg:grid-cols-[1.3fr_0.7fr] lg:px-8">
          <div className="space-y-5">
            <span className="inline-flex rounded-full border border-mint/30 bg-mint/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.28em] text-mint">
              EyeQ MVP
            </span>
            <div className="space-y-3">
              <h1 className="max-w-3xl font-display text-4xl font-bold leading-tight text-white sm:text-5xl">
                AI-powered abuse detection for high-risk care environments.
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-sand/80 sm:text-base">{headline}</p>
            </div>
          </div>
          <LiveStatus status={status} />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-6">
          <Controls
            running={status.running}
            busy={busy}
            sourceMode={sourceMode}
            setSourceMode={setSourceMode}
            cameraIndex={cameraIndex}
            setCameraIndex={setCameraIndex}
            rtspUrl={rtspUrl}
            setRtspUrl={setRtspUrl}
            onStart={handleStart}
            onStop={handleStop}
          />
          <LiveFeed
            apiBase={API_BASE}
            running={status.running}
            status={status}
            latestAlert={alerts[0] ?? null}
            onReview={setSelectedAlert}
          />
          <RecordingReview apiBase={API_BASE} onReview={setSelectedAlert} onError={setErrorMessage} />
          <div className="panel p-5">
            <p className="text-xs uppercase tracking-[0.3em] text-sand/45">Detection stack</p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-sand/75">
              <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                <p className="font-medium text-white">Pose + Proximity</p>
                <p className="mt-2 text-xs leading-6">YOLOv8-pose tracks bodies and flags high-motion close contact or caretaker absence.</p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                <p className="font-medium text-white">Scene Reasoning</p>
                <p className="mt-2 text-xs leading-6">OpenRouter vision models verify context before any clip is saved or alerts are sent.</p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                <p className="font-medium text-white">Evidence Buffer</p>
                <p className="mt-2 text-xs leading-6">A rolling 30-second MP4 clip is preserved only around flagged moments.</p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                <p className="font-medium text-white">Immediate Escalation</p>
                <p className="mt-2 text-xs leading-6">Push notifications send the guardian straight to the incident snapshot and clip instead of raw video review.</p>
              </div>
            </div>
          </div>
          {errorMessage ? (
            <div className="rounded-2xl border border-coral/25 bg-coral/10 px-4 py-3 text-sm text-coral">
              {errorMessage}
            </div>
          ) : null}
        </div>

        <AlertFeed alerts={alerts} onReview={setSelectedAlert} />
      </section>

      <ClipModal alert={selectedAlert} apiBase={API_BASE} onClose={() => setSelectedAlert(null)} />
    </main>
  );
}

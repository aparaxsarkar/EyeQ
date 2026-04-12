import { useRef } from "react";

function formatSeconds(totalSeconds) {
  const wholeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(wholeSeconds / 60);
  const seconds = wholeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function ClipModal({ alert, apiBase, onClose }) {
  if (!alert) {
    return null;
  }

  const videoRef = useRef(null);
  const clipUrl = alert.clip_url ? `${apiBase}${alert.clip_url}` : null;
  const incidentOffset = typeof alert.incident_offset_seconds === "number" ? alert.incident_offset_seconds : null;
  const incidentStart = incidentOffset !== null ? Math.max(incidentOffset - 3, 0) : 0;

  function jumpToIncident() {
    if (!videoRef.current || incidentOffset === null) {
      return;
    }
    videoRef.current.currentTime = incidentStart;
    void videoRef.current.play().catch(() => {});
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/75 px-4 py-6 backdrop-blur-sm sm:items-center">
      <div className="panel w-full max-w-3xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-sand/45">Flagged clip</p>
            <h3 className="mt-2 font-display text-2xl font-semibold text-white">Scene review</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 px-3 py-1 text-sm text-sand/70 transition hover:border-white/30 hover:text-white"
          >
            Close
          </button>
        </div>

        <div className="space-y-5 p-5">
          {clipUrl ? (
            <div className="space-y-3">
              <video
                ref={videoRef}
                controls
                className="w-full rounded-3xl border border-white/10 bg-black/40"
                src={clipUrl}
                onLoadedMetadata={() => {
                  if (incidentOffset !== null && videoRef.current) {
                    videoRef.current.currentTime = incidentStart;
                  }
                }}
              />
              {incidentOffset !== null ? (
                <div className="flex flex-col gap-3 rounded-2xl border border-white/8 bg-black/20 p-4 text-sm text-sand/75 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-sand/40">Incident Playback</p>
                    <p className="mt-2">
                      Incident detected at {formatSeconds(alert.timestamp_seconds ?? 0)} in the original recording.
                    </p>
                    <p className="mt-1 text-xs text-sand/50">
                      Saved review clip covers {formatSeconds(alert.clip_start_seconds ?? 0)} to {formatSeconds(alert.clip_end_seconds ?? alert.timestamp_seconds ?? 0)}.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={jumpToIncident}
                    className="rounded-2xl border border-mint/30 bg-mint/10 px-4 py-2 text-sm font-medium text-mint transition hover:bg-mint/15"
                  >
                    Jump To Incident
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-3xl border border-dashed border-white/12 bg-black/20 p-8 text-sm text-sand/60">
              No clip path was stored for this alert.
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-3xl border border-white/8 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.26em] text-sand/45">Reason</p>
              <p className="mt-3 text-sm leading-7 text-sand/80">{alert.reason}</p>
            </div>
            <div className="rounded-3xl border border-white/8 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.26em] text-sand/45">Suggested action</p>
              <p className="mt-3 text-sm leading-7 text-sand/80">{alert.suggested_action || "Review the clip and check on the dependent immediately."}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

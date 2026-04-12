import { useMemo } from "react";

function getOutcome(status) {
  if (status?.review_in_progress) {
    return {
      label: "Reviewing",
      tone: "border-mint/30 bg-mint/10 text-mint",
      detail: "CareWatch is checking the suspicious scene now.",
    };
  }

  if (status?.last_classifier_severity === "high" || status?.last_classifier_severity === "medium" || status?.last_classifier_severity === "low") {
    return {
      label: "Flagged",
      tone:
        status?.last_classifier_severity === "high"
          ? "border-coral/30 bg-coral/10 text-coral"
          : status?.last_classifier_severity === "medium"
            ? "border-amberglow/30 bg-amberglow/10 text-amberglow"
            : "border-citron/30 bg-citron/10 text-citron",
      detail: status?.last_classifier_reason ?? "A concerning scene was flagged.",
    };
  }

  if (status?.last_classifier_severity === "timeout") {
    return {
      label: "Timed Out",
      tone: "border-amberglow/30 bg-amberglow/10 text-amberglow",
      detail: status?.last_classifier_reason ?? "The review did not finish in time.",
    };
  }

  if (status?.last_classifier_severity === "error") {
    return {
      label: "Review Failed",
      tone: "border-coral/30 bg-coral/10 text-coral",
      detail: status?.last_classifier_reason ?? "The review failed.",
    };
  }

  return {
    label: "Cleared",
    tone: "border-white/10 bg-white/5 text-white",
    detail: status?.last_classifier_reason ?? "No concern detected.",
  };
}

export default function LiveFeed({ apiBase, running, status, latestAlert, onReview }) {
  const streamUrl = useMemo(() => {
    if (!running) {
      return "";
    }
    return `${apiBase}/stream/mjpeg?ts=${Date.now()}`;
  }, [apiBase, running]);
  const snapshotUrl = useMemo(() => {
    if (!status?.last_snapshot_url) {
      return "";
    }
    return `${apiBase}${status.last_snapshot_url}`;
  }, [apiBase, status?.last_snapshot_url]);
  const outcome = getOutcome(status);

  const severityColor =
    status?.last_classifier_severity === "high"
      ? "text-coral"
      : status?.last_classifier_severity === "medium"
        ? "text-amberglow"
        : status?.last_classifier_severity === "low"
          ? "text-citron"
          : status?.last_classifier_severity === "reviewing"
            ? "text-mint"
            : status?.last_classifier_severity === "timeout"
              ? "text-amberglow"
            : "text-white";

  return (
    <section className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-sand/45">Live feed</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-white">Annotated monitoring preview</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${running ? "bg-mint/15 text-mint" : "bg-white/10 text-sand/60"}`}>
          {running ? "Streaming" : "Idle"}
        </span>
      </div>

      <div className="relative aspect-video overflow-hidden bg-black/40">
        {running ? (
          <>
            <img
              src={streamUrl}
              alt="Live monitoring frame"
              className={`h-full w-full object-cover transition duration-300 ${status?.review_in_progress ? "scale-[1.01] blur-[1.5px] saturate-[0.85]" : ""}`}
            />
            {status?.review_in_progress ? (
              <div className="absolute inset-0 flex items-center justify-center bg-ink/35 backdrop-blur-[1px]">
                <div className="mx-6 w-full max-w-md rounded-3xl border border-mint/25 bg-black/45 px-5 py-4 text-center shadow-[0_18px_60px_rgba(0,0,0,0.28)]">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-mint/35 bg-mint/10">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-mint/30 border-t-mint" />
                  </div>
                  <p className="mt-4 text-xs uppercase tracking-[0.28em] text-mint/80">Processing live scene</p>
                  <p className="mt-2 text-sm leading-6 text-sand/85">
                    CareWatch is reviewing the suspicious movement now. The live feed can pause briefly while the scene is scored.
                  </p>
                  <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full w-1/3 animate-pulse rounded-full bg-mint/80" />
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm leading-7 text-sand/55">
            Start monitoring to show the live camera feed with CareWatch person boxes and keypoints.
          </div>
        )}
      </div>

      <div className="grid gap-3 border-t border-white/8 bg-black/20 px-5 py-4 text-sm text-sand/70 md:grid-cols-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">People</p>
          <p className="mt-2 text-white">{status?.people_count ?? 0}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Heuristic</p>
          <p className="mt-2 text-white">{status?.last_heuristic_reason ?? "monitoring"}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Vision Decision</p>
          <p className={`mt-2 ${severityColor}`}>
            {status?.last_classifier_severity ?? "none"}: {status?.last_classifier_reason ?? "No concern detected."}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Detection FPS</p>
          <p className="mt-2 text-white">{status?.estimated_detection_fps ?? 0}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Review Latency</p>
          <p className="mt-2 text-white">
            {status?.last_review_latency_ms ? `${status.last_review_latency_ms} ms` : "Idle"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Review State</p>
          <p className={`mt-2 ${status?.review_in_progress ? "text-mint" : "text-white"}`}>
            {status?.review_in_progress ? "reviewing scene" : "ready"}
          </p>
        </div>
      </div>

      <div className="border-t border-white/8 px-5 py-4">
        <div className="rounded-3xl border border-white/8 bg-black/20 p-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="space-y-3">
              <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Live Outcome</p>
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${outcome.tone}`}>
                {outcome.label}
              </span>
              <p className="max-w-2xl text-sm leading-7 text-sand/80">{outcome.detail}</p>
            </div>

            {latestAlert?.clip_url && (status?.last_classifier_severity === "high" || status?.last_classifier_severity === "medium" || status?.last_classifier_severity === "low") ? (
              <button
                type="button"
                onClick={() => onReview(latestAlert)}
                className="rounded-2xl border border-mint/30 bg-mint/10 px-4 py-2 text-sm font-medium text-mint transition hover:border-mint/50 hover:bg-mint/15"
              >
                Open Latest Clip
              </button>
            ) : null}
          </div>

          {snapshotUrl ? (
            <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
              <img
                src={snapshotUrl}
                alt="Latest suspicious live snapshot"
                className="aspect-video w-full rounded-2xl border border-white/10 object-cover"
              />
              <div className="space-y-2 text-sm text-sand/75">
                <p className="text-xs uppercase tracking-[0.22em] text-sand/40">Latest Suspicious Frame</p>
                <p className="text-white">
                  {status?.last_snapshot_reason ?? "suspicious_activity"}
                </p>
                <p>
                  {status?.last_snapshot_timestamp
                    ? new Date(status.last_snapshot_timestamp).toLocaleString()
                    : "Timestamp unavailable"}
                </p>
                <p className="leading-7 text-sand/65">
                  CareWatch saves a still frame when a new live anomaly review begins so the operator can see what triggered the check.
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

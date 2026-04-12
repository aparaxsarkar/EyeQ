const severityStyles = {
  high: "bg-coral/15 text-coral border-coral/25",
  medium: "bg-amberglow/15 text-amberglow border-amberglow/25",
  low: "bg-citron/15 text-citron border-citron/25",
  none: "bg-white/10 text-sand/70 border-white/10",
};

export default function AlertFeed({ alerts, onReview }) {
  return (
    <section className="panel flex min-h-[28rem] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-sand/45">Alert feed</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-white">Recent escalations</h2>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-sand/60">
          {alerts.length} loaded
        </span>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {alerts.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-white/10 bg-black/10 p-6 text-sm leading-7 text-sand/60">
            No alerts yet. Once a scene is flagged and verified, it will appear here with its saved clip.
          </div>
        ) : null}

        {alerts.map((alert) => (
          <article key={alert.id} className="rounded-3xl border border-white/8 bg-black/20 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
                      severityStyles[alert.severity] ?? severityStyles.none
                    }`}
                  >
                    {alert.severity}
                  </span>
                  <span className="text-xs text-sand/45">{new Date(alert.timestamp).toLocaleString()}</span>
                </div>
                <p className="text-sm leading-7 text-sand/80">{alert.reason}</p>
              </div>

              <button
                type="button"
                disabled={!alert.clip_url}
                onClick={() => onReview(alert)}
                className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-medium text-white transition hover:border-mint/50 hover:bg-mint/10 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Review Clip
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}


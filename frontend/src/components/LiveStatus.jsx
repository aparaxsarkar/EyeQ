function formatUptime(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return [hrs, mins, secs].map((value) => String(value).padStart(2, "0")).join(":");
}

export default function LiveStatus({ status }) {
  const online = status?.running;

  return (
    <div className="panel flex flex-col justify-between gap-6 border border-white/8 bg-black/20 p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.28em] text-sand/45">Live status</span>
        <span
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
            online ? "bg-mint/15 text-mint" : "bg-coral/15 text-coral"
          }`}
        >
          <span className={`h-2.5 w-2.5 rounded-full ${online ? "bg-mint" : "bg-coral"}`} />
          {online ? "Active" : "Stopped"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-sand/40">Uptime</p>
          <p className="mt-3 font-display text-2xl font-semibold text-white">{formatUptime(status?.uptime_seconds ?? 0)}</p>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-sand/40">Alerts</p>
          <p className="mt-3 font-display text-2xl font-semibold text-white">{status?.alert_count ?? 0}</p>
        </div>
      </div>

      <p className="text-sm leading-7 text-sand/70">
        CareWatch records only the last 30 seconds around a flagged event, keeping evidence focused and reviewable.
      </p>
    </div>
  );
}


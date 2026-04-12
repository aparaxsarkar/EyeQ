export default function Controls({
  running,
  busy,
  sourceMode,
  setSourceMode,
  cameraIndex,
  setCameraIndex,
  rtspUrl,
  setRtspUrl,
  onStart,
  onStop,
}) {
  return (
    <section className="panel p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-sand/45">Controls</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-white">Monitoring session</h2>
        </div>

        <button
          type="button"
          onClick={running ? onStop : onStart}
          disabled={busy}
          className={`rounded-2xl px-5 py-3 text-sm font-semibold transition ${
            running
              ? "bg-coral text-white hover:bg-coral/90"
              : "bg-citron text-ink-950 hover:bg-citron/90"
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          {busy ? "Working..." : running ? "Stop Monitoring" : "Start Monitoring"}
        </button>
      </div>

      <div className="mt-5 space-y-4 rounded-2xl border border-white/8 bg-black/20 p-4 text-sm text-sand/75">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSourceMode("camera")}
            className={`rounded-full px-3 py-1.5 text-xs font-medium uppercase tracking-[0.16em] ${
              sourceMode === "camera" ? "bg-citron text-ink-950" : "bg-white/8 text-sand/70"
            }`}
          >
            Local Camera
          </button>
          <button
            type="button"
            onClick={() => setSourceMode("rtsp")}
            className={`rounded-full px-3 py-1.5 text-xs font-medium uppercase tracking-[0.16em] ${
              sourceMode === "rtsp" ? "bg-citron text-ink-950" : "bg-white/8 text-sand/70"
            }`}
          >
            RTSP Stream
          </button>
        </div>

        {sourceMode === "camera" ? (
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-sand/45">Camera index</span>
            <input
              type="number"
              min="0"
              value={cameraIndex}
              onChange={(event) => setCameraIndex(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-citron/50"
            />
          </label>
        ) : (
          <label className="block">
            <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-sand/45">RTSP URL</span>
            <input
              type="text"
              value={rtspUrl}
              onChange={(event) => setRtspUrl(event.target.value)}
              placeholder="rtsp://user:pass@camera/stream"
              className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-citron/50"
            />
          </label>
        )}
      </div>
    </section>
  );
}

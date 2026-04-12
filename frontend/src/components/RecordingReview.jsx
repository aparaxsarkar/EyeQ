import { useRef, useState } from "react";

async function readJson(response) {
  const payload = await response.text();
  if (!response.ok) {
    throw new Error(payload || `Request failed with ${response.status}`);
  }
  return payload ? JSON.parse(payload) : {};
}

const severityStyles = {
  high: "bg-coral/15 text-coral border-coral/25",
  medium: "bg-amberglow/15 text-amberglow border-amberglow/25",
  low: "bg-citron/15 text-citron border-citron/25",
  none: "bg-white/10 text-sand/70 border-white/10",
};

function formatSeconds(totalSeconds) {
  const wholeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(wholeSeconds / 60);
  const seconds = wholeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function RecordingReview({ apiBase, onReview, onError }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function handleAnalyze() {
    const resolvedFile = file ?? inputRef.current?.files?.[0] ?? null;
    if (!resolvedFile) {
      onError("Choose a recording first.");
      return;
    }

    setBusy(true);
    onError("");
    try {
      const formData = new FormData();
      formData.append("file", resolvedFile);
      const response = await fetch(`${apiBase}/recordings/analyze`, {
        method: "POST",
        body: formData,
      });
      const payload = await readJson(response);
      setResult(payload);
    } catch (error) {
      onError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-sand/45">Recording review</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-white">Analyze saved footage</h2>
        </div>
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={busy}
          className="rounded-2xl bg-amberglow px-5 py-3 text-sm font-semibold text-ink-950 transition hover:bg-amberglow/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Analyzing..." : "Analyze Recording"}
        </button>
      </div>

      <div className="mt-5 rounded-2xl border border-white/8 bg-black/20 p-4">
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          onChange={(event) => {
            const nextFile = event.target.files?.[0] ?? null;
            setFile(nextFile);
            setSelectedFilename(nextFile?.name ?? "");
            onError("");
          }}
          className="block w-full text-sm text-sand/75 file:mr-4 file:rounded-full file:border-0 file:bg-white/10 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white"
        />
        {selectedFilename ? (
          <div className="mt-3 inline-flex rounded-full border border-mint/30 bg-mint/10 px-3 py-1 text-xs font-medium text-mint">
            Selected: {selectedFilename}
          </div>
        ) : null}
      </div>

      {result ? (
        <div className="mt-5 space-y-3">
          <div className="rounded-2xl border border-white/8 bg-black/20 p-4 text-sm text-sand/75">
            <p>
              <span className="font-medium text-white">{result.filename}</span> scanned with{" "}
              <span className="font-medium text-white">{result.finding_count}</span> flagged finding(s).
            </p>
          </div>

          {result.findings.length === 0 ? (
            <div className="rounded-2xl border border-white/8 bg-black/20 p-4 text-sm text-sand/60">
              No flagged moments were found in this recording.
            </div>
          ) : null}

          {result.findings.map((finding, index) => (
            <article key={`${finding.timestamp_seconds}-${index}`} className="rounded-3xl border border-white/8 bg-black/20 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
                        severityStyles[finding.severity] ?? severityStyles.none
                      }`}
                    >
                      {finding.severity}
                    </span>
                    <span className="text-xs text-sand/45">Incident at {formatSeconds(finding.timestamp_seconds)}</span>
                  </div>
                  <p className="text-sm leading-7 text-sand/80">{finding.reason}</p>
                  <p className="text-xs leading-6 text-sand/50">
                    Review clip covers {formatSeconds(finding.clip_start_seconds ?? 0)} to {formatSeconds(finding.clip_end_seconds ?? finding.timestamp_seconds)} in the original recording.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={!finding.clip_url}
                  onClick={() => onReview(finding)}
                  className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-medium text-white transition hover:border-mint/50 hover:bg-mint/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Review Clip
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

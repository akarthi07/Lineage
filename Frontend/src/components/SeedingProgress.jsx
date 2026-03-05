import { useEffect, useState } from "react";

const STAGES = [
  { label: "Searching MusicBrainz", detail: "Fetching documented relationships" },
  { label: "Querying Last.fm", detail: "Mapping listener patterns" },
  { label: "Resolving identities", detail: "Cross-referencing sources" },
  { label: "Building the graph", detail: "Calculating influence strength" },
  { label: "Almost ready", detail: "Finalising the lineage map" },
];

export default function SeedingProgress({ artistName, onRetry }) {
  const [stageIdx, setStageIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const stageTimer = setInterval(() => {
      setStageIdx((i) => Math.min(i + 1, STAGES.length - 1));
    }, 6000);

    const elapsedTimer = setInterval(() => {
      setElapsed((s) => s + 1);
    }, 1000);

    return () => {
      clearInterval(stageTimer);
      clearInterval(elapsedTimer);
    };
  }, []);

  const stage = STAGES[stageIdx];
  const progress = ((stageIdx + 1) / STAGES.length) * 100;

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 animate-fade-in">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <p className="text-text-muted text-sm font-medium uppercase tracking-widest">Mapping lineage</p>
          <h2 className="text-2xl font-semibold text-text-primary">
            {artistName}
          </h2>
          <p className="text-text-secondary text-sm">
            We're tracing the roots of this artist across multiple sources.
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-3">
          <div className="h-1 bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-purple rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${progress}%`, boxShadow: "0 0 8px rgba(124,92,252,0.5)" }}
            />
          </div>

          {/* Current stage */}
          <div className="flex items-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-purple flex-shrink-0"
              style={{ boxShadow: "0 0 6px rgba(124,92,252,0.8)", animation: "pulse 2s infinite" }}
            />
            <div>
              <p className="text-sm font-medium text-text-primary">{stage.label}</p>
              <p className="text-xs text-text-muted">{stage.detail}</p>
            </div>
            <span className="ml-auto text-xs text-text-muted font-mono">{elapsed}s</span>
          </div>
        </div>

        {/* Stage list */}
        <div className="space-y-2">
          {STAGES.map((s, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 py-2 px-3 rounded-xl transition-all duration-300 ${
                i === stageIdx
                  ? "bg-purple/10 border border-purple/20"
                  : i < stageIdx
                  ? "opacity-40"
                  : "opacity-20"
              }`}
            >
              <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${
                i < stageIdx
                  ? "bg-purple border-purple"
                  : i === stageIdx
                  ? "border-purple"
                  : "border-border"
              }`}>
                {i < stageIdx && (
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                    <path d="M1.5 4l2 2 3-3" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              <span className="text-xs text-text-secondary">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Retry note */}
        {elapsed > 45 && (
          <div className="text-center animate-fade-in">
            <p className="text-xs text-text-muted mb-2">Taking longer than usual?</p>
            <button className="btn-ghost text-xs" onClick={onRetry}>
              Check status
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

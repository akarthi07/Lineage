export default function StrengthIndicator({ strength, sourceType, showLabel = false }) {
  const pct = Math.round((strength ?? 0) * 100);

  const color = sourceType === "musicbrainz"
    ? "bg-purple"
    : sourceType === "lastfm_similar"
    ? "bg-teal"
    : "bg-text-muted";

  const label = sourceType === "musicbrainz"
    ? "Documented"
    : sourceType === "lastfm_similar"
    ? "Connected"
    : "Inferred";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-2xs text-text-muted font-mono w-8 text-right">{pct}%</span>
      )}
      {showLabel && (
        <span className="text-2xs text-text-secondary">{label}</span>
      )}
    </div>
  );
}

export default function UndergroundBadge({ score, size = "sm" }) {
  if (score === undefined || score === null) return null;

  const getLabel = (s) => {
    if (s >= 0.85) return "Deep Underground";
    if (s >= 0.7)  return "Underground";
    if (s >= 0.4)  return "Indie";
    if (s >= 0.15) return "Semi-mainstream";
    return "Mainstream";
  };

  const getColor = (s) => {
    if (s >= 0.7)  return "text-underground border-underground/30 bg-underground/10";
    if (s >= 0.4)  return "text-teal border-teal/30 bg-teal/10";
    if (s >= 0.15) return "text-text-secondary border-border bg-elevated";
    return "text-mainstream border-border bg-elevated";
  };

  const sizeClass = size === "xs"
    ? "text-2xs px-1.5 py-0.5"
    : "text-xs px-2 py-0.5";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-medium ${sizeClass} ${getColor(score)}`}>
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ background: "currentColor", opacity: 0.8 }}
      />
      {getLabel(score)}
    </span>
  );
}

import { useState, useEffect, useRef } from "react";

const PLACEHOLDERS = [
  "What influenced Radiohead?",
  "Trace the roots of osamason",
  "Show me the lineage of Joy Division",
  "What came before Talk Talk?",
  "Find who shaped Portishead",
  "Explore the origins of Can",
];

export default function SearchBar({ onSubmit, loading = false, size = "default" }) {
  const [value, setValue] = useState("");
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (focused) return;
    const id = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % PLACEHOLDERS.length);
    }, 3000);
    return () => clearInterval(id);
  }, [focused]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || loading) return;
    onSubmit(q);
  };

  const large = size === "large";

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div
        className={`relative flex items-center gap-3 bg-elevated border rounded-2xl transition-all duration-200 ${
          focused
            ? "border-purple shadow-glow"
            : "border-border hover:border-border/80"
        } ${large ? "px-5 py-4" : "px-4 py-3"}`}
      >
        {/* Search icon */}
        <svg
          className={`flex-shrink-0 transition-colors duration-200 ${focused ? "text-purple" : "text-text-muted"}`}
          width={large ? 18 : 16}
          height={large ? 18 : 16}
          viewBox="0 0 16 16"
          fill="none"
        >
          <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>

        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={PLACEHOLDERS[placeholderIdx]}
          className={`flex-1 bg-transparent outline-none text-text-primary placeholder-text-muted transition-all duration-200 ${
            large ? "text-base" : "text-sm"
          }`}
          disabled={loading}
          autoComplete="off"
          spellCheck={false}
        />

        {/* Loading dots or submit */}
        {loading ? (
          <div className="flex items-center gap-1 px-2">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-purple"
                style={{ animation: `dotBounce 1.4s ${i * 0.16}s infinite ease-in-out` }}
              />
            ))}
          </div>
        ) : value.trim() ? (
          <button
            type="submit"
            className="btn-primary py-1.5 px-3 text-xs"
          >
            Map
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M1 5h8M6 2l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        ) : null}
      </div>

      <style>{`
        @keyframes dotBounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </form>
  );
}

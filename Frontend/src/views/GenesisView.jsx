import { useState, useEffect } from "react";
import { mockGenesis } from "../data/mockGenesis";
import UndergroundBadge from "../components/shared/UndergroundBadge";
import GenreTag from "../components/shared/GenreTag";
import { CardSkeleton } from "../components/shared/Skeleton";

function ArtistCard({ artist, delay = 0 }) {
  return (
    <div
      className="card card-hover p-4 animate-slide-up"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="font-semibold text-sm text-text-primary">{artist.name}</p>
          <p className="text-xs text-text-muted mt-0.5">{artist.role}</p>
        </div>
        <UndergroundBadge score={artist.underground_score} size="xs" />
      </div>
      <div className="flex items-center gap-1.5 text-2xs text-text-muted mb-3 font-mono">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="text-text-muted">
          <circle cx="5" cy="5" r="4" stroke="currentColor" strokeWidth="1.2" />
          <path d="M5 2.5v2.5l1.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        {(artist.lastfm_listeners ?? 0).toLocaleString()} Last.fm listeners
      </div>
      <div className="flex flex-wrap gap-1">
        {(artist.tags ?? []).slice(0, 3).map((t) => (
          <GenreTag key={t} label={t} variant="purple" />
        ))}
      </div>
    </div>
  );
}

function LineageRoot({ root, delay = 0 }) {
  return (
    <div
      className="flex items-start gap-3 p-4 rounded-xl border border-border hover:border-purple/30 transition-colors duration-200 animate-slide-up"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}
    >
      <div className="w-1.5 h-1.5 rounded-full bg-purple mt-1.5 flex-shrink-0" />
      <div>
        <p className="font-medium text-sm text-text-primary">{root.name}</p>
        <p className="text-xs text-text-muted mt-0.5">{root.description}</p>
      </div>
    </div>
  );
}

export default function GenesisView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Try real API, fall back to mock
    fetch("/api/genesis/featured")
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setData(mockGenesis))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }

  if (!data) return null;

  const statusColor = data.timeline?.current_status === "expanding"
    ? "text-underground bg-underground/10 border-underground/30"
    : "text-text-secondary bg-elevated border-border";

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-10 animate-fade-in">
      {/* Hero */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-text-muted uppercase tracking-widest">Genesis Mode</span>
          <div className="h-px flex-1 bg-border" />
          <span className={`text-2xs font-medium px-2 py-0.5 rounded-full border ${statusColor}`}>
            {data.timeline?.current_status}
          </span>
        </div>

        <div>
          <h1 className="text-4xl font-semibold text-text-primary tracking-tight mb-3">
            {data.name}
          </h1>
          <p className="text-text-secondary text-base leading-relaxed max-w-2xl">
            {data.description}
          </p>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-text-muted">
              <path d="M6 1a3 3 0 100 6 3 3 0 000-6zM1 11c0-2.21 2.24-4 5-4s5 1.79 5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            <span className="text-xs text-text-muted">{data.key_artists?.length} key artists</span>
          </div>
          <div className="flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-text-muted">
              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M6 3v3l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            <span className="text-xs text-text-muted">Emerged {data.timeline?.emerged}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(data.geography ?? []).map((g) => (
              <span key={g} className="text-xs text-text-muted px-2 py-0.5 rounded-lg bg-elevated border border-border">{g}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Sound characteristics */}
      <div>
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Sound profile</h2>
        <div className="flex flex-wrap gap-2">
          {(data.sound_characteristics ?? []).map((s, i) => (
            <GenreTag key={i} label={s} variant="teal" />
          ))}
        </div>
      </div>

      {/* Artists grid */}
      <div>
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Key artists</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(data.key_artists ?? []).map((a, i) => (
            <ArtistCard key={a.name} artist={a} delay={i * 60} />
          ))}
        </div>
      </div>

      {/* Lineage roots */}
      <div>
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Where it came from</h2>
        <div className="space-y-2">
          {(data.lineage_roots ?? []).map((r, i) => (
            <LineageRoot key={r.name} root={r} delay={i * 60} />
          ))}
        </div>
      </div>
    </div>
  );
}

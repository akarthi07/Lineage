import { useState, useEffect } from "react";
import { mockGenesis } from "../data/mockGenesis";
import UndergroundBadge from "../components/shared/UndergroundBadge";
import GenreTag from "../components/shared/GenreTag";
import { CardSkeleton } from "../components/shared/Skeleton";

/* ── Shared sub-components ─────────────────────────────────────── */

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

/* ── Detected cluster card ─────────────────────────────────────── */

function ClusterCard({ cluster, delay = 0, onExpand }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="card p-5 space-y-4 animate-slide-up"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xs font-mono text-teal bg-teal/10 border border-teal/30 px-1.5 py-0.5 rounded">
              Cluster #{cluster.cluster_id}
            </span>
            <span className="text-2xs text-text-muted font-mono">
              {cluster.size} artists
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-2xs text-text-muted">
              cohesion: {(cluster.cohesion_score * 100).toFixed(0)}%
            </span>
            <span className="text-2xs text-text-muted">
              avg underground: {(cluster.avg_underground * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      {cluster.description && (
        <p className="text-sm text-text-secondary leading-relaxed">
          {cluster.description}
        </p>
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {(cluster.top_tags ?? []).slice(0, 8).map((t) => (
          <GenreTag key={t} label={t} variant="teal" />
        ))}
      </div>

      {/* Geography + Era row */}
      <div className="flex flex-wrap items-center gap-3 text-2xs text-text-muted">
        {cluster.avg_year && (
          <span className="flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="text-text-muted">
              <circle cx="5" cy="5" r="4" stroke="currentColor" strokeWidth="1.2" />
              <path d="M5 2.5v2.5l1.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            ~{Math.round(cluster.avg_year)}
          </span>
        )}
        {(cluster.geography ?? []).map((g) => (
          <span key={g} className="px-1.5 py-0.5 rounded-md bg-elevated border border-border">
            {g}
          </span>
        ))}
      </div>

      {/* Artists (collapsible) */}
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-purple hover:text-purple/80 transition-colors font-medium"
        >
          {expanded ? "Hide artists" : `Show ${cluster.artists?.length ?? 0} artists`}
        </button>

        {expanded && (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(cluster.artists ?? []).map((a, i) => (
              <div
                key={a.mbid}
                className="flex items-center justify-between gap-2 p-2.5 rounded-lg border border-border hover:border-purple/30 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-xs font-medium text-text-primary truncate">{a.name}</p>
                  <p className="text-2xs text-text-muted font-mono">
                    {(a.lastfm_listeners ?? 0).toLocaleString()} listeners
                  </p>
                </div>
                <UndergroundBadge score={a.underground_score} size="xs" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lineage roots */}
      {cluster.lineage_roots?.length > 0 && (
        <div>
          <p className="text-2xs font-medium text-text-muted uppercase tracking-widest mb-2">
            Shared lineage roots
          </p>
          <div className="space-y-1.5">
            {cluster.lineage_roots.slice(0, 5).map((root) => (
              <div key={root.mbid} className="flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-1 h-1 rounded-full bg-purple flex-shrink-0" />
                  <span className="text-text-primary truncate">{root.name}</span>
                </div>
                <span className="text-text-muted font-mono text-2xs flex-shrink-0">
                  {Math.round(root.fraction * 100)}% share
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Curated showcase section ──────────────────────────────────── */

function CuratedShowcase({ data }) {
  const statusColor = data.timeline?.current_status === "expanding"
    ? "text-underground bg-underground/10 border-underground/30"
    : "text-text-secondary bg-elevated border-border";

  return (
    <div className="space-y-10">
      {/* Hero */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-text-muted uppercase tracking-widest">Featured</span>
          <div className="h-px flex-1 bg-border" />
          <span className={`text-2xs font-medium px-2 py-0.5 rounded-full border ${statusColor}`}>
            {data.timeline?.current_status}
          </span>
        </div>

        <div>
          <h2 className="text-3xl font-semibold text-text-primary tracking-tight mb-3">
            {data.name}
          </h2>
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
        <h3 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Sound profile</h3>
        <div className="flex flex-wrap gap-2">
          {(data.sound_characteristics ?? []).map((s, i) => (
            <GenreTag key={i} label={s} variant="teal" />
          ))}
        </div>
      </div>

      {/* Artists grid */}
      <div>
        <h3 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Key artists</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(data.key_artists ?? []).map((a, i) => (
            <ArtistCard key={a.name} artist={a} delay={i * 60} />
          ))}
        </div>
      </div>

      {/* Lineage roots */}
      <div>
        <h3 className="text-xs font-medium text-text-muted uppercase tracking-widest mb-4">Where it came from</h3>
        <div className="space-y-2">
          {(data.lineage_roots ?? []).map((r, i) => (
            <LineageRoot key={r.name} root={r} delay={i * 60} />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Detected clusters section ─────────────────────────────────── */

function DetectedClusters({ clusters, loading, error }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[...Array(3)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-text-muted py-4">
        Could not detect clusters: {error}
      </p>
    );
  }

  if (!clusters || clusters.length === 0) {
    return (
      <p className="text-sm text-text-muted py-4">
        No proto-genre clusters detected yet. Run the embedding pipeline and ensure
        there are enough underground artists with vectors.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {clusters.map((c, i) => (
        <ClusterCard key={c.cluster_id} cluster={c} delay={i * 80} />
      ))}
    </div>
  );
}

/* ── Main view ─────────────────────────────────────────────────── */

export default function GenesisView() {
  const [featured, setFeatured] = useState(null);
  const [detected, setDetected] = useState(null);
  const [loadingFeatured, setLoadingFeatured] = useState(true);
  const [loadingDetected, setLoadingDetected] = useState(true);
  const [detectedError, setDetectedError] = useState(null);
  const [activeTab, setActiveTab] = useState("featured");

  useEffect(() => {
    // Fetch curated showcase
    fetch("/api/genesis/featured")
      .then((r) => r.json())
      .then((d) => setFeatured(d))
      .catch(() => setFeatured(mockGenesis))
      .finally(() => setLoadingFeatured(false));

    // Fetch detected clusters
    fetch("/api/genesis/detect")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d) => setDetected(d.clusters ?? []))
      .catch((err) => {
        setDetectedError(err.message);
        setDetected([]);
      })
      .finally(() => setLoadingDetected(false));
  }, []);

  const loading = activeTab === "featured" ? loadingFeatured : loadingDetected;

  if (loading && !featured && !detected) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-8 animate-fade-in">
      {/* Page header + tabs */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-text-muted uppercase tracking-widest">Genesis Mode</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <div className="flex gap-1 p-0.5 rounded-lg bg-elevated border border-border w-fit">
          <button
            onClick={() => setActiveTab("featured")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
              activeTab === "featured"
                ? "bg-surface text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Featured
          </button>
          <button
            onClick={() => setActiveTab("detected")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 flex items-center gap-1.5 ${
              activeTab === "detected"
                ? "bg-surface text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Detected
            {detected && detected.length > 0 && (
              <span className="text-2xs bg-teal/15 text-teal px-1.5 py-0.5 rounded-full font-mono">
                {detected.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "featured" && featured && <CuratedShowcase data={featured} />}

      {activeTab === "detected" && (
        <DetectedClusters
          clusters={detected}
          loading={loadingDetected}
          error={detectedError}
        />
      )}
    </div>
  );
}

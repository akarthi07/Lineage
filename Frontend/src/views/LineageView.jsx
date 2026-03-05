import { useState, useMemo } from "react";
import GenealogyMap from "../components/GenealogyMap";
import ArtistDetailPanel from "../components/ArtistDetailPanel";
import SeedingProgress from "../components/SeedingProgress";
import SearchBar from "../components/SearchBar";
import UndergroundBadge from "../components/shared/UndergroundBadge";
import { useNavigate } from "react-router-dom";

// ─── Small sub-components ─────────────────────────────────────────────────────

function MetaPill({ label, value }) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-elevated border border-border">
      <span className="text-2xs text-text-muted uppercase tracking-wider">{label}</span>
      <span className="text-xs font-mono font-medium text-text-primary">{value}</span>
    </div>
  );
}

function DepthControl({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-elevated border border-border">
      <span className="text-2xs text-text-muted uppercase tracking-wider mr-1">Depth</span>
      {[1, 2, 3, 4].map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={`w-6 h-6 rounded-md text-xs font-medium transition-all duration-150 ${
            value === d
              ? "bg-purple text-white"
              : "text-text-muted hover:text-text-primary hover:bg-surface"
          }`}
        >
          {d}
        </button>
      ))}
    </div>
  );
}

// ─── Filter Panel (slides in from right side) ─────────────────────────────────

const DECADES = ["1950", "1960", "1970", "1980", "1990", "2000", "2010", "2020"];
const SOURCE_OPTIONS = [
  { value: null,               label: "All sources" },
  { value: "musicbrainz",      label: "Documented (MusicBrainz)" },
  { value: "lastfm_similar",   label: "Scene (Last.fm)" },
];

function FilterPanel({ filters, onChange, onClose, data }) {
  // Derive available countries from the data
  const countries = useMemo(() => {
    if (!data?.nodes) return [];
    const seen = new Set();
    data.nodes.forEach((n) => { if (n.country) seen.add(n.country); });
    return Array.from(seen).sort();
  }, [data]);

  const set = (key, val) => onChange({ ...filters, [key]: val });

  const activeCount = [
    filters.underground_only,
    filters.source_type,
    filters.era,
    filters.geo,
  ].filter(Boolean).length;

  return (
    <div className="w-64 border-l border-border bg-surface flex flex-col flex-shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold text-text-primary">Filters</p>
          {activeCount > 0 && (
            <span className="text-2xs px-1.5 py-0.5 rounded-full bg-purple/20 text-purple font-medium">
              {activeCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeCount > 0 && (
            <button
              onClick={() => onChange({})}
              className="text-2xs text-text-muted hover:text-text-primary transition-colors"
            >
              Clear all
            </button>
          )}
          <button
            onClick={onClose}
            className="w-6 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-elevated transition-all duration-150"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M1 1l8 8M9 1L1 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      <div className="p-4 space-y-5">

        {/* Underground only */}
        <div>
          <label className="flex items-center justify-between cursor-pointer group">
            <div>
              <p className="text-xs font-medium text-text-primary">Underground only</p>
              <p className="text-2xs text-text-muted mt-0.5">Highlight artists with score ≥ 40%</p>
            </div>
            <button
              role="switch"
              aria-checked={!!filters.underground_only}
              onClick={() => set("underground_only", !filters.underground_only)}
              className={`relative w-9 h-5 rounded-full transition-all duration-200 flex-shrink-0 ${
                filters.underground_only ? "bg-purple" : "bg-elevated border border-border"
              }`}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-200 ${
                  filters.underground_only ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
          </label>
        </div>

        {/* Connection type */}
        <div>
          <p className="text-2xs text-text-muted uppercase tracking-wider mb-2">Connection type</p>
          <div className="space-y-1">
            {SOURCE_OPTIONS.map(({ value, label }) => (
              <button
                key={String(value)}
                onClick={() => set("source_type", value)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all duration-150 ${
                  filters.source_type === value
                    ? "bg-purple/15 text-purple border border-purple/30"
                    : "text-text-secondary hover:text-text-primary hover:bg-elevated border border-transparent"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Era / decade */}
        <div>
          <p className="text-2xs text-text-muted uppercase tracking-wider mb-2">Era</p>
          <div className="grid grid-cols-4 gap-1">
            {DECADES.map((dec) => (
              <button
                key={dec}
                onClick={() => set("era", filters.era === dec ? null : dec)}
                className={`py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  filters.era === dec
                    ? "bg-purple/15 text-purple border border-purple/30"
                    : "text-text-muted hover:text-text-primary bg-elevated border border-transparent hover:border-border"
                }`}
              >
                {dec.slice(2)}s
              </button>
            ))}
          </div>
          {filters.era && (
            <p className="text-2xs text-text-muted mt-1.5">
              Dimming artists outside the {filters.era}s
            </p>
          )}
        </div>

        {/* Geography */}
        {countries.length > 0 && (
          <div>
            <p className="text-2xs text-text-muted uppercase tracking-wider mb-2">Country</p>
            <div className="space-y-1">
              {countries.map((c) => (
                <button
                  key={c}
                  onClick={() => set("geo", filters.geo === c ? null : c)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all duration-150 ${
                    filters.geo === c
                      ? "bg-purple/15 text-purple border border-purple/30"
                      : "text-text-secondary hover:text-text-primary hover:bg-elevated border border-transparent"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

// ─── Main view ───────────────────────────────────────────────────────────────

export default function LineageView({ data, seeding, artistName, onSearch, loading }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const [depth, setDepth]               = useState(3);
  const [filters, setFilters]           = useState({});
  const [showFilters, setShowFilters]   = useState(false);
  const navigate = useNavigate();

  const rootNode = data?.results?.nodes?.find((n) => n.depth_level === 0);
  const meta     = data?.results?.metadata ?? {};

  const activeFilterCount = [
    filters.underground_only,
    filters.source_type,
    filters.era,
    filters.geo,
  ].filter(Boolean).length;

  const handleDepthChange = (d) => {
    setDepth(d);
    if (rootNode) onSearch(rootNode.name);
  };

  if (seeding) {
    return (
      <SeedingProgress
        artistName={artistName}
        onRetry={() => onSearch(artistName)}
      />
    );
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col overflow-hidden">

      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <div className="border-b border-border bg-bg/80 backdrop-blur-xl px-4 py-2.5 flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => navigate("/")}
          className="btn-ghost py-1.5 px-2.5 text-xs flex items-center gap-1.5"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M9 6H3M5 3L2 6l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>

        <div className="flex-1 max-w-md">
          <SearchBar onSubmit={onSearch} loading={loading} />
        </div>

        {data && (
          <div className="flex items-center gap-2 ml-auto">
            <MetaPill label="nodes" value={meta.total_nodes ?? 0} />
            <MetaPill
              label="underground"
              value={`${Math.round((meta.underground_percentage ?? 0) * 100)}%`}
            />
          </div>
        )}
      </div>

      {/* ── Artist header strip ──────────────────────────────────────────── */}
      {rootNode && (
        <div className="border-b border-border bg-surface/60 backdrop-blur px-4 py-3 flex items-center gap-3 flex-shrink-0">
          {rootNode.image_url ? (
            <img
              src={rootNode.image_url}
              alt={rootNode.name}
              className="w-10 h-10 rounded-xl object-cover border border-border flex-shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-xl bg-elevated border border-border flex items-center justify-center flex-shrink-0">
              <span className="text-base font-semibold text-text-muted">
                {rootNode.name.charAt(0)}
              </span>
            </div>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold text-text-primary truncate">{rootNode.name}</h1>
              <UndergroundBadge score={rootNode.underground_score} size="xs" />
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              {rootNode.formation_year && (
                <span className="text-2xs text-text-muted">est. {rootNode.formation_year}</span>
              )}
              {rootNode.country && (
                <span className="text-2xs text-text-muted">{rootNode.country}</span>
              )}
              {meta.deepest_level_reached != null && (
                <span className="text-2xs text-text-muted">
                  {meta.deepest_level_reached} generation{meta.deepest_level_reached !== 1 ? "s" : ""} deep
                </span>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <DepthControl value={depth} onChange={handleDepthChange} />

            {/* Filter toggle */}
            <button
              onClick={() => setShowFilters((v) => !v)}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium transition-all duration-150 ${
                showFilters || activeFilterCount > 0
                  ? "bg-purple/15 border-purple/30 text-purple"
                  : "bg-elevated border-border text-text-muted hover:text-text-primary hover:border-border"
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path
                  d="M1 2.5h11M3 6.5h7M5 10.5h3"
                  stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
                />
              </svg>
              Filters
              {activeFilterCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-purple text-white text-2xs font-medium flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* Graph canvas — full height, no padding */}
        <div className="flex-1 relative min-w-0">
          {data ? (
            <GenealogyMap
              data={data.results}
              onNodeSelect={setSelectedNode}
              selectedNode={selectedNode}
              filters={filters}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-8"
              style={{ background: "#0A0B0F" }}>
              <div className="w-14 h-14 rounded-2xl bg-surface border border-border flex items-center justify-center mb-5">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-text-muted">
                  <circle cx="12" cy="5"  r="3" stroke="currentColor" strokeWidth="1.5" />
                  <circle cx="5"  cy="19" r="3" stroke="currentColor" strokeWidth="1.5" />
                  <circle cx="19" cy="19" r="3" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M12 8v7M9.5 17.5L6.5 17M14.5 17.5L17.5 17"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              <p className="text-sm font-medium text-text-primary">No lineage loaded</p>
              <p className="text-xs text-text-muted mt-1.5 max-w-xs">
                Search for an artist above to trace their underground roots and documented influences.
              </p>
            </div>
          )}
        </div>

        {/* Filter panel */}
        {showFilters && data && (
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            onClose={() => setShowFilters(false)}
            data={data.results}
          />
        )}

        {/* Artist detail panel */}
        {selectedNode && (
          <div className="w-80 border-l border-border bg-surface overflow-y-auto flex-shrink-0">
            <ArtistDetailPanel
              artist={selectedNode}
              edges={data?.results?.edges ?? []}
              onClose={() => setSelectedNode(null)}
              onExplore={(a) => {
                setSelectedNode(null);
                onSearch(a.name);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

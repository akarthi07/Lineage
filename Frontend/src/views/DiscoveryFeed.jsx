import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import UndergroundBadge from "../components/shared/UndergroundBadge";
import GenreTag from "../components/shared/GenreTag";
import { mockRadioheadLineage } from "../data/mockRadiohead";
import { mockUndergroundLineage } from "../data/mockUnderground";
import { mockGenesis } from "../data/mockGenesis";

const EXAMPLE_QUERIES = [
  "What influenced Radiohead?",
  "Trace the roots of osamason",
  "Show me Joy Division's lineage",
  "What came before Talk Talk?",
  "Find who shaped Portishead",
];

function FeaturedLineageCard({ data, onClick, delay = 0 }) {
  const root = data.results.nodes.find((n) => n.depth_level === 0);
  const meta = data.results.metadata;
  const connections = data.results.edges.length;
  const underground = Math.round((meta.underground_percentage ?? 0) * 100);

  return (
    <button
      onClick={onClick}
      className="card card-hover p-5 text-left w-full animate-slide-up"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}
    >
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-elevated border border-border flex items-center justify-center flex-shrink-0">
          <span className="text-xl font-semibold text-text-muted">
            {root?.name.charAt(0)}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-text-primary">{root?.name}</p>
              <div className="flex items-center gap-2 mt-1">
                <UndergroundBadge score={root?.underground_score} size="xs" />
                {root?.country && (
                  <span className="text-2xs text-text-muted">{root.country}</span>
                )}
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs font-mono text-purple">{underground}%</p>
              <p className="text-2xs text-text-muted">underground</p>
            </div>
          </div>

          <div className="flex items-center gap-3 mt-3 text-xs text-text-muted">
            <span>{meta.total_nodes} artists</span>
            <span className="w-0.5 h-0.5 rounded-full bg-text-muted" />
            <span>{connections} connections</span>
            <span className="w-0.5 h-0.5 rounded-full bg-text-muted" />
            <span>depth {meta.deepest_level_reached}</span>
          </div>

          {root?.tags && root.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {root.tags.slice(0, 4).map((t) => (
                <GenreTag key={t} label={t} />
              ))}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

function GenesisCard({ data, onClick, delay = 0 }) {
  return (
    <button
      onClick={onClick}
      className="card card-hover p-5 text-left w-full animate-slide-up border-teal/20 bg-teal/5"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "both" }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <span className="text-2xs font-medium text-teal uppercase tracking-widest">Genesis</span>
          <h3 className="font-semibold text-text-primary mt-1">{data.name}</h3>
        </div>
        <span className="text-2xs px-2 py-0.5 rounded-full bg-teal/10 border border-teal/30 text-teal font-medium">
          {data.timeline?.current_status}
        </span>
      </div>

      <p className="text-xs text-text-secondary leading-relaxed line-clamp-2 mb-3">
        {data.description}
      </p>

      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-1">
          {(data.sound_characteristics ?? []).slice(0, 3).map((s) => (
            <GenreTag key={s} label={s} variant="teal" />
          ))}
        </div>
        <span className="text-xs text-text-muted">{data.key_artists?.length} artists</span>
      </div>
    </button>
  );
}

export default function DiscoveryFeed({ onSearch, loading }) {
  const navigate = useNavigate();

  const handleSearch = (q) => {
    onSearch(q);
    navigate("/lineage");
  };

  const handleExampleClick = (q) => {
    handleSearch(q);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-16 space-y-16">
      {/* Hero */}
      <div className="text-center space-y-6 animate-fade-in">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple/10 border border-purple/20 text-purple text-xs font-medium mb-2">
          <span className="w-1.5 h-1.5 rounded-full bg-purple" />
          Music Genealogy
        </div>

        <h1 className="text-5xl sm:text-6xl font-semibold tracking-tight text-balance">
          Trace the DNA
          <br />
          <span className="gradient-text">of any sound</span>
        </h1>

        <p className="text-text-secondary text-lg max-w-xl mx-auto leading-relaxed">
          Every artist has roots. Discover the underground artists who shaped your favourite music — and the ones still underground today.
        </p>

        {/* Search */}
        <div className="max-w-lg mx-auto">
          <SearchBar onSubmit={handleSearch} loading={loading} size="large" />
        </div>

        {/* Example queries */}
        <div className="flex flex-wrap justify-center gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => handleExampleClick(q)}
              className="text-xs text-text-muted px-3 py-1.5 rounded-xl bg-elevated border border-border hover:border-purple/40 hover:text-text-primary transition-all duration-150"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Featured lineages */}
      <div>
        <div className="flex items-center gap-3 mb-6">
          <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest">Featured lineages</h2>
          <div className="flex-1 h-px bg-border" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <FeaturedLineageCard
            data={mockRadioheadLineage}
            onClick={() => handleSearch("Radiohead")}
            delay={0}
          />
          <FeaturedLineageCard
            data={mockUndergroundLineage}
            onClick={() => handleSearch("osamason")}
            delay={60}
          />
        </div>
      </div>

      {/* Genesis showcase */}
      <div>
        <div className="flex items-center gap-3 mb-6">
          <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest">Emerging sounds</h2>
          <div className="flex-1 h-px bg-border" />
          <button
            onClick={() => navigate("/genesis")}
            className="text-xs text-purple hover:text-purple/80 transition-colors"
          >
            View all
          </button>
        </div>

        <GenesisCard
          data={mockGenesis}
          onClick={() => navigate("/genesis")}
          delay={120}
        />
      </div>

      {/* How it works */}
      <div>
        <div className="flex items-center gap-3 mb-8">
          <h2 className="text-xs font-medium text-text-muted uppercase tracking-widest">How it works</h2>
          <div className="flex-1 h-px bg-border" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { title: "Archaeology", desc: "Trace any sound backwards through its documented influences and underground roots.", icon: "M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" },
            { title: "Multi-source", desc: "MusicBrainz relationships, Last.fm listener patterns, and Spotify metadata combined.", icon: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" },
            { title: "Underground first", desc: "Artists with fewer listeners are amplified. The deep cuts are the point.", icon: "M13 10V3L4 14h7v7l9-11h-7z" },
          ].map(({ title, desc, icon }, i) => (
            <div
              key={title}
              className="p-5 rounded-2xl border border-border bg-surface animate-slide-up"
              style={{ animationDelay: `${i * 80}ms`, animationFillMode: "both" }}
            >
              <div className="w-8 h-8 rounded-lg bg-purple/10 border border-purple/20 flex items-center justify-center mb-4">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-purple">
                  <path d={icon} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="font-semibold text-sm text-text-primary mb-1.5">{title}</p>
              <p className="text-xs text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

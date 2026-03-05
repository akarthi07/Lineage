import UndergroundBadge from "./shared/UndergroundBadge";
import GenreTag from "./shared/GenreTag";
import StrengthIndicator from "./shared/StrengthIndicator";

function StatPill({ label, value }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-2xs text-text-muted uppercase tracking-wider font-medium">{label}</span>
      <span className="text-sm font-semibold text-text-primary font-mono">
        {typeof value === "number" ? value.toLocaleString() : value}
      </span>
    </div>
  );
}

export default function ArtistDetailPanel({ artist, edges = [], onClose, onExplore }) {
  if (!artist) return null;

  const connections = edges.filter(
    (e) => e.source === artist.id || e.target === artist.id
  );

  return (
    <div className="animate-slide-in-right h-full flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between p-5 border-b border-border">
        <div className="flex items-center gap-3">
          {artist.image_url ? (
            <img
              src={artist.image_url}
              alt={artist.name}
              className="w-12 h-12 rounded-xl object-cover border border-border flex-shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-xl bg-elevated border border-border flex items-center justify-center flex-shrink-0">
              <span className="text-lg font-semibold text-text-muted">
                {artist.name.charAt(0).toUpperCase()}
              </span>
            </div>
          )}
          <div>
            <h2 className="font-semibold text-text-primary text-base leading-tight">{artist.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <UndergroundBadge score={artist.underground_score} size="xs" />
              {artist.country && (
                <span className="text-2xs text-text-muted">{artist.country}</span>
              )}
              {artist.formation_year && (
                <span className="text-2xs text-text-muted">est. {artist.formation_year}</span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg bg-elevated border border-border flex items-center justify-center text-text-muted hover:text-text-primary hover:border-border/80 transition-colors"
          aria-label="Close panel"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Stats */}
      <div className="p-5 border-b border-border">
        <div className="grid grid-cols-2 gap-4">
          <StatPill label="Last.fm listeners" value={artist.lastfm_listeners} />
          <StatPill label="Spotify popularity" value={artist.spotify_popularity ? `${artist.spotify_popularity} / 100` : null} />
          <StatPill label="Underground score" value={artist.underground_score !== undefined ? `${Math.round(artist.underground_score * 100)}%` : null} />
          <StatPill label="Connections" value={connections.length} />
        </div>
      </div>

      {/* Tags */}
      {artist.tags && artist.tags.length > 0 && (
        <div className="p-5 border-b border-border">
          <p className="text-2xs text-text-muted uppercase tracking-wider font-medium mb-3">Tags</p>
          <div className="flex flex-wrap gap-1.5">
            {artist.tags.slice(0, 10).map((tag) => (
              <GenreTag key={tag} label={tag} />
            ))}
          </div>
        </div>
      )}

      {/* Connections */}
      {connections.length > 0 && (
        <div className="p-5 border-b border-border flex-1 overflow-y-auto">
          <p className="text-2xs text-text-muted uppercase tracking-wider font-medium mb-3">
            Influence connections
          </p>
          <div className="space-y-3">
            {connections.slice(0, 8).map((edge, i) => {
              const isSource = edge.source === artist.id;
              const label = edge.musicbrainz_type === "influenced by"
                ? isSource ? "influenced by" : "influenced"
                : isSource ? "connected to" : "connected from";
              return (
                <div key={i} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-secondary">
                      <span className="text-text-muted">{label}</span>{" "}
                      <span className="text-text-primary font-medium">
                        {isSource ? edge.target : edge.source}
                      </span>
                    </span>
                    <span className="text-2xs text-text-muted font-mono">
                      {Math.round(edge.strength * 100)}%
                    </span>
                  </div>
                  <StrengthIndicator strength={edge.strength} sourceType={edge.source_type} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* CTA */}
      <div className="p-5">
        <button
          className="btn-primary w-full"
          onClick={() => onExplore && onExplore(artist)}
        >
          Explore their lineage
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1 6h10M7 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {artist.spotify_id && (
          <a
            href={`https://open.spotify.com/artist/${artist.spotify_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost w-full mt-2 text-sm"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
            Open in Spotify
          </a>
        )}
      </div>
    </div>
  );
}

// Sparse mock — osamason lineage (~8 nodes)
export const mockUndergroundLineage = {
  query_id: "mock-002",
  query_type: "artist_lineage",
  artist_name: "osamason",
  parsed: { artist: "osamason", direction: "backward", depth: 2, underground_level: "deep" },
  results: {
    nodes: [
      { id: "osa", name: "osamason", mbid: "osa", underground_score: 0.3, lastfm_listeners: 427129, spotify_popularity: 48, genres: ["plugg"], tags: ["dark plugg", "plugg", "trap", "rage"], formation_year: null, country: "US", image_url: null, depth_level: 0 },
      { id: "che", name: "Che", mbid: "che", underground_score: 0.3, lastfm_listeners: 421000, spotify_popularity: 44, genres: ["plugg"], tags: ["dark plugg", "plugg", "underground"], formation_year: null, country: "US", image_url: null, depth_level: 1 },
      { id: "summrs", name: "Summrs", mbid: "summrs", underground_score: 0.5, lastfm_listeners: 180000, spotify_popularity: 38, genres: ["plugg"], tags: ["plugg", "dark plugg", "rap"], formation_year: null, country: "US", image_url: null, depth_level: 1 },
      { id: "izaya", name: "Izaya Tiji", mbid: "izaya", underground_score: 0.7, lastfm_listeners: 85000, spotify_popularity: 28, genres: ["underground rap"], tags: ["dark plugg", "underground rap"], formation_year: null, country: "US", image_url: null, depth_level: 1 },
      { id: "1oneam", name: "1oneam", mbid: "1oneam", underground_score: 0.85, lastfm_listeners: 12000, spotify_popularity: 18, genres: [], tags: ["dark plugg", "underground"], formation_year: null, country: "US", image_url: null, depth_level: 2 },
      { id: "bleood", name: "bleood", mbid: "bleood", underground_score: 0.7, lastfm_listeners: 71000, spotify_popularity: 22, genres: [], tags: ["dark plugg", "plugg"], formation_year: null, country: "US", image_url: null, depth_level: 2 },
      { id: "destroy", name: "Destroy Lonely", mbid: "destroy", underground_score: 0.3, lastfm_listeners: 410000, spotify_popularity: 55, genres: ["plugg", "rage"], tags: ["rage", "plugg", "trap"], formation_year: null, country: "US", image_url: null, depth_level: 1 },
      { id: "netts", name: "nettspend", mbid: "netts", underground_score: 0.5, lastfm_listeners: 160000, spotify_popularity: 40, genres: ["plugg"], tags: ["dark plugg", "plugg", "rage"], formation_year: null, country: "US", image_url: null, depth_level: 2 },
    ],
    edges: [
      { source: "osa", target: "che", strength: 0.72, source_type: "lastfm_similar", confidence: 0.80, musicbrainz_type: null },
      { source: "osa", target: "summrs", strength: 0.61, source_type: "lastfm_similar", confidence: 0.74, musicbrainz_type: null },
      { source: "osa", target: "izaya", strength: 0.55, source_type: "lastfm_similar", confidence: 0.70, musicbrainz_type: null },
      { source: "osa", target: "destroy", strength: 0.58, source_type: "lastfm_similar", confidence: 0.72, musicbrainz_type: null },
      { source: "summrs", target: "1oneam", strength: 0.49, source_type: "lastfm_similar", confidence: 0.62, musicbrainz_type: null },
      { source: "che", target: "bleood", strength: 0.44, source_type: "lastfm_similar", confidence: 0.60, musicbrainz_type: null },
      { source: "destroy", target: "netts", strength: 0.52, source_type: "lastfm_similar", confidence: 0.68, musicbrainz_type: null },
    ],
    metadata: {
      total_nodes: 8,
      underground_percentage: 0.75,
      deepest_level_reached: 2,
      data_sources_used: ["lastfm", "spotify"],
      note: "Limited MusicBrainz data available for this artist. Connections sourced from Last.fm listener patterns.",
    },
  },
};

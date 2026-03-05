// Drain Gang lineage — Bladee (~12 nodes, deep underground)
export const mockBladeeLineage = {
  query_id: "mock-003",
  query_type: "artist_lineage",
  artist_name: "Bladee",
  parsed: { artist: "Bladee", direction: "backward", depth: 3, underground_level: "deep" },
  results: {
    nodes: [
      // depth 0
      { id: "bladee",    name: "Bladee",           underground_score: 0.45, lastfm_listeners: 820000,  spotify_popularity: 52, genres: ["drain"],           tags: ["drain", "cloud rap", "experimental"],     formation_year: 2013, country: "SE", image_url: null, depth_level: 0 },
      // depth 1 — Drain Gang peers + direct upstream
      { id: "ecco2k",   name: "Ecco2k",            underground_score: 0.72, lastfm_listeners: 310000,  spotify_popularity: 38, genres: ["drain"],           tags: ["drain", "experimental", "avant-garde"],   formation_year: 2013, country: "SE", image_url: null, depth_level: 1 },
      { id: "yunglean", name: "Yung Lean",          underground_score: 0.28, lastfm_listeners: 1400000, spotify_popularity: 65, genres: ["cloud rap"],        tags: ["cloud rap", "sad boys", "trap"],          formation_year: 2012, country: "SE", image_url: null, depth_level: 1 },
      { id: "thaiboy",  name: "Thaiboy Digital",   underground_score: 0.80, lastfm_listeners: 180000,  spotify_popularity: 32, genres: ["drain"],           tags: ["drain", "cloud rap", "underground"],      formation_year: 2013, country: "TH", image_url: null, depth_level: 1 },
      // depth 2 — upstream influences
      { id: "salem",    name: "Salem",              underground_score: 0.75, lastfm_listeners: 210000,  spotify_popularity: 30, genres: ["witch house"],      tags: ["witch house", "dark", "experimental"],    formation_year: 2006, country: "US", image_url: null, depth_level: 2 },
      { id: "three6",   name: "Three 6 Mafia",      underground_score: 0.15, lastfm_listeners: 1900000, spotify_popularity: 62, genres: ["memphis rap"],      tags: ["memphis rap", "crunk", "southern rap"],   formation_year: 1991, country: "US", image_url: null, depth_level: 2 },
      { id: "crystalc", name: "Crystal Castles",    underground_score: 0.55, lastfm_listeners: 780000,  spotify_popularity: 44, genres: ["electronic"],      tags: ["electronic", "noise pop", "experimental"], formation_year: 2004, country: "CA", image_url: null, depth_level: 2 },
      { id: "lil_ugly", name: "Lil Ugly Mane",      underground_score: 0.82, lastfm_listeners: 145000,  spotify_popularity: 28, genres: ["memphis rap"],      tags: ["underground rap", "memphis", "dark"],      formation_year: 2010, country: "US", image_url: null, depth_level: 2 },
      // depth 3 — deeper roots
      { id: "djscrew",  name: "DJ Screw",           underground_score: 0.35, lastfm_listeners: 580000,  spotify_popularity: 40, genres: ["chopped & screwed"], tags: ["chopped and screwed", "houston", "rap"],  formation_year: 1990, country: "US", image_url: null, depth_level: 3 },
      { id: "cocteau",  name: "Cocteau Twins",      underground_score: 0.30, lastfm_listeners: 960000,  spotify_popularity: 48, genres: ["dream pop"],        tags: ["dream pop", "shoegaze", "ethereal"],       formation_year: 1979, country: "GB", image_url: null, depth_level: 3 },
      { id: "suicide",  name: "Suicide",            underground_score: 0.60, lastfm_listeners: 310000,  spotify_popularity: 35, genres: ["no wave"],          tags: ["no wave", "proto-punk", "minimalist"],    formation_year: 1970, country: "US", image_url: null, depth_level: 3 },
      { id: "enya",     name: "Enya",               underground_score: 0.10, lastfm_listeners: 2800000, spotify_popularity: 66, genres: ["new age"],          tags: ["new age", "ambient", "celtic"],           formation_year: 1980, country: "IE", image_url: null, depth_level: 3 },
    ],
    edges: [
      // Bladee's direct connections
      { source: "bladee",   target: "ecco2k",   strength: 0.95, source_type: "lastfm_similar",  confidence: 0.97, musicbrainz_type: null },
      { source: "bladee",   target: "yunglean", strength: 0.88, source_type: "musicbrainz",     confidence: 0.94, musicbrainz_type: "influenced by" },
      { source: "bladee",   target: "thaiboy",  strength: 0.92, source_type: "lastfm_similar",  confidence: 0.96, musicbrainz_type: null },
      // Ecco2k upstream
      { source: "ecco2k",   target: "crystalc", strength: 0.72, source_type: "musicbrainz",     confidence: 0.82, musicbrainz_type: "influenced by" },
      { source: "ecco2k",   target: "cocteau",  strength: 0.68, source_type: "lastfm_similar",  confidence: 0.78, musicbrainz_type: null },
      // Yung Lean upstream
      { source: "yunglean", target: "three6",   strength: 0.80, source_type: "musicbrainz",     confidence: 0.88, musicbrainz_type: "influenced by" },
      { source: "yunglean", target: "salem",    strength: 0.85, source_type: "musicbrainz",     confidence: 0.91, musicbrainz_type: "influenced by" },
      // Thaiboy upstream
      { source: "thaiboy",  target: "lil_ugly", strength: 0.75, source_type: "lastfm_similar",  confidence: 0.82, musicbrainz_type: null },
      // Deeper connections
      { source: "three6",   target: "djscrew",  strength: 0.70, source_type: "lastfm_similar",  confidence: 0.80, musicbrainz_type: null },
      { source: "salem",    target: "suicide",  strength: 0.65, source_type: "musicbrainz",     confidence: 0.75, musicbrainz_type: "influenced by" },
      { source: "lil_ugly", target: "djscrew",  strength: 0.72, source_type: "musicbrainz",     confidence: 0.82, musicbrainz_type: "influenced by" },
      { source: "crystalc", target: "enya",     strength: 0.52, source_type: "tag_overlap",     confidence: 0.62, musicbrainz_type: null },
    ],
    metadata: {
      total_nodes: 12,
      underground_percentage: 0.65,
      deepest_level_reached: 3,
      data_sources_used: ["musicbrainz", "lastfm"],
    },
  },
};

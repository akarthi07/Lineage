// Opium / Rage lineage — Ken Carson (~13 nodes)
export const mockKenCarsonLineage = {
  query_id: "mock-004",
  query_type: "artist_lineage",
  artist_name: "Ken Carson",
  parsed: { artist: "Ken Carson", direction: "backward", depth: 3, underground_level: "balanced" },
  results: {
    nodes: [
      // depth 0
      { id: "ken",      name: "Ken Carson",       underground_score: 0.38, lastfm_listeners: 620000,  spotify_popularity: 62, genres: ["rage", "plugg"],   tags: ["rage", "plugg", "trap", "opium"],         formation_year: 2019, country: "US", image_url: null, depth_level: 0 },
      // depth 1
      { id: "carti",    name: "Playboi Carti",    underground_score: 0.05, lastfm_listeners: 4800000, spotify_popularity: 86, genres: ["trap", "rage"],    tags: ["trap", "rage", "mumble rap"],             formation_year: 2015, country: "US", image_url: null, depth_level: 1 },
      { id: "destroy",  name: "Destroy Lonely",   underground_score: 0.30, lastfm_listeners: 720000,  spotify_popularity: 65, genres: ["rage", "plugg"],   tags: ["rage", "plugg", "opium"],                 formation_year: 2020, country: "US", image_url: null, depth_level: 1 },
      { id: "pierre",   name: "Pi'erre Bourne",   underground_score: 0.48, lastfm_listeners: 340000,  spotify_popularity: 55, genres: ["trap"],            tags: ["trap", "producer", "plugg"],              formation_year: 2015, country: "US", image_url: null, depth_level: 1 },
      // depth 2
      { id: "thug",     name: "Young Thug",       underground_score: 0.05, lastfm_listeners: 5200000, spotify_popularity: 84, genres: ["trap"],            tags: ["trap", "atlanta", "melodic rap"],         formation_year: 2010, country: "US", image_url: null, depth_level: 2 },
      { id: "future",   name: "Future",           underground_score: 0.05, lastfm_listeners: 6100000, spotify_popularity: 87, genres: ["trap"],            tags: ["trap", "atlanta", "auto-tune"],           formation_year: 2010, country: "US", image_url: null, depth_level: 2 },
      { id: "yeat",     name: "Yeat",             underground_score: 0.22, lastfm_listeners: 1800000, spotify_popularity: 75, genres: ["rage", "plugg"],   tags: ["rage", "plugg", "underground"],           formation_year: 2018, country: "US", image_url: null, depth_level: 2 },
      { id: "richiesouf", name: "Richie Souf",    underground_score: 0.72, lastfm_listeners: 85000,   spotify_popularity: 30, genres: ["plugg"],           tags: ["plugg", "producer", "underground"],       formation_year: 2013, country: "US", image_url: null, depth_level: 2 },
      // depth 3
      { id: "gucci",    name: "Gucci Mane",       underground_score: 0.05, lastfm_listeners: 3900000, spotify_popularity: 78, genres: ["trap"],            tags: ["trap", "atlanta", "street rap"],          formation_year: 2001, country: "US", image_url: null, depth_level: 3 },
      { id: "lil_wayne", name: "Lil Wayne",       underground_score: 0.02, lastfm_listeners: 7200000, spotify_popularity: 82, genres: ["hip-hop"],         tags: ["hip-hop", "southern rap", "new orleans"],  formation_year: 1994, country: "US", image_url: null, depth_level: 3 },
      { id: "travis",   name: "Travis Scott",     underground_score: 0.05, lastfm_listeners: 7800000, spotify_popularity: 92, genres: ["trap"],            tags: ["trap", "psychedelic rap", "houston"],     formation_year: 2012, country: "US", image_url: null, depth_level: 3 },
      { id: "djsmokey", name: "DJ Smokey",        underground_score: 0.88, lastfm_listeners: 22000,   spotify_popularity: 18, genres: ["plugg"],           tags: ["plugg", "producer", "underground"],       formation_year: 2012, country: "US", image_url: null, depth_level: 3 },
      { id: "uzi",      name: "Lil Uzi Vert",     underground_score: 0.08, lastfm_listeners: 5600000, spotify_popularity: 85, genres: ["trap"],            tags: ["trap", "emo rap", "philadelphia"],        formation_year: 2014, country: "US", image_url: null, depth_level: 2 },
    ],
    edges: [
      // Ken Carson's direct connections
      { source: "ken",     target: "carti",    strength: 0.95, source_type: "musicbrainz",    confidence: 0.98, musicbrainz_type: "influenced by" },
      { source: "ken",     target: "destroy",  strength: 0.88, source_type: "lastfm_similar", confidence: 0.93, musicbrainz_type: null },
      { source: "ken",     target: "pierre",   strength: 0.80, source_type: "lastfm_similar", confidence: 0.87, musicbrainz_type: null },
      // Carti upstream
      { source: "carti",   target: "thug",     strength: 0.90, source_type: "musicbrainz",    confidence: 0.95, musicbrainz_type: "influenced by" },
      { source: "carti",   target: "future",   strength: 0.88, source_type: "musicbrainz",    confidence: 0.93, musicbrainz_type: "influenced by" },
      { source: "carti",   target: "uzi",      strength: 0.82, source_type: "lastfm_similar", confidence: 0.89, musicbrainz_type: null },
      // Destroy Lonely upstream
      { source: "destroy", target: "yeat",     strength: 0.72, source_type: "lastfm_similar", confidence: 0.80, musicbrainz_type: null },
      // Pierre Bourne upstream
      { source: "pierre",  target: "richiesouf", strength: 0.75, source_type: "lastfm_similar", confidence: 0.82, musicbrainz_type: null },
      // Deeper connections
      { source: "thug",    target: "lil_wayne", strength: 0.85, source_type: "musicbrainz",    confidence: 0.92, musicbrainz_type: "influenced by" },
      { source: "future",  target: "gucci",    strength: 0.88, source_type: "musicbrainz",    confidence: 0.93, musicbrainz_type: "influenced by" },
      { source: "travis",  target: "future",   strength: 0.82, source_type: "musicbrainz",    confidence: 0.90, musicbrainz_type: "influenced by" },
      { source: "carti",   target: "travis",   strength: 0.78, source_type: "lastfm_similar", confidence: 0.85, musicbrainz_type: null },
      { source: "richiesouf", target: "djsmokey", strength: 0.80, source_type: "lastfm_similar", confidence: 0.86, musicbrainz_type: null },
    ],
    metadata: {
      total_nodes: 13,
      underground_percentage: 0.28,
      deepest_level_reached: 3,
      data_sources_used: ["musicbrainz", "lastfm", "spotify"],
    },
  },
};

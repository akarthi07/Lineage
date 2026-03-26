# Genesis Mode — Implementation Chunks

## What Genesis Does

Find genres before they have names.

Instead of tracing an existing artist's history (Lineage), Genesis identifies clusters of
mostly-unknown artists independently converging on something new — proto-genres forming
in real time, before they have a name or scene.

Example queries:
- "What's emerging that sounds like if Aphex Twin and Bon Iver collaborated?"
- "Show me new scenes forming right now"
- "Find artists blending metal with R&B before it's a thing"
- "What's happening in underground music in Southeast Asia?"

Example output:
```
Emerging: Glitch-Country
23 artists identified | Forming since mid-2024
Concentrated in: Nashville, Berlin, Tokyo
Blends: Country songwriting + glitch production + ambient textures
Lineage roots: Folktronica (early 2000s), hyperpop production, alt-country
Status: Unnamed — no established genre tag yet
Confidence: 74%
```

Prerequisites: Lineage Chunk 7 (backend connected), Chunk 2 (Claude NLP).

---

## Chunk G1 — Data Clients

Build the raw data fetchers for underground sources.

### Files to create

**Backend/services/genesis/bandcamp_client.py**
- `search_bandcamp(tags: list[str], location: str = None) -> list[dict]`
- Scrapes Bandcamp tag pages (e.g. bandcamp.com/tag/glitch-country)
- Returns: artist name, location, tags, upload date, plays, purchase count, bandcamp URL
- No official API — use httpx + BeautifulSoup
- Rate limit: 1 req/2s, respect robots.txt

**Backend/services/genesis/soundcloud_client.py**
- `search_soundcloud(query: str, max_plays: int = 10000) -> list[dict]`
- Uses SoundCloud public API (no auth needed for search)
- Filters to tracks under max_plays but with high likes-to-plays ratio
- Returns: artist name, track URL, play count, like count, repost count, tags, location

**Backend/services/genesis/reddit_client.py**
- `get_artist_mentions(subreddits: list[str], query: str) -> list[dict]`
- Uses Reddit public JSON API (no auth needed)
- Pulls posts from r/indieheads, r/experimentalmusic, genre-specific subs
- Extracts artist name mentions, post score, comment count
- Returns: artist name, mention count, subreddit, post score, date

**Backend/services/genesis/spotify_longtail_client.py**
- `search_emerging(genre_keywords: list[str], max_listeners: int = 50000) -> list[dict]`
- Wraps existing spotify_client.py
- Searches by genre keyword, filters to artists under max_listeners monthly equivalent
- Returns: artist name, spotify_id, popularity, followers, genres

### What this chunk produces
Raw candidate artists from 4 sources. Not yet clustered or scored — just raw data.

---

## Chunk G2 — Artist Embedding + Similarity

Turn raw artist data into vectors so we can cluster by musical similarity.

### Files to create

**Backend/services/genesis/embedding_client.py**
- `embed_artist(artist: dict) -> list[float]`
- Input: artist dict with tags, genre descriptors, location, source
- Uses text embedding — call OpenAI `text-embedding-3-small` or a HuggingFace model
- Concatenates: tags + genre strings + self-descriptors into a text blob, then embeds
- Returns a 1536-dim (or model-dependent) float vector
- Cache embeddings in Redis (key: `embed:{artist_name_normalized}`, TTL: 7 days)

**Backend/services/genesis/cluster_engine.py**
- `cluster_artists(artists: list[dict]) -> list[list[dict]]`
- Takes artists with their embedding vectors
- Runs HDBSCAN clustering (min_cluster_size=5, min_samples=3)
- Returns groups of artists — each group is a candidate proto-genre cluster
- Filters out clusters with fewer than 5 artists
- Install: `pip install hdbscan`

### Notes
- If no GPU available, text-only embeddings are fine. Audio embeddings (CLAP) are a future upgrade.
- HDBSCAN handles noise (outlier artists) gracefully — better than K-means for this use case.

### What this chunk produces
Given a list of raw artists, returns them grouped into clusters by musical similarity.

---

## Chunk G3 — Confidence Scorer + Cluster Naming

Score how "real" each cluster is and name it.

### Files to create

**Backend/services/genesis/confidence_scorer.py**
- `score_cluster(cluster: list[dict]) -> float`
- Returns 0.0–1.0 confidence that this is a real emerging movement
- Factors:
  - Artist count (5+ = base, 20+ = strong signal)
  - Geographic concentration (Gini coefficient on lat/lon — tighter = higher score)
  - Temporal clustering (are most artists emerging in the same 12-24 month window?)
  - Cross-platform presence (appears on Bandcamp AND SoundCloud AND Spotify = higher)
  - Engagement quality (high likes-to-plays or purchase-to-stream = higher)
  - Tag vocabulary gap (no existing genre tag matches = higher — means it's unnamed)

**Backend/services/genesis/cluster_namer.py**
- `name_cluster(cluster: list[dict]) -> str | None`
- Calls Claude with a prompt listing the cluster's tags, descriptors, locations, lineage roots
- Claude returns a proposed genre name or null if too early to name
- Returns the name string or None
- Example prompt:
  ```
  These {n} artists share these characteristics:
  Tags: {top_tags}
  Location concentration: {cities}
  Forming since: {date}
  Lineage roots: {existing_genres}

  Propose a genre name for this emerging sound, or return null if it's too early.
  Be creative but grounded. No marketing speak.
  ```

### What this chunk produces
Each cluster now has a confidence score (0–1) and an optional name.

---

## Chunk G4 — Geographic + Timeline Data

Enrich clusters with location and time data for the visualizations.

### Files to create

**Backend/services/genesis/geo_enricher.py**
- `enrich_locations(artists: list[dict]) -> list[dict]`
- Takes artist dicts with `location` string (e.g. "Nashville, TN")
- Geocodes each location to lat/lon using a free geocoding API (e.g. Nominatim/OpenStreetMap)
- Returns artists with `lat`, `lon` fields added
- Cache geocode results in Redis (key: `geo:{location_string}`, TTL: 30 days)
- Rate limit: 1 req/sec for Nominatim

**Backend/services/genesis/timeline_builder.py**
- `build_timeline(cluster: list[dict]) -> list[dict]`
- Takes a cluster of artists with `emerged_at` dates
- Returns a sorted list of timeline events:
  ```python
  [
    { "date": "2024-03", "artist_count": 3, "artists": ["name1", "name2", "name3"] },
    { "date": "2024-06", "artist_count": 7, ... },
  ]
  ```
- Groups by month, shows cumulative growth
- Identifies acceleration point (fastest month-over-month growth)

### What this chunk produces
Clusters now have lat/lon per artist and a timeline of emergence. Ready for the map and timeline visualizations.

---

## Chunk G5 — Genesis API Routes

Wire everything together into FastAPI endpoints.

### Files to create

**Backend/models/genesis.py**
```python
class GenesisArtist(BaseModel):
    name: str
    mbid: Optional[str]
    bandcamp_url: Optional[str]
    soundcloud_url: Optional[str]
    spotify_id: Optional[str]
    location: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    emerged_at: Optional[date]
    engagement_score: float
    best_track_url: Optional[str]
    tags: list[str]

class GenesisCluster(BaseModel):
    id: str
    name: Optional[str]
    description: str
    artists: list[GenesisArtist]
    total_artists: int
    concentrated_in: list[str]
    forming_since: date
    sound_descriptors: list[str]
    lineage_roots: list[str]
    confidence: float
    timeline: list[dict]
    geo_data: list[dict]
    last_updated: datetime

class GenesisResult(BaseModel):
    query: str
    clusters: list[GenesisCluster]
    total_artists_scanned: int
    sources_used: list[str]
```

**Backend/routers/genesis.py** (extend existing file)
```
POST /api/genesis/query     — full Genesis query, returns GenesisResult
GET  /api/genesis/featured  — pre-computed clusters (from featured_genesis.json)
GET  /api/genesis/cluster/{id} — single cluster full detail
```

**Backend/services/genesis/genesis_query.py**
- `run_genesis_query(query: str) -> GenesisResult`
- Orchestrates the full pipeline:
  1. Claude parses query → sound descriptors, region, time window
  2. Fetch candidates from all 4 data sources in parallel (asyncio.gather)
  3. Deduplicate artists across sources by name similarity
  4. Embed all artists
  5. Cluster via HDBSCAN
  6. Score + name each cluster
  7. Enrich with geo + timeline data
  8. Return GenesisResult

### What this chunk produces
A working `/api/genesis/query` endpoint. Can be tested with curl or the frontend.

---

## Chunk G6 — Frontend Views

Build the Genesis pages in React.

### Files to create

**Frontend/src/views/GenesisView.jsx**
- Main Genesis page at `/genesis`
- Top section: search bar for Genesis queries ("Show me new scenes forming")
- Below: grid of GenesisClusterCards (pre-computed featured clusters)
- On query submit: shows loading state, then renders results

**Frontend/src/views/GenesisResultView.jsx**
- Full result page for a single Genesis query
- Left panel: list of clusters with confidence scores
- Right panel: selected cluster detail (artist list, tags, lineage roots)
- Tabs: Artists | Map | Timeline

**Frontend/src/components/genesis/ClusterMap.jsx**
- D3 force-directed graph (similar to GenealogyMap but cluster-focused)
- Nodes = artists, sized by engagement score, colored by sub-cluster
- Edges = collaboration links (shared label, remix, feature)

**Frontend/src/components/genesis/GeoHeatMap.jsx**
- World map using D3 + TopoJSON
- Dots at artist locations, sized by cluster concentration
- Tooltip on hover: artist name, location, tags

**Frontend/src/components/genesis/ClusterTimeline.jsx**
- Horizontal timeline showing artist emergence over time
- Acceleration point highlighted
- Each point clickable → shows artist info

**Frontend/src/hooks/useGenesisQuery.js**
- Mirrors useLineageQuery.js
- Calls POST /api/genesis/query
- Returns { data, loading, error }

### What this chunk produces
Full Genesis UI connected to the backend.

---

## Chunk G7 — Pre-computed Featured Clusters

Run Genesis nightly on known emerging scenes and cache results.

### Files to create/modify

**Backend/scripts/compute_genesis.py**
- Runs a set of seed queries (e.g. "emerging underground rap", "new experimental electronic")
- Stores results in `Backend/data/featured_genesis.json`
- Run nightly via cron or Windows Task Scheduler

**Backend/data/featured_genesis.json** (already exists — replace static content with computed output)

**Backend/routers/genesis.py**
- `GET /api/genesis/featured` already exists — just reads featured_genesis.json
- No change needed if compute_genesis.py writes the same format

### Schedule
Run `python scripts/compute_genesis.py` weekly to refresh featured clusters.
Set up as a cron job or Task Scheduler entry when deploying.

### What this chunk produces
The Genesis discovery feed always has fresh pre-computed clusters without needing a live query.

---

## Implementation Order

| Chunk | Depends On | Est. Complexity |
|---|---|---|
| G1 — Data Clients | Nothing | Medium |
| G2 — Embedding + Clustering | G1 | Medium |
| G3 — Confidence + Naming | G2, Claude NLP (Chunk 2) | Medium |
| G4 — Geo + Timeline | G1 | Low |
| G5 — API Routes | G1 G2 G3 G4 | Medium |
| G6 — Frontend Views | G5, Lineage Chunk 7 | High |
| G7 — Pre-computed Featured | G5 | Low |

Start with G1 + G4 in parallel (both are just data fetching, no dependencies on each other).

---

## Open Questions

- **Audio embeddings**: Text-only embeddings (tags + descriptors) are the MVP. True audio similarity (CLAP model) needs a GPU or a hosted API — decide before G2.
- **Bandcamp scraping**: No official API. Check ToS. Rate limit aggressively.
- **RateYourMusic**: No API, scraping only — brittle. Deprioritize or skip in MVP.
- **Artist deduplication across sources**: Same artist on Bandcamp + SoundCloud + Spotify will have slightly different names. Use fuzzy string matching (rapidfuzz) before embedding.
- **Storage**: Store computed GenesisCluster objects in Neo4j (new label) or just flat JSON? Neo4j makes sense if we want to link Genesis clusters to Lineage artists.
- **Refresh cadence**: Weekly featured refresh is fine for MVP. Real-time Genesis queries are on-demand.

"""
Proto-genre cluster detection using DBSCAN on artist embedding vectors.

Filters to underground artists, clusters them in embedding space, and
extracts metadata (tags, geography, era, cohesion) for each cluster.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuneable constants — adjust per 17.7
#
# TUNING GUIDE:
#   eps (0.1–1.0): DBSCAN neighbourhood radius in cosine distance space.
#     - Lower → tighter, fewer clusters.  Higher → looser, bigger clusters.
#     - Start at 0.40. If 0 clusters found → raise to 0.50.
#     - If everything merges into 1 cluster → lower to 0.30.
#     - Test with: 0.25, 0.30, 0.35, 0.40, 0.50, 0.60
#
#   min_samples (2–20): minimum artists for a core point.
#     - Lower → more small clusters.  Higher → only large clusters.
#     - For <200 underground artists: use 3–4.
#     - For 200–1000: use 4–6.  For 1000+: use 5–8.
#
#   UNDERGROUND_THRESHOLD: artists below this score are excluded.
#     - 0.45 gives a good mix of indie + underground.
#     - Raise to 0.65 for deep-underground-only clusters.
#
#   The /api/genesis/detect endpoint exposes eps and min_samples as
#   query params so you can experiment without code changes.
# ---------------------------------------------------------------------------
DEFAULT_EPS = 0.30            # DBSCAN neighbourhood radius (cosine distance)
DEFAULT_MIN_SAMPLES = 4       # minimum artists to form a cluster
UNDERGROUND_THRESHOLD = 0.45  # min underground_score to enter clustering
MIN_CLUSTER_SIZE = 4          # discard clusters smaller than this
# Filters for "interesting" clusters (set to None to disable)
MIN_AVG_UNDERGROUND = 0.55
MIN_AVG_YEAR: int | None = None  # e.g. 2015 — set once you have enough data


@dataclass
class ClusterArtist:
    mbid: str
    name: str
    underground_score: float
    tags: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    formation_year: int | None = None
    country: str = ""
    lastfm_listeners: int | None = None


@dataclass
class ProtoGenre:
    cluster_id: int
    artists: list[ClusterArtist]
    avg_year: float | None
    avg_underground: float
    top_tags: list[str]
    top_genres: list[str]
    geography: list[str]          # most common countries
    cohesion_score: float         # avg pairwise cosine sim within cluster
    size: int
    description: str = ""         # filled later by genre_describer
    lineage_roots: list[dict] = field(default_factory=list)  # filled by lineage_tracer

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "avg_year": self.avg_year,
            "avg_underground": round(self.avg_underground, 3),
            "top_tags": self.top_tags,
            "top_genres": self.top_genres,
            "geography": self.geography,
            "cohesion_score": round(self.cohesion_score, 3),
            "description": self.description,
            "lineage_roots": self.lineage_roots,
            "artists": [
                {
                    "mbid": a.mbid,
                    "name": a.name,
                    "underground_score": round(a.underground_score, 3),
                    "tags": a.tags[:5],
                    "formation_year": a.formation_year,
                    "country": a.country,
                    "lastfm_listeners": a.lastfm_listeners,
                }
                for a in self.artists
            ],
        }


def detect_proto_genres(
    *,
    eps: float = DEFAULT_EPS,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> list[ProtoGenre]:
    """
    Detect proto-genre clusters from the current embedding space.

    1. Load the vector engine to get all artist vectors + metadata
    2. Filter to underground artists (underground_score > threshold)
    3. Run DBSCAN on L2-normalised vectors (cosine metric)
    4. Extract metadata per cluster
    5. Filter to "interesting" clusters
    """
    from ml.embeddings.search_engine import get_vector_engine
    from services.graph_manager import get_driver

    engine = get_vector_engine()
    if engine is None:
        logger.warning("Vector engine not loaded — cannot detect clusters")
        return []

    # ── 1. Gather artist metadata from Neo4j ──────────────────────────
    driver = get_driver()
    meta: dict[str, dict] = {}
    with driver.session() as session:
        result = session.run(
            "MATCH (a:Artist) WHERE a.mbid IS NOT NULL AND a.mbid <> '' "
            "RETURN a.mbid AS mbid, a.name AS name, "
            "       a.underground_score AS us, a.tags AS tags, "
            "       a.genres AS genres, a.formation_year AS year, "
            "       a.country AS country, a.lastfm_listeners AS listeners"
        )
        for rec in result:
            meta[rec["mbid"]] = {
                "name": rec["name"] or "",
                "underground_score": rec["us"] or 0.0,
                "tags": rec["tags"] or [],
                "genres": rec["genres"] or [],
                "formation_year": rec["year"],
                "country": rec["country"] or "",
                "lastfm_listeners": rec["listeners"],
            }

    # ── 2. Filter to underground artists that have embeddings ─────────
    ug_mbids: list[str] = []
    ug_vectors: list[np.ndarray] = []

    for mbid in engine.mbid_list:
        m = meta.get(mbid)
        if m is None:
            continue
        if m["underground_score"] < UNDERGROUND_THRESHOLD:
            continue
        vec = engine.get_vector(mbid)
        if vec is None:
            continue
        ug_mbids.append(mbid)
        ug_vectors.append(vec)

    if len(ug_mbids) < min_samples:
        logger.info(f"Only {len(ug_mbids)} underground artists with embeddings — too few for clustering")
        return []

    logger.info(f"Clustering {len(ug_mbids)} underground artists (eps={eps}, min_samples={min_samples})")

    # ── 3. Run DBSCAN (cosine metric via precomputed distance) ────────
    X = np.array(ug_vectors, dtype=np.float32)
    # Normalise so dot product = cosine similarity
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X_norm = X / norms

    # Cosine distance = 1 - cosine_similarity
    sim_matrix = X_norm @ X_norm.T
    np.clip(sim_matrix, -1.0, 1.0, out=sim_matrix)
    dist_matrix = 1.0 - sim_matrix

    db = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = db.fit_predict(dist_matrix)

    unique_labels = set(labels)
    unique_labels.discard(-1)  # noise
    logger.info(f"DBSCAN found {len(unique_labels)} clusters ({(labels == -1).sum()} noise points)")

    # ── 4. Build ProtoGenre for each cluster ──────────────────────────
    proto_genres: list[ProtoGenre] = []

    for label in sorted(unique_labels):
        indices = [i for i, l in enumerate(labels) if l == label]
        if len(indices) < MIN_CLUSTER_SIZE:
            continue

        cluster_mbids = [ug_mbids[i] for i in indices]
        cluster_vecs = X_norm[indices]

        # Metadata aggregation
        artists: list[ClusterArtist] = []
        tag_counter: Counter = Counter()
        genre_counter: Counter = Counter()
        country_counter: Counter = Counter()
        years: list[int] = []
        ug_scores: list[float] = []

        for mbid in cluster_mbids:
            m = meta[mbid]
            artists.append(ClusterArtist(
                mbid=mbid,
                name=m["name"],
                underground_score=m["underground_score"],
                tags=m["tags"],
                genres=m["genres"],
                formation_year=m["formation_year"],
                country=m["country"],
                lastfm_listeners=m["lastfm_listeners"],
            ))
            for t in m["tags"]:
                tag_counter[t] += 1
            for g in m["genres"]:
                genre_counter[g] += 1
            if m["country"]:
                country_counter[m["country"]] += 1
            if m["formation_year"]:
                years.append(m["formation_year"])
            ug_scores.append(m["underground_score"])

        avg_year = round(sum(years) / len(years), 1) if years else None
        avg_ug = sum(ug_scores) / len(ug_scores)

        # Cohesion: average pairwise cosine similarity within cluster
        n = len(cluster_vecs)
        if n > 1:
            pairwise = cluster_vecs @ cluster_vecs.T
            # Mean of upper triangle (excluding diagonal)
            tri = np.triu(pairwise, k=1)
            cohesion = float(tri.sum() / (n * (n - 1) / 2))
        else:
            cohesion = 1.0

        pg = ProtoGenre(
            cluster_id=int(label),
            artists=artists,
            avg_year=avg_year,
            avg_underground=avg_ug,
            top_tags=[t for t, _ in tag_counter.most_common(10)],
            top_genres=[g for g, _ in genre_counter.most_common(5)],
            geography=[c for c, _ in country_counter.most_common(5)],
            cohesion_score=cohesion,
            size=len(artists),
        )
        proto_genres.append(pg)

    # ── 5. Filter to interesting clusters ─────────────────────────────
    filtered: list[ProtoGenre] = []
    for pg in proto_genres:
        if MIN_AVG_UNDERGROUND and pg.avg_underground < MIN_AVG_UNDERGROUND:
            continue
        if MIN_AVG_YEAR and pg.avg_year and pg.avg_year < MIN_AVG_YEAR:
            continue
        filtered.append(pg)

    # Sort by cohesion descending (tightest clusters first)
    filtered.sort(key=lambda p: p.cohesion_score, reverse=True)

    logger.info(f"Returning {len(filtered)} interesting proto-genre clusters")
    return filtered

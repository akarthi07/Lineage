"""
Last.fm similarity matrix builder — uses getSimilar data from Redis cache.

L[i][j] = lastfm match score if artist j appears in artist i's similar list.
The matrix is symmetrized: L = (L + L.T) / 2.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import redis

from config import settings
from ml.data_exporter import GraphExport

logger = logging.getLogger(__name__)


def build_lastfm_matrix(graph_export: GraphExport) -> np.ndarray:
    """
    Build an NxN Last.fm similarity matrix from cached getSimilar data.

    Reads from Redis cache (key: lastfm:artist:{name}:similar).
    If cache miss, that artist simply has no Last.fm similarity data.
    The matrix is symmetrized by averaging: L = (L + L.T) / 2.
    """
    n = graph_export.n
    matrix = np.zeros((n, n), dtype=np.float64)

    # Build a name->index lookup (lowercased for matching)
    name_to_index: dict[str, int] = {}
    for artist in graph_export.artists:
        name_to_index[artist.name.lower()] = graph_export.artist_index[artist.mbid]

    # Try to connect to Redis
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        r.ping()
    except Exception as exc:
        logger.warning(f"Redis unavailable, returning empty Last.fm matrix: {exc}")
        return matrix

    cache_hits = 0
    cache_misses = 0

    for artist in graph_export.artists:
        i = graph_export.artist_index[artist.mbid]
        cache_key = f"lastfm:artist:{artist.name.lower()}:similar"

        try:
            cached = r.get(cache_key)
        except Exception:
            cached = None

        if not cached:
            cache_misses += 1
            continue

        cache_hits += 1
        similar_list = json.loads(cached)

        for entry in similar_list:
            similar_name = entry.get("name", "").lower()
            match_score = float(entry.get("match", 0))

            j = name_to_index.get(similar_name)
            if j is not None and j != i:
                matrix[i][j] = max(matrix[i][j], match_score)

    # Symmetrize: average both directions
    matrix = (matrix + matrix.T) / 2.0

    logger.info(
        f"Last.fm matrix: {cache_hits} cache hits, {cache_misses} misses, "
        f"{np.count_nonzero(matrix)} non-zero entries."
    )
    return matrix

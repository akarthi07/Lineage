"""Genesis Mode endpoints — curated showcase + automated proto-genre detection."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import redis
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"
_GENESIS_CACHE_KEY = "genesis:detected_clusters"
_GENESIS_CACHE_TTL = 86400  # 24 hours


def _get_redis() -> redis.Redis:
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )


@router.get(
    "/featured",
    summary="Get the curated featured proto-genre showcase",
)
async def get_featured_genesis():
    """
    Returns the manually curated Genesis Mode showcase —
    an emerging proto-genre with artists, geography, timeline, and lineage roots.
    """
    path = _DATA_DIR / "featured_genesis.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Genesis data not yet available.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"Failed to read featured_genesis.json: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load genesis data.")


@router.get(
    "/detect",
    summary="Detect proto-genre clusters from embedding space",
)
async def detect_genesis(
    eps: float = Query(0.30, ge=0.1, le=1.0, description="DBSCAN eps (cosine distance)"),
    min_samples: int = Query(4, ge=2, le=20, description="DBSCAN min_samples"),
    force: bool = Query(False, description="Bypass Redis cache and re-detect"),
):
    """
    Run DBSCAN clustering on underground artist embeddings to detect
    emerging proto-genre clusters. Results are cached in Redis for 24h.

    Each cluster includes: artists, tags, geography, cohesion score,
    an AI-generated description, and shared lineage roots.
    """
    # Check cache first
    if not force:
        try:
            r = _get_redis()
            cached = r.get(_GENESIS_CACHE_KEY)
            if cached:
                logger.info("Returning cached genesis detection results")
                return json.loads(cached)
        except Exception:
            pass  # Redis down — just compute fresh

    # Run detection pipeline
    from ml.genesis.cluster_detector import detect_proto_genres
    from ml.genesis.genre_describer import describe_proto_genres
    from ml.genesis.lineage_tracer import trace_all_clusters

    clusters = detect_proto_genres(eps=eps, min_samples=min_samples)

    if not clusters:
        return {
            "clusters": [],
            "total_clusters": 0,
            "message": "No proto-genre clusters detected. "
                       "This may mean there aren't enough underground artists "
                       "with embeddings, or the DBSCAN parameters need tuning.",
        }

    # Enrich with lineage roots (graph traversal — fast)
    trace_all_clusters(clusters)

    # Enrich with AI descriptions (API calls — slower)
    await describe_proto_genres(clusters)

    result = {
        "clusters": [pg.to_dict() for pg in clusters],
        "total_clusters": len(clusters),
        "parameters": {"eps": eps, "min_samples": min_samples},
    }

    # Cache in Redis
    try:
        r = _get_redis()
        r.setex(_GENESIS_CACHE_KEY, _GENESIS_CACHE_TTL, json.dumps(result))
        logger.info(f"Cached {len(clusters)} genesis clusters (TTL={_GENESIS_CACHE_TTL}s)")
    except Exception as exc:
        logger.warning(f"Failed to cache genesis results: {exc}")

    return result

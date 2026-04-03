"""Embedding-powered search endpoints: similar, discover, midpoint."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ml.embeddings.search_engine import get_vector_engine
from services import graph_manager as gm

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class SimilarArtistEntry(BaseModel):
    mbid: str
    name: Optional[str] = None
    score: float
    underground_score: Optional[float] = None
    in_graph: bool = False
    source: str = "embedding"


class SimilarResponse(BaseModel):
    mbid: str
    name: Optional[str] = None
    results: list[SimilarArtistEntry] = Field(default_factory=list)
    total: int = 0


class DiscoverRequest(BaseModel):
    positive_artists: list[str] = Field(..., min_length=1)
    negative_artists: list[str] = Field(default_factory=list)
    top_n: int = Field(default=20, ge=1, le=100)
    min_underground: float = Field(default=0.0, ge=0.0, le=1.0)


class MidpointRequest(BaseModel):
    mbid_a: str
    mbid_b: str
    top_n: int = Field(default=20, ge=1, le=100)


class MidpointResponse(BaseModel):
    mbid_a: str
    mbid_b: str
    name_a: Optional[str] = None
    name_b: Optional[str] = None
    results: list[SimilarArtistEntry] = Field(default_factory=list)
    common_tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_engine():
    engine = get_vector_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Vector search not available. Run scripts/retrain_all.py first.",
        )
    return engine


def _artist_name(mbid: str) -> Optional[str]:
    artist = gm.get_artist(mbid)
    return artist.name if artist else None


def _enrich_results(
    raw: list[tuple[str, float]], min_underground: float = 0.0
) -> list[SimilarArtistEntry]:
    results = []
    for mbid, score in raw:
        artist = gm.get_artist(mbid)
        ug = artist.underground_score if artist else 0.0
        if min_underground > 0.0 and ug < min_underground:
            continue
        results.append(
            SimilarArtistEntry(
                mbid=mbid,
                name=artist.name if artist else None,
                score=round(score, 4),
                underground_score=round(ug, 3) if artist else None,
                in_graph=gm.artist_exists(mbid),
            )
        )
    return results


# ---------------------------------------------------------------------------
# GET /api/similar/{mbid}
# ---------------------------------------------------------------------------
@router.get(
    "/similar/{mbid}",
    response_model=SimilarResponse,
    summary="Find similar artists via embedding proximity",
)
async def get_similar(
    mbid: str,
    top_n: int = Query(default=20, ge=1, le=100),
    min_underground: float = Query(default=0.0, ge=0.0, le=1.0),
):
    engine = _require_engine()
    if not engine.has_artist(mbid):
        raise HTTPException(status_code=404, detail="Artist not in embedding index.")

    raw = engine.search_similar(mbid, top_n=top_n + 20)  # fetch extra for filtering
    results = _enrich_results(raw, min_underground)[:top_n]

    return SimilarResponse(
        mbid=mbid,
        name=_artist_name(mbid),
        results=results,
        total=len(results),
    )


# ---------------------------------------------------------------------------
# POST /api/discover
# ---------------------------------------------------------------------------
@router.post(
    "/discover",
    response_model=SimilarResponse,
    summary="Vibe search — vector arithmetic discovery",
)
async def discover(req: DiscoverRequest):
    engine = _require_engine()

    # Validate that at least some positive artists exist in the index
    valid_pos = [m for m in req.positive_artists if engine.has_artist(m)]
    if not valid_pos:
        raise HTTPException(
            status_code=404,
            detail="None of the positive artists are in the embedding index.",
        )

    valid_neg = [m for m in req.negative_artists if engine.has_artist(m)]

    raw = engine.vector_arithmetic(
        positive_mbids=valid_pos,
        negative_mbids=valid_neg,
        top_n=req.top_n + 20,
    )
    results = _enrich_results(raw, req.min_underground)[:req.top_n]

    return SimilarResponse(
        mbid=valid_pos[0],
        name=_artist_name(valid_pos[0]),
        results=results,
        total=len(results),
    )


# ---------------------------------------------------------------------------
# POST /api/midpoint
# ---------------------------------------------------------------------------
@router.post(
    "/midpoint",
    response_model=MidpointResponse,
    summary="Find artists between two others in embedding space",
)
async def midpoint(req: MidpointRequest):
    engine = _require_engine()

    if not engine.has_artist(req.mbid_a):
        raise HTTPException(status_code=404, detail=f"Artist {req.mbid_a} not in embedding index.")
    if not engine.has_artist(req.mbid_b):
        raise HTTPException(status_code=404, detail=f"Artist {req.mbid_b} not in embedding index.")

    mid_vec = engine.compute_midpoint(req.mbid_a, req.mbid_b)
    if mid_vec is None:
        raise HTTPException(status_code=500, detail="Failed to compute midpoint.")

    raw = engine.search_by_vector(
        mid_vec, top_n=req.top_n, exclude_mbids={req.mbid_a, req.mbid_b}
    )
    results = _enrich_results(raw)

    # Find common tags among midpoint results for "blending" explanation
    tag_counts: dict[str, int] = {}
    for entry in results[:10]:
        artist = gm.get_artist(entry.mbid)
        if artist:
            for tag in (artist.tags or []) + (artist.genres or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    common_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:8]

    return MidpointResponse(
        mbid_a=req.mbid_a,
        mbid_b=req.mbid_b,
        name_a=_artist_name(req.mbid_a),
        name_b=_artist_name(req.mbid_b),
        results=results,
        common_tags=common_tags,
    )

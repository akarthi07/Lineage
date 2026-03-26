"""Similarity matrix query endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ml.similarity_engine import get_engine
from services import graph_manager as gm

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class PairSimilarityResponse(BaseModel):
    mbid_a: str
    mbid_b: str
    score: float
    name_a: Optional[str] = None
    name_b: Optional[str] = None


class SimilarArtistEntry(BaseModel):
    mbid: str
    name: Optional[str] = None
    score: float
    underground_score: Optional[float] = None
    in_graph: bool = False


class SimilarArtistsResponse(BaseModel):
    mbid: str
    name: Optional[str] = None
    results: list[SimilarArtistEntry] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_engine():
    engine = get_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Similarity matrix not available. Run scripts/recompute_matrix.py first.",
        )
    return engine


def _artist_name(mbid: str) -> Optional[str]:
    artist = gm.get_artist(mbid)
    return artist.name if artist else None


# ---------------------------------------------------------------------------
# GET /api/similarity/{mbid_a}/{mbid_b}
# ---------------------------------------------------------------------------
@router.get(
    "/{mbid_a}/{mbid_b}",
    response_model=PairSimilarityResponse,
    summary="Get pairwise similarity score between two artists",
)
async def get_pair_similarity(mbid_a: str, mbid_b: str):
    engine = _require_engine()

    score = engine.get_similarity(mbid_a, mbid_b)
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="One or both artists not found in the similarity matrix.",
        )

    return PairSimilarityResponse(
        mbid_a=mbid_a,
        mbid_b=mbid_b,
        score=round(score, 4),
        name_a=_artist_name(mbid_a),
        name_b=_artist_name(mbid_b),
    )


# ---------------------------------------------------------------------------
# GET /api/similarity/{mbid}/similar
# ---------------------------------------------------------------------------
@router.get(
    "/{mbid}/similar",
    response_model=SimilarArtistsResponse,
    summary="Get most similar artists from the similarity matrix",
)
async def get_similar_artists(
    mbid: str,
    top_n: int = Query(default=20, ge=1, le=100),
    min_underground: float = Query(default=0.0, ge=0.0, le=1.0),
):
    engine = _require_engine()

    if not engine.has_artist(mbid):
        raise HTTPException(status_code=404, detail="Artist not in similarity matrix.")

    # Build underground scores dict for filtering if needed
    artist_scores = None
    if min_underground > 0.0:
        artist_scores = {}
        driver = gm.get_driver()
        with driver.session() as session:
            result = session.run(
                "MATCH (a:Artist) RETURN a.mbid AS mbid, a.underground_score AS score"
            )
            for record in result:
                artist_scores[record["mbid"]] = record["score"] or 0.0

    pairs = engine.get_most_similar(
        mbid, top_n=top_n, min_underground=min_underground, artist_scores=artist_scores
    )

    results = []
    for other_mbid, score in pairs:
        artist = gm.get_artist(other_mbid)
        results.append(
            SimilarArtistEntry(
                mbid=other_mbid,
                name=artist.name if artist else None,
                score=round(score, 4),
                underground_score=artist.underground_score if artist else None,
                in_graph=gm.artist_exists(other_mbid),
            )
        )

    return SimilarArtistsResponse(
        mbid=mbid,
        name=_artist_name(mbid),
        results=results,
        total=len(results),
    )

"""Natural language discovery search endpoint."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.lastfm_client import get_similar_artists, get_artist_info
from services import graph_manager as gm
from models.artist import ArtistNode

logger = logging.getLogger(__name__)
router = APIRouter()


class NaturalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=50)


class NaturalSearchResponse(BaseModel):
    query: str
    results: list[ArtistNode]
    total: int
    note: str = ""


@router.post(
    "/natural",
    response_model=NaturalSearchResponse,
    summary="Natural language discovery — find artists matching a description",
)
async def search_natural(req: NaturalSearchRequest):
    """
    Handles discovery queries like "find me something like X but weirder."

    For now: extracts the artist name from the query and returns their
    Last.fm similar artists, enriched with any Neo4j data we have.

    Claude NLP parsing (Chunk 2) will replace the naive name extraction
    and enable full modifier/vibe handling.
    """
    # Naive extraction until Claude NLP is wired in (Chunk 2)
    artist_name = req.query.strip()

    info = get_artist_info(artist_name)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"'{artist_name}' not found on Last.fm.",
        )

    similar = get_similar_artists(artist_name, limit=req.limit)
    if not similar:
        return NaturalSearchResponse(
            query=req.query,
            results=[],
            total=0,
            note="No similar artists found. The artist may be too underground for Last.fm's algorithm.",
        )

    # Build ArtistNode list — prefer Neo4j data if we have it, else use Last.fm data
    results: list[ArtistNode] = []
    for s in similar:
        name = s.get("name", "")
        mbid = s.get("mbid") or None

        # Try to pull richer data from Neo4j
        neo4j_artist = gm.get_artist(mbid) if mbid else None
        if neo4j_artist:
            results.append(ArtistNode(
                id=neo4j_artist.mbid or mbid or name,
                name=neo4j_artist.name,
                mbid=neo4j_artist.mbid,
                spotify_id=neo4j_artist.spotify_id,
                lastfm_listeners=neo4j_artist.lastfm_listeners,
                spotify_popularity=neo4j_artist.spotify_popularity,
                underground_score=neo4j_artist.underground_score,
                genres=neo4j_artist.genres,
                tags=neo4j_artist.tags,
                image_url=neo4j_artist.image_url,
                depth_level=1,
            ))
        else:
            results.append(ArtistNode(
                id=mbid or name,
                name=name,
                mbid=mbid,
                depth_level=1,
            ))

    return NaturalSearchResponse(
        query=req.query,
        results=results,
        total=len(results),
    )

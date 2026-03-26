"""Natural language discovery search endpoint."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.lastfm_client import get_similar_artists, get_artist_info
from services.nlp_client import parse_query, resolve_discovery
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
    discovery_params: dict = {}
    note: str = ""


@router.post(
    "/natural",
    response_model=NaturalSearchResponse,
    summary="Natural language discovery — find artists matching a description",
)
async def search_natural(req: NaturalSearchRequest):
    """
    Handles discovery queries like "find me something like X but weirder."

    Uses Claude NLP to parse the query and resolve abstract modifiers into
    concrete search tags and seed artists, then searches Last.fm + Neo4j.
    """
    # --- NLP parse ---
    discovery_params = {}
    seed_artist_name = req.query.strip()

    try:
        parsed = parse_query(req.query)
        # Use the primary artist name from the parse
        if parsed.artist_names:
            seed_artist_name = parsed.artist_names[0]

        # If this is a discovery query, resolve abstract modifiers
        if parsed.query_type == "discovery":
            try:
                discovery_params = resolve_discovery(parsed)
                # Use seed artists from discovery if available
                seed_names = discovery_params.get("seed_artists", [])
                if seed_names:
                    seed_artist_name = seed_names[0]
            except Exception as exc:
                logger.warning(f"Discovery resolve failed, falling back: {exc}")
    except Exception as exc:
        logger.warning(f"NLP parse failed, using raw query: {exc}")

    # --- Fetch similar artists from Last.fm ---
    info = get_artist_info(seed_artist_name)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"'{seed_artist_name}' not found on Last.fm.",
        )

    similar = get_similar_artists(seed_artist_name, limit=req.limit)
    if not similar:
        return NaturalSearchResponse(
            query=req.query,
            results=[],
            total=0,
            discovery_params=discovery_params,
            note="No similar artists found. The artist may be too underground for Last.fm's algorithm.",
        )

    # --- Filter by discovery tags if we have them ---
    search_tags = set(t.lower() for t in discovery_params.get("search_tags", []))
    exclude_tags = set(t.lower() for t in discovery_params.get("exclude_tags", []))

    # Build ArtistNode list — prefer Neo4j data if we have it
    results: list[ArtistNode] = []
    for s in similar:
        name = s.get("name", "")
        mbid = s.get("mbid") or None

        # Try to pull richer data from Neo4j
        neo4j_artist = gm.get_artist(mbid) if mbid else None
        if neo4j_artist:
            node = ArtistNode(
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
            )
        else:
            node = ArtistNode(
                id=mbid or name,
                name=name,
                mbid=mbid,
                depth_level=1,
            )

        # If we have discovery tags, boost artists that match and skip excluded
        if exclude_tags:
            artist_tags = set(t.lower() for t in node.tags)
            if artist_tags & exclude_tags:
                continue

        results.append(node)

    # Sort: if we have search_tags, prioritize artists whose tags overlap
    if search_tags:
        def tag_score(node: ArtistNode) -> int:
            artist_tags = set(t.lower() for t in node.tags)
            return len(artist_tags & search_tags)
        results.sort(key=tag_score, reverse=True)

    return NaturalSearchResponse(
        query=req.query,
        results=results,
        total=len(results),
        discovery_params=discovery_params,
    )

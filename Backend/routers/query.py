"""POST /api/query — main entry point for natural language queries."""
from __future__ import annotations
import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional

from models.artist import LineageResult
from services import graph_manager as gm
from services.identity_resolver import resolve_artist
from services.artist_seeder import seed_artist_network

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    depth: int = Field(default=3, ge=1, le=5)
    underground_level: Literal["surface", "balanced", "deep"] = "balanced"


class SeedingResponse(BaseModel):
    status: Literal["seeding_in_progress"]
    artist_name: str
    check_back_in: int = 30
    message: str


class QueryResponse(BaseModel):
    query_id: str
    query_type: str
    artist_name: str
    parsed: dict
    results: LineageResult


def _run_seed(artist_name: str, depth: int) -> None:
    """Background task — seeds an artist network into Neo4j."""
    try:
        seed_artist_network(artist_name, depth=depth)
        logger.info(f"Background seed complete: {artist_name}")
    except Exception as exc:
        logger.error(f"Background seed failed for '{artist_name}': {exc}")


@router.post(
    "",
    response_model=QueryResponse | SeedingResponse,
    summary="Parse a natural language music query and return a lineage map",
)
async def post_query(req: QueryRequest, background_tasks: BackgroundTasks):
    """
    Main query endpoint. Accepts a natural language string and returns a
    force-directed graph (nodes + edges) representing the artist's lineage.

    If the artist is not yet in the graph, seeding is triggered as a
    background task and a `seeding_in_progress` response is returned
    immediately. The client should poll again after `check_back_in` seconds.
    """
    # For now: treat the query as a direct artist name.
    # Claude NLP parsing is wired in during Chunk 2.
    artist_name = req.query.strip()

    # Resolve artist to get their MBID
    artist = resolve_artist(artist_name)
    if not artist:
        raise HTTPException(
            status_code=404,
            detail=f"Artist '{artist_name}' not found on MusicBrainz, Last.fm, or Spotify.",
        )

    node_id = artist.mbid
    if not node_id:
        raise HTTPException(
            status_code=404,
            detail=f"Could not obtain a stable ID for '{artist_name}'.",
        )

    # Check if artist is already seeded in Neo4j
    if not gm.artist_exists(node_id):
        logger.info(f"Artist '{artist_name}' not in graph — triggering background seed")
        background_tasks.add_task(_run_seed, artist_name, req.depth)
        return SeedingResponse(
            status="seeding_in_progress",
            artist_name=artist.name,
            check_back_in=30,
            message=f"We're mapping {artist.name}'s lineage. Check back in about 30 seconds.",
        )

    # Artist is seeded — query the graph
    lineage = gm.get_lineage(
        mbid=node_id,
        direction="backward",
        depth=req.depth,
        underground_level=req.underground_level,
    )

    return QueryResponse(
        query_id=str(uuid.uuid4()),
        query_type="artist_lineage",
        artist_name=artist.name,
        parsed={
            "artist": artist.name,
            "mbid": node_id,
            "direction": "backward",
            "depth": req.depth,
            "underground_level": req.underground_level,
        },
        results=lineage,
    )

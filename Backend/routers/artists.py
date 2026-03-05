"""Artist detail and lineage endpoints."""
from __future__ import annotations
import logging
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query

from models.artist import Artist, LineageResult
from services import graph_manager as gm
from services.identity_resolver import resolve_artist

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{node_id}",
    response_model=Artist,
    summary="Get full artist detail by ID",
)
async def get_artist(node_id: str):
    """
    Returns full artist metadata for a given node ID (MBID or synthetic ID).
    Data is pulled from Neo4j and enriched with cached API data.
    """
    artist = gm.get_artist(node_id)
    if not artist:
        raise HTTPException(status_code=404, detail=f"Artist '{node_id}' not found in graph.")
    return artist


@router.get(
    "/{node_id}/lineage",
    response_model=LineageResult,
    summary="Get lineage graph for an artist",
)
async def get_artist_lineage(
    node_id: str,
    direction: Literal["backward", "forward", "both"] = Query(
        default="backward",
        description="backward = influences of artist, forward = artists influenced by them",
    ),
    depth: int = Query(default=3, ge=1, le=5, description="Graph traversal depth"),
    underground_level: Literal["surface", "balanced", "deep"] = Query(
        default="balanced",
        description="surface = mainstream only, deep = underground prioritised",
    ),
    era_filter: Optional[str] = Query(default=None, description="Filter by era e.g. '1970s'"),
    geo_filter: Optional[str] = Query(default=None, description="Filter by country/region"),
):
    """
    Direct lineage query — bypasses NLP, uses the artist's node ID directly.
    Returns a force-directed graph (nodes + edges) ready for D3.js rendering.

    era_filter and geo_filter are applied client-side for now;
    they are passed through in metadata for the frontend to consume.
    """
    if not gm.artist_exists(node_id):
        raise HTTPException(
            status_code=404,
            detail=f"Artist '{node_id}' is not in the graph. Seed them first via POST /api/query.",
        )

    lineage = gm.get_lineage(
        mbid=node_id,
        direction=direction,
        depth=depth,
        underground_level=underground_level,
    )

    # Attach filter params to metadata for frontend
    lineage.metadata["era_filter"] = era_filter
    lineage.metadata["geo_filter"] = geo_filter

    return lineage

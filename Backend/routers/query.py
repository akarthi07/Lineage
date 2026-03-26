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
from services.nlp_client import parse_query, parse_clarification, resolve_discovery

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    depth: int = Field(default=3, ge=1, le=5)
    underground_level: Literal["surface", "balanced", "deep"] = "balanced"


class ClarificationRequest(BaseModel):
    original_query: str
    clarification_question: str
    user_response: str = Field(..., min_length=1, max_length=500)


class SeedingResponse(BaseModel):
    status: Literal["seeding_in_progress"]
    artist_name: str
    check_back_in: int = 30
    message: str


class ClarificationResponse(BaseModel):
    status: Literal["clarification_needed"]
    query_type: str = "clarification_needed"
    original_query: str
    question: str


class DiscoveryResponse(BaseModel):
    query_id: str
    query_type: str = "discovery"
    parsed: dict
    discovery_params: dict
    results: LineageResult


class ConnectionResponse(BaseModel):
    query_id: str
    query_type: str = "connection"
    artists: list[str]
    parsed: dict
    results: LineageResult


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


def _resolve_and_get_lineage(
    artist_name: str,
    direction: str,
    depth: int,
    underground_level: str,
    background_tasks: BackgroundTasks,
) -> tuple[Optional[str], Optional[LineageResult], Optional[SeedingResponse]]:
    """
    Resolve an artist name → MBID, check if seeded, return lineage or trigger seeding.
    Returns (artist_display_name, lineage_result, seeding_response).
    """
    artist = resolve_artist(artist_name)
    if not artist:
        return None, None, None

    node_id = artist.mbid
    if not node_id:
        return None, None, None

    if not gm.artist_exists(node_id):
        logger.info(f"Artist '{artist_name}' not in graph — triggering background seed")
        background_tasks.add_task(_run_seed, artist_name, depth)
        return (
            artist.name,
            None,
            SeedingResponse(
                status="seeding_in_progress",
                artist_name=artist.name,
                check_back_in=30,
                message=f"We're mapping {artist.name}'s lineage. Check back in about 30 seconds.",
            ),
        )

    lineage = gm.get_lineage(
        mbid=node_id,
        direction=direction,
        depth=depth,
        underground_level=underground_level,
    )
    return artist.name, lineage, None


@router.post(
    "",
    response_model=QueryResponse | SeedingResponse | ClarificationResponse | DiscoveryResponse | ConnectionResponse,
    summary="Parse a natural language music query and return a lineage map",
)
async def post_query(req: QueryRequest, background_tasks: BackgroundTasks):
    """
    Main query endpoint. Accepts a natural language string, parses it with
    Claude NLP, and returns a force-directed graph (nodes + edges).

    If the query is ambiguous, returns a clarification question.
    If the artist is not yet in the graph, triggers background seeding.
    """
    # --- NLP parse ---
    try:
        parsed = parse_query(req.query)
    except Exception as exc:
        logger.error(f"NLP parse failed: {exc}")
        # Fallback: treat entire query as artist name (pre-NLP behaviour)
        parsed = None

    # Fallback if NLP is down
    if parsed is None:
        artist_name = req.query.strip()
        artist = resolve_artist(artist_name)
        if not artist:
            raise HTTPException(status_code=404, detail=f"Artist '{artist_name}' not found.")
        node_id = artist.mbid
        if not node_id:
            raise HTTPException(status_code=404, detail=f"No stable ID for '{artist_name}'.")
        if not gm.artist_exists(node_id):
            background_tasks.add_task(_run_seed, artist_name, req.depth)
            return SeedingResponse(
                status="seeding_in_progress",
                artist_name=artist.name,
                check_back_in=30,
                message=f"We're mapping {artist.name}'s lineage. Check back in about 30 seconds.",
            )
        lineage = gm.get_lineage(mbid=node_id, direction="backward", depth=req.depth, underground_level=req.underground_level)
        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query_type="artist_lineage",
            artist_name=artist.name,
            parsed={"artist": artist.name, "mbid": node_id, "direction": "backward", "depth": req.depth},
            results=lineage,
        )

    # --- Clarification needed ---
    if parsed.query_type == "clarification_needed":
        # If we detected an artist name, just treat it as a lineage query
        # instead of bouncing back a clarification the frontend can't handle yet
        if parsed.artist_names:
            parsed.query_type = "artist_lineage"
            parsed.direction = "backward"
        else:
            return ClarificationResponse(
                status="clarification_needed",
                original_query=req.query,
                question=parsed.clarification_question or "Could you be more specific about what you're looking for?",
            )

    # --- Use NLP-parsed depth/underground if not overridden ---
    depth = parsed.depth if req.depth == 3 else req.depth  # prefer explicit override
    underground = parsed.underground_preference if req.underground_level == "balanced" else req.underground_level

    # --- Artist lineage ---
    if parsed.query_type == "artist_lineage":
        artist_name = parsed.artist_names[0] if parsed.artist_names else req.query.strip()
        display_name, lineage, seeding = _resolve_and_get_lineage(
            artist_name, parsed.direction, depth, underground, background_tasks,
        )
        if seeding:
            return seeding
        if lineage is None:
            raise HTTPException(status_code=404, detail=f"Artist '{artist_name}' not found.")
        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query_type="artist_lineage",
            artist_name=display_name,
            parsed=parsed.model_dump(),
            results=lineage,
        )

    # --- Genesis (same as lineage but may expand in future) ---
    if parsed.query_type == "genesis":
        artist_name = parsed.artist_names[0] if parsed.artist_names else req.query.strip()
        display_name, lineage, seeding = _resolve_and_get_lineage(
            artist_name, "backward", max(depth, 5), underground, background_tasks,
        )
        if seeding:
            return seeding
        if lineage is None:
            raise HTTPException(status_code=404, detail=f"Could not find a root artist for this genesis query.")
        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query_type="genesis",
            artist_name=display_name,
            parsed=parsed.model_dump(),
            results=lineage,
        )

    # --- Connection (two artists) ---
    if parsed.query_type == "connection":
        if len(parsed.artist_names) < 2:
            raise HTTPException(status_code=400, detail="Connection queries need exactly two artists.")
        # Resolve both artists and return combined lineage
        all_nodes = []
        all_edges = []
        artist_display_names = []
        for name in parsed.artist_names[:2]:
            display_name, lineage, seeding = _resolve_and_get_lineage(
                name, "both", depth, underground, background_tasks,
            )
            if seeding:
                return seeding
            if lineage is None:
                raise HTTPException(status_code=404, detail=f"Artist '{name}' not found.")
            artist_display_names.append(display_name)
            all_nodes.extend(lineage.nodes)
            all_edges.extend(lineage.edges)

        # Deduplicate nodes by ID
        seen_ids = set()
        unique_nodes = []
        for n in all_nodes:
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                unique_nodes.append(n)

        combined = LineageResult(
            nodes=unique_nodes,
            edges=all_edges,
            metadata={"connection_between": artist_display_names},
        )
        return ConnectionResponse(
            query_id=str(uuid.uuid4()),
            artists=artist_display_names,
            parsed=parsed.model_dump(),
            results=combined,
        )

    # --- Discovery ---
    if parsed.query_type == "discovery":
        try:
            discovery_params = resolve_discovery(parsed)
        except Exception as exc:
            logger.error(f"Discovery resolve failed: {exc}")
            discovery_params = {"search_tags": parsed.musical_characteristics, "seed_artists": parsed.artist_names}

        # Use seed artists from discovery to build a lineage graph
        all_nodes = []
        all_edges = []
        seed_artists = discovery_params.get("seed_artists", parsed.artist_names)
        for name in seed_artists[:3]:  # limit to 3 seed artists
            display_name, lineage, seeding = _resolve_and_get_lineage(
                name, "backward", depth, underground, background_tasks,
            )
            if seeding:
                return seeding
            if lineage:
                all_nodes.extend(lineage.nodes)
                all_edges.extend(lineage.edges)

        # Deduplicate
        seen_ids = set()
        unique_nodes = []
        for n in all_nodes:
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                unique_nodes.append(n)

        combined = LineageResult(
            nodes=unique_nodes,
            edges=all_edges,
            metadata={
                "discovery_tags": discovery_params.get("search_tags", []),
                "explanation": discovery_params.get("explanation", ""),
            },
        )
        return DiscoveryResponse(
            query_id=str(uuid.uuid4()),
            parsed=parsed.model_dump(),
            discovery_params=discovery_params,
            results=combined,
        )

    # Fallback — shouldn't reach here
    raise HTTPException(status_code=400, detail=f"Unknown query type: {parsed.query_type}")


@router.post(
    "/clarify",
    response_model=QueryResponse | SeedingResponse | DiscoveryResponse | ConnectionResponse,
    summary="Resolve a clarification exchange and return results",
)
async def post_clarification(req: ClarificationRequest, background_tasks: BackgroundTasks):
    """
    Second turn of the clarification flow. Takes the original query,
    the clarification question, and the user's response, then re-parses.
    """
    try:
        parsed = parse_clarification(req.original_query, req.clarification_question, req.user_response)
    except Exception as exc:
        logger.error(f"Clarification parse failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to understand your response. Please try a new query.")

    # Re-dispatch through the main handler by constructing a QueryRequest
    fake_req = QueryRequest(query=req.user_response)
    # Override parsed — we call the same logic inline
    # For simplicity, handle the most common case (artist_lineage)
    if parsed.artist_names:
        artist_name = parsed.artist_names[0]
        display_name, lineage, seeding = _resolve_and_get_lineage(
            artist_name, parsed.direction, parsed.depth, parsed.underground_preference, background_tasks,
        )
        if seeding:
            return seeding
        if lineage is None:
            raise HTTPException(status_code=404, detail=f"Artist '{artist_name}' not found.")
        return QueryResponse(
            query_id=str(uuid.uuid4()),
            query_type=parsed.query_type,
            artist_name=display_name,
            parsed=parsed.model_dump(),
            results=lineage,
        )

    raise HTTPException(status_code=400, detail="Could not determine what you're looking for. Please try a new query.")

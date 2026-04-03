"""
Query router — maps parsed query types to the right combination of
search engines and defines execution plans for the search executor.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from models.query import ParsedQuery

logger = logging.getLogger(__name__)


@dataclass
class SearchPlan:
    """Describes which engines to invoke and how to weight them."""

    query_type: str
    artist_mbids: list[str] = field(default_factory=list)
    artist_names: list[str] = field(default_factory=list)

    # Which engines to run (True = include in parallel execution)
    use_graph: bool = False
    use_matrix: bool = False
    use_vector: bool = False
    use_audio: bool = False
    use_lyrics: bool = False
    use_production: bool = False

    # Weight overrides (None = use defaults)
    weights: Optional[dict[str, float]] = None

    # Search parameters
    direction: str = "backward"
    depth: int = 3
    underground_level: str = "balanced"
    top_n: int = 30

    # Vector-specific
    positive_mbids: list[str] = field(default_factory=list)
    negative_mbids: list[str] = field(default_factory=list)

    # Text query for lyric/audio search
    text_query: str = ""
    musical_characteristics: list[str] = field(default_factory=list)
    mood_descriptors: list[str] = field(default_factory=list)


# Default fusion weights per query type
WEIGHTS_BY_TYPE = {
    "artist_lineage": {
        "graph": 0.30,
        "vector": 0.25,
        "matrix": 0.20,
        "audio": 0.10,
        "lyrics": 0.10,
        "production": 0.05,
    },
    "discovery": {
        "graph": 0.15,
        "vector": 0.30,
        "matrix": 0.25,
        "audio": 0.15,
        "lyrics": 0.10,
        "production": 0.05,
    },
    "connection": {
        "graph": 0.35,
        "vector": 0.25,
        "matrix": 0.20,
        "audio": 0.05,
        "lyrics": 0.05,
        "production": 0.10,
    },
    "genesis": {
        "graph": 0.35,
        "vector": 0.20,
        "matrix": 0.25,
        "audio": 0.05,
        "lyrics": 0.05,
        "production": 0.10,
    },
}


def route_query(parsed: ParsedQuery, artist_mbids: list[str] | None = None) -> SearchPlan:
    """
    Given a ParsedQuery and resolved artist MBIDs, produce a SearchPlan
    that tells the executor which engines to invoke.
    """
    mbids = artist_mbids or []
    qt = parsed.query_type

    plan = SearchPlan(
        query_type=qt,
        artist_mbids=mbids,
        artist_names=parsed.artist_names,
        direction=parsed.direction,
        depth=parsed.depth,
        underground_level=parsed.underground_preference,
        musical_characteristics=parsed.musical_characteristics,
        mood_descriptors=parsed.mood_descriptors,
        weights=WEIGHTS_BY_TYPE.get(qt, WEIGHTS_BY_TYPE["artist_lineage"]),
    )

    if qt == "artist_lineage":
        plan.use_graph = True
        plan.use_matrix = True
        plan.use_vector = True
        plan.use_audio = True
        plan.use_lyrics = True
        plan.use_production = True

    elif qt == "discovery":
        plan.use_vector = True
        plan.use_matrix = True
        plan.use_audio = True
        plan.use_lyrics = True
        plan.use_production = True
        # Vector arithmetic: positive = seed artists
        plan.positive_mbids = mbids
        # Build text query from characteristics and mood
        parts = parsed.musical_characteristics + parsed.mood_descriptors + parsed.modifiers
        plan.text_query = " ".join(parts)

    elif qt == "connection":
        plan.use_graph = True
        plan.use_vector = True
        plan.use_matrix = True
        plan.use_production = True

    elif qt == "genesis":
        plan.use_graph = True
        plan.use_matrix = True
        plan.use_vector = True
        plan.use_production = True
        plan.depth = max(parsed.depth, 5)

    else:
        # Fallback: use everything
        plan.use_graph = True
        plan.use_matrix = True
        plan.use_vector = True

    logger.info(
        f"Routed '{qt}' → graph={plan.use_graph} matrix={plan.use_matrix} "
        f"vector={plan.use_vector} audio={plan.use_audio} "
        f"lyrics={plan.use_lyrics} production={plan.use_production}"
    )
    return plan

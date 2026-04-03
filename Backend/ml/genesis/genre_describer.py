"""
Proto-genre description generator using the Claude API.

Takes a detected ProtoGenre cluster and produces a natural language
description of what the cluster represents musically.
"""
from __future__ import annotations

import logging

import anthropic
from config import settings
from ml.genesis.cluster_detector import ProtoGenre

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def describe_proto_genre(pg: ProtoGenre) -> str:
    """
    Generate a 2-4 sentence description of a proto-genre cluster.

    Returns the description string. Falls back to a template-based
    description if the API call fails.
    """
    artist_names = [a.name for a in pg.artists[:12]]
    tags = pg.top_tags[:8]
    genres = pg.top_genres[:5]
    geo = pg.geography[:4] if pg.geography else ["Internet-native"]
    era = f"avg formation year ~{pg.avg_year:.0f}" if pg.avg_year else "varied era"

    prompt = (
        "You are a music journalist specializing in underground and emerging genres. "
        "A clustering algorithm detected a group of artists that form a potential unnamed proto-genre. "
        "Write a concise 2-4 sentence description of this cluster. Focus on what unifies them sonically "
        "and culturally, and what established genres they are closest to (without being fully part of). "
        "Do NOT invent a genre name — just describe the sound and scene.\n\n"
        f"Artists: {', '.join(artist_names)}\n"
        f"Common tags: {', '.join(tags)}\n"
        f"Genres: {', '.join(genres)}\n"
        f"Geography: {', '.join(geo)}\n"
        f"Era: {era}\n"
        f"Cluster size: {pg.size} artists\n"
        f"Average underground score: {pg.avg_underground:.2f} (0=mainstream, 1=deep underground)\n"
        f"Cohesion score: {pg.cohesion_score:.2f} (how tightly grouped in embedding space)\n"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        description = response.content[0].text.strip()
        logger.info(f"Generated description for cluster {pg.cluster_id} ({pg.size} artists)")
        return description
    except Exception as exc:
        logger.warning(f"Claude API call failed for cluster {pg.cluster_id}: {exc}")
        return _fallback_description(pg)


def _fallback_description(pg: ProtoGenre) -> str:
    """Template-based fallback when the API is unavailable."""
    artists_str = ", ".join(a.name for a in pg.artists[:5])
    if len(pg.artists) > 5:
        artists_str += f", and {len(pg.artists) - 5} more"

    tags_str = ", ".join(pg.top_tags[:5]) if pg.top_tags else "varied styles"
    geo_str = ", ".join(pg.geography[:3]) if pg.geography else "internet-native"
    era_str = f"around {pg.avg_year:.0f}" if pg.avg_year else "across varied eras"

    return (
        f"A cluster of {pg.size} underground artists ({artists_str}) "
        f"concentrated in {geo_str}, active {era_str}. "
        f"Common threads include {tags_str}. "
        f"No established genre name fully covers this group."
    )


async def describe_proto_genres(clusters: list[ProtoGenre]) -> list[ProtoGenre]:
    """
    Enrich a list of ProtoGenre clusters with AI-generated descriptions.
    Mutates each cluster's .description field in place and returns the list.
    """
    for pg in clusters:
        if not pg.description:
            pg.description = describe_proto_genre(pg)
    return clusters

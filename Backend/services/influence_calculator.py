"""Influence strength calculation combining signals from multiple sources."""
from __future__ import annotations
from typing import Optional


def _jaccard(set_a: list[str], set_b: list[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    a, b = set(t.lower() for t in set_a), set(t.lower() for t in set_b)
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def calculate_influence_strength(
    artist_a_tags: list[str],
    artist_b_tags: list[str],
    artist_a_year: Optional[int],
    artist_b_year: Optional[int],
    artist_a_underground_score: float,
    artist_b_underground_score: float,
    mb_relationship_type: Optional[str] = None,
    lastfm_match: Optional[float] = None,
    shared_producers: int = 0,
    has_sample_connection: bool = False,
) -> tuple[float, float]:
    """
    Returns (strength, confidence) both in [0.0, 1.0].

    Parameters:
        artist_a_tags: tags for the influenced artist (the one doing the listening)
        artist_b_tags: tags for the influence (the older/source artist)
        artist_a_year: formation year of artist_a
        artist_b_year: formation year of artist_b (should be older for temporal bonus)
        mb_relationship_type: MusicBrainz relationship type string, if any
        lastfm_match: Last.fm similarity match score 0-1, if any
    """
    sources_used = 0
    sources_agreeing = 0

    # --- MusicBrainz documented relationship (strongest signal) ---
    if mb_relationship_type is not None:
        sources_used += 1
        sources_agreeing += 1
        mb_type_lower = mb_relationship_type.lower()
        if "influenced by" in mb_type_lower or "influenced" in mb_type_lower:
            base_score = 0.9
        elif "member of" in mb_type_lower or "subgroup" in mb_type_lower:
            base_score = 0.7
        elif "collaboration" in mb_type_lower or "collaborated" in mb_type_lower:
            base_score = 0.6
        else:
            base_score = 0.5
    else:
        base_score = 0.0

    # --- Last.fm similar artist score (behavioral signal) ---
    if lastfm_match is not None:
        sources_used += 1
        if lastfm_match > 0.2:
            sources_agreeing += 1
        # Last.fm is the most reliable and widely-available signal
        lastfm_bonus = lastfm_match * 0.6
        # Floor: any Last.fm match > 0.05 guarantees a minimum connection
        if lastfm_match > 0.05 and lastfm_bonus < 0.12:
            lastfm_bonus = 0.12
    else:
        lastfm_bonus = 0.0

    # If no signal at all, don't create the relationship
    if base_score == 0.0 and lastfm_bonus == 0.0 and shared_producers == 0 and not has_sample_connection:
        return 0.0, 0.0

    # --- Tag/genre overlap (metadata signal) ---
    tag_overlap = _jaccard(artist_a_tags, artist_b_tags) * 0.15

    # --- Temporal bonus (artist_b formed before artist_a = direction makes sense) ---
    temporal_bonus = 0.0
    if artist_a_year and artist_b_year and artist_b_year < artist_a_year:
        temporal_bonus = 0.1

    # --- Underground bonus ---
    underground_bonus = 0.0
    if artist_a_underground_score > 0.7 or artist_b_underground_score > 0.7:
        underground_bonus = 0.05

    # --- Production credit bonus ---
    production_bonus = 0.0
    if shared_producers > 0:
        sources_used += 1
        sources_agreeing += 1
        production_bonus = min(0.3, 0.15 * shared_producers)
    if has_sample_connection:
        sources_used += 1
        sources_agreeing += 1
        production_bonus += 0.5

    strength = min(
        1.0,
        base_score + lastfm_bonus + tag_overlap + temporal_bonus + underground_bonus + production_bonus,
    )

    # Confidence: based on how many sources agree
    if sources_used == 0:
        confidence = 0.3  # only tag/temporal signals
    else:
        confidence = min(1.0, 0.5 + (sources_agreeing / sources_used) * 0.5)

    return round(strength, 4), round(confidence, 4)

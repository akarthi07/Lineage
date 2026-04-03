"""Artist seeder — orchestrates fetching from all sources and seeding Neo4j."""
from __future__ import annotations
import time
from typing import Optional

from models.artist import Artist
from services.identity_resolver import resolve_artist
from services.influence_calculator import calculate_influence_strength
from services import musicbrainz_client as mb
from services import lastfm_client as lastfm
from services import graph_manager as gm

# Minimum strength threshold to create a relationship
MIN_STRENGTH = 0.10

# MusicBrainz relationship types we care about
RELEVANT_MB_TYPES = {
    "influenced by", "member of band", "collaboration",
    "subgroup", "tribute", "is person",
}


def seed_artist_network(artist_name: str, depth: int = 2) -> Optional[Artist]:
    """
    Resolve an artist, fetch all their connections, store everything in Neo4j.
    Returns the root Artist object.

    depth: how many hops to recurse (1 = only direct connections, 2 = one level deeper)
    """
    print(f"[Seeder] Starting seed for '{artist_name}' (depth={depth})")
    root = resolve_artist(artist_name)
    if not root:
        print(f"[Seeder] Could not resolve '{artist_name}' from any source")
        return None

    if not root.mbid:
        print(f"[Seeder] '{artist_name}' not found on any source — cannot store")
        return None

    id_type = "real MBID" if not root.mbid.startswith(("spotify:", "lastfm:")) else f"synthetic ({root.mbid.split(':')[0]})"
    gm.upsert_artist(root)
    print(f"[Seeder] Stored root artist: {root.name} ({id_type}: {root.mbid})")

    _seed_connections(root, current_depth=1, max_depth=depth, visited={root.mbid})
    return root


def _seed_connections(
    artist: Artist,
    current_depth: int,
    max_depth: int,
    visited: set[str],
) -> None:
    if current_depth > max_depth or not artist.mbid or not artist.name:
        return

    # Collect all connections: MB documented + Last.fm similar
    connections: list[tuple[str, Optional[str], Optional[float]]] = []
    # Each entry: (artist_name, mb_relationship_type, lastfm_match_score)

    # --- MusicBrainz relationships ---
    mb_rels = mb.get_artist_relationships(artist.mbid)
    mb_name_to_type: dict[str, str] = {}
    for rel in mb_rels:
        rel_type = rel.get("type", "").lower()
        target = rel.get("artist") or {}
        target_name = target.get("name", "")
        if target_name and rel_type:
            mb_name_to_type[target_name] = rel.get("type", "")
            connections.append((target_name, rel.get("type"), None))

    # --- Last.fm similar artists ---
    lastfm_similar = lastfm.get_similar_artists(artist.name, limit=30)
    lastfm_name_to_match: dict[str, float] = {}
    for s in lastfm_similar:
        name = s.get("name", "")
        match = s.get("match", 0.0)
        if name and match > 0:
            lastfm_name_to_match[name] = match

    # Merge: if both sources have the same artist, combine
    all_names = set(mb_name_to_type.keys()) | set(lastfm_name_to_match.keys())
    merged_connections: list[tuple[str, Optional[str], Optional[float]]] = []
    for name in all_names:
        mb_type = mb_name_to_type.get(name)
        lfm_match = lastfm_name_to_match.get(name)
        merged_connections.append((name, mb_type, lfm_match))

    print(f"[Seeder] {artist.name}: {len(merged_connections)} connections to process (depth {current_depth})")

    for connected_name, mb_type, lfm_match in merged_connections:
        # Resolve the connected artist
        connected = resolve_artist(connected_name)
        if not connected or not connected.mbid:
            continue

        if not connected.mbid:
            continue

        if connected.mbid in visited:
            # Already seeded — still try to create the relationship
            _try_create_relationship(artist, connected, mb_type, lfm_match)
            continue

        visited.add(connected.mbid)
        gm.upsert_artist(connected)
        _try_create_relationship(artist, connected, mb_type, lfm_match)

        # Recurse if not at max depth
        if current_depth < max_depth:
            _seed_connections(connected, current_depth + 1, max_depth, visited)


def _try_create_relationship(
    source: Artist,
    target: Artist,
    mb_type: Optional[str],
    lastfm_match: Optional[float],
) -> None:
    if not source.mbid or not target.mbid or not source.name or not target.name:
        return

    strength, confidence = calculate_influence_strength(
        artist_a_tags=source.tags,
        artist_b_tags=target.tags,
        artist_a_year=source.formation_year,
        artist_b_year=target.formation_year,
        artist_a_underground_score=source.underground_score,
        artist_b_underground_score=target.underground_score,
        mb_relationship_type=mb_type,
        lastfm_match=lastfm_match,
    )

    if strength < MIN_STRENGTH:
        return

    source_type = "musicbrainz" if mb_type else ("lastfm_similar" if lastfm_match else "tag_overlap")

    gm.upsert_relationship(
        source_mbid=source.mbid,
        target_mbid=target.mbid,
        strength=strength,
        confidence=confidence,
        source_type=source_type,
        mb_type=mb_type,
        lastfm_match=lastfm_match,
    )
    print(f"  → {source.name} ←[{source_type}]— {target.name} (strength={strength:.2f}, conf={confidence:.2f})")

"""
Neo4j data exporter — bridge between the graph database and numpy.

Exports all Artist nodes and INFLUENCED_BY relationships into clean
Python objects suitable for matrix construction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from models.artist import Artist, Relationship
from services.graph_manager import get_driver

logger = logging.getLogger(__name__)


@dataclass
class GraphExport:
    """Container for the full exported graph data."""

    artists: list[Artist] = field(default_factory=list)
    artist_index: dict[str, int] = field(default_factory=dict)  # {mbid: index}
    relationships: list[Relationship] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.artists)


def export_graph_data() -> GraphExport:
    """
    Query Neo4j for all Artist nodes and INFLUENCED_BY relationships.
    Returns a GraphExport with artists sorted by index, an mbid->index map,
    and all relationships.
    """
    driver = get_driver()

    artists_by_mbid: dict[str, Artist] = {}
    relationships: list[Relationship] = []

    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Artist)
            OPTIONAL MATCH (a)-[r:INFLUENCED_BY]->(b:Artist)
            RETURN a, r, b
            """
        )

        for record in result:
            a_node = record["a"]
            r_rel = record["r"]
            b_node = record["b"]

            # Always process the source artist
            a_mbid = a_node.get("mbid", "")
            if a_mbid and a_mbid not in artists_by_mbid:
                artists_by_mbid[a_mbid] = _node_to_artist(a_node)

            # Process the target artist if the relationship exists
            if b_node is not None:
                b_mbid = b_node.get("mbid", "")
                if b_mbid and b_mbid not in artists_by_mbid:
                    artists_by_mbid[b_mbid] = _node_to_artist(b_node)

                # Process the relationship
                if r_rel is not None and a_mbid and b_mbid:
                    rel = Relationship(
                        source_mbid=a_mbid,
                        target_mbid=b_mbid,
                        strength=r_rel.get("strength", 0.5),
                        confidence=r_rel.get("confidence", 0.5),
                        source=r_rel.get("source", "unknown"),
                        musicbrainz_type=r_rel.get("musicbrainz_type") or None,
                        lastfm_match=r_rel.get("lastfm_match"),
                    )
                    relationships.append(rel)

    # Sort artists by name for deterministic ordering
    sorted_artists = sorted(artists_by_mbid.values(), key=lambda a: a.name.lower())
    artist_index = {artist.mbid: i for i, artist in enumerate(sorted_artists)}

    export = GraphExport(
        artists=sorted_artists,
        artist_index=artist_index,
        relationships=relationships,
    )

    logger.info(f"Exported {export.n} artists, {len(relationships)} relationships.")
    return export


def _node_to_artist(node) -> Artist:
    """Convert a Neo4j node dict to an Artist model."""
    return Artist(
        mbid=node.get("mbid") or None,
        spotify_id=node.get("spotify_id") or None,
        lastfm_url=node.get("lastfm_url") or None,
        name=node.get("name", ""),
        lastfm_listeners=node.get("lastfm_listeners"),
        lastfm_playcount=node.get("lastfm_playcount"),
        spotify_popularity=node.get("spotify_popularity"),
        spotify_followers=node.get("spotify_followers"),
        genres=node.get("genres") or [],
        tags=node.get("tags") or [],
        formation_year=node.get("formation_year"),
        country=node.get("country") or None,
        image_url=node.get("image_url") or None,
        underground_score=node.get("underground_score", 0.5),
    )

"""Neo4j graph manager — stores and queries the artist lineage graph."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase, Driver
from models.artist import Artist, ArtistNode, Edge, LineageResult


_driver: Optional[Driver] = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "lineagepassword")
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver


def close_driver() -> None:
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def ensure_indexes() -> None:
    """Create indexes if they don't exist (idempotent)."""
    driver = get_driver()
    with driver.session() as session:
        session.run("CREATE INDEX artist_mbid IF NOT EXISTS FOR (a:Artist) ON (a.mbid)")
        session.run("CREATE INDEX artist_spotify_id IF NOT EXISTS FOR (a:Artist) ON (a.spotify_id)")
        session.run("CREATE INDEX artist_name IF NOT EXISTS FOR (a:Artist) ON (a.name)")


def upsert_artist(artist: Artist) -> None:
    """Create or update an Artist node in Neo4j."""
    driver = get_driver()
    now = datetime.now(timezone.utc).isoformat()

    props = {
        "name": artist.name,
        "mbid": artist.mbid or "",
        "spotify_id": artist.spotify_id or "",
        "lastfm_url": artist.lastfm_url or "",
        "lastfm_listeners": artist.lastfm_listeners,
        "lastfm_playcount": artist.lastfm_playcount,
        "spotify_popularity": artist.spotify_popularity,
        "spotify_followers": artist.spotify_followers,
        "genres": artist.genres,
        "tags": artist.tags,
        "formation_year": artist.formation_year,
        "country": artist.country or "",
        "image_url": artist.image_url or "",
        "underground_score": artist.underground_score,
        "last_updated": now,
    }

    # Use MBID as the merge key if available, else name
    with driver.session() as session:
        if artist.mbid:
            session.run(
                """
                MERGE (a:Artist {mbid: $mbid})
                SET a += $props
                SET a.seeded_at = COALESCE(a.seeded_at, $now)
                """,
                mbid=artist.mbid,
                props=props,
                now=now,
            )
        else:
            session.run(
                """
                MERGE (a:Artist {name: $name})
                SET a += $props
                SET a.seeded_at = COALESCE(a.seeded_at, $now)
                """,
                name=artist.name,
                props=props,
                now=now,
            )


def upsert_relationship(
    source_mbid: str,
    target_mbid: str,
    strength: float,
    confidence: float,
    source_type: str,
    mb_type: Optional[str] = None,
    lastfm_match: Optional[float] = None,
) -> None:
    """Create or update an INFLUENCED_BY relationship between two artists."""
    driver = get_driver()
    now = datetime.now(timezone.utc).isoformat()

    with driver.session() as session:
        session.run(
            """
            MATCH (a:Artist {mbid: $source_mbid})
            MATCH (b:Artist {mbid: $target_mbid})
            MERGE (a)-[r:INFLUENCED_BY]->(b)
            SET r.strength = $strength,
                r.confidence = $confidence,
                r.source = $source_type,
                r.musicbrainz_type = $mb_type,
                r.lastfm_match = $lastfm_match,
                r.created_at = COALESCE(r.created_at, $now),
                r.updated_at = $now
            """,
            source_mbid=source_mbid,
            target_mbid=target_mbid,
            strength=strength,
            confidence=confidence,
            source_type=source_type,
            mb_type=mb_type or "",
            lastfm_match=lastfm_match,
            now=now,
        )


def artist_exists(mbid: str) -> bool:
    """Check if an artist node exists in Neo4j by MBID."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (a:Artist {mbid: $mbid}) RETURN count(a) AS cnt",
            mbid=mbid,
        )
        return result.single()["cnt"] > 0


def get_artist(mbid: str) -> Optional[Artist]:
    """Fetch an Artist node from Neo4j by MBID."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (a:Artist {mbid: $mbid}) RETURN a",
            mbid=mbid,
        )
        record = result.single()
        if not record:
            return None
        return _node_to_artist(record["a"])


def _underground_multiplier(score: float) -> float:
    if score > 0.7:
        return 3.0
    elif score > 0.4:
        return 2.0
    elif score > 0.1:
        return 1.0
    else:
        return 0.5


def get_lineage(
    mbid: str,
    direction: str = "backward",
    depth: int = 3,
    underground_level: str = "balanced",
) -> LineageResult:
    """
    Traverse the graph and return nodes + edges for the frontend.

    direction: "backward" (influences of artist), "forward" (artists influenced by), "both"
    underground_level: "surface" | "balanced" | "deep"
    """
    driver = get_driver()

    # Build Cypher based on direction
    if direction == "backward":
        rel_pattern = f"(start:Artist {{mbid: $mbid}})-[:INFLUENCED_BY*1..{depth}]->(influence:Artist)"
        match_clause = f"MATCH path = {rel_pattern}"
    elif direction == "forward":
        rel_pattern = f"(influence:Artist)-[:INFLUENCED_BY*1..{depth}]->(start:Artist {{mbid: $mbid}})"
        match_clause = f"MATCH path = {rel_pattern}"
    else:  # both
        match_clause = (
            f"MATCH path = (start:Artist {{mbid: $mbid}})-[:INFLUENCED_BY*1..{depth}]-(influence:Artist)"
        )

    query = f"""
    {match_clause}
    WITH path, start, nodes(path) AS path_nodes, relationships(path) AS rels
    RETURN path_nodes, rels, length(path) AS depth_level
    ORDER BY depth_level
    LIMIT 200
    """

    nodes_map: dict[str, ArtistNode] = {}
    edges_set: set[tuple] = set()
    edges_list: list[Edge] = []

    with driver.session() as session:
        # Add the root artist
        root_result = session.run("MATCH (a:Artist {mbid: $mbid}) RETURN a", mbid=mbid)
        root_record = root_result.single()
        if root_record:
            root = _node_to_artist_node(root_record["a"], depth_level=0)
            nodes_map[mbid] = root

        result = session.run(query, mbid=mbid)
        for record in result:
            path_nodes = record["path_nodes"]
            rels = record["rels"]
            depth_level = record["depth_level"]

            for i, node in enumerate(path_nodes):
                node_mbid = node.get("mbid", "")
                if node_mbid and node_mbid not in nodes_map:
                    level = 0 if node_mbid == mbid else i
                    nodes_map[node_mbid] = _node_to_artist_node(node, depth_level=level)

            for rel in rels:
                src = rel.start_node.get("mbid", "")
                tgt = rel.end_node.get("mbid", "")
                edge_key = (src, tgt)
                if src and tgt and edge_key not in edges_set:
                    edges_set.add(edge_key)
                    edges_list.append(Edge(
                        source=src,
                        target=tgt,
                        strength=rel.get("strength", 0.5),
                        source_type=rel.get("source", "unknown"),
                        confidence=rel.get("confidence", 0.5),
                        musicbrainz_type=rel.get("musicbrainz_type") or None,
                    ))

    # Apply underground filtering based on level preference
    if underground_level == "surface":
        # Show only mainstream (score < 0.5)
        nodes_map = {k: v for k, v in nodes_map.items() if v.underground_score < 0.5 or k == mbid}
    elif underground_level == "deep":
        pass  # Show everything, underground nodes already prominent

    nodes = list(nodes_map.values())
    underground_count = sum(1 for n in nodes if n.underground_score > 0.4)

    return LineageResult(
        nodes=nodes,
        edges=edges_list,
        metadata={
            "total_nodes": len(nodes),
            "underground_percentage": round(underground_count / max(len(nodes), 1), 2),
            "deepest_level_reached": depth,
            "data_sources_used": ["musicbrainz", "lastfm", "spotify"],
        },
    )


def _node_to_artist(node) -> Artist:
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


def _node_to_artist_node(node, depth_level: int = 0) -> ArtistNode:
    mbid = node.get("mbid", "")
    return ArtistNode(
        id=mbid,
        name=node.get("name", ""),
        mbid=mbid or None,
        spotify_id=node.get("spotify_id") or None,
        lastfm_listeners=node.get("lastfm_listeners"),
        spotify_popularity=node.get("spotify_popularity"),
        underground_score=node.get("underground_score", 0.5),
        genres=node.get("genres") or [],
        tags=node.get("tags") or [],
        formation_year=node.get("formation_year"),
        country=node.get("country") or None,
        image_url=node.get("image_url") or None,
        depth_level=depth_level,
    )

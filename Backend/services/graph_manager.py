"""Neo4j graph manager — stores and queries the artist lineage graph."""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase, Driver
from models.artist import Artist, ArtistNode, Edge, LineageResult

logger = logging.getLogger(__name__)


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

    lineage = LineageResult(
        nodes=nodes,
        edges=edges_list,
        metadata={
            "total_nodes": len(nodes),
            "underground_percentage": round(underground_count / max(len(nodes), 1), 2),
            "deepest_level_reached": depth,
            "data_sources_used": ["musicbrainz", "lastfm", "spotify"],
        },
    )

    # Enrich with matrix-suggested connections
    _enrich_with_matrix_suggestions(lineage, nodes_map, edges_set)

    # Enrich with embedding-suggested connections
    _enrich_with_embedding_suggestions(lineage, nodes_map, edges_set)

    return lineage


def _enrich_with_matrix_suggestions(
    lineage: LineageResult,
    nodes_map: dict[str, ArtistNode],
    existing_edges: set[tuple],
    suggestions_per_node: int = 3,
) -> None:
    """
    For each node in the lineage, find top matrix-similar artists that are NOT
    already in the graph result. Adds them as 'suggested connection' edges
    with source_type='matrix_similarity'.
    """
    from ml.similarity_engine import get_engine

    engine = get_engine()
    if engine is None or not lineage.nodes:
        return

    # Collect MBIDs already in the result
    existing_mbids = set(nodes_map.keys())

    added_nodes = 0
    added_edges = 0
    max_suggestions = 9  # cap total suggestions to avoid clutter

    for node in list(lineage.nodes):
        if added_nodes >= max_suggestions:
            break
        if not engine.has_artist(node.id):
            continue

        similar = engine.get_most_similar(node.id, top_n=suggestions_per_node + 5)

        count = 0
        for other_mbid, score in similar:
            if count >= suggestions_per_node or added_nodes >= max_suggestions:
                break
            # Skip if already in the graph result (as node or edge)
            if other_mbid in existing_mbids:
                continue
            edge_key = (node.id, other_mbid)
            reverse_key = (other_mbid, node.id)
            if edge_key in existing_edges or reverse_key in existing_edges:
                continue
            # Only suggest if score is meaningful
            if score < 0.15:
                continue

            # Fetch the suggested artist from Neo4j
            artist = get_artist(other_mbid)
            if not artist:
                continue

            # Add as a new node
            suggested_node = ArtistNode(
                id=other_mbid,
                name=artist.name,
                mbid=artist.mbid,
                spotify_id=artist.spotify_id,
                lastfm_listeners=artist.lastfm_listeners,
                spotify_popularity=artist.spotify_popularity,
                underground_score=artist.underground_score,
                genres=artist.genres,
                tags=artist.tags,
                formation_year=artist.formation_year,
                country=artist.country,
                image_url=artist.image_url,
                depth_level=(node.depth_level or 0) + 1,
            )
            lineage.nodes.append(suggested_node)
            existing_mbids.add(other_mbid)
            added_nodes += 1

            # Add the suggested edge
            lineage.edges.append(Edge(
                source=node.id,
                target=other_mbid,
                strength=round(min(score, 1.0), 3),
                source_type="matrix_similarity",
                confidence=round(min(score, 1.0), 3),
            ))
            existing_edges.add(edge_key)
            added_edges += 1
            count += 1

    if added_nodes > 0:
        lineage.metadata["matrix_suggestions"] = added_nodes
        if "matrix" not in lineage.metadata.get("data_sources_used", []):
            lineage.metadata["data_sources_used"].append("matrix")
        logger.info(f"Added {added_nodes} matrix-suggested nodes, {added_edges} edges")


def _enrich_with_embedding_suggestions(
    lineage: LineageResult,
    nodes_map: dict[str, ArtistNode],
    existing_edges: set[tuple],
    suggestions_per_node: int = 2,
) -> None:
    """
    For each node in the lineage, find top embedding-similar artists that are
    NOT already in the result. Adds them as 'embedding_similarity' edges
    (dotted teal lines in the frontend).
    """
    from ml.embeddings.search_engine import get_vector_engine

    engine = get_vector_engine()
    if engine is None or not lineage.nodes:
        return

    existing_mbids = set(nodes_map.keys())
    # Also include any nodes added by matrix suggestions
    for node in lineage.nodes:
        existing_mbids.add(node.id)

    added_nodes = 0
    added_edges = 0
    max_suggestions = 6

    for node in list(lineage.nodes):
        if added_nodes >= max_suggestions:
            break
        if not engine.has_artist(node.id):
            continue

        similar = engine.search_similar(node.id, top_n=suggestions_per_node + 5)

        count = 0
        for other_mbid, score in similar:
            if count >= suggestions_per_node or added_nodes >= max_suggestions:
                break
            if other_mbid in existing_mbids:
                continue
            edge_key = (node.id, other_mbid)
            reverse_key = (other_mbid, node.id)
            if edge_key in existing_edges or reverse_key in existing_edges:
                continue
            if score < 0.3:
                continue

            artist = get_artist(other_mbid)
            if not artist:
                continue

            suggested_node = ArtistNode(
                id=other_mbid,
                name=artist.name,
                mbid=artist.mbid,
                spotify_id=artist.spotify_id,
                lastfm_listeners=artist.lastfm_listeners,
                spotify_popularity=artist.spotify_popularity,
                underground_score=artist.underground_score,
                genres=artist.genres,
                tags=artist.tags,
                formation_year=artist.formation_year,
                country=artist.country,
                image_url=artist.image_url,
                depth_level=(node.depth_level or 0) + 1,
            )
            lineage.nodes.append(suggested_node)
            existing_mbids.add(other_mbid)
            added_nodes += 1

            lineage.edges.append(Edge(
                source=node.id,
                target=other_mbid,
                strength=round(min(score, 1.0), 3),
                source_type="embedding_similarity",
                confidence=round(min(score, 1.0), 3),
            ))
            existing_edges.add(edge_key)
            added_edges += 1
            count += 1

    if added_nodes > 0:
        lineage.metadata["embedding_suggestions"] = added_nodes
        if "embedding" not in lineage.metadata.get("data_sources_used", []):
            lineage.metadata["data_sources_used"].append("embedding")
        logger.info(f"Added {added_nodes} embedding-suggested nodes, {added_edges} edges")


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

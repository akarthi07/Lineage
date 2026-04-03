"""
Neo4j-to-NetworkX graph exporter for Node2Vec training.

Converts the Neo4j artist/influence graph into a NetworkX DiGraph with
node attributes (name, underground_score, tags) and edge weights (strength).
"""
from __future__ import annotations

import logging

import networkx as nx

from services.graph_manager import get_driver

logger = logging.getLogger(__name__)


def export_to_networkx() -> nx.DiGraph:
    """
    Query Neo4j for all Artist nodes and INFLUENCED_BY edges.
    Returns a NetworkX DiGraph with MBID as node IDs.
    """
    driver = get_driver()
    G = nx.DiGraph()

    with driver.session() as session:
        # Fetch all artists
        artists_result = session.run(
            "MATCH (a:Artist) WHERE a.mbid IS NOT NULL AND a.mbid <> '' RETURN a"
        )
        for record in artists_result:
            node = record["a"]
            mbid = node.get("mbid", "")
            if not mbid:
                continue
            G.add_node(
                mbid,
                name=node.get("name", ""),
                underground_score=node.get("underground_score", 0.5),
                tags=node.get("tags") or [],
                genres=node.get("genres") or [],
                formation_year=node.get("formation_year"),
                country=node.get("country") or "",
                lastfm_listeners=node.get("lastfm_listeners"),
            )

        # Fetch all INFLUENCED_BY edges
        edges_result = session.run(
            """
            MATCH (a:Artist)-[r:INFLUENCED_BY]->(b:Artist)
            WHERE a.mbid IS NOT NULL AND a.mbid <> ''
              AND b.mbid IS NOT NULL AND b.mbid <> ''
            RETURN a.mbid AS source, b.mbid AS target,
                   r.strength AS strength, r.confidence AS confidence
            """
        )
        for record in edges_result:
            source = record["source"]
            target = record["target"]
            strength = record["strength"] or 0.5
            if source in G and target in G:
                G.add_edge(source, target, weight=strength)

    logger.info(f"Exported {G.number_of_nodes()} nodes, {G.number_of_edges()} edges to NetworkX graph.")
    return G

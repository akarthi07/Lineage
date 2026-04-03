"""
Production credit network manager — creates and queries Recording, Producer
nodes and their relationships in Neo4j.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.graph_manager import get_driver

logger = logging.getLogger(__name__)


def ensure_production_indexes() -> None:
    """Create indexes for Recording and Producer nodes (idempotent)."""
    driver = get_driver()
    with driver.session() as session:
        session.run("CREATE INDEX recording_mbid IF NOT EXISTS FOR (r:Recording) ON (r.mbid)")
        session.run("CREATE INDEX producer_mbid IF NOT EXISTS FOR (p:Producer) ON (p.mbid)")
        session.run("CREATE INDEX producer_name IF NOT EXISTS FOR (p:Producer) ON (p.name)")
    logger.info("Production indexes OK")


def upsert_recording(
    mbid: str,
    title: str,
    artist_mbid: str,
    year: Optional[int] = None,
) -> None:
    """Create or update a Recording node and link it to its Artist."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (r:Recording {mbid: $mbid})
            SET r.title = $title,
                r.artist_mbid = $artist_mbid,
                r.year = $year
            WITH r
            MATCH (a:Artist {mbid: $artist_mbid})
            MERGE (r)-[:PERFORMED_BY]->(a)
            """,
            mbid=mbid,
            title=title,
            artist_mbid=artist_mbid,
            year=year,
        )


def upsert_producer(
    mbid: str,
    name: str,
) -> None:
    """Create or update a Producer node."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (p:Producer {mbid: $mbid})
            SET p.name = $name
            """,
            mbid=mbid,
            name=name,
        )


def link_recording_producer(
    recording_mbid: str,
    producer_mbid: str,
    role: str = "producer",
) -> None:
    """Create a PRODUCED_BY relationship between a Recording and Producer."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (r:Recording {mbid: $rec_mbid})
            MATCH (p:Producer {mbid: $prod_mbid})
            MERGE (r)-[rel:PRODUCED_BY]->(p)
            SET rel.role = $role
            """,
            rec_mbid=recording_mbid,
            prod_mbid=producer_mbid,
            role=role,
        )


def link_artist_producer(
    artist_mbid: str,
    producer_mbid: str,
    role: str = "producer",
) -> None:
    """Create a WORKED_WITH relationship between an Artist and Producer."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (a:Artist {mbid: $artist_mbid})
            MATCH (p:Producer {mbid: $prod_mbid})
            MERGE (a)-[rel:WORKED_WITH]->(p)
            SET rel.role = $role
            """,
            artist_mbid=artist_mbid,
            prod_mbid=producer_mbid,
            role=role,
        )


def link_recording_samples(
    sampling_mbid: str,
    sampled_mbid: str,
) -> None:
    """Create a SAMPLES relationship between two Recordings."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (a:Recording {mbid: $sampling_mbid})
            MATCH (b:Recording {mbid: $sampled_mbid})
            MERGE (a)-[:SAMPLES]->(b)
            """,
            sampling_mbid=sampling_mbid,
            sampled_mbid=sampled_mbid,
        )


def get_shared_producers(artist_mbid_a: str, artist_mbid_b: str) -> list[dict]:
    """
    Find producers who worked with both artists.
    Returns list of {mbid, name, count_a, count_b}.
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Artist {mbid: $mbid_a})-[:WORKED_WITH]->(p:Producer)<-[:WORKED_WITH]-(b:Artist {mbid: $mbid_b})
            RETURN p.mbid AS mbid, p.name AS name
            """,
            mbid_a=artist_mbid_a,
            mbid_b=artist_mbid_b,
        )
        return [{"mbid": r["mbid"], "name": r["name"]} for r in result]


def get_production_stats() -> dict:
    """Return counts of production-related nodes and edges."""
    driver = get_driver()
    with driver.session() as session:
        recordings = session.run("MATCH (r:Recording) RETURN count(r) AS cnt").single()["cnt"]
        producers = session.run("MATCH (p:Producer) RETURN count(p) AS cnt").single()["cnt"]
        produced_by = session.run("MATCH ()-[r:PRODUCED_BY]->() RETURN count(r) AS cnt").single()["cnt"]
        worked_with = session.run("MATCH ()-[r:WORKED_WITH]->() RETURN count(r) AS cnt").single()["cnt"]
        samples = session.run("MATCH ()-[r:SAMPLES]->() RETURN count(r) AS cnt").single()["cnt"]
    return {
        "recordings": recordings,
        "producers": producers,
        "produced_by_edges": produced_by,
        "worked_with_edges": worked_with,
        "samples_edges": samples,
    }

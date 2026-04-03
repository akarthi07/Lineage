"""
Lineage tracer for proto-genre clusters.

For each cluster, walks backward through the influence graph to find
common ancestors — the established artists/genres that most cluster
members trace back to.
"""
from __future__ import annotations

import logging
from collections import Counter

from ml.genesis.cluster_detector import ProtoGenre
from services.graph_manager import get_driver

logger = logging.getLogger(__name__)

# How many hops back to trace influences
MAX_DEPTH = 3
# Minimum fraction of cluster members that must share an ancestor
MIN_ANCESTOR_FRACTION = 0.25


def trace_cluster_lineage(pg: ProtoGenre) -> list[dict]:
    """
    For each artist in the cluster, traverse INFLUENCED_BY edges backward
    up to MAX_DEPTH hops. Count how often each ancestor appears across
    cluster members. Return the shared ancestors sorted by frequency.

    Returns a list of dicts:
        [{"mbid": ..., "name": ..., "shared_by": 5, "fraction": 0.6,
          "underground_score": 0.2, "tags": [...]}]
    """
    driver = get_driver()
    cluster_mbids = {a.mbid for a in pg.artists}
    ancestor_counter: Counter = Counter()
    ancestor_meta: dict[str, dict] = {}

    with driver.session() as session:
        for artist in pg.artists:
            result = session.run(
                f"""
                MATCH (start:Artist {{mbid: $mbid}})-[:INFLUENCED_BY*1..{MAX_DEPTH}]->(ancestor:Artist)
                WHERE ancestor.mbid IS NOT NULL AND ancestor.mbid <> ''
                RETURN DISTINCT ancestor.mbid AS mbid, ancestor.name AS name,
                       ancestor.underground_score AS us,
                       ancestor.tags AS tags, ancestor.genres AS genres,
                       ancestor.country AS country
                """,
                mbid=artist.mbid,
            )
            for rec in result:
                a_mbid = rec["mbid"]
                # Skip self-references and cluster members (we want external ancestors)
                if a_mbid in cluster_mbids:
                    continue
                ancestor_counter[a_mbid] += 1
                if a_mbid not in ancestor_meta:
                    ancestor_meta[a_mbid] = {
                        "mbid": a_mbid,
                        "name": rec["name"] or "",
                        "underground_score": rec["us"] or 0.0,
                        "tags": rec["tags"] or [],
                        "genres": rec["genres"] or [],
                        "country": rec["country"] or "",
                    }

    # Filter to ancestors shared by a meaningful fraction of the cluster
    min_count = max(2, int(len(pg.artists) * MIN_ANCESTOR_FRACTION))
    roots = []
    for mbid, count in ancestor_counter.most_common(15):
        if count < min_count:
            continue
        m = ancestor_meta[mbid]
        roots.append({
            "mbid": m["mbid"],
            "name": m["name"],
            "shared_by": count,
            "fraction": round(count / len(pg.artists), 2),
            "underground_score": round(m["underground_score"], 3),
            "tags": m["tags"][:5],
            "genres": m["genres"][:3],
            "country": m["country"],
        })

    logger.info(
        f"Cluster {pg.cluster_id}: found {len(roots)} shared lineage roots "
        f"(from {len(ancestor_counter)} total ancestors)"
    )
    return roots


def trace_all_clusters(clusters: list[ProtoGenre]) -> list[ProtoGenre]:
    """
    Enrich each ProtoGenre with lineage roots.
    Mutates .lineage_roots in place.
    """
    for pg in clusters:
        pg.lineage_roots = trace_cluster_lineage(pg)
    return clusters

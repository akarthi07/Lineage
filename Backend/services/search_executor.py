"""
Parallel search executor — runs multiple search engines concurrently
and collects results for fusion.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from services.query_router import SearchPlan

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5.0


@dataclass
class SearchResults:
    """Collects raw results from all engines before fusion."""

    # Graph: list of (mbid, name, strength)
    graph_results: list[tuple[str, str, float]] = field(default_factory=list)
    # Matrix: list of (mbid, score)
    matrix_results: list[tuple[str, float]] = field(default_factory=list)
    # Vector: list of (mbid, score)
    vector_results: list[tuple[str, float]] = field(default_factory=list)
    # Audio: list of (song_meta, score) — aggregated to artist level
    audio_results: list[tuple[str, float]] = field(default_factory=list)
    # Lyrics: list of (song_meta, score) — aggregated to artist level
    lyric_results: list[tuple[str, float]] = field(default_factory=list)
    # Production: list of (mbid, shared_producer_count)
    production_results: list[tuple[str, float]] = field(default_factory=list)
    # Metadata about what ran
    engines_used: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def _run_graph_search(plan: SearchPlan) -> list[tuple[str, str, float]]:
    """Query Neo4j graph for connected artists."""
    from services import graph_manager as gm

    results = []
    for mbid in plan.artist_mbids:
        if not gm.artist_exists(mbid):
            continue
        lineage = gm.get_lineage(
            mbid=mbid,
            direction=plan.direction,
            depth=plan.depth,
            underground_level=plan.underground_level,
        )
        for node in lineage.nodes:
            if node.id != mbid:
                # Find edge strength
                strength = 0.5
                for edge in lineage.edges:
                    if (edge.source == mbid and edge.target == node.id) or \
                       (edge.target == mbid and edge.source == node.id):
                        strength = max(strength, edge.strength)
                        break
                results.append((node.id, node.name, strength))
    return results


def _run_matrix_search(plan: SearchPlan) -> list[tuple[str, float]]:
    """Query the similarity matrix for similar artists."""
    from ml.similarity_engine import get_engine

    engine = get_engine()
    if engine is None:
        return []

    results = []
    seen = set()
    for mbid in plan.artist_mbids:
        similar = engine.get_most_similar(mbid, top_n=plan.top_n)
        for other_mbid, score in similar:
            if other_mbid not in seen:
                seen.add(other_mbid)
                results.append((other_mbid, score))
    return results


def _run_vector_search(plan: SearchPlan) -> list[tuple[str, float]]:
    """Query FAISS embedding index."""
    from ml.embeddings.search_engine import get_vector_engine

    engine = get_vector_engine()
    if engine is None:
        return []

    # Discovery: use vector arithmetic
    if plan.query_type == "discovery" and plan.positive_mbids:
        return engine.vector_arithmetic(
            positive_mbids=plan.positive_mbids,
            negative_mbids=plan.negative_mbids,
            top_n=plan.top_n,
        )

    # Standard: nearest neighbors per artist
    results = []
    seen = set()
    for mbid in plan.artist_mbids:
        similar = engine.search_similar(mbid, top_n=plan.top_n)
        for other_mbid, score in similar:
            if other_mbid not in seen:
                seen.add(other_mbid)
                results.append((other_mbid, score))
    return results


def _run_audio_search(plan: SearchPlan) -> list[tuple[str, float]]:
    """Query audio FAISS index, aggregate song-level to artist-level."""
    from ml.audio.audio_index import get_audio_engine

    engine = get_audio_engine()
    if engine is None:
        return []

    # For each artist, search for sonically similar songs
    artist_scores: dict[str, list[float]] = {}
    for mbid in plan.artist_mbids:
        # Find songs by this artist in the index
        for i, meta in enumerate(engine.metadata):
            if meta.get("artist_mbid") == mbid:
                vec = engine.index.reconstruct(i)
                similar = engine.search_similar_songs(vec, top_n=30)
                for song_meta, score in similar:
                    other_mbid = song_meta.get("artist_mbid", "")
                    if other_mbid and other_mbid != mbid:
                        if other_mbid not in artist_scores:
                            artist_scores[other_mbid] = []
                        artist_scores[other_mbid].append(score)
                break  # one song per artist is enough for routing

    # Average scores per artist
    return [(mbid, max(scores)) for mbid, scores in artist_scores.items()]


def _run_lyric_search(plan: SearchPlan) -> list[tuple[str, float]]:
    """Query lyric FAISS index, aggregate to artist-level."""
    from ml.lyrics.lyric_index import get_lyric_engine

    engine = get_lyric_engine()
    if engine is None:
        return []

    # If we have a text query (discovery mode), search by text
    if plan.text_query:
        results = engine.search_similar_lyrics(plan.text_query, top_n=30)
        artist_scores: dict[str, list[float]] = {}
        for meta, score in results:
            mbid = meta.get("artist_mbid", "")
            if mbid:
                if mbid not in artist_scores:
                    artist_scores[mbid] = []
                artist_scores[mbid].append(score)
        return [(mbid, max(scores)) for mbid, scores in artist_scores.items()]

    # Otherwise find lyrically similar songs for each seed artist
    artist_scores = {}
    for mbid in plan.artist_mbids:
        for i, meta in enumerate(engine.metadata):
            if meta.get("artist_mbid") == mbid:
                vec = engine.index.reconstruct(i)
                similar = engine._search_by_vector(vec, top_n=30)
                for song_meta, score in similar:
                    other_mbid = song_meta.get("artist_mbid", "")
                    if other_mbid and other_mbid != mbid:
                        if other_mbid not in artist_scores:
                            artist_scores[other_mbid] = []
                        artist_scores[other_mbid].append(score)
                break
    return [(mbid, max(scores)) for mbid, scores in artist_scores.items()]


def _run_production_search(plan: SearchPlan) -> list[tuple[str, float]]:
    """Find artists who share producers with seed artists."""
    from services.production_manager import get_shared_producers
    from services import graph_manager as gm

    results = []
    seen = set()

    for seed_mbid in plan.artist_mbids:
        # Get all artists in the graph and check shared producers
        driver = gm.get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (seed:Artist {mbid: $mbid})-[:WORKED_WITH]->(p:Producer)<-[:WORKED_WITH]-(other:Artist)
                WHERE other.mbid <> $mbid
                RETURN other.mbid AS mbid, other.name AS name, count(p) AS shared_count
                ORDER BY shared_count DESC
                LIMIT 30
                """,
                mbid=seed_mbid,
            )
            for record in result:
                other_mbid = record["mbid"]
                if other_mbid and other_mbid not in seen:
                    seen.add(other_mbid)
                    # Normalize: 1 shared producer = 0.3, 2 = 0.6, 3+ = 1.0
                    score = min(1.0, record["shared_count"] * 0.3)
                    results.append((other_mbid, score))

        # Also check sample connections
        with driver.session() as session:
            result = session.run(
                """
                MATCH (r1:Recording)-[:PERFORMED_BY]->(seed:Artist {mbid: $mbid})
                MATCH (r1)-[:SAMPLES]->(r2:Recording)-[:PERFORMED_BY]->(other:Artist)
                WHERE other.mbid <> $mbid
                RETURN other.mbid AS mbid, count(*) AS sample_count
                ORDER BY sample_count DESC
                LIMIT 20
                """,
                mbid=seed_mbid,
            )
            for record in result:
                other_mbid = record["mbid"]
                if other_mbid and other_mbid not in seen:
                    seen.add(other_mbid)
                    results.append((other_mbid, min(1.0, record["sample_count"] * 0.5)))

    return results


# Engine function mapping
_ENGINE_MAP = {
    "graph": _run_graph_search,
    "matrix": _run_matrix_search,
    "vector": _run_vector_search,
    "audio": _run_audio_search,
    "lyrics": _run_lyric_search,
    "production": _run_production_search,
}


def execute_search(plan: SearchPlan) -> SearchResults:
    """
    Run all enabled search engines in parallel with a timeout.
    Returns collected results for fusion.
    """
    results = SearchResults()

    if not plan.artist_mbids and plan.query_type != "discovery":
        return results

    # Determine which engines to run
    engines_to_run = []
    if plan.use_graph:
        engines_to_run.append("graph")
    if plan.use_matrix:
        engines_to_run.append("matrix")
    if plan.use_vector:
        engines_to_run.append("vector")
    if plan.use_audio:
        engines_to_run.append("audio")
    if plan.use_lyrics:
        engines_to_run.append("lyrics")
    if plan.use_production:
        engines_to_run.append("production")

    if not engines_to_run:
        return results

    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=len(engines_to_run)) as executor:
        future_to_engine = {}
        for engine_name in engines_to_run:
            fn = _ENGINE_MAP[engine_name]
            future = executor.submit(fn, plan)
            future_to_engine[future] = engine_name

        for future in as_completed(future_to_engine, timeout=TIMEOUT_SECONDS):
            engine_name = future_to_engine[future]
            engine_t0 = time.perf_counter()
            try:
                data = future.result(timeout=TIMEOUT_SECONDS)
                elapsed = time.perf_counter() - engine_t0
                results.timings[engine_name] = round(elapsed * 1000, 1)
                results.engines_used.append(engine_name)

                if engine_name == "graph":
                    results.graph_results = data
                elif engine_name == "matrix":
                    results.matrix_results = data
                elif engine_name == "vector":
                    results.vector_results = data
                elif engine_name == "audio":
                    results.audio_results = data
                elif engine_name == "lyrics":
                    results.lyric_results = data
                elif engine_name == "production":
                    results.production_results = data

                logger.info(f"  {engine_name}: {len(data)} results in {results.timings[engine_name]}ms")

            except Exception as exc:
                results.errors[engine_name] = str(exc)
                logger.warning(f"  {engine_name} failed: {exc}")

    total_elapsed = (time.perf_counter() - t0) * 1000
    logger.info(
        f"Search execution complete: {len(results.engines_used)}/{len(engines_to_run)} "
        f"engines in {total_elapsed:.0f}ms"
    )
    return results

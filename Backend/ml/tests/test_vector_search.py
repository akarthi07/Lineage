"""
Tests for the FAISS vector search engine.

Run from Backend/:
    python -m ml.tests.test_vector_search
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_vector_search")


def main() -> None:
    from ml.embeddings.search_engine import VectorSearchEngine
    from ml.data_exporter import export_graph_data

    logger.info("Loading VectorSearchEngine …")
    engine = VectorSearchEngine()

    logger.info("Loading graph export for name lookups …")
    graph_export = export_graph_data()
    mbid_to_name = {a.mbid: a.name for a in graph_export.artists}
    mbid_to_ug = {a.mbid: a.underground_score for a in graph_export.artists}

    def name(mbid: str) -> str:
        return mbid_to_name.get(mbid, mbid[:12])

    # --- Test 1: search_similar for several artists ---
    logger.info("=" * 60)
    logger.info("TEST 1 — search_similar (top 10 for sample artists)")
    logger.info("=" * 60)
    sample_mbids = list(engine.mbid_to_idx.keys())[:5]
    for mbid in sample_mbids:
        results = engine.search_similar(mbid, top_n=10)
        logger.info(f"\n  {name(mbid)}:")
        for other, score in results:
            ug = mbid_to_ug.get(other, 0)
            logger.info(f"    {name(other):30s}  sim={score:.3f}  ug={ug:.2f}")

    # --- Test 2: search_similar filtered by underground ---
    logger.info("=" * 60)
    logger.info("TEST 2 — search_similar filtered to underground > 0.7")
    logger.info("=" * 60)
    for mbid in sample_mbids[:2]:
        results = engine.search_similar(mbid, top_n=20)
        underground = [(m, s) for m, s in results if mbid_to_ug.get(m, 0) > 0.7][:10]
        logger.info(f"\n  {name(mbid)} (underground only):")
        for other, score in underground:
            logger.info(f"    {name(other):30s}  sim={score:.3f}  ug={mbid_to_ug.get(other, 0):.2f}")

    # --- Test 3: midpoint ---
    logger.info("=" * 60)
    logger.info("TEST 3 — midpoint between first two sample artists")
    logger.info("=" * 60)
    if len(sample_mbids) >= 2:
        a, b = sample_mbids[0], sample_mbids[1]
        mid = engine.compute_midpoint(a, b)
        if mid is not None:
            results = engine.search_by_vector(mid, top_n=10, exclude_mbids={a, b})
            logger.info(f"\n  Midpoint of {name(a)} and {name(b)}:")
            for other, score in results:
                logger.info(f"    {name(other):30s}  sim={score:.3f}")

    # --- Test 4: vector arithmetic ---
    logger.info("=" * 60)
    logger.info("TEST 4 — vector arithmetic (positive only)")
    logger.info("=" * 60)
    if len(sample_mbids) >= 2:
        results = engine.vector_arithmetic(
            positive_mbids=[sample_mbids[0], sample_mbids[1]],
            top_n=10,
        )
        logger.info(f"\n  {name(sample_mbids[0])} + {name(sample_mbids[1])}:")
        for other, score in results:
            logger.info(f"    {name(other):30s}  sim={score:.3f}")

    # --- Test 5: pairwise similarity ---
    logger.info("=" * 60)
    logger.info("TEST 5 — pairwise similarity")
    logger.info("=" * 60)
    for i in range(min(len(sample_mbids), 3)):
        for j in range(i + 1, min(len(sample_mbids), 5)):
            a, b = sample_mbids[i], sample_mbids[j]
            sim = engine.get_similarity(a, b)
            logger.info(f"  {name(a):25s} <-> {name(b):25s}  cosine={sim:.3f}")

    logger.info("\nAll vector search tests complete.")


if __name__ == "__main__":
    main()

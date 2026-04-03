#!/usr/bin/env python
"""
Seed production credits for all artists in Neo4j.

Usage (from Backend/):
    python scripts/seed_production.py                  # all artists
    python scripts/seed_production.py --limit 50       # first 50 artists
    python scripts/seed_production.py --recordings 5   # 5 recordings per artist

NOTE: MusicBrainz rate limit is 1 req/sec. For 1000 artists x 10 recordings,
this takes ~3-4 hours (1 req for recordings + 10 reqs for credits per artist).
"""
from __future__ import annotations

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_production")


def parse_args():
    parser = argparse.ArgumentParser(description="Seed production credits from MusicBrainz")
    parser.add_argument("--limit", type=int, default=0, help="Max artists (0 = all)")
    parser.add_argument("--recordings", type=int, default=10, help="Recordings per artist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()

    # Step 1: Ensure indexes
    logger.info("Step 1/3 — Creating production indexes …")
    from services.production_manager import ensure_production_indexes, get_production_stats
    ensure_production_indexes()

    # Step 2: Get artists
    logger.info("Step 2/3 — Loading artists from Neo4j …")
    from ml.data_exporter import export_graph_data
    graph = export_graph_data()

    artists = [a for a in graph.artists if a.mbid]
    if args.limit > 0:
        artists = artists[:args.limit]

    logger.info(f"  Processing {len(artists)} artists, {args.recordings} recordings each")

    # Step 3: Seed credits
    logger.info("Step 3/3 — Seeding production credits …")
    from services.production_seeder import seed_production_credits

    total_producers = 0
    total_samples = 0
    total_recordings = 0
    artists_with_credits = 0

    for i, artist in enumerate(artists):
        logger.info(f"  [{i+1}/{len(artists)}] {artist.name}")
        stats = seed_production_credits(
            artist_mbid=artist.mbid,
            artist_name=artist.name,
            max_recordings=args.recordings,
        )
        total_recordings += stats["recordings_checked"]
        total_producers += stats["producers_found"]
        total_samples += stats["samples_found"]
        if stats["producers_found"] > 0 or stats["samples_found"] > 0:
            artists_with_credits += 1

    elapsed = time.perf_counter() - t0

    # Print final stats
    db_stats = get_production_stats()
    logger.info(
        f"\nDone! Production seeding complete in {elapsed:.1f}s\n"
        f"  Artists processed: {len(artists)}\n"
        f"  Artists with credits: {artists_with_credits}\n"
        f"  Recordings checked: {total_recordings}\n"
        f"  Producers found: {total_producers}\n"
        f"  Samples found: {total_samples}\n"
        f"\n  Neo4j totals:\n"
        f"    Recordings: {db_stats['recordings']}\n"
        f"    Producers: {db_stats['producers']}\n"
        f"    PRODUCED_BY edges: {db_stats['produced_by_edges']}\n"
        f"    WORKED_WITH edges: {db_stats['worked_with_edges']}\n"
        f"    SAMPLES edges: {db_stats['samples_edges']}"
    )


if __name__ == "__main__":
    main()

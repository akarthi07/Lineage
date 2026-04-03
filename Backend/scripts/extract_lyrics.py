#!/usr/bin/env python
"""
Extract lyrics for artists in Neo4j, embed them, and build the lyrics FAISS index.

Usage (from Backend/):
    python scripts/extract_lyrics.py                   # all artists
    python scripts/extract_lyrics.py --limit 50        # first 50 artists
    python scripts/extract_lyrics.py --tracks 3        # 3 tracks per artist

Requires GENIUS_API_TOKEN in .env
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
logger = logging.getLogger("extract_lyrics")


def parse_args():
    parser = argparse.ArgumentParser(description="Extract lyrics and build FAISS index")
    parser.add_argument("--limit", type=int, default=0, help="Max artists to process (0 = all)")
    parser.add_argument("--tracks", type=int, default=5, help="Top tracks per artist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()

    # Check for Genius token
    if not os.getenv("GENIUS_API_TOKEN"):
        logger.error("GENIUS_API_TOKEN not set in environment. Add it to .env")
        sys.exit(1)

    # Step 1: Get artists from Neo4j
    logger.info("Step 1/3 — Loading artists from Neo4j …")
    from ml.data_exporter import export_graph_data
    graph = export_graph_data()

    artists = graph.artists
    if args.limit > 0:
        artists = artists[:args.limit]

    logger.info(f"  Processing {len(artists)} artists, {args.tracks} tracks each")

    # Step 2: Extract and embed lyrics
    logger.info("Step 2/3 — Fetching lyrics and embedding …")
    from ml.lyrics.lyric_index import embed_lyrics_for_artist

    all_features = []
    success_count = 0
    for i, artist in enumerate(artists):
        logger.info(f"  [{i+1}/{len(artists)}] {artist.name}")
        features = embed_lyrics_for_artist(
            artist_name=artist.name,
            artist_mbid=artist.mbid or "",
            spotify_id=artist.spotify_id,
            top_n_tracks=args.tracks,
        )
        all_features.extend(features)
        if features:
            success_count += 1

    logger.info(f"  Embedded {len(all_features)} tracks from {success_count}/{len(artists)} artists")

    if not all_features:
        logger.error("No lyrics embedded. Check GENIUS_API_TOKEN and network.")
        sys.exit(1)

    # Step 3: Build and save FAISS index
    logger.info("Step 3/3 — Building lyrics FAISS index …")
    from ml.lyrics.lyric_index import build_lyrics_index, save_lyrics_index

    index, metadata = build_lyrics_index(all_features)
    save_lyrics_index(index, metadata)

    elapsed = time.perf_counter() - t0
    logger.info(
        f"\nDone! Lyrics pipeline complete in {elapsed:.1f}s\n"
        f"  Songs indexed: {index.ntotal}\n"
        f"  Artists with lyrics: {success_count}/{len(artists)}\n"
        f"  Ready for LyricSearchEngine."
    )


if __name__ == "__main__":
    main()

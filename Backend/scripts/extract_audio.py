#!/usr/bin/env python
"""
Extract audio features for artists in Neo4j and build the audio FAISS index.

Usage (from Backend/):
    python scripts/extract_audio.py                    # all artists
    python scripts/extract_audio.py --limit 50         # first 50 artists
    python scripts/extract_audio.py --tracks 3         # 3 tracks per artist
"""
from __future__ import annotations

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extract_audio")


def parse_args():
    parser = argparse.ArgumentParser(description="Extract audio features and build FAISS index")
    parser.add_argument("--limit", type=int, default=0, help="Max artists to process (0 = all)")
    parser.add_argument("--tracks", type=int, default=5, help="Top tracks per artist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()

    # Step 1: Get artists from Neo4j
    logger.info("Step 1/3 — Loading artists from Neo4j …")
    from ml.data_exporter import export_graph_data
    graph = export_graph_data()

    artists = graph.artists
    if args.limit > 0:
        artists = artists[:args.limit]

    logger.info(f"  Processing {len(artists)} artists, {args.tracks} tracks each")

    # Step 2: Extract features
    logger.info("Step 2/3 — Extracting audio features …")
    from ml.audio.batch_extract import extract_features_for_artist

    all_features = []
    success_count = 0
    for i, artist in enumerate(artists):
        logger.info(f"  [{i+1}/{len(artists)}] {artist.name}")
        features = extract_features_for_artist(
            artist_name=artist.name,
            artist_mbid=artist.mbid or "",
            spotify_id=artist.spotify_id,
            top_n_tracks=args.tracks,
        )
        all_features.extend(features)
        if features:
            success_count += 1

    logger.info(f"  Extracted {len(all_features)} tracks from {success_count}/{len(artists)} artists")

    if not all_features:
        logger.error("No audio features extracted. Check Spotify credentials and network.")
        sys.exit(1)

    # Step 3: Build and save FAISS index
    logger.info("Step 3/3 — Building audio FAISS index …")
    from ml.audio.audio_index import build_audio_index, save_audio_index

    index, metadata = build_audio_index(all_features)
    save_audio_index(index, metadata)

    elapsed = time.perf_counter() - t0
    logger.info(
        f"\nDone! Audio pipeline complete in {elapsed:.1f}s\n"
        f"  Songs indexed: {index.ntotal}\n"
        f"  Artists with audio: {success_count}/{len(artists)}\n"
        f"  Ready for AudioSearchEngine."
    )


if __name__ == "__main__":
    main()

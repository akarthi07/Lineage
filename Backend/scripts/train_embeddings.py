#!/usr/bin/env python
"""
Train Node2Vec embeddings on the artist influence graph.

Usage (from Backend/):
    python scripts/train_embeddings.py
    python scripts/train_embeddings.py --dimensions 64 --walk-length 30  # quick mode
"""
from __future__ import annotations

import argparse
import sys
import os
import time

# Ensure Backend/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_embeddings")


def parse_args():
    parser = argparse.ArgumentParser(description="Train Node2Vec embeddings")
    parser.add_argument("--dimensions", type=int, default=128, help="Embedding dimensions")
    parser.add_argument("--walk-length", type=int, default=40, help="Random walk length")
    parser.add_argument("--num-walks", type=int, default=15, help="Walks per node")
    parser.add_argument("--p", type=float, default=0.5, help="Return parameter")
    parser.add_argument("--q", type=float, default=0.5, help="In-out parameter")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--window", type=int, default=10, help="Word2Vec window")
    parser.add_argument("--epochs", type=int, default=5, help="Word2Vec epochs")
    parser.add_argument("--skip-validation", action="store_true", help="Skip validation step")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()

    hyperparams = {
        "dimensions": args.dimensions,
        "walk_length": args.walk_length,
        "num_walks": args.num_walks,
        "p": args.p,
        "q": args.q,
        "window": args.window,
        "epochs": args.epochs,
    }

    # --- Step 1: Export graph ---
    logger.info("Step 1/4 — Exporting graph from Neo4j to NetworkX …")
    from ml.graph_exporter import export_to_networkx
    G = export_to_networkx()

    if G.number_of_nodes() == 0:
        logger.error("No artists found in Neo4j. Seed the database first.")
        sys.exit(1)

    # --- Step 2: Train Node2Vec ---
    logger.info("Step 2/4 — Training Node2Vec embeddings …")
    from ml.embeddings.train_node2vec import train_embeddings, save_model
    model = train_embeddings(
        G,
        dimensions=args.dimensions,
        walk_length=args.walk_length,
        num_walks=args.num_walks,
        p=args.p,
        q=args.q,
        workers=args.workers,
        window=args.window,
        epochs=args.epochs,
    )

    # --- Step 3: Validate ---
    validation_scores = {}
    if not args.skip_validation:
        logger.info("Step 3/4 — Validating embeddings …")
        from ml.data_exporter import export_graph_data
        from ml.embeddings.validate_embeddings import validate_embeddings

        graph_export = export_graph_data()

        # Try to load similarity matrix for correlation check
        sim_matrix = None
        try:
            from ml.similarity_engine import load_matrix
            sim_matrix, _ = load_matrix()
            logger.info("  Loaded similarity matrix for correlation check")
        except FileNotFoundError:
            logger.info("  No similarity matrix found — skipping correlation check")

        validation_scores = validate_embeddings(model, graph_export, sim_matrix)
    else:
        logger.info("Step 3/4 — Validation skipped")

    # --- Step 4: Save ---
    logger.info("Step 4/4 — Saving model and metadata …")
    save_model(model, hyperparams=hyperparams, validation_scores=validation_scores)

    elapsed = time.perf_counter() - t0
    logger.info(
        f"Done! Embeddings trained: {len(model.wv)} vectors x {model.wv.vector_size} dims, "
        f"took {elapsed:.1f}s"
    )


if __name__ == "__main__":
    main()

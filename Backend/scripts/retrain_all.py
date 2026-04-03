#!/usr/bin/env python
"""
Full retraining pipeline: export graph → train Node2Vec → validate →
build FAISS index → save everything.

Usage (from Backend/):
    python scripts/retrain_all.py
    python scripts/retrain_all.py --skip-validation
    python scripts/retrain_all.py --dimensions 64 --walk-length 30  # quick mode
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
logger = logging.getLogger("retrain_all")


def parse_args():
    parser = argparse.ArgumentParser(description="Full retrain pipeline")
    parser.add_argument("--dimensions", type=int, default=128)
    parser.add_argument("--walk-length", type=int, default=40)
    parser.add_argument("--num-walks", type=int, default=15)
    parser.add_argument("--p", type=float, default=0.5)
    parser.add_argument("--q", type=float, default=0.5)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true", help="Skip matrix recomputation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()
    steps_total = 6 if not args.skip_matrix else 5

    hyperparams = {
        "dimensions": args.dimensions,
        "walk_length": args.walk_length,
        "num_walks": args.num_walks,
        "p": args.p,
        "q": args.q,
        "window": args.window,
        "epochs": args.epochs,
    }

    # --- Step 1: Recompute similarity matrix (optional) ---
    step = 1
    if not args.skip_matrix:
        logger.info(f"Step {step}/{steps_total} — Recomputing similarity matrix …")
        from ml.data_exporter import export_graph_data
        from ml.similarity_engine import build_unified_matrix, save_matrix

        graph_export = export_graph_data()
        if graph_export.n == 0:
            logger.error("No artists in Neo4j. Seed the database first.")
            sys.exit(1)

        matrix = build_unified_matrix(graph_export)
        save_matrix(matrix, graph_export.artist_index)
        logger.info(f"  Matrix saved: {graph_export.n}x{graph_export.n}")
        step += 1
    else:
        logger.info(f"Step {step}/{steps_total} — Skipping matrix recomputation")
        step += 1

    # --- Step 2: Export graph to NetworkX ---
    logger.info(f"Step {step}/{steps_total} — Exporting graph to NetworkX …")
    from ml.graph_exporter import export_to_networkx
    G = export_to_networkx()

    if G.number_of_nodes() == 0:
        logger.error("No artists in Neo4j. Seed the database first.")
        sys.exit(1)
    step += 1

    # --- Step 3: Train Node2Vec ---
    logger.info(f"Step {step}/{steps_total} — Training Node2Vec embeddings …")
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
    step += 1

    # --- Step 4: Validate ---
    validation_scores = {}
    if not args.skip_validation:
        logger.info(f"Step {step}/{steps_total} — Validating embeddings …")
        from ml.data_exporter import export_graph_data
        from ml.embeddings.validate_embeddings import validate_embeddings

        graph_export = export_graph_data()
        sim_matrix = None
        try:
            from ml.similarity_engine import load_matrix
            sim_matrix, _ = load_matrix()
        except FileNotFoundError:
            pass
        validation_scores = validate_embeddings(model, graph_export, sim_matrix)
    else:
        logger.info(f"Step {step}/{steps_total} — Validation skipped")
    step += 1

    # --- Step 5: Save model ---
    logger.info(f"Step {step}/{steps_total} — Saving model + metadata …")
    save_model(model, hyperparams=hyperparams, validation_scores=validation_scores)
    step += 1

    # --- Step 6: Build + save FAISS index ---
    logger.info(f"Step {step}/{steps_total} — Building FAISS index …")
    from ml.embeddings.vector_index import build_faiss_index, save_index
    index, mbid_list = build_faiss_index(model)
    save_index(index, mbid_list)

    elapsed = time.perf_counter() - t0
    logger.info(
        f"\nDone! Full pipeline complete in {elapsed:.1f}s\n"
        f"  Embeddings: {len(model.wv)} vectors x {model.wv.vector_size} dims\n"
        f"  FAISS index: {index.ntotal} vectors\n"
        f"  Ready for VectorSearchEngine to load."
    )


if __name__ == "__main__":
    main()

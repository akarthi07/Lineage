#!/usr/bin/env python
"""
Recompute the unified similarity matrix from the current Neo4j graph.

Usage (from Backend/):
    python scripts/recompute_matrix.py
"""
from __future__ import annotations

import sys
import os
import time

# Ensure Backend/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("recompute_matrix")


def main() -> None:
    from ml.data_exporter import export_graph_data
    from ml.similarity_engine import build_unified_matrix, save_matrix
    import numpy as np

    t0 = time.perf_counter()

    # --- Step 1: Export graph ---
    logger.info("Step 1/4 — Exporting graph from Neo4j …")
    graph_export = export_graph_data()

    if graph_export.n == 0:
        logger.error("No artists found in Neo4j. Seed the database first.")
        sys.exit(1)

    logger.info(f"  Exported {graph_export.n} artists, {len(graph_export.relationships)} relationships")

    # --- Step 2: Build unified matrix ---
    logger.info("Step 2/4 — Building unified similarity matrix …")
    matrix = build_unified_matrix(graph_export)

    # --- Step 3: Stats ---
    n = graph_export.n
    non_zero = np.count_nonzero(matrix)
    total = n * n
    sparsity = 1.0 - non_zero / total if total > 0 else 0.0

    # Off-diagonal stats
    if n > 1:
        mask = ~np.eye(n, dtype=bool)
        off_diag = matrix[mask]
        mean_val = np.mean(off_diag)
        max_val = np.max(off_diag)
    else:
        mean_val = max_val = 0.0

    logger.info("Step 3/4 — Matrix stats:")
    logger.info(f"  Shape:      {matrix.shape}")
    logger.info(f"  Sparsity:   {sparsity:.1%}")
    logger.info(f"  Mean (off-diag): {mean_val:.4f}")
    logger.info(f"  Max  (off-diag): {max_val:.4f}")
    logger.info(f"  Non-zero:   {non_zero}/{total}")

    # --- Step 4: Save ---
    logger.info("Step 4/4 — Saving to disk …")
    save_matrix(matrix, graph_export.artist_index)

    elapsed = time.perf_counter() - t0
    logger.info(
        f"Done! Matrix computed: {n}x{n}, sparsity: {sparsity:.1%}, "
        f"took {elapsed:.1f}s"
    )


if __name__ == "__main__":
    main()

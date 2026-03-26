"""
Unified similarity engine — combines all component matrices into a single
NxN similarity matrix and provides query methods for instant lookups.

Weights (tunable):
  adjacency (graph edges):     0.35
  tag co-occurrence (Jaccard):  0.25
  Last.fm similarity:          0.25
  temporal proximity:          0.10
  geographic proximity:        0.05
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from threading import Lock

import numpy as np

from ml.data_exporter import GraphExport, export_graph_data
from ml.matrices.adjacency import build_adjacency_matrix
from ml.matrices.tag_cooccurrence import build_tag_matrix
from ml.matrices.lastfm_similarity import build_lastfm_matrix
from ml.matrices.temporal import build_temporal_matrix
from ml.matrices.geographic import build_geographic_matrix

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default combination weights — sum to 1.0
# ---------------------------------------------------------------------------
WEIGHTS = {
    "adjacency": 0.35,
    "tag": 0.25,
    "lastfm": 0.25,
    "temporal": 0.10,
    "geographic": 0.05,
}

# Default save locations (relative to Backend/)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_MATRIX_PATH = DATA_DIR / "similarity_matrix.npy"
DEFAULT_INDEX_PATH = DATA_DIR / "artist_index.json"


# ---------------------------------------------------------------------------
# 9.2 — Normalization
# ---------------------------------------------------------------------------
def normalize_matrix(m: np.ndarray) -> np.ndarray:
    """
    Min-max normalize a matrix to [0, 1].

    If the matrix is constant (max == min), returns zeros.
    """
    mn = m.min()
    mx = m.max()
    if mx - mn < 1e-12:
        return np.zeros_like(m)
    return (m - mn) / (mx - mn)


# ---------------------------------------------------------------------------
# 9.1 — Matrix combiner
# ---------------------------------------------------------------------------
def build_unified_matrix(
    graph_export: GraphExport,
    weights: dict[str, float] | None = None,
) -> np.ndarray:
    """
    Build all 5 component matrices, normalize each to [0, 1], then combine
    with a weighted sum.  Returns the unified NxN similarity matrix.
    """
    w = weights or WEIGHTS

    t0 = time.perf_counter()
    n = graph_export.n
    logger.info(f"Building unified matrix for {n} artists …")

    # Build individual matrices
    logger.info("  → adjacency …")
    adj = build_adjacency_matrix(graph_export)
    logger.info("  → tag co-occurrence …")
    tag = build_tag_matrix(graph_export)
    logger.info("  → Last.fm similarity …")
    lfm = build_lastfm_matrix(graph_export)
    logger.info("  → temporal proximity …")
    tmp = build_temporal_matrix(graph_export)
    logger.info("  → geographic proximity …")
    geo = build_geographic_matrix(graph_export)

    # Normalize each to [0, 1]
    adj_n = normalize_matrix(adj)
    tag_n = normalize_matrix(tag)
    lfm_n = normalize_matrix(lfm)
    tmp_n = normalize_matrix(tmp)
    geo_n = normalize_matrix(geo)

    # Weighted combination
    unified = (
        w["adjacency"] * adj_n
        + w["tag"] * tag_n
        + w["lastfm"] * lfm_n
        + w["temporal"] * tmp_n
        + w["geographic"] * geo_n
    )

    elapsed = time.perf_counter() - t0
    non_zero = np.count_nonzero(unified)
    sparsity = 1.0 - non_zero / (n * n) if n > 0 else 0.0
    logger.info(
        f"Unified matrix ready: {n}x{n}, sparsity {sparsity:.1%}, "
        f"took {elapsed:.2f}s"
    )

    return unified


# ---------------------------------------------------------------------------
# 9.3 — Serialization
# ---------------------------------------------------------------------------
def save_matrix(
    matrix: np.ndarray,
    artist_index: dict[str, int],
    matrix_path: str | Path = DEFAULT_MATRIX_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
) -> None:
    """Save the unified matrix (.npy) and artist-to-index mapping (.json)."""
    matrix_path = Path(matrix_path)
    index_path = Path(index_path)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)

    np.save(str(matrix_path), matrix)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(artist_index, f, indent=2)

    logger.info(f"Matrix saved → {matrix_path}  ({matrix.nbytes / 1024:.1f} KB)")
    logger.info(f"Index  saved → {index_path}  ({len(artist_index)} artists)")


def load_matrix(
    matrix_path: str | Path = DEFAULT_MATRIX_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
) -> tuple[np.ndarray, dict[str, int]]:
    """Load a previously saved matrix and artist index from disk."""
    matrix_path = Path(matrix_path)
    index_path = Path(index_path)

    if not matrix_path.exists() or not index_path.exists():
        raise FileNotFoundError(
            f"Matrix files not found at {matrix_path} / {index_path}. "
            "Run recompute_matrix.py first."
        )

    matrix = np.load(str(matrix_path))
    with open(index_path, "r", encoding="utf-8") as f:
        artist_index = json.load(f)

    logger.info(
        f"Loaded matrix {matrix.shape} and index ({len(artist_index)} artists)"
    )
    return matrix, artist_index


# ---------------------------------------------------------------------------
# 9.4 — Query interface (singleton)
# ---------------------------------------------------------------------------
class SimilarityEngine:
    """
    In-memory query interface over the precomputed similarity matrix.

    Load once at server startup, query O(1) per pair.
    """

    def __init__(
        self,
        matrix_path: str | Path = DEFAULT_MATRIX_PATH,
        index_path: str | Path = DEFAULT_INDEX_PATH,
    ):
        self.matrix, self.artist_index = load_matrix(matrix_path, index_path)
        # Reverse mapping: index → mbid
        self.index_artist: dict[int, str] = {
            v: k for k, v in self.artist_index.items()
        }
        self.n = self.matrix.shape[0]
        logger.info(f"SimilarityEngine ready — {self.n} artists loaded")

    # -- single-pair lookup ---------------------------------------------------
    def get_similarity(self, mbid_a: str, mbid_b: str) -> float | None:
        """Return the similarity score between two artists, or None if unknown."""
        i = self.artist_index.get(mbid_a)
        j = self.artist_index.get(mbid_b)
        if i is None or j is None:
            return None
        return float(self.matrix[i][j])

    # -- top-N most similar ---------------------------------------------------
    def get_most_similar(
        self,
        mbid: str,
        top_n: int = 20,
        min_underground: float = 0.0,
        artist_scores: dict[str, float] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Return the *top_n* most similar artists to *mbid* sorted by score desc.

        Parameters
        ----------
        mbid : target artist MBID
        top_n : number of results
        min_underground : optional underground score filter (requires artist_scores)
        artist_scores : optional dict {mbid: underground_score} for filtering

        Returns list of (mbid, similarity_score).
        """
        i = self.artist_index.get(mbid)
        if i is None:
            return []

        row = self.matrix[i].copy()
        row[i] = -1.0  # exclude self

        # Sort by score descending
        ranked_indices = np.argsort(row)[::-1]

        results: list[tuple[str, float]] = []
        for idx in ranked_indices:
            if len(results) >= top_n:
                break
            score = float(row[idx])
            if score <= 0.0:
                break
            other_mbid = self.index_artist.get(int(idx))
            if other_mbid is None:
                continue

            # Underground filter
            if min_underground > 0.0 and artist_scores:
                ug = artist_scores.get(other_mbid, 0.0)
                if ug < min_underground:
                    continue

            results.append((other_mbid, score))

        return results

    # -- full similarity row --------------------------------------------------
    def get_similarity_row(self, mbid: str) -> dict[str, float]:
        """Return similarity scores against all other artists."""
        i = self.artist_index.get(mbid)
        if i is None:
            return {}
        return {
            self.index_artist[j]: float(self.matrix[i][j])
            for j in range(self.n)
            if j != i and self.matrix[i][j] > 0.0
        }

    # -- check membership ----------------------------------------------------
    def has_artist(self, mbid: str) -> bool:
        return mbid in self.artist_index


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------
_engine: SimilarityEngine | None = None
_lock = Lock()


def get_engine() -> SimilarityEngine | None:
    """Return the global SimilarityEngine, or None if not loaded."""
    return _engine


def load_engine(
    matrix_path: str | Path = DEFAULT_MATRIX_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
) -> SimilarityEngine | None:
    """
    Load (or reload) the global SimilarityEngine singleton.

    Returns None if matrix files don't exist yet (graceful degradation).
    """
    global _engine
    with _lock:
        try:
            _engine = SimilarityEngine(matrix_path, index_path)
            return _engine
        except FileNotFoundError:
            logger.warning(
                "Similarity matrix not found — matrix search disabled. "
                "Run scripts/recompute_matrix.py to generate it."
            )
            _engine = None
            return None

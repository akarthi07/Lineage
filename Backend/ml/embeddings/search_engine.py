"""
Vector search engine — wraps gensim model + FAISS index to provide
similarity search, midpoint queries, and vector arithmetic.

Loaded once at server startup as a singleton.
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

import faiss
import numpy as np
from gensim.models import Word2Vec

from ml.embeddings.train_node2vec import DEFAULT_MODEL_PATH
from ml.embeddings.vector_index import (
    DEFAULT_INDEX_PATH,
    DEFAULT_MBIDS_PATH,
    build_faiss_index,
    load_index,
    save_index,
)

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """
    In-memory vector search over artist embeddings.

    Supports:
      - Nearest-neighbor search by MBID
      - Raw vector search (for arithmetic results)
      - Midpoint computation between two artists
      - Vector arithmetic ("A + B - C")
      - Pairwise cosine similarity
    """

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        index_path: str | Path = DEFAULT_INDEX_PATH,
        mbids_path: str | Path = DEFAULT_MBIDS_PATH,
    ):
        self.model = Word2Vec.load(str(model_path))
        self.index, self.mbid_list = load_index(index_path, mbids_path)
        self.mbid_to_idx = {mbid: i for i, mbid in enumerate(self.mbid_list)}
        self.dimensions = self.model.wv.vector_size
        logger.info(
            f"VectorSearchEngine ready — {len(self.mbid_list)} artists, "
            f"{self.dimensions} dims"
        )

    def _get_normalized_vector(self, mbid: str) -> np.ndarray | None:
        """Get the L2-normalized vector for an artist."""
        if mbid not in self.model.wv:
            return None
        vec = self.model.wv[mbid].astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        return vec

    def get_vector(self, mbid: str) -> np.ndarray | None:
        """Return the raw (unnormalized) embedding vector for an artist."""
        if mbid not in self.model.wv:
            return None
        return self.model.wv[mbid].copy()

    def search_similar(
        self, mbid: str, top_n: int = 20
    ) -> list[tuple[str, float]]:
        """Find the N nearest artists to a given MBID by cosine similarity."""
        vec = self._get_normalized_vector(mbid)
        if vec is None:
            return []
        # Search top_n+1 to account for self-match
        scores, indices = self.index.search(vec, top_n + 1)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.mbid_list):
                continue
            other_mbid = self.mbid_list[idx]
            if other_mbid == mbid:
                continue
            results.append((other_mbid, float(score)))
            if len(results) >= top_n:
                break
        return results

    def search_by_vector(
        self, vector: np.ndarray, top_n: int = 20, exclude_mbids: set[str] | None = None
    ) -> list[tuple[str, float]]:
        """Search by a raw vector (for arithmetic/midpoint queries)."""
        vec = vector.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, top_n + (len(exclude_mbids) if exclude_mbids else 0))
        results = []
        exclude = exclude_mbids or set()
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.mbid_list):
                continue
            mbid = self.mbid_list[idx]
            if mbid in exclude:
                continue
            results.append((mbid, float(score)))
            if len(results) >= top_n:
                break
        return results

    def compute_midpoint(self, mbid_a: str, mbid_b: str) -> np.ndarray | None:
        """Return the vector halfway between two artists."""
        vec_a = self.get_vector(mbid_a)
        vec_b = self.get_vector(mbid_b)
        if vec_a is None or vec_b is None:
            return None
        return (vec_a + vec_b) / 2.0

    def vector_arithmetic(
        self,
        positive_mbids: list[str],
        negative_mbids: list[str] | None = None,
        top_n: int = 20,
    ) -> list[tuple[str, float]]:
        """
        "A + B - C" style queries.

        Computes mean(positive_vectors) - mean(negative_vectors) and
        searches for nearest results. Excludes input artists from results.
        """
        negative_mbids = negative_mbids or []

        pos_vecs = [self.get_vector(m) for m in positive_mbids]
        pos_vecs = [v for v in pos_vecs if v is not None]
        if not pos_vecs:
            return []

        result_vec = np.mean(pos_vecs, axis=0)

        if negative_mbids:
            neg_vecs = [self.get_vector(m) for m in negative_mbids]
            neg_vecs = [v for v in neg_vecs if v is not None]
            if neg_vecs:
                result_vec -= np.mean(neg_vecs, axis=0)

        exclude = set(positive_mbids) | set(negative_mbids)
        return self.search_by_vector(result_vec, top_n=top_n, exclude_mbids=exclude)

    def get_similarity(self, mbid_a: str, mbid_b: str) -> float | None:
        """Cosine similarity between two specific artists."""
        vec_a = self._get_normalized_vector(mbid_a)
        vec_b = self._get_normalized_vector(mbid_b)
        if vec_a is None or vec_b is None:
            return None
        return float(np.dot(vec_a[0], vec_b[0]))

    def has_artist(self, mbid: str) -> bool:
        return mbid in self.mbid_to_idx


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------
_engine: VectorSearchEngine | None = None
_lock = Lock()


def get_vector_engine() -> VectorSearchEngine | None:
    """Return the global VectorSearchEngine, or None if not loaded."""
    return _engine


def load_vector_engine(
    model_path: str | Path = DEFAULT_MODEL_PATH,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    mbids_path: str | Path = DEFAULT_MBIDS_PATH,
) -> VectorSearchEngine | None:
    """
    Load (or reload) the global VectorSearchEngine singleton.

    Returns None if embedding files don't exist yet (graceful degradation).
    """
    global _engine
    with _lock:
        try:
            _engine = VectorSearchEngine(model_path, index_path, mbids_path)
            return _engine
        except FileNotFoundError:
            logger.warning(
                "Embedding/FAISS files not found — vector search disabled. "
                "Run scripts/retrain_all.py to generate them."
            )
            _engine = None
            return None

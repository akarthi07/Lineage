"""
FAISS vector index builder and serialization.

Converts gensim Word2Vec embeddings into a FAISS IndexFlatIP for
millisecond cosine-similarity nearest-neighbor search.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np
from gensim.models import Word2Vec

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"
DEFAULT_INDEX_PATH = DATA_DIR / "faiss_index.bin"
DEFAULT_MBIDS_PATH = DATA_DIR / "faiss_mbids.json"


def build_faiss_index(model: Word2Vec) -> tuple[faiss.Index, list[str]]:
    """
    Build a FAISS inner-product index from a trained gensim model.

    Returns (faiss_index, mbid_list) where mbid_list[i] corresponds
    to the i-th vector in the index.
    """
    mbid_list = list(model.wv.key_to_index.keys())
    dimensions = model.wv.vector_size

    # Extract vectors into a contiguous float32 matrix
    vectors = np.array([model.wv[mbid] for mbid in mbid_list], dtype=np.float32)

    # L2-normalize so inner product == cosine similarity
    faiss.normalize_L2(vectors)

    # IndexFlatIP = exact inner-product search (fine for <100k vectors)
    index = faiss.IndexFlatIP(dimensions)
    index.add(vectors)

    logger.info(f"Built FAISS index: {index.ntotal} vectors, {dimensions} dimensions.")
    return index, mbid_list


def save_index(
    index: faiss.Index,
    mbid_list: list[str],
    index_path: str | Path = DEFAULT_INDEX_PATH,
    mbids_path: str | Path = DEFAULT_MBIDS_PATH,
) -> None:
    """Save the FAISS index and MBID mapping to disk."""
    index_path = Path(index_path)
    mbids_path = Path(mbids_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))
    with open(mbids_path, "w", encoding="utf-8") as f:
        json.dump(mbid_list, f)

    logger.info(f"FAISS index saved → {index_path} ({index.ntotal} vectors)")
    logger.info(f"MBID list saved  → {mbids_path}")


def load_index(
    index_path: str | Path = DEFAULT_INDEX_PATH,
    mbids_path: str | Path = DEFAULT_MBIDS_PATH,
) -> tuple[faiss.Index, list[str]]:
    """Load a previously saved FAISS index and MBID mapping."""
    index_path = Path(index_path)
    mbids_path = Path(mbids_path)

    if not index_path.exists() or not mbids_path.exists():
        raise FileNotFoundError(
            f"FAISS files not found at {index_path} / {mbids_path}. "
            "Run scripts/retrain_all.py first."
        )

    index = faiss.read_index(str(index_path))
    with open(mbids_path, "r", encoding="utf-8") as f:
        mbid_list = json.load(f)

    logger.info(f"Loaded FAISS index: {index.ntotal} vectors, {index.d} dims")
    return index, mbid_list

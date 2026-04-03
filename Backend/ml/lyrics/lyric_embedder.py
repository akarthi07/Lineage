"""
Lyric embedder — converts song lyrics into 384-dimensional vectors
using a lightweight sentence-transformers model.

Model: all-MiniLM-L6-v2 (~80MB, downloads on first use)
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

LYRIC_DIM = 384
_model = None


def _get_model():
    """Lazy-load the sentence transformer model (cached after first call)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2) …")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Model loaded.")
    return _model


def embed_lyrics(lyrics_text: str) -> Optional[np.ndarray]:
    """
    Embed lyrics text into a 384-dim vector.

    Truncates to first ~512 tokens (first verses are most representative).
    Returns None if lyrics are too short to be meaningful.
    """
    if not lyrics_text or len(lyrics_text.strip()) < 20:
        return None

    # Truncate to roughly 512 tokens (~2000 chars)
    text = lyrics_text[:2000]

    try:
        model = _get_model()
        vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)
    except Exception as exc:
        logger.error(f"Lyric embedding failed: {exc}")
        return None


def embed_query(query_text: str) -> Optional[np.ndarray]:
    """
    Embed a search query (e.g. "sad songs about loss") into the same
    384-dim space as lyrics. Enables semantic lyric search.
    """
    if not query_text or len(query_text.strip()) < 2:
        return None

    try:
        model = _get_model()
        vec = model.encode(query_text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)
    except Exception as exc:
        logger.error(f"Query embedding failed: {exc}")
        return None

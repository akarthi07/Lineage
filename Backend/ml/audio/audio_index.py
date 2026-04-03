"""
Audio FAISS index — stores and searches song-level audio feature vectors.

36-dimensional vectors (from feature_extractor.py) indexed for
millisecond nearest-neighbor search by sonic similarity.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Optional

import faiss
import numpy as np

from ml.audio.batch_extract import SongFeature
from ml.audio.feature_extractor import FEATURE_DIM, extract_features

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio"
DEFAULT_INDEX_PATH = DATA_DIR / "faiss_audio_index.bin"
DEFAULT_META_PATH = DATA_DIR / "audio_meta.json"


class AudioSearchEngine:
    """
    In-memory search over song audio features using FAISS.
    """

    def __init__(
        self,
        index_path: str | Path = DEFAULT_INDEX_PATH,
        meta_path: str | Path = DEFAULT_META_PATH,
    ):
        index_path = Path(index_path)
        meta_path = Path(meta_path)

        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Audio index not found at {index_path}. "
                "Run the audio extraction pipeline first."
            )

        self.index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)  # list of {track_name, artist_name, artist_mbid, album}

        logger.info(f"AudioSearchEngine ready — {self.index.ntotal} songs, {FEATURE_DIM} dims")

    def search_similar_songs(
        self, feature_vector: np.ndarray, top_n: int = 20
    ) -> list[tuple[dict, float]]:
        """
        Find sonically similar songs by feature vector.

        Returns list of (song_meta_dict, similarity_score).
        """
        vec = feature_vector.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, top_n)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            results.append((self.metadata[idx], float(score)))
        return results

    def search_similar_to_track(
        self, track_name: str, artist_name: str, top_n: int = 20
    ) -> list[tuple[dict, float]]:
        """
        Extract features from a specific track and find similar songs.
        """
        from ml.audio.audio_source import get_audio_url

        url = get_audio_url(track_name, artist_name)
        if not url:
            return []

        vec = extract_features(url)
        if vec is None:
            return []

        return self.search_similar_songs(vec, top_n=top_n)


def build_audio_index(
    song_features: list[SongFeature],
) -> tuple[faiss.Index, list[dict]]:
    """
    Build a FAISS index from extracted song features.

    Returns (index, metadata_list).
    """
    if not song_features:
        raise ValueError("No song features to index.")

    vectors = np.array(
        [sf.feature_vector for sf in song_features], dtype=np.float32
    )
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(FEATURE_DIM)
    index.add(vectors)

    metadata = [
        {
            "track_name": sf.track_name,
            "artist_name": sf.artist_name,
            "artist_mbid": sf.artist_mbid,
            "album": sf.album,
        }
        for sf in song_features
    ]

    logger.info(f"Built audio FAISS index: {index.ntotal} songs, {FEATURE_DIM} dims")
    return index, metadata


def save_audio_index(
    index: faiss.Index,
    metadata: list[dict],
    index_path: str | Path = DEFAULT_INDEX_PATH,
    meta_path: str | Path = DEFAULT_META_PATH,
) -> None:
    """Save audio FAISS index and metadata to disk."""
    index_path = Path(index_path)
    meta_path = Path(meta_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Audio index saved → {index_path} ({index.ntotal} songs)")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: Optional[AudioSearchEngine] = None
_lock = Lock()


def get_audio_engine() -> Optional[AudioSearchEngine]:
    return _engine


def load_audio_engine(
    index_path: str | Path = DEFAULT_INDEX_PATH,
    meta_path: str | Path = DEFAULT_META_PATH,
) -> Optional[AudioSearchEngine]:
    global _engine
    with _lock:
        try:
            _engine = AudioSearchEngine(index_path, meta_path)
            return _engine
        except FileNotFoundError:
            logger.warning("Audio index not found — audio search disabled.")
            _engine = None
            return None

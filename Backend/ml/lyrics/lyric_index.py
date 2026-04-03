"""
Lyric FAISS index — stores and searches song lyric embeddings.

384-dimensional vectors (from lyric_embedder.py) indexed for
semantic similarity search by meaning/mood.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Optional

import faiss
import numpy as np

from ml.lyrics.lyric_embedder import LYRIC_DIM, embed_lyrics, embed_query
from services.genius_client import get_lyrics

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "lyrics"
DEFAULT_INDEX_PATH = DATA_DIR / "faiss_lyrics_index.bin"
DEFAULT_META_PATH = DATA_DIR / "lyrics_meta.json"


@dataclass
class LyricFeature:
    track_name: str
    artist_name: str
    artist_mbid: str
    vector: np.ndarray
    album: str = ""


class LyricSearchEngine:
    """In-memory semantic search over song lyrics using FAISS."""

    def __init__(
        self,
        index_path: str | Path = DEFAULT_INDEX_PATH,
        meta_path: str | Path = DEFAULT_META_PATH,
    ):
        index_path = Path(index_path)
        meta_path = Path(meta_path)

        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Lyrics index not found at {index_path}. "
                "Run scripts/extract_lyrics.py first."
            )

        self.index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        logger.info(f"LyricSearchEngine ready — {self.index.ntotal} songs, {LYRIC_DIM} dims")

    def search_similar_lyrics(
        self, query_text: str, top_n: int = 20
    ) -> list[tuple[dict, float]]:
        """
        Search by natural language query (e.g. "sad songs about loneliness").
        Embeds the query and finds nearest lyrics.
        """
        vec = embed_query(query_text)
        if vec is None:
            return []
        return self._search_by_vector(vec, top_n)

    def search_similar_to_song(
        self, track_name: str, artist_name: str, top_n: int = 20
    ) -> list[tuple[dict, float]]:
        """Find songs with lyrically similar content to a specific track."""
        lyrics = get_lyrics(track_name, artist_name)
        if not lyrics:
            return []
        vec = embed_lyrics(lyrics)
        if vec is None:
            return []
        return self._search_by_vector(vec, top_n)

    def _search_by_vector(
        self, vec: np.ndarray, top_n: int
    ) -> list[tuple[dict, float]]:
        vec = vec.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, top_n)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            results.append((self.metadata[idx], float(score)))
        return results


def embed_lyrics_for_artist(
    artist_name: str,
    artist_mbid: str = "",
    spotify_id: Optional[str] = None,
    top_n_tracks: int = 5,
) -> list[LyricFeature]:
    """
    Fetch lyrics for an artist's top tracks and embed them.
    Uses Last.fm for track names (Spotify top-tracks is 403 for new apps).
    Skips tracks with no lyrics (instrumentals).
    """
    from services.lastfm_client import get_artist_top_tracks as lastfm_top_tracks

    tracks = lastfm_top_tracks(artist_name, limit=top_n_tracks)
    if not tracks:
        return []

    results = []
    for track in tracks[:top_n_tracks]:
        lyrics = get_lyrics(track["name"], artist_name)
        if not lyrics:
            continue

        vec = embed_lyrics(lyrics)
        if vec is None:
            continue

        results.append(LyricFeature(
            track_name=track["name"],
            artist_name=artist_name,
            artist_mbid=artist_mbid,
            vector=vec,
            album=track.get("album", ""),
        ))

    logger.info(f"Embedded {len(results)}/{min(len(tracks), top_n_tracks)} lyrics for {artist_name}")
    return results


def build_lyrics_index(
    features: list[LyricFeature],
) -> tuple[faiss.Index, list[dict]]:
    """Build a FAISS index from lyric feature vectors."""
    if not features:
        raise ValueError("No lyric features to index.")

    vectors = np.array([f.vector for f in features], dtype=np.float32)
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(LYRIC_DIM)
    index.add(vectors)

    metadata = [
        {
            "track_name": f.track_name,
            "artist_name": f.artist_name,
            "artist_mbid": f.artist_mbid,
            "album": f.album,
        }
        for f in features
    ]

    logger.info(f"Built lyrics FAISS index: {index.ntotal} songs, {LYRIC_DIM} dims")
    return index, metadata


def save_lyrics_index(
    index: faiss.Index,
    metadata: list[dict],
    index_path: str | Path = DEFAULT_INDEX_PATH,
    meta_path: str | Path = DEFAULT_META_PATH,
) -> None:
    """Save lyrics FAISS index and metadata to disk."""
    index_path = Path(index_path)
    meta_path = Path(meta_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Lyrics index saved → {index_path} ({index.ntotal} songs)")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: Optional[LyricSearchEngine] = None
_lock = Lock()


def get_lyric_engine() -> Optional[LyricSearchEngine]:
    return _engine


def load_lyric_engine(
    index_path: str | Path = DEFAULT_INDEX_PATH,
    meta_path: str | Path = DEFAULT_META_PATH,
) -> Optional[LyricSearchEngine]:
    global _engine
    with _lock:
        try:
            _engine = LyricSearchEngine(index_path, meta_path)
            return _engine
        except FileNotFoundError:
            logger.warning("Lyrics index not found — lyric search disabled.")
            _engine = None
            return None

"""
Result fusion — merges results from all search engines (graph, matrix,
vector, audio, lyrics, production) into a single ranked list.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default fusion weights — sum to 1.0
DEFAULT_WEIGHTS = {
    "graph": 0.30,
    "vector": 0.25,
    "matrix": 0.20,
    "audio": 0.10,
    "lyrics": 0.10,
    "production": 0.05,
}


@dataclass
class FusedResult:
    mbid: str
    name: str
    combined_score: float
    sources: list[str] = field(default_factory=list)
    graph_score: float = 0.0
    embedding_score: float = 0.0
    matrix_score: float = 0.0
    audio_score: float = 0.0
    lyric_score: float = 0.0
    production_score: float = 0.0
    underground_score: float = 0.0


def fuse_results(
    graph_results: list[tuple[str, str, float]] | None = None,
    matrix_results: list[tuple[str, float]] | None = None,
    vector_results: list[tuple[str, float]] | None = None,
    audio_results: list[tuple[str, float]] | None = None,
    lyric_results: list[tuple[str, float]] | None = None,
    production_results: list[tuple[str, float]] | None = None,
    artist_meta: dict[str, dict] | None = None,
    weights: dict[str, float] | None = None,
    top_n: int = 30,
    exclude_mbids: set[str] | None = None,
) -> list[FusedResult]:
    """
    Merge results from all search engines into a ranked list.

    Parameters
    ----------
    graph_results : list of (mbid, name, strength) from graph traversal
    matrix_results : list of (mbid, score) from similarity matrix
    vector_results : list of (mbid, score) from embedding search
    audio_results : list of (mbid, score) from audio FAISS
    lyric_results : list of (mbid, score) from lyric FAISS
    production_results : list of (mbid, score) from production network
    artist_meta : dict {mbid: {"name": str, "underground_score": float}}
    weights : optional weight overrides
    top_n : max results to return
    exclude_mbids : MBIDs to exclude from results (e.g. seed artists)
    """
    w = weights or DEFAULT_WEIGHTS
    meta = artist_meta or {}
    exclude = exclude_mbids or set()
    merged: dict[str, FusedResult] = {}

    def _ensure(mbid: str, name: str = "") -> FusedResult:
        if mbid not in merged:
            m = meta.get(mbid, {})
            merged[mbid] = FusedResult(
                mbid=mbid,
                name=name or m.get("name", ""),
                combined_score=0.0,
                underground_score=m.get("underground_score", 0.0),
            )
        return merged[mbid]

    # Graph results: (mbid, name, strength)
    for mbid, name, score in (graph_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid, name)
        r.graph_score = max(r.graph_score, score)
        if "graph" not in r.sources:
            r.sources.append("graph")

    # Matrix results: (mbid, score)
    for mbid, score in (matrix_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid)
        r.matrix_score = max(r.matrix_score, score)
        if "matrix" not in r.sources:
            r.sources.append("matrix")

    # Vector results: (mbid, score)
    for mbid, score in (vector_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid)
        r.embedding_score = max(r.embedding_score, score)
        if "vector" not in r.sources:
            r.sources.append("vector")

    # Audio results: (mbid, score)
    for mbid, score in (audio_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid)
        r.audio_score = max(r.audio_score, score)
        if "audio" not in r.sources:
            r.sources.append("audio")

    # Lyric results: (mbid, score)
    for mbid, score in (lyric_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid)
        r.lyric_score = max(r.lyric_score, score)
        if "lyrics" not in r.sources:
            r.sources.append("lyrics")

    # Production results: (mbid, score)
    for mbid, score in (production_results or []):
        if mbid in exclude:
            continue
        r = _ensure(mbid)
        r.production_score = max(r.production_score, score)
        if "production" not in r.sources:
            r.sources.append("production")

    # Compute combined scores with underground boost
    for r in merged.values():
        raw = (
            w.get("graph", 0.30) * r.graph_score
            + w.get("vector", 0.25) * r.embedding_score
            + w.get("matrix", 0.20) * r.matrix_score
            + w.get("audio", 0.10) * r.audio_score
            + w.get("lyrics", 0.10) * r.lyric_score
            + w.get("production", 0.05) * r.production_score
        )

        # Multi-source bonus: artists found by 3+ engines get a boost
        source_count = len(r.sources)
        if source_count >= 4:
            raw *= 1.15
        elif source_count >= 3:
            raw *= 1.08

        # Underground boost: 1.0x for mainstream, up to 1.5x for deep underground
        ug_mult = 1.0 + 0.5 * r.underground_score
        r.combined_score = round(raw * ug_mult, 4)

    ranked = sorted(merged.values(), key=lambda r: r.combined_score, reverse=True)
    return ranked[:top_n]

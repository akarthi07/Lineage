"""
Explanation generator — produces human-readable explanations for why
each artist appears in the results.
"""
from __future__ import annotations

import logging
from services.result_fusion import FusedResult

logger = logging.getLogger(__name__)


def explain_result(result: FusedResult, seed_artist_name: str = "") -> str:
    """
    Generate a one-line explanation for why this artist was surfaced.

    Prioritizes the strongest signal source for clarity.
    """
    parts = []

    # Lead with the strongest signal
    scores = [
        ("graph", result.graph_score, _explain_graph),
        ("vector", result.embedding_score, _explain_vector),
        ("matrix", result.matrix_score, _explain_matrix),
        ("audio", result.audio_score, _explain_audio),
        ("lyrics", result.lyric_score, _explain_lyrics),
        ("production", result.production_score, _explain_production),
    ]

    # Sort by score descending, take top contributing sources
    active = [(name, score, fn) for name, score, fn in scores if score > 0]
    active.sort(key=lambda x: x[1], reverse=True)

    if not active:
        return "Discovered through cross-referencing multiple data sources."

    # Primary reason
    primary_name, primary_score, primary_fn = active[0]
    parts.append(primary_fn(primary_score, seed_artist_name, result.name))

    # Secondary reason (if exists and meaningful)
    if len(active) >= 2:
        sec_name, sec_score, sec_fn = active[1]
        if sec_score > 0.1:
            parts.append(sec_fn(sec_score, seed_artist_name, result.name))

    # Underground callout
    if result.underground_score > 0.7:
        parts.append("Deep underground find")
    elif result.underground_score > 0.4:
        parts.append("Under-the-radar artist")

    return " · ".join(parts)


def _explain_graph(score: float, seed: str, name: str) -> str:
    if score > 0.8:
        return f"Direct documented influence{_of(seed)}"
    elif score > 0.5:
        return f"Strong lineage connection{_of(seed)}"
    else:
        return f"Connected in the influence graph{_of(seed)}"


def _explain_vector(score: float, seed: str, name: str) -> str:
    if score > 0.8:
        return "Very close in the musical embedding space"
    elif score > 0.5:
        return "Similar position in the musical landscape"
    else:
        return "Related musical neighborhood"


def _explain_matrix(score: float, seed: str, name: str) -> str:
    if score > 0.5:
        return "High cross-signal similarity (tags, era, region)"
    else:
        return "Overlap in genre, era, or geography"


def _explain_audio(score: float, seed: str, name: str) -> str:
    if score > 0.7:
        return "Very similar sonic profile"
    elif score > 0.4:
        return "Similar sound characteristics"
    else:
        return "Sonically adjacent"


def _explain_lyrics(score: float, seed: str, name: str) -> str:
    if score > 0.7:
        return "Thematically aligned lyrics"
    elif score > 0.4:
        return "Similar lyrical themes"
    else:
        return "Related lyrical territory"


def _explain_production(score: float, seed: str, name: str) -> str:
    if score > 0.5:
        return f"Shares multiple producers{_with(seed)}"
    else:
        return f"Connected through production credits{_with(seed)}"


def _of(seed: str) -> str:
    return f" of {seed}" if seed else ""


def _with(seed: str) -> str:
    return f" with {seed}" if seed else ""


def generate_explanations(
    results: list[FusedResult],
    seed_artist_name: str = "",
) -> dict[str, str]:
    """
    Generate explanations for a batch of fused results.
    Returns {mbid: explanation_string}.
    """
    explanations = {}
    for r in results:
        explanations[r.mbid] = explain_result(r, seed_artist_name)
    return explanations

"""
Tag co-occurrence matrix builder — Jaccard similarity of artist tag sets.

Tags are the merged Last.fm + MusicBrainz + Spotify genre tags stored on
each Artist node (artist.genres + artist.tags, deduplicated).
"""
from __future__ import annotations

import numpy as np

from ml.data_exporter import GraphExport


def build_tag_matrix(graph_export: GraphExport) -> np.ndarray:
    """
    Build an NxN tag co-occurrence matrix using Jaccard similarity.

    J(A, B) = |tags_A ∩ tags_B| / |tags_A ∪ tags_B|

    Diagonal is 1.0 (artist is identical to itself).
    Artists with no tags get 0.0 similarity with everyone (including themselves).
    """
    n = graph_export.n

    # Pre-compute tag sets (merge genres + tags, lowercased for consistency)
    tag_sets: list[set[str]] = []
    for artist in graph_export.artists:
        combined = set(t.lower() for t in artist.genres) | set(t.lower() for t in artist.tags)
        tag_sets.append(combined)

    matrix = np.zeros((n, n), dtype=np.float64)

    for i in range(n):
        tags_i = tag_sets[i]
        if not tags_i:
            continue

        # Diagonal: artist is identical to itself
        matrix[i][i] = 1.0

        for j in range(i + 1, n):
            tags_j = tag_sets[j]
            if not tags_j:
                continue

            intersection = len(tags_i & tags_j)
            if intersection == 0:
                continue

            union = len(tags_i | tags_j)
            jaccard = intersection / union

            matrix[i][j] = jaccard
            matrix[j][i] = jaccard

    return matrix

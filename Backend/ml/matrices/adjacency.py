"""
Adjacency matrix builder — converts INFLUENCED_BY edges into an NxN numpy array.

A[i][j] = relationship strength if an edge exists, 0.0 otherwise.
The matrix is symmetrized: influence is directional but similarity is not.
"""
from __future__ import annotations

import numpy as np

from ml.data_exporter import GraphExport


def build_adjacency_matrix(graph_export: GraphExport) -> np.ndarray:
    """
    Build a symmetric NxN adjacency matrix from graph relationships.

    A[i][j] = max(strength) of edges between artists i and j.
    Symmetrized: A[i][j] = A[j][i] = max of both directions.
    Diagonal is always 0.0.
    """
    n = graph_export.n
    matrix = np.zeros((n, n), dtype=np.float64)

    for rel in graph_export.relationships:
        i = graph_export.artist_index.get(rel.source_mbid)
        j = graph_export.artist_index.get(rel.target_mbid)

        if i is None or j is None:
            continue
        if i == j:
            continue

        # Use max strength if multiple edges exist between the same pair
        strength = rel.strength
        matrix[i][j] = max(matrix[i][j], strength)
        matrix[j][i] = max(matrix[j][i], strength)

    return matrix

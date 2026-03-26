"""
Temporal proximity matrix builder — how close in time two artists are.

P[i][j] = 1.0 - min(1.0, |year_i - year_j| / 50)

Artists 0 years apart get 1.0, 25 years apart get 0.5, 50+ years apart get 0.0.
Missing formation_year uses 0.5 (neutral).
"""
from __future__ import annotations

import numpy as np

from ml.data_exporter import GraphExport

# Artists 50+ years apart are considered fully dissimilar temporally
MAX_YEAR_GAP = 50

# Default score when either artist has no formation_year
MISSING_YEAR_DEFAULT = 0.5


def build_temporal_matrix(graph_export: GraphExport) -> np.ndarray:
    """
    Build an NxN temporal proximity matrix.

    Dense matrix — every cell has a value. Diagonal is always 1.0.
    """
    n = graph_export.n
    matrix = np.zeros((n, n), dtype=np.float64)

    # Extract formation years (None if missing)
    years = [artist.formation_year for artist in graph_export.artists]

    for i in range(n):
        matrix[i][i] = 1.0  # Self-similarity

        for j in range(i + 1, n):
            if years[i] is None or years[j] is None:
                score = MISSING_YEAR_DEFAULT
            else:
                gap = abs(years[i] - years[j])
                score = 1.0 - min(1.0, gap / MAX_YEAR_GAP)

            matrix[i][j] = score
            matrix[j][i] = score

    return matrix

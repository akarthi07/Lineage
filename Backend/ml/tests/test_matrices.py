"""
Test suite for all component matrices.

Exports the graph from Neo4j, builds each matrix, and verifies:
- Shape is NxN
- Value ranges are correct
- Symmetry holds
- Summary stats (sparsity, mean, max)
- Spot-checks on known pairs where possible
"""
from __future__ import annotations

import sys
import os

# Ensure Backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from ml.data_exporter import export_graph_data, GraphExport
from ml.matrices.adjacency import build_adjacency_matrix
from ml.matrices.tag_cooccurrence import build_tag_matrix
from ml.matrices.lastfm_similarity import build_lastfm_matrix
from ml.matrices.temporal import build_temporal_matrix
from ml.matrices.geographic import build_geographic_matrix


def _print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _print_stats(name: str, matrix: np.ndarray, n: int) -> None:
    """Print summary statistics for a matrix."""
    total_cells = n * n
    non_zero = np.count_nonzero(matrix)
    sparsity = 1.0 - (non_zero / total_cells) if total_cells > 0 else 0.0

    # Exclude diagonal for off-diagonal stats
    if n > 1:
        mask = ~np.eye(n, dtype=bool)
        off_diag = matrix[mask]
        mean_val = np.mean(off_diag)
        max_val = np.max(off_diag)
        min_nonzero = np.min(off_diag[off_diag > 0]) if np.any(off_diag > 0) else 0.0
    else:
        mean_val = max_val = min_nonzero = 0.0

    print(f"\n  [{name}] Summary Stats:")
    print(f"    Shape:            {matrix.shape}")
    print(f"    Non-zero entries: {non_zero}/{total_cells}")
    print(f"    Sparsity:         {sparsity:.1%}")
    print(f"    Off-diag mean:    {mean_val:.4f}")
    print(f"    Off-diag max:     {max_val:.4f}")
    print(f"    Min non-zero:     {min_nonzero:.4f}")


def _check_shape(name: str, matrix: np.ndarray, n: int) -> bool:
    ok = matrix.shape == (n, n)
    status = "PASS" if ok else "FAIL"
    print(f"  [{name}] Shape is {n}x{n}: {status} (got {matrix.shape})")
    return ok


def _check_symmetry(name: str, matrix: np.ndarray) -> bool:
    ok = np.allclose(matrix, matrix.T, atol=1e-10)
    status = "PASS" if ok else "FAIL"
    if not ok:
        diff = np.max(np.abs(matrix - matrix.T))
        print(f"  [{name}] Symmetric: {status} (max asymmetry: {diff:.6f})")
    else:
        print(f"  [{name}] Symmetric: {status}")
    return ok


def _check_range(name: str, matrix: np.ndarray, low: float, high: float) -> bool:
    actual_min = np.min(matrix)
    actual_max = np.max(matrix)
    ok = actual_min >= low - 1e-10 and actual_max <= high + 1e-10
    status = "PASS" if ok else "FAIL"
    print(f"  [{name}] Range [{low}, {high}]: {status} (actual [{actual_min:.4f}, {actual_max:.4f}])")
    return ok


def _check_diagonal(name: str, matrix: np.ndarray, expected: float) -> bool:
    diag = np.diag(matrix)
    ok = np.allclose(diag, expected, atol=1e-10)
    status = "PASS" if ok else "FAIL"
    if not ok:
        unique = np.unique(diag)
        print(f"  [{name}] Diagonal == {expected}: {status} (unique values: {unique[:5]})")
    else:
        print(f"  [{name}] Diagonal == {expected}: {status}")
    return ok


def _spot_check_pairs(
    name: str,
    matrix: np.ndarray,
    graph_export: GraphExport,
    pairs: list[tuple[str, str, str]],
) -> None:
    """Spot-check specific artist pairs. Each tuple: (artist_a, artist_b, expected_level)."""
    print(f"\n  [{name}] Spot checks:")
    name_to_idx: dict[str, int] = {}
    for artist in graph_export.artists:
        name_to_idx[artist.name.lower()] = graph_export.artist_index[artist.mbid]

    for a_name, b_name, expectation in pairs:
        i = name_to_idx.get(a_name.lower())
        j = name_to_idx.get(b_name.lower())
        if i is None or j is None:
            missing = a_name if i is None else b_name
            print(f"    {a_name} <-> {b_name}: SKIP ('{missing}' not in graph)")
            continue
        val = matrix[i][j]
        print(f"    {a_name} <-> {b_name}: {val:.4f} (expected: {expectation})")


def test_adjacency(graph_export: GraphExport) -> None:
    _print_header("Adjacency Matrix")
    matrix = build_adjacency_matrix(graph_export)
    n = graph_export.n

    _check_shape("adjacency", matrix, n)
    _check_symmetry("adjacency", matrix)
    _check_range("adjacency", matrix, 0.0, 1.0)
    _check_diagonal("adjacency", matrix, 0.0)
    _print_stats("adjacency", matrix, n)

    # Non-zero entries should roughly match edge count (x2 for symmetry, minus overlaps)
    edge_count = len(graph_export.relationships)
    non_zero = np.count_nonzero(matrix)
    print(f"\n  Relationships: {edge_count}, Non-zero cells: {non_zero}")

    _spot_check_pairs("adjacency", matrix, graph_export, [
        ("Radiohead", "Thom Yorke", "high"),
        ("The Beatles", "Led Zeppelin", "medium"),
        ("Aphex Twin", "Boards of Canada", "medium-high"),
    ])


def test_tag_cooccurrence(graph_export: GraphExport) -> None:
    _print_header("Tag Co-occurrence Matrix")
    matrix = build_tag_matrix(graph_export)
    n = graph_export.n

    _check_shape("tags", matrix, n)
    _check_symmetry("tags", matrix)
    _check_range("tags", matrix, 0.0, 1.0)
    _print_stats("tags", matrix, n)

    # Check diagonal: 1.0 for artists with tags, 0.0 for those without
    for i, artist in enumerate(graph_export.artists):
        has_tags = bool(artist.genres or artist.tags)
        expected = 1.0 if has_tags else 0.0
        actual = matrix[i][i]
        if abs(actual - expected) > 1e-10:
            print(f"  [tags] Diagonal MISMATCH at {artist.name}: {actual} (expected {expected})")
            break
    else:
        print(f"  [tags] Diagonal values: PASS (1.0 if tags, 0.0 if none)")

    _spot_check_pairs("tags", matrix, graph_export, [
        ("Radiohead", "Muse", "medium-high"),
        ("Miles Davis", "John Coltrane", "high"),
        ("Aphex Twin", "Squarepusher", "high"),
    ])


def test_lastfm_similarity(graph_export: GraphExport) -> None:
    _print_header("Last.fm Similarity Matrix")
    matrix = build_lastfm_matrix(graph_export)
    n = graph_export.n

    _check_shape("lastfm", matrix, n)
    _check_symmetry("lastfm", matrix)
    _check_range("lastfm", matrix, 0.0, 1.0)
    _check_diagonal("lastfm", matrix, 0.0)
    _print_stats("lastfm", matrix, n)

    _spot_check_pairs("lastfm", matrix, graph_export, [
        ("Radiohead", "Muse", "medium-high"),
        ("Pink Floyd", "Led Zeppelin", "medium"),
        ("Burial", "Four Tet", "medium-high"),
    ])


def test_temporal(graph_export: GraphExport) -> None:
    _print_header("Temporal Proximity Matrix")
    matrix = build_temporal_matrix(graph_export)
    n = graph_export.n

    _check_shape("temporal", matrix, n)
    _check_symmetry("temporal", matrix)
    _check_range("temporal", matrix, 0.0, 1.0)
    _check_diagonal("temporal", matrix, 1.0)
    _print_stats("temporal", matrix, n)

    _spot_check_pairs("temporal", matrix, graph_export, [
        ("The Beatles", "Led Zeppelin", "high (similar era)"),
        ("Mozart", "Radiohead", "low (centuries apart)"),
        ("Aphex Twin", "Boards of Canada", "high (same era)"),
    ])


def test_geographic(graph_export: GraphExport) -> None:
    _print_header("Geographic Proximity Matrix")
    matrix = build_geographic_matrix(graph_export)
    n = graph_export.n

    _check_shape("geographic", matrix, n)
    _check_symmetry("geographic", matrix)
    _check_range("geographic", matrix, 0.0, 1.0)
    _check_diagonal("geographic", matrix, 1.0)
    _print_stats("geographic", matrix, n)

    _spot_check_pairs("geographic", matrix, graph_export, [
        ("Radiohead", "Muse", "0.5 (both GB)"),
        ("Radiohead", "Kraftwerk", "0.25 (both Europe)"),
        ("Radiohead", "Kendrick Lamar", "0.0 (different regions)"),
    ])


def main() -> None:
    print("Exporting graph data from Neo4j...")
    graph_export = export_graph_data()

    if graph_export.n == 0:
        print("\nNo artists found in Neo4j. Seed the database first.")
        return

    print(f"Exported {graph_export.n} artists, {len(graph_export.relationships)} relationships.")

    # List first 10 artists as sanity check
    print(f"\nFirst 10 artists (alphabetical):")
    for i, artist in enumerate(graph_export.artists[:10]):
        tags_preview = ", ".join((artist.genres + artist.tags)[:3]) or "no tags"
        year = artist.formation_year or "?"
        country = artist.country or "?"
        print(f"  [{i}] {artist.name} ({year}, {country}) — {tags_preview}")

    all_passed = True

    test_adjacency(graph_export)
    test_tag_cooccurrence(graph_export)
    test_lastfm_similarity(graph_export)
    test_temporal(graph_export)
    test_geographic(graph_export)

    _print_header("ALL TESTS COMPLETE")
    print(f"  Artists: {graph_export.n}")
    print(f"  Relationships: {len(graph_export.relationships)}")
    print()


if __name__ == "__main__":
    main()

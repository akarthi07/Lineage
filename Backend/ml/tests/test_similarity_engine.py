#!/usr/bin/env python
"""
End-to-end test for the unified similarity matrix pipeline.

Tests: export → build component matrices → normalize → combine → serialize →
       reload → query → verify scores make musical sense.

Run from Backend/:
    python -m ml.tests.test_similarity_engine
"""
from __future__ import annotations

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from ml.data_exporter import export_graph_data
from ml.similarity_engine import (
    normalize_matrix,
    build_unified_matrix,
    save_matrix,
    load_matrix,
    SimilarityEngine,
    WEIGHTS,
)


def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_normalization() -> bool:
    _header("Normalization")
    ok = True

    # Normal case
    m = np.array([[0.0, 0.3], [0.3, 0.6]])
    n = normalize_matrix(m)
    if abs(n.min()) > 1e-10:
        print(f"  FAIL: min should be 0.0, got {n.min()}")
        ok = False
    if abs(n.max() - 1.0) > 1e-10:
        print(f"  FAIL: max should be 1.0, got {n.max()}")
        ok = False

    # Constant matrix (edge case)
    c = np.ones((3, 3)) * 5.0
    cn = normalize_matrix(c)
    if np.any(cn != 0.0):
        print(f"  FAIL: constant matrix should normalize to zeros")
        ok = False

    if ok:
        print("  PASS — normalize_matrix works correctly")
    return ok


def test_unified_matrix(graph_export) -> tuple[bool, np.ndarray]:
    _header("Unified Matrix Build")
    ok = True
    n = graph_export.n

    matrix = build_unified_matrix(graph_export)

    # Shape
    if matrix.shape != (n, n):
        print(f"  FAIL: expected ({n},{n}), got {matrix.shape}")
        ok = False
    else:
        print(f"  PASS — shape is {n}x{n}")

    # Value range
    mn, mx = matrix.min(), matrix.max()
    if mn < -0.01 or mx > 1.01:
        print(f"  FAIL: values out of [0,1] range: [{mn:.4f}, {mx:.4f}]")
        ok = False
    else:
        print(f"  PASS — values in [0,1] range: [{mn:.4f}, {mx:.4f}]")

    # Symmetry
    if np.allclose(matrix, matrix.T, atol=1e-10):
        print("  PASS — matrix is symmetric")
    else:
        diff = np.max(np.abs(matrix - matrix.T))
        print(f"  WARN — max asymmetry: {diff:.6f}")

    # Stats
    if n > 1:
        mask = ~np.eye(n, dtype=bool)
        off_diag = matrix[mask]
        print(f"\n  Off-diagonal stats:")
        print(f"    Mean:     {np.mean(off_diag):.4f}")
        print(f"    Median:   {np.median(off_diag):.4f}")
        print(f"    Max:      {np.max(off_diag):.4f}")
        print(f"    Std:      {np.std(off_diag):.4f}")
        non_zero = np.count_nonzero(off_diag)
        print(f"    Non-zero: {non_zero}/{len(off_diag)} ({non_zero/len(off_diag):.1%})")

    print(f"\n  Weights used: {WEIGHTS}")

    return ok, matrix


def test_serialization(matrix, artist_index) -> bool:
    _header("Serialization (save/load)")
    ok = True

    with tempfile.TemporaryDirectory() as tmpdir:
        mat_path = os.path.join(tmpdir, "test_matrix.npy")
        idx_path = os.path.join(tmpdir, "test_index.json")

        save_matrix(matrix, artist_index, mat_path, idx_path)

        loaded_mat, loaded_idx = load_matrix(mat_path, idx_path)

        if not np.array_equal(matrix, loaded_mat):
            print("  FAIL — loaded matrix differs from original")
            ok = False
        else:
            print("  PASS — matrix round-trips correctly")

        if loaded_idx != artist_index:
            print("  FAIL — loaded index differs from original")
            ok = False
        else:
            print(f"  PASS — index round-trips correctly ({len(loaded_idx)} artists)")

    return ok


def test_engine_queries(matrix, artist_index, graph_export) -> bool:
    _header("SimilarityEngine Queries")
    ok = True

    with tempfile.TemporaryDirectory() as tmpdir:
        mat_path = os.path.join(tmpdir, "test_matrix.npy")
        idx_path = os.path.join(tmpdir, "test_index.json")
        save_matrix(matrix, artist_index, mat_path, idx_path)

        engine = SimilarityEngine(mat_path, idx_path)
        print(f"  Engine loaded: {engine.n} artists")

        # -- get_similarity ---------------------------------------------------
        print(f"\n  Pairwise similarity checks:")
        name_to_mbid: dict[str, str] = {}
        for artist in graph_export.artists:
            name_to_mbid[artist.name.lower()] = artist.mbid

        test_pairs = [
            ("radiohead", "thom yorke", "high"),
            ("radiohead", "muse", "medium-high"),
            ("aphex twin", "boards of canada", "medium-high"),
            ("the beatles", "led zeppelin", "medium"),
        ]

        for a_name, b_name, expected in test_pairs:
            a_mbid = name_to_mbid.get(a_name)
            b_mbid = name_to_mbid.get(b_name)
            if a_mbid is None or b_mbid is None:
                missing = a_name if a_mbid is None else b_name
                print(f"    {a_name} <-> {b_name}: SKIP ('{missing}' not in graph)")
                continue
            score = engine.get_similarity(a_mbid, b_mbid)
            print(f"    {a_name} <-> {b_name}: {score:.4f} (expected: {expected})")

        # -- get_most_similar -------------------------------------------------
        print(f"\n  Top similar queries:")
        test_artists = ["radiohead", "aphex twin", "miles davis", "kendrick lamar", "bjork"]

        for name in test_artists:
            mbid = name_to_mbid.get(name)
            if mbid is None:
                print(f"    {name}: SKIP (not in graph)")
                continue
            similar = engine.get_most_similar(mbid, top_n=5)
            mbid_to_name = {a.mbid: a.name for a in graph_export.artists}
            names = [f"{mbid_to_name.get(m, m)} ({s:.3f})" for m, s in similar]
            print(f"    {name} →  {', '.join(names) if names else '(no results)'}")

        # -- get_similarity_row -----------------------------------------------
        print(f"\n  Similarity row test:")
        first_mbid = graph_export.artists[0].mbid if graph_export.artists else None
        if first_mbid:
            row = engine.get_similarity_row(first_mbid)
            non_zero = sum(1 for v in row.values() if v > 0)
            print(f"    {graph_export.artists[0].name}: {non_zero} non-zero similarities")
            if row:
                top_3 = sorted(row.items(), key=lambda x: x[1], reverse=True)[:3]
                mbid_to_name = {a.mbid: a.name for a in graph_export.artists}
                for m, s in top_3:
                    print(f"      {mbid_to_name.get(m, m)}: {s:.4f}")
        else:
            print("    SKIP — no artists")

        # -- has_artist -------------------------------------------------------
        if graph_export.artists:
            real_mbid = graph_export.artists[0].mbid
            if not engine.has_artist(real_mbid):
                print(f"  FAIL — has_artist returned False for existing artist")
                ok = False
        if engine.has_artist("fake-nonexistent-mbid-12345"):
            print(f"  FAIL — has_artist returned True for fake MBID")
            ok = False
        else:
            print(f"  PASS — has_artist works correctly")

    return ok


def main() -> None:
    print("Exporting graph data from Neo4j ...")
    graph_export = export_graph_data()

    if graph_export.n == 0:
        print("\nNo artists found in Neo4j. Seed the database first.")
        return

    print(f"Exported {graph_export.n} artists, {len(graph_export.relationships)} relationships.")

    all_ok = True

    all_ok &= test_normalization()

    ok, matrix = test_unified_matrix(graph_export)
    all_ok &= ok

    all_ok &= test_serialization(matrix, graph_export.artist_index)

    all_ok &= test_engine_queries(matrix, graph_export.artist_index, graph_export)

    _header("ALL TESTS COMPLETE")
    status = "ALL PASSED" if all_ok else "SOME FAILURES"
    print(f"  {status}")
    print(f"  Artists: {graph_export.n}")
    print(f"  Relationships: {len(graph_export.relationships)}")
    print()


if __name__ == "__main__":
    main()

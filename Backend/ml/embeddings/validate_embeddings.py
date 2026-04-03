"""
Embedding validation — sanity checks to verify trained vectors capture
meaningful musical relationships.
"""
from __future__ import annotations

import logging

import numpy as np
from gensim.models import Word2Vec

from ml.data_exporter import GraphExport

logger = logging.getLogger(__name__)


def validate_embeddings(
    model: Word2Vec,
    graph_export: GraphExport,
    similarity_matrix: np.ndarray | None = None,
) -> dict:
    """
    Run validation checks on trained embeddings.

    Returns a dict with:
      - similar_pairs_correct: int (out of tested similar pairs)
      - dissimilar_pairs_correct: int (out of tested dissimilar pairs)
      - total_similar_tested: int
      - total_dissimilar_tested: int
      - matrix_correlation: float | None (if similarity_matrix provided)
      - top_similar_samples: dict[str, list] (artist name -> top 10 similar)
    """
    vocab = set(model.wv.key_to_index.keys())
    index_to_mbid = {v: k for k, v in graph_export.artist_index.items()}
    mbid_to_name = {a.mbid: a.name for a in graph_export.artists}

    # -- Find connected pairs from graph edges (should be similar) --
    similar_pairs = []
    for rel in graph_export.relationships:
        if rel.source_mbid in vocab and rel.target_mbid in vocab:
            similar_pairs.append((rel.source_mbid, rel.target_mbid, rel.strength))
    similar_pairs.sort(key=lambda x: x[2], reverse=True)
    similar_pairs = similar_pairs[:20]  # top 20 strongest edges

    # -- Find unconnected pairs (should be dissimilar) --
    # Pick random pairs of artists with no direct edge
    connected = {(r.source_mbid, r.target_mbid) for r in graph_export.relationships}
    connected |= {(r.target_mbid, r.source_mbid) for r in graph_export.relationships}

    artists_in_vocab = [a for a in graph_export.artists if a.mbid in vocab]
    dissimilar_pairs = []
    for i in range(min(len(artists_in_vocab), 50)):
        for j in range(i + 1, min(len(artists_in_vocab), 50)):
            a = artists_in_vocab[i]
            b = artists_in_vocab[j]
            if (a.mbid, b.mbid) not in connected:
                dissimilar_pairs.append((a.mbid, b.mbid))
                if len(dissimilar_pairs) >= 20:
                    break
        if len(dissimilar_pairs) >= 20:
            break

    # -- Test similar pairs --
    similar_correct = 0
    similar_tested = 0
    logger.info("--- Similar pairs (should have cosine > 0.3) ---")
    for src, tgt, strength in similar_pairs:
        sim = model.wv.similarity(src, tgt)
        name_a = mbid_to_name.get(src, src[:8])
        name_b = mbid_to_name.get(tgt, tgt[:8])
        passed = sim > 0.3
        if passed:
            similar_correct += 1
        similar_tested += 1
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{status}] {name_a} <-> {name_b}: cosine={sim:.3f} (edge strength={strength:.2f})")

    # -- Test dissimilar pairs --
    dissimilar_correct = 0
    dissimilar_tested = 0
    logger.info("--- Dissimilar pairs (should have cosine < 0.5) ---")
    for src, tgt in dissimilar_pairs[:10]:
        sim = model.wv.similarity(src, tgt)
        name_a = mbid_to_name.get(src, src[:8])
        name_b = mbid_to_name.get(tgt, tgt[:8])
        passed = sim < 0.5
        if passed:
            dissimilar_correct += 1
        dissimilar_tested += 1
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{status}] {name_a} <-> {name_b}: cosine={sim:.3f}")

    # -- Top similar for sample artists --
    top_similar_samples = {}
    sample_artists = artists_in_vocab[:5]
    logger.info("--- Top 10 most similar for sample artists ---")
    for artist in sample_artists:
        if artist.mbid not in vocab:
            continue
        try:
            most_similar = model.wv.most_similar(artist.mbid, topn=10)
            names = []
            for other_mbid, score in most_similar:
                other_name = mbid_to_name.get(other_mbid, other_mbid[:8])
                names.append((other_name, round(score, 3)))
            top_similar_samples[artist.name] = names
            logger.info(f"  {artist.name}:")
            for name, score in names:
                logger.info(f"    {name}: {score}")
        except KeyError:
            continue

    # -- Matrix correlation (if available) --
    matrix_corr = None
    if similarity_matrix is not None:
        logger.info("--- Matrix vs Embedding correlation ---")
        matrix_sims = []
        embed_sims = []
        for i, artist_a in enumerate(artists_in_vocab[:100]):
            for j, artist_b in enumerate(artists_in_vocab[:100]):
                if i >= j:
                    continue
                if artist_a.mbid not in vocab or artist_b.mbid not in vocab:
                    continue
                idx_a = graph_export.artist_index.get(artist_a.mbid)
                idx_b = graph_export.artist_index.get(artist_b.mbid)
                if idx_a is None or idx_b is None:
                    continue
                matrix_sims.append(similarity_matrix[idx_a][idx_b])
                embed_sims.append(model.wv.similarity(artist_a.mbid, artist_b.mbid))

        if len(matrix_sims) > 10:
            matrix_corr = float(np.corrcoef(matrix_sims, embed_sims)[0, 1])
            logger.info(f"  Pearson correlation: {matrix_corr:.3f} (over {len(matrix_sims)} pairs)")

    # -- Summary --
    results = {
        "similar_pairs_correct": similar_correct,
        "total_similar_tested": similar_tested,
        "dissimilar_pairs_correct": dissimilar_correct,
        "total_dissimilar_tested": dissimilar_tested,
        "matrix_correlation": matrix_corr,
        "top_similar_samples": top_similar_samples,
        "vocab_size": len(vocab),
    }

    logger.info(
        f"Validation: {similar_correct}/{similar_tested} similar pairs correct, "
        f"{dissimilar_correct}/{dissimilar_tested} dissimilar pairs correct"
    )

    return results

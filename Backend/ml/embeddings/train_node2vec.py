"""
Node2Vec embedding trainer.

Generates random walks on the artist influence graph and trains Word2Vec
to produce 128-dimensional artist embeddings.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
from gensim.models import Word2Vec
from node2vec import Node2Vec

logger = logging.getLogger(__name__)

# Default save paths (relative to Backend/)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "embeddings"
DEFAULT_MODEL_PATH = DATA_DIR / "node2vec_model.bin"
DEFAULT_METADATA_PATH = DATA_DIR / "metadata.json"


def train_embeddings(
    G: nx.DiGraph,
    dimensions: int = 128,
    walk_length: int = 40,
    num_walks: int = 15,
    p: float = 0.5,
    q: float = 0.5,
    workers: int = 1,
    window: int = 10,
    min_count: int = 1,
    epochs: int = 5,
) -> Word2Vec:
    """
    Train Node2Vec embeddings on a NetworkX graph.

    Parameters
    ----------
    G : NetworkX DiGraph with artist MBIDs as nodes and edge weights.
    dimensions : Embedding vector size (default 128).
    walk_length : Length of each random walk (default 40).
    num_walks : Number of walks per node (default 15).
    p : Return parameter — lower = more local/BFS-like (default 0.5).
    q : In-out parameter — lower = more exploratory/DFS-like (default 0.5).
    workers : Parallel workers for walk generation (default 1 for Windows).
    window : Word2Vec context window size (default 10).
    min_count : Min occurrences for Word2Vec vocab (default 1 — keep all).
    epochs : Word2Vec training epochs (default 5).

    Returns the trained gensim Word2Vec model.
    """
    if G.number_of_nodes() == 0:
        raise ValueError("Graph has no nodes — cannot train embeddings.")

    # Convert to undirected for Node2Vec (similarity is bidirectional)
    G_undirected = G.to_undirected()

    logger.info(
        f"Training Node2Vec: {G_undirected.number_of_nodes()} nodes, "
        f"{G_undirected.number_of_edges()} edges, "
        f"dims={dimensions}, walks={num_walks}x{walk_length}, p={p}, q={q}"
    )

    t0 = time.perf_counter()

    # Generate random walks
    logger.info("Generating random walks …")
    node2vec = Node2Vec(
        G_undirected,
        dimensions=dimensions,
        walk_length=walk_length,
        num_walks=num_walks,
        p=p,
        q=q,
        workers=workers,
        quiet=False,
    )

    # Train Word2Vec on walks
    logger.info("Training Word2Vec …")
    model = node2vec.fit(
        window=window,
        min_count=min_count,
        batch_words=4,
        workers=workers,
        epochs=epochs,
    )

    elapsed = time.perf_counter() - t0
    logger.info(f"Training complete in {elapsed:.1f}s — vocab size: {len(model.wv)}")

    return model


def save_model(
    model: Word2Vec,
    path: str | Path = DEFAULT_MODEL_PATH,
    metadata_path: str | Path = DEFAULT_METADATA_PATH,
    hyperparams: dict | None = None,
    validation_scores: dict | None = None,
) -> None:
    """Save the gensim Word2Vec model and training metadata to disk."""
    path = Path(path)
    metadata_path = Path(metadata_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    model.save(str(path))
    logger.info(f"Model saved → {path}")

    metadata = {
        "training_date": datetime.now(timezone.utc).isoformat(),
        "node_count": len(model.wv),
        "dimensions": model.wv.vector_size,
        "hyperparams": hyperparams or {},
        "validation_scores": validation_scores or {},
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved → {metadata_path}")


def load_model(path: str | Path = DEFAULT_MODEL_PATH) -> Word2Vec:
    """Load a previously saved gensim Word2Vec model."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model not found at {path}. Run scripts/train_embeddings.py first."
        )
    model = Word2Vec.load(str(path))
    logger.info(f"Loaded model: {len(model.wv)} vectors, {model.wv.vector_size} dims")
    return model

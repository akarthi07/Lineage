#!/usr/bin/env python3
"""
detect_genesis.py
─────────────────
Run proto-genre detection, compare against previous runs, and store
detection history.

Run from the Backend/ directory:
    python scripts/detect_genesis.py
    python scripts/detect_genesis.py --eps 0.35 --min-samples 5
"""
from __future__ import annotations

import argparse
import json
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: F401 — loads env vars

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("detect_genesis")

HISTORY_FILE = ROOT / "data" / "genesis" / "detection_history.json"
LATEST_FILE = ROOT / "data" / "genesis" / "latest_detection.json"


def _load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def _save_history(history: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Detect proto-genre clusters")
    parser.add_argument("--eps", type=float, default=0.40, help="DBSCAN eps (default 0.40)")
    parser.add_argument("--min-samples", type=int, default=4, help="DBSCAN min_samples (default 4)")
    parser.add_argument("--no-describe", action="store_true", help="Skip Claude API descriptions")
    args = parser.parse_args()

    log.info("=" * 58)
    log.info("  Proto-Genre Detection")
    log.info(f"  eps={args.eps}  min_samples={args.min_samples}")
    log.info("=" * 58)

    # ── 0. Load vector engine (normally done at FastAPI startup) ──
    from ml.embeddings.search_engine import load_vector_engine

    engine = load_vector_engine()
    if engine is None:
        log.error("Could not load vector engine. Run scripts/retrain_all.py first.")
        return
    log.info(f"Vector engine loaded: {len(engine.mbid_list)} artists")

    # ── 1. Detect clusters ────────────────────────────────────────
    from ml.genesis.cluster_detector import detect_proto_genres

    clusters = detect_proto_genres(eps=args.eps, min_samples=args.min_samples)

    if not clusters:
        log.info("No clusters detected. Try adjusting eps or min_samples.")
        return

    log.info(f"\nFound {len(clusters)} clusters:")
    for pg in clusters:
        artists = ", ".join(a.name for a in pg.artists[:5])
        if len(pg.artists) > 5:
            artists += f" +{len(pg.artists) - 5} more"
        log.info(
            f"  Cluster #{pg.cluster_id}: {pg.size} artists, "
            f"cohesion={pg.cohesion_score:.2f}, "
            f"avg_ug={pg.avg_underground:.2f}"
        )
        log.info(f"    Artists: {artists}")
        log.info(f"    Tags: {', '.join(pg.top_tags[:6])}")

    # ── 2. Trace lineage ──��───────────────────────────────────────
    log.info("\nTracing lineage roots...")
    from ml.genesis.lineage_tracer import trace_all_clusters

    trace_all_clusters(clusters)

    for pg in clusters:
        if pg.lineage_roots:
            root_names = ", ".join(r["name"] for r in pg.lineage_roots[:5])
            log.info(f"  Cluster #{pg.cluster_id} roots: {root_names}")
        else:
            log.info(f"  Cluster #{pg.cluster_id}: no shared lineage roots found")

    # ── 3. Generate descriptions ──────────────────────────────────
    if not args.no_describe:
        log.info("\nGenerating AI descriptions...")
        from ml.genesis.genre_describer import describe_proto_genre

        for pg in clusters:
            pg.description = describe_proto_genre(pg)
            log.info(f"  Cluster #{pg.cluster_id}: {pg.description[:100]}...")
    else:
        log.info("\nSkipping AI descriptions (--no-describe)")

    # ── 4. Save latest detection ──────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    detection = {
        "detected_at": now,
        "parameters": {"eps": args.eps, "min_samples": args.min_samples},
        "total_clusters": len(clusters),
        "clusters": [pg.to_dict() for pg in clusters],
    }

    LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_FILE.write_text(json.dumps(detection, indent=2), encoding="utf-8")
    log.info(f"\nLatest detection saved → {LATEST_FILE}")

    # ── 5. Compare with previous run ──────────────────────────────
    history = _load_history()

    if history:
        prev = history[-1]
        prev_ids = {c["cluster_id"] for c in prev.get("clusters", [])}
        curr_ids = {c["cluster_id"] for c in detection["clusters"]}
        prev_sizes = {c["cluster_id"]: c["size"] for c in prev.get("clusters", [])}
        curr_sizes = {c["cluster_id"]: c["size"] for c in detection["clusters"]}

        new_clusters = curr_ids - prev_ids
        lost_clusters = prev_ids - curr_ids
        stable_clusters = curr_ids & prev_ids

        log.info(f"\nCompared with previous run ({prev.get('detected_at', '?')}):")
        log.info(f"  New clusters: {len(new_clusters)}")
        log.info(f"  Lost clusters: {len(lost_clusters)}")
        log.info(f"  Stable clusters: {len(stable_clusters)}")

        for cid in stable_clusters:
            delta = curr_sizes.get(cid, 0) - prev_sizes.get(cid, 0)
            if delta > 0:
                log.info(f"    Cluster #{cid}: grew by {delta} artists")
            elif delta < 0:
                log.info(f"    Cluster #{cid}: shrank by {abs(delta)} artists")
    else:
        log.info("\nNo previous detection to compare against.")

    # ── 6. Append to history ──────────────────────────────────────
    # Keep a compact summary in history (not full artist data)
    summary = {
        "detected_at": now,
        "parameters": {"eps": args.eps, "min_samples": args.min_samples},
        "total_clusters": len(clusters),
        "clusters": [
            {
                "cluster_id": pg.cluster_id,
                "size": pg.size,
                "cohesion_score": round(pg.cohesion_score, 3),
                "avg_underground": round(pg.avg_underground, 3),
                "top_tags": pg.top_tags[:5],
                "geography": pg.geography[:3],
            }
            for pg in clusters
        ],
    }
    history.append(summary)
    # Keep last 50 runs
    if len(history) > 50:
        history = history[-50:]
    _save_history(history)
    log.info(f"History updated → {HISTORY_FILE} ({len(history)} runs)")

    log.info("\n" + "=" * 58)
    log.info("  Detection complete")
    log.info("=" * 58)


if __name__ == "__main__":
    main()

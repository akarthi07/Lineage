#!/usr/bin/env python3
"""
seed_database.py
────────────────
Seeds the 50 curated Lineage artists into Neo4j.

Steps per artist:
  1. seed_artist_network()  — resolves the artist, crawls MusicBrainz and
                               Last.fm at depth=SEED_DEPTH, stores all nodes
                               and edges automatically.
  2. inject_known_edges()   — manually upserts the curated relationships from
                               seed_lineages.json. Captures connections APIs
                               are likely to miss (underground-to-underground,
                               producer links, cross-genre citations).

Progress is written to data/seed_progress.json after each artist.
Re-running the script skips already-completed artists safely.

Run from the Backend/ directory:
    python scripts/seed_database.py

Estimated runtime: 1–2 hours (MusicBrainz enforces 1 req/sec).
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Config must be imported before any service module so env vars are loaded
from config import settings  # noqa: F401
from services.artist_seeder import seed_artist_network
from services import graph_manager as gm
from services.identity_resolver import resolve_artist

# ── Paths ─────────────────────────────────────────────────────────────────────
LINEAGES_FILE = ROOT / "data" / "seed_lineages.json"
PROGRESS_FILE = ROOT / "data" / "seed_progress.json"
LOG_FILE      = ROOT / "data" / "seed_run.log"

# ── Tuning ────────────────────────────────────────────────────────────────────
SEED_DEPTH              = 2      # hard cap — depth 3 on well-connected artists takes hours
BETWEEN_ARTISTS_DELAY   = 3.0   # seconds — gives MB rate limiter breathing room
BETWEEN_EDGE_INJECTS    = 0.4   # seconds — between API calls inside inject_known_edges
MIN_EDGE_STRENGTH       = 0.30  # skip injecting edges below this threshold

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("seed_db")


# ── Progress helpers ──────────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Progress file corrupt — starting fresh")
    return {
        "completed": [],
        "failed": [],
        "started_at": None,
        "last_updated": None,
    }


def save_progress(progress: dict) -> None:
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


# ── Edge injection ────────────────────────────────────────────────────────────

def inject_known_edges(root_mbid: str, root_name: str, known_influences: list) -> int:
    """
    Manually upsert curated known_influences for one artist into Neo4j.

    Each entry in known_influences:
        artist           — name of the influence
        relationship_type — e.g. "influenced by", "from same scene"
        strength         — float 0–1
        confidence       — float 0–1
        source           — "musicbrainz" | "interview" | "editorial" | "research"
        notes            — optional string

    Returns the number of edges successfully injected.
    """
    injected = 0
    skipped  = 0

    for edge in known_influences:
        influence_name = edge.get("artist", "").strip()
        strength       = float(edge.get("strength",   0.6))
        confidence     = float(edge.get("confidence", 0.75))
        source         = edge.get("source", "research")
        rel_type       = edge.get("relationship_type", "influenced by")

        if not influence_name:
            continue
        if strength < MIN_EDGE_STRENGTH:
            skipped += 1
            continue

        try:
            # Resolve via Last.fm only — MB SSL is broken, Spotify is rate-limited
            influence = resolve_artist(influence_name, skip_mb=True, skip_spotify=True)
            if not influence or not influence.mbid:
                log.warning(f"    [inject] could not resolve {influence_name!r} — skipping")
                skipped += 1
                time.sleep(BETWEEN_EDGE_INJECTS)
                continue

            # Ensure the influence artist node exists
            gm.upsert_artist(influence)

            # Map source string to what graph_manager expects
            gm_source  = source if source in ("musicbrainz", "lastfm_similar", "tag_overlap") else "research"
            mb_type    = rel_type if source == "musicbrainz" else None

            gm.upsert_relationship(
                source_mbid=root_mbid,
                target_mbid=influence.mbid,
                strength=strength,
                confidence=confidence,
                source_type=gm_source,
                mb_type=mb_type,
                lastfm_match=None,
            )

            injected += 1
            log.info(f"    [inject] {root_name} → {influence_name}  ({strength:.2f}  {source})")

        except Exception as exc:
            log.error(f"    [inject] error on {influence_name!r}: {exc}")
            skipped += 1

        time.sleep(BETWEEN_EDGE_INJECTS)

    return injected


# ── Single-artist seeding ─────────────────────────────────────────────────────

def seed_one(artist_data: dict) -> bool:
    name    = artist_data["name"]
    tier    = artist_data.get("tier", "?")
    genre   = artist_data.get("genre_group", "?")
    depth   = min(artist_data.get("seed_depth", SEED_DEPTH), SEED_DEPTH)  # never exceed cap
    edges   = artist_data.get("known_influences", [])

    log.info(f"  Tier: {tier}  |  Genre: {genre}  |  Seed depth: {depth}")

    # ── Resolve root artist (Last.fm + Spotify only — MB skipped) ────────────
    # API-driven graph crawl is skipped: MusicBrainz bulk-request SSL failures
    # make it unusable for seeding. Curated edges in seed_lineages.json are the
    # primary data source. Users trigger fresh discovery on-demand via queries.
    root = None
    try:
        root = resolve_artist(name, skip_mb=True, skip_spotify=True)
        if root and root.mbid:
            gm.ensure_indexes()
            gm.upsert_artist(root)
            log.info(f"  ✓ Resolved — MBID: {root.mbid}")
        else:
            log.warning(f"  ⚠ Could not resolve {name!r} from any source")
    except Exception as exc:
        log.error(f"  ✗ Resolve failed for {name!r}: {exc}")

    # ── Inject curated edges ──────────────────────────────────────────────────
    if not edges:
        log.info("  — no curated edges for this artist")
        return root is not None

    root_mbid = root.mbid if root else None
    if not root_mbid:
        log.error(f"  Cannot inject curated edges — no MBID for {name!r}")
        return False

    injected = inject_known_edges(root_mbid, name, edges)
    log.info(f"  ✓ Injected {injected}/{len(edges)} curated edges")

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not LINEAGES_FILE.exists():
        log.error(f"Lineages file not found: {LINEAGES_FILE}")
        sys.exit(1)

    lineages = json.loads(LINEAGES_FILE.read_text(encoding="utf-8"))
    artists  = lineages["artists"]
    total    = len(artists)

    progress = load_progress()
    if not progress["started_at"]:
        progress["started_at"] = datetime.now(timezone.utc).isoformat()

    completed_set = set(progress["completed"])
    remaining     = total - len(completed_set)

    log.info("═" * 58)
    log.info(f"  Lineage Seed Run — {total} artists")
    log.info(f"  Already done : {len(completed_set)}")
    log.info(f"  To seed      : {remaining}")
    log.info(f"  Depth        : {SEED_DEPTH}")
    log.info("═" * 58)

    if remaining == 0:
        log.info("All artists already seeded. Nothing to do.")
        _print_summary(progress, total)
        return

    # Ensure Neo4j indexes exist before we start writing
    gm.ensure_indexes()

    for i, artist_data in enumerate(artists, 1):
        name = artist_data["name"]

        if name in completed_set:
            log.info(f"[{i:02d}/{total}] SKIP  {name!r}")
            continue

        log.info(f"\n[{i:02d}/{total}] ── {name} {'─' * max(0, 40 - len(name))}")

        success = seed_one(artist_data)

        if success:
            progress["completed"].append(name)
            completed_set.add(name)
            if name in progress["failed"]:
                progress["failed"].remove(name)
        else:
            if name not in progress["failed"]:
                progress["failed"].append(name)
            log.warning(f"  ↳ {name!r} marked as failed — will retry on next run")

        save_progress(progress)

        # Throttle between artists
        if i < total and name not in (progress.get("completed") or []):
            pass  # already failed, no need to wait
        elif i < total:
            log.info(f"  ⏳ Waiting {BETWEEN_ARTISTS_DELAY}s before next artist…")
            time.sleep(BETWEEN_ARTISTS_DELAY)

    _print_summary(progress, total)


def _print_summary(progress: dict, total: int) -> None:
    done   = len(progress["completed"])
    failed = len(progress["failed"])
    log.info("\n" + "═" * 58)
    log.info("  Seed Run Complete")
    log.info(f"  Completed : {done}/{total}")
    log.info(f"  Failed    : {failed}")
    if progress["failed"]:
        log.info(f"  Failed artists :")
        for name in progress["failed"]:
            log.info(f"    • {name}")
    log.info(f"  Log file  : {LOG_FILE}")
    log.info(f"  Progress  : {PROGRESS_FILE}")
    log.info("═" * 58)

    if failed > 0:
        log.info("\nTo retry failed artists, just re-run the script.")
        log.info("Completed artists will be skipped automatically.")


if __name__ == "__main__":
    main()

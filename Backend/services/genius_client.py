"""Genius API client — fetches song lyrics. Cached in Redis (7 days)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

import redis

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 7  # 7 days


def _get_redis() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def _get_genius():
    """Lazy-init the lyricsgenius client."""
    import lyricsgenius

    token = os.getenv("GENIUS_API_TOKEN", "")
    if not token:
        logger.warning("GENIUS_API_TOKEN not set — lyrics unavailable")
        return None

    genius = lyricsgenius.Genius(
        token,
        timeout=15,
        retries=2,
        verbose=False,
        remove_section_headers=True,
    )
    genius.excluded_terms = ["(Remix)", "(Live)", "(Demo)"]
    return genius


def get_lyrics(track_name: str, artist_name: str) -> Optional[str]:
    """
    Fetch lyrics for a track. Returns the lyrics text or None.
    Results are cached in Redis for 7 days.
    """
    cache_key = f"genius:lyrics:{hashlib.md5(f'{artist_name}:{track_name}'.lower().encode()).hexdigest()[:16]}"

    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return cached if cached != "__none__" else None
    except Exception:
        pass

    genius = _get_genius()
    if genius is None:
        return None

    try:
        song = genius.search_song(track_name, artist_name)
        if song and song.lyrics:
            lyrics = _clean_lyrics(song.lyrics)
            try:
                r = _get_redis()
                r.setex(cache_key, CACHE_TTL, lyrics)
            except Exception:
                pass
            return lyrics
    except Exception as exc:
        logger.error(f"Genius search failed for {artist_name} - {track_name}: {exc}")

    # Cache the miss
    try:
        r = _get_redis()
        r.setex(cache_key, CACHE_TTL, "__none__")
    except Exception:
        pass

    return None


def _clean_lyrics(raw: str) -> str:
    """Remove common Genius artifacts from lyrics text."""
    lines = raw.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        # Skip empty lines at start
        if not cleaned and not line:
            continue
        # Skip "XXX Lyrics" header and "Embed" footer
        if line.endswith("Lyrics") and len(cleaned) == 0:
            continue
        if line.startswith("Embed"):
            continue
        if line.endswith("Embed"):
            line = line[:-5].rstrip()
        cleaned.append(line)
    return "\n".join(cleaned).strip()

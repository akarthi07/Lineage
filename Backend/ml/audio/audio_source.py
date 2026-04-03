"""
Audio source resolver — finds playable audio URLs for tracks.

Primary source: Spotify 30-second preview URLs (free, no auth needed for playback).
About 50-60% of tracks have previews available.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

import redis
import requests

logger = logging.getLogger(__name__)

SPOTIFY_BASE = "https://api.spotify.com/v1"
CACHE_TTL = 86400 * 7  # 7 days


def _get_redis() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def _spotify_headers() -> Optional[dict]:
    """Get Spotify auth headers (reuses spotify_client token logic)."""
    from services.spotify_client import _headers
    return _headers()


def get_audio_url(track_name: str, artist_name: str) -> Optional[str]:
    """
    Resolve a playable audio URL for a track.

    Returns a Spotify preview URL (30-sec MP3) or None.
    """
    cache_key = f"audio:url:{hashlib.md5(f'{artist_name}:{track_name}'.lower().encode()).hexdigest()[:16]}"

    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return cached if cached != "__none__" else None
    except Exception:
        pass

    url = _search_spotify_preview(track_name, artist_name)

    try:
        r = _get_redis()
        r.setex(cache_key, CACHE_TTL, url or "__none__")
    except Exception:
        pass

    return url


def _search_spotify_preview(track_name: str, artist_name: str) -> Optional[str]:
    """Search Spotify for a track and return its preview_url."""
    headers = _spotify_headers()
    if not headers:
        return None

    query = f"track:{track_name} artist:{artist_name}"
    try:
        resp = requests.get(
            f"{SPOTIFY_BASE}/search",
            params={"q": query, "type": "track", "limit": 3},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])

        for item in items:
            preview = item.get("preview_url")
            if preview:
                return preview

        return None
    except Exception as exc:
        logger.error(f"Spotify track search failed: {exc}")
        return None


def get_artist_top_tracks(artist_name: str, spotify_id: Optional[str] = None) -> list[dict]:
    """
    Get an artist's top tracks from Spotify.

    Returns list of {name, preview_url, spotify_id, album}.
    """
    cache_key = f"audio:top_tracks:{hashlib.md5(artist_name.lower().encode()).hexdigest()[:16]}"

    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # Resolve spotify_id if not provided
    if not spotify_id:
        from services.spotify_client import search_artist
        result = search_artist(artist_name)
        if result:
            spotify_id = result.get("id")

    if not spotify_id:
        return []

    headers = _spotify_headers()
    if not headers:
        return []

    try:
        resp = requests.get(
            f"{SPOTIFY_BASE}/artists/{spotify_id}/top-tracks",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        tracks = resp.json().get("tracks", [])

        result = []
        for t in tracks:
            result.append({
                "name": t.get("name", ""),
                "preview_url": t.get("preview_url"),
                "spotify_id": t.get("id", ""),
                "album": t.get("album", {}).get("name", ""),
            })

        try:
            r = _get_redis()
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

        return result
    except Exception as exc:
        logger.error(f"Spotify top tracks failed for {artist_name}: {exc}")
        return []

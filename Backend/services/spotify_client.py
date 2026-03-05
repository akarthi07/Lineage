"""Spotify API client — supplementary source for metadata and images only.

NOTE: Related Artists, Audio Features, and Recommendations are DEPRECATED
for new apps (403). Do NOT call those endpoints.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
import requests
import redis
from typing import Optional

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_BASE = "https://api.spotify.com/v1"

_token: Optional[str] = None
_token_expiry: float = 0.0


def _get_redis() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def _get_token() -> Optional[str]:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry - 30:
        return _token

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("[Spotify] SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not set")
        return None

    try:
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _token_expiry = time.time() + data["expires_in"]
        return _token
    except Exception as exc:
        print(f"[Spotify] Token fetch error: {exc}")
        return None


def _headers() -> Optional[dict]:
    token = _get_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def search_artist(name: str) -> Optional[dict]:
    """Search Spotify for an artist. Returns dict with id, name, genres, popularity, followers, images."""
    query_hash = hashlib.md5(name.lower().encode()).hexdigest()[:12]
    cache_key = f"spotify:search:{query_hash}"

    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    headers = _headers()
    if not headers:
        return None

    try:
        resp = requests.get(
            f"{SPOTIFY_BASE}/search",
            params={"q": name, "type": "artist", "limit": 5},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("artists", {}).get("items", [])
        if not items:
            return None

        # Prefer exact name match
        best = None
        for a in items:
            if a.get("name", "").lower() == name.lower():
                best = a
                break
        if best is None:
            best = items[0]

        result = _parse_artist(best)

        try:
            r = _get_redis()
            r.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

        return result
    except Exception as exc:
        print(f"[Spotify] search_artist error for '{name}': {exc}")
        return None


def get_artist(spotify_id: str) -> Optional[dict]:
    """Get artist metadata by Spotify ID."""
    cache_key = f"spotify:artist:{spotify_id}"

    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    headers = _headers()
    if not headers:
        return None

    try:
        resp = requests.get(
            f"{SPOTIFY_BASE}/artists/{spotify_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        result = _parse_artist(resp.json())

        try:
            r = _get_redis()
            r.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

        return result
    except Exception as exc:
        print(f"[Spotify] get_artist error for id '{spotify_id}': {exc}")
        return None


def _parse_artist(data: dict) -> dict:
    images = data.get("images", [])
    image_url = images[0]["url"] if images else None
    return {
        "id": data.get("id", ""),
        "name": data.get("name", ""),
        "genres": data.get("genres", []),
        "popularity": data.get("popularity"),
        "followers": data.get("followers", {}).get("total"),
        "image_url": image_url,
        "spotify_url": data.get("external_urls", {}).get("spotify", ""),
    }

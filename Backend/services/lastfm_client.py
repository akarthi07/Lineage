"""Last.fm API client — primary source for similar artists and listener data."""
from __future__ import annotations
import json
import os
import time
import requests
import redis
from typing import Optional

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"
_last_request_time: float = 0.0


def _get_redis() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def _api_key() -> str:
    key = os.getenv("LASTFM_API_KEY", "")
    if not key:
        raise RuntimeError("LASTFM_API_KEY not set in environment")
    return key


def _rate_limit() -> None:
    """Enforce Last.fm 5 req/sec soft limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 0.21:
        time.sleep(0.21 - elapsed)
    _last_request_time = time.time()


def _get(params: dict) -> Optional[dict]:
    _rate_limit()
    params["api_key"] = _api_key()
    params["format"] = "json"
    try:
        resp = requests.get(LASTFM_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            print(f"[Last.fm] API error {data['error']}: {data.get('message', '')}")
            return None
        return data
    except Exception as exc:
        print(f"[Last.fm] Request error: {exc}")
        return None


def get_similar_artists(name: str, limit: int = 50) -> list[dict]:
    """
    Returns list of similar artists with match scores.
    Each dict has: name, match (float 0-1), mbid (may be empty), url.
    """
    cache_key = f"lastfm:artist:{name.lower()}:similar"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get({"method": "artist.getSimilar", "artist": name, "limit": limit})
    if not data:
        return []

    similar = data.get("similarartists", {}).get("artist", [])
    result = []
    for s in similar:
        result.append({
            "name": s.get("name", ""),
            "match": float(s.get("match", 0)),
            "mbid": s.get("mbid", ""),
            "url": s.get("url", ""),
        })

    try:
        r = _get_redis()
        r.setex(cache_key, 21600, json.dumps(result))  # 6 hours
    except Exception:
        pass

    return result


def get_artist_info(name: str) -> Optional[dict]:
    """
    Returns artist info: listeners, playcount, bio, mbid, tags, url.
    """
    cache_key = f"lastfm:artist:{name.lower()}:info"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get({"method": "artist.getInfo", "artist": name, "autocorrect": 1})
    if not data:
        return None

    artist = data.get("artist")
    if not artist:
        return None

    stats = artist.get("stats", {})
    result = {
        "name": artist.get("name", name),
        "mbid": artist.get("mbid", ""),
        "url": artist.get("url", ""),
        "listeners": int(stats.get("listeners", 0)),
        "playcount": int(stats.get("playcount", 0)),
        "bio": artist.get("bio", {}).get("summary", ""),
        "tags": [t["name"] for t in artist.get("tags", {}).get("tag", [])],
        "image": next(
            (img["#text"] for img in artist.get("image", []) if img.get("size") == "extralarge"),
            None,
        ),
    }

    try:
        r = _get_redis()
        r.setex(cache_key, 21600, json.dumps(result))
    except Exception:
        pass

    return result


def get_artist_tags(name: str) -> list[dict]:
    """
    Returns top tags with vote counts: [{name, count}].
    """
    cache_key = f"lastfm:artist:{name.lower()}:tags"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get({"method": "artist.getTopTags", "artist": name, "autocorrect": 1})
    if not data:
        return []

    tags = data.get("toptags", {}).get("tag", [])
    result = [{"name": t["name"], "count": int(t.get("count", 0))} for t in tags]

    try:
        r = _get_redis()
        r.setex(cache_key, 21600, json.dumps(result))
    except Exception:
        pass

    return result

"""MusicBrainz API client — primary source for curated artist relationships."""
from __future__ import annotations
import time
import json
import os
import certifi
import requests
import redis
from typing import Optional

MB_BASE = "https://musicbrainz.org/ws/2"
_last_request_time: float = 0.0

# Retry config for transient SSL/network errors
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds to wait before each retry


def _get_redis() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)


def _rate_limit() -> None:
    """Enforce MusicBrainz 1 req/sec rate limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_request_time = time.time()


def _headers() -> dict:
    ua = os.getenv("MUSICBRAINZ_USER_AGENT", "Lineage/1.0 (lineage@example.com)")
    return {"User-Agent": ua, "Accept": "application/json"}


def _get_with_retry(url: str, params: dict) -> Optional[dict]:
    """Make a GET request with retry logic for transient SSL/network errors."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        _rate_limit()
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=15, verify=certifi.where())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            wait = RETRY_BACKOFF[attempt]
            print(f"[MusicBrainz] Attempt {attempt + 1}/{MAX_RETRIES} failed: {type(exc).__name__}. Retrying in {wait}s...")
            time.sleep(wait)
    print(f"[MusicBrainz] All {MAX_RETRIES} attempts failed: {last_exc}")
    return None


def search_artist(name: str) -> Optional[dict]:
    """Search MusicBrainz for an artist by name. Returns the best match dict."""
    cache_key = f"mb:search:{name.lower()}"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(f"{MB_BASE}/artist/", {"query": name, "fmt": "json", "limit": 5})
    if not data:
        return None

    artists = data.get("artists", [])
    if not artists:
        return None

    # Pick the best match: prefer exact name match, then highest score
    best = None
    for a in artists:
        if a.get("name", "").lower() == name.lower():
            best = a
            break
    if best is None:
        best = artists[0]

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(best))
    except Exception:
        pass

    return best


def get_artist(mbid: str) -> Optional[dict]:
    """Get basic artist metadata from MusicBrainz by MBID."""
    cache_key = f"mb:artist:{mbid}"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(f"{MB_BASE}/artist/{mbid}", {"fmt": "json"})
    if not data:
        return None

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(data))
    except Exception:
        pass

    return data


def get_artist_relationships(mbid: str) -> list[dict]:
    """
    Fetch artist with ?inc=artist-rels+tags and return parsed relationship list.

    Each returned dict has:
      - type: str (e.g. "influenced by", "member of band", "collaboration")
      - direction: str ("forward" | "backward")
      - artist: dict with name, id (mbid)
      - attributes: list[str]
    """
    cache_key = f"mb:artist:{mbid}:rels"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(f"{MB_BASE}/artist/{mbid}", {"inc": "artist-rels+tags", "fmt": "json"})
    if not data:
        return []

    relations = data.get("relations", [])
    artist_rels = []
    for rel in relations:
        if rel.get("target-type") != "artist":
            continue
        artist_rels.append({
            "type": rel.get("type", ""),
            "direction": rel.get("direction", "forward"),
            "artist": rel.get("artist", {}),
            "attributes": rel.get("attributes", []),
        })

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(artist_rels))
    except Exception:
        pass

    return artist_rels


def get_artist_recordings(mbid: str, limit: int = 25) -> list[dict]:
    """
    Get an artist's recordings (tracks) from MusicBrainz.
    Returns list of {mbid, title, first_release_year}.
    """
    cache_key = f"mb:artist:{mbid}:recordings"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(
        f"{MB_BASE}/recording/",
        {"artist": mbid, "limit": limit, "fmt": "json"},
    )
    if not data:
        return []

    recordings = []
    for rec in data.get("recordings", []):
        year = None
        frd = rec.get("first-release-date", "")
        if frd and len(frd) >= 4:
            try:
                year = int(frd[:4])
            except ValueError:
                pass
        recordings.append({
            "mbid": rec.get("id", ""),
            "title": rec.get("title", ""),
            "first_release_year": year,
        })

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(recordings))
    except Exception:
        pass

    return recordings


def get_recording_credits(recording_mbid: str) -> list[dict]:
    """
    Fetch recording credits (producer, engineer, mixer, etc.) from MusicBrainz.

    Uses ?inc=artist-rels on the recording endpoint.
    Returns list of {type, artist_mbid, artist_name, role}.
    """
    cache_key = f"mb:recording:{recording_mbid}:credits"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(
        f"{MB_BASE}/recording/{recording_mbid}",
        {"inc": "artist-rels+recording-rels", "fmt": "json"},
    )
    if not data:
        return []

    credits = []

    # Artist relationships on the recording (producer, engineer, etc.)
    for rel in data.get("relations", []):
        rel_type = rel.get("type", "")
        target_type = rel.get("target-type", "")

        if target_type == "artist":
            artist = rel.get("artist", {})
            role = rel_type.lower()
            # Filter to production-relevant roles
            if any(keyword in role for keyword in [
                "producer", "engineer", "mix", "master", "remix",
                "arranger", "programming", "recording",
            ]):
                credits.append({
                    "type": rel_type,
                    "artist_mbid": artist.get("id", ""),
                    "artist_name": artist.get("name", ""),
                    "role": role,
                })

        # Recording-recording relationships (samples)
        elif target_type == "recording":
            other_rec = rel.get("recording", {})
            if "sample" in rel.get("type", "").lower():
                credits.append({
                    "type": "samples",
                    "recording_mbid": other_rec.get("id", ""),
                    "recording_title": other_rec.get("title", ""),
                    "role": "samples",
                })

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(credits))
    except Exception:
        pass

    return credits


def get_artist_tags(mbid: str) -> list[dict]:
    """Return tags from a full artist+tags lookup (cached alongside rels call)."""
    cache_key = f"mb:artist:{mbid}:tags"
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    data = _get_with_retry(f"{MB_BASE}/artist/{mbid}", {"inc": "tags", "fmt": "json"})
    if not data:
        return []

    tags = data.get("tags", [])

    try:
        r = _get_redis()
        r.setex(cache_key, 86400, json.dumps(tags))
    except Exception:
        pass

    return tags

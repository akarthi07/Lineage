"""Cross-source identity resolution: name → unified Artist object."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from models.artist import Artist
from services import musicbrainz_client as mb
from services import lastfm_client as lastfm
from services import spotify_client as spotify
from services.underground_scorer import calculate_underground_score


def _parse_year(year_str: Optional[str]) -> Optional[int]:
    if not year_str:
        return None
    try:
        return int(str(year_str)[:4])
    except (ValueError, TypeError):
        return None


def resolve_artist(
    name: str,
    skip_mb: bool = False,
    skip_spotify: bool = False,
) -> Optional[Artist]:
    """
    Resolve an artist name across MusicBrainz, Last.fm, and Spotify.
    Returns a unified Artist object, or None if not found anywhere.

    skip_mb      — skip MusicBrainz lookup (use when MB is rate-limited or SSL-broken)
    skip_spotify — skip Spotify lookup (use when Spotify is rate-limited)
    """
    mb_data: Optional[dict] = None
    lastfm_data: Optional[dict] = None
    spotify_data: Optional[dict] = None

    # --- MusicBrainz ---
    if not skip_mb:
        mb_result = mb.search_artist(name)
        if mb_result:
            mbid = mb_result.get("id")
            if mbid:
                mb_data = mb.get_artist(mbid) or mb_result
            else:
                mb_data = mb_result

    # --- Last.fm ---
    lastfm_data = lastfm.get_artist_info(name)

    # --- Spotify ---
    if not skip_spotify:
        spotify_data = spotify.search_artist(name)

    # Need at least one source
    if not mb_data and not lastfm_data and not spotify_data:
        return None

    # --- Merge: canonical name ---
    artist_name = name
    if mb_data:
        artist_name = mb_data.get("name", name)
    elif lastfm_data:
        artist_name = lastfm_data.get("name", name)

    # --- MBID (real or synthetic fallback) ---
    mbid = None
    if mb_data:
        mbid = mb_data.get("id")
    if not mbid and lastfm_data:
        mbid = lastfm_data.get("mbid") or None
    # Synthetic stable ID so underground artists without MusicBrainz entries can still be stored
    if not mbid:
        if spotify_data and spotify_data.get("id"):
            mbid = f"spotify:{spotify_data['id']}"
        elif lastfm_data and lastfm_data.get("url"):
            mbid = f"lastfm:{artist_name.lower().replace(' ', '_')}"

    # --- Spotify ID ---
    spotify_id = spotify_data.get("id") if spotify_data else None

    # --- Last.fm URL ---
    lastfm_url = lastfm_data.get("url") if lastfm_data else None

    # --- Listener / popularity data ---
    lastfm_listeners = lastfm_data.get("listeners") if lastfm_data else None
    lastfm_playcount = lastfm_data.get("playcount") if lastfm_data else None
    spotify_popularity = spotify_data.get("popularity") if spotify_data else None
    spotify_followers = spotify_data.get("followers") if spotify_data else None

    # --- Genres and tags (merge from all sources) ---
    all_tags: list[str] = []
    if lastfm_data:
        all_tags.extend(lastfm_data.get("tags", []))
    if spotify_data:
        all_tags.extend(spotify_data.get("genres", []))
    if mb_data:
        for tag in mb_data.get("tags", []):
            if isinstance(tag, dict):
                all_tags.append(tag.get("name", ""))
            elif isinstance(tag, str):
                all_tags.append(tag)

    # Deduplicate preserving order
    seen: set[str] = set()
    tags: list[str] = []
    genres: list[str] = []
    for t in all_tags:
        t_lower = t.lower().strip()
        if t_lower and t_lower not in seen:
            seen.add(t_lower)
            tags.append(t)
    # Genres = Spotify genres specifically
    if spotify_data:
        genres = spotify_data.get("genres", [])

    # --- Formation year and country (MusicBrainz) ---
    formation_year: Optional[int] = None
    country: Optional[str] = None
    if mb_data:
        life_span = mb_data.get("life-span", {})
        formation_year = _parse_year(life_span.get("begin"))
        country = mb_data.get("country") or mb_data.get("area", {}).get("name")

    # --- Image (Spotify > Last.fm) ---
    image_url: Optional[str] = None
    if spotify_data and spotify_data.get("image_url"):
        image_url = spotify_data["image_url"]
    elif lastfm_data and lastfm_data.get("image"):
        image_url = lastfm_data["image"]

    # --- Underground score ---
    underground_score = calculate_underground_score(lastfm_listeners, spotify_popularity)

    return Artist(
        mbid=mbid,
        spotify_id=spotify_id,
        lastfm_url=lastfm_url,
        name=artist_name,
        lastfm_listeners=lastfm_listeners,
        lastfm_playcount=lastfm_playcount,
        spotify_popularity=spotify_popularity,
        spotify_followers=spotify_followers,
        genres=genres,
        tags=tags,
        formation_year=formation_year,
        country=country,
        image_url=image_url,
        underground_score=underground_score,
        seeded_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )

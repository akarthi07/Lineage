"""
Batch audio feature extraction — extracts features for an artist's top tracks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ml.audio.feature_extractor import extract_features
from ml.audio.audio_source import get_audio_url
from services.lastfm_client import get_artist_top_tracks as lastfm_top_tracks

logger = logging.getLogger(__name__)


@dataclass
class SongFeature:
    track_name: str
    artist_name: str
    artist_mbid: str
    feature_vector: np.ndarray
    source_url: str
    album: str = ""


def extract_features_for_artist(
    artist_name: str,
    artist_mbid: str = "",
    spotify_id: Optional[str] = None,
    top_n_tracks: int = 5,
) -> list[SongFeature]:
    """
    Get an artist's top tracks and extract audio features from each.

    Returns list of SongFeature for tracks where audio was available.
    Budget ~5 seconds per track (download + extraction).
    """
    tracks = lastfm_top_tracks(artist_name, limit=top_n_tracks)
    if not tracks:
        logger.info(f"No top tracks found for {artist_name}")
        return []

    results = []
    for track in tracks[:top_n_tracks]:
        preview_url = track.get("preview_url")

        # If no preview in top tracks response, try searching
        if not preview_url:
            preview_url = get_audio_url(track["name"], artist_name)

        if not preview_url:
            logger.debug(f"No audio for {artist_name} - {track['name']}")
            continue

        logger.info(f"Extracting features: {artist_name} - {track['name']}")
        vec = extract_features(preview_url)
        if vec is None:
            continue

        results.append(SongFeature(
            track_name=track["name"],
            artist_name=artist_name,
            artist_mbid=artist_mbid,
            feature_vector=vec,
            source_url=preview_url,
            album=track.get("album", ""),
        ))

    logger.info(f"Extracted {len(results)}/{min(len(tracks), top_n_tracks)} tracks for {artist_name}")
    return results

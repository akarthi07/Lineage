"""Underground score calculation based on listener data."""
from typing import Optional


def calculate_underground_score(
    lastfm_listeners: Optional[int] = None,
    spotify_popularity: Optional[int] = None,
) -> float:
    """
    Returns a float 0.0 (mainstream) to 1.0 (deep underground).
    Uses Last.fm listeners as primary signal, Spotify popularity as fallback.
    """
    if lastfm_listeners is not None:
        if lastfm_listeners < 5_000:
            return 1.0
        elif lastfm_listeners < 20_000:
            return 0.85
        elif lastfm_listeners < 50_000:
            return 0.7
        elif lastfm_listeners < 100_000:
            return 0.5
        elif lastfm_listeners < 500_000:
            return 0.3
        elif lastfm_listeners < 1_000_000:
            return 0.15
        else:
            return 0.0

    if spotify_popularity is not None:
        if spotify_popularity < 20:
            return 0.9
        elif spotify_popularity < 40:
            return 0.6
        elif spotify_popularity < 60:
            return 0.3
        else:
            return 0.1

    # No data — assume somewhat underground
    return 0.5

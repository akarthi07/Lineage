"""
Production network seeder — fetches recording credits from MusicBrainz
and creates Producer nodes, PRODUCED_BY edges, and WORKED_WITH edges in Neo4j.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.musicbrainz_client import get_artist_recordings, get_recording_credits
from services.production_manager import (
    upsert_recording,
    upsert_producer,
    link_recording_producer,
    link_artist_producer,
    link_recording_samples,
)

logger = logging.getLogger(__name__)


def seed_production_credits(
    artist_mbid: str,
    artist_name: str,
    max_recordings: int = 10,
) -> dict:
    """
    Fetch top recordings for an artist, get credits for each,
    and create production nodes/edges in Neo4j.

    Returns stats: {recordings_checked, producers_found, samples_found}.
    """
    recordings = get_artist_recordings(artist_mbid, limit=max_recordings)
    if not recordings:
        return {"recordings_checked": 0, "producers_found": 0, "samples_found": 0}

    producers_found = 0
    samples_found = 0
    seen_producers = set()

    for rec in recordings[:max_recordings]:
        rec_mbid = rec.get("mbid", "")
        if not rec_mbid:
            continue

        # Create recording node
        upsert_recording(
            mbid=rec_mbid,
            title=rec.get("title", ""),
            artist_mbid=artist_mbid,
            year=rec.get("first_release_year"),
        )

        # Fetch credits
        credits = get_recording_credits(rec_mbid)

        for credit in credits:
            if credit.get("role") == "samples":
                # Sample relationship
                sampled_mbid = credit.get("recording_mbid", "")
                if sampled_mbid:
                    upsert_recording(
                        mbid=sampled_mbid,
                        title=credit.get("recording_title", ""),
                        artist_mbid="",  # unknown artist for sampled recording
                    )
                    link_recording_samples(rec_mbid, sampled_mbid)
                    samples_found += 1
            else:
                # Producer/engineer credit
                prod_mbid = credit.get("artist_mbid", "")
                prod_name = credit.get("artist_name", "")
                role = credit.get("role", "producer")

                if not prod_mbid:
                    continue

                upsert_producer(mbid=prod_mbid, name=prod_name)
                link_recording_producer(rec_mbid, prod_mbid, role=role)

                # Also link artist <-> producer
                if prod_mbid not in seen_producers:
                    link_artist_producer(artist_mbid, prod_mbid, role=role)
                    seen_producers.add(prod_mbid)
                    producers_found += 1

    return {
        "recordings_checked": len(recordings[:max_recordings]),
        "producers_found": producers_found,
        "samples_found": samples_found,
    }

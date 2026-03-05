from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Artist(BaseModel):
    # Primary identifiers
    mbid: Optional[str] = None
    spotify_id: Optional[str] = None
    lastfm_url: Optional[str] = None

    # Core metadata
    name: str
    disambiguation: Optional[str] = None

    # Listener/popularity data
    lastfm_listeners: Optional[int] = None
    lastfm_playcount: Optional[int] = None
    spotify_popularity: Optional[int] = None
    spotify_followers: Optional[int] = None

    # Genre/style data
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Origin data
    formation_year: Optional[int] = None
    country: Optional[str] = None

    # Media
    image_url: Optional[str] = None

    # Computed scores
    underground_score: float = 0.0

    # Timestamps
    seeded_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Relationship(BaseModel):
    source_mbid: str
    target_mbid: str
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "musicbrainz" | "lastfm_similar" | "tag_overlap" | "user_contributed"
    musicbrainz_type: Optional[str] = None
    lastfm_match: Optional[float] = None
    created_at: Optional[datetime] = None


class ArtistNode(BaseModel):
    """Artist enriched with depth for graph rendering."""
    id: str  # mbid
    name: str
    mbid: Optional[str] = None
    spotify_id: Optional[str] = None
    lastfm_listeners: Optional[int] = None
    spotify_popularity: Optional[int] = None
    underground_score: float = 0.0
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    formation_year: Optional[int] = None
    country: Optional[str] = None
    image_url: Optional[str] = None
    depth_level: int = 0


class Edge(BaseModel):
    source: str  # mbid
    target: str  # mbid
    strength: float
    source_type: str
    confidence: float
    musicbrainz_type: Optional[str] = None


class LineageResult(BaseModel):
    nodes: list[ArtistNode] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .artist import LineageResult


class ParsedQuery(BaseModel):
    query_type: Literal[
        "artist_lineage", "discovery", "genesis", "connection", "clarification_needed"
    ]
    artist_names: list[str] = Field(default_factory=list)
    direction: Literal["backward", "forward", "both"] = "backward"
    depth: int = Field(default=3, ge=1, le=10)
    underground_preference: Literal["surface", "balanced", "deep"] = "balanced"
    musical_characteristics: list[str] = Field(default_factory=list)
    mood_descriptors: list[str] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    era_filter: Optional[str] = None
    geo_filter: Optional[str] = None
    clarification_question: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    depth: int = Field(default=3, ge=1, le=10)
    underground_level: Literal["surface", "balanced", "deep"] = "balanced"


class QueryResponse(BaseModel):
    query_id: str
    query_type: str
    parsed: dict
    results: LineageResult

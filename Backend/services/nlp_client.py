"""Claude NLP client — parses natural language queries into structured search parameters."""
from __future__ import annotations

import json
import hashlib
import logging
import os
from typing import Optional

import anthropic
import redis

from models.query import ParsedQuery
from services.prompts import (
    QUERY_PARSE_SYSTEM,
    DISCOVERY_SYSTEM,
    CLARIFICATION_SYSTEM,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis helper
# ---------------------------------------------------------------------------
_NLP_CACHE_TTL = 60 * 60 * 6  # 6 hours


def _get_redis() -> redis.Redis:
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )


def _cache_key(prefix: str, text: str) -> str:
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"nlp:{prefix}:{h}"


# ---------------------------------------------------------------------------
# Claude API helper with retry
# ---------------------------------------------------------------------------
_client: Optional[anthropic.Anthropic] = None
MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 2


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to Backend/.env"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _call_claude(system: str, user_message: str, max_tokens: int = 1024) -> str:
    """Send a message to Claude and return the text response. Retries on failure."""
    client = _get_client()
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            logger.warning(f"Claude rate-limited (attempt {attempt + 1})")
            last_error = "Rate limited by Claude API"
        except anthropic.APIError as e:
            logger.warning(f"Claude API error (attempt {attempt + 1}): {e}")
            last_error = str(e)

    raise RuntimeError(f"Claude API failed after {MAX_RETRIES + 1} attempts: {last_error}")


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from Claude's response, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


# ---------------------------------------------------------------------------
# 2.1 — Main query parser
# ---------------------------------------------------------------------------
def parse_query(raw_text: str) -> ParsedQuery:
    """
    Parse a natural language query into a structured ParsedQuery using Claude.
    Results are cached in Redis for 6 hours.
    """
    # Check cache
    cache_key = _cache_key("parse", raw_text)
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            logger.info(f"NLP cache hit: {cache_key}")
            return ParsedQuery(**json.loads(cached))
    except redis.ConnectionError:
        logger.warning("Redis unavailable — skipping NLP cache")

    # Call Claude
    raw_response = _call_claude(QUERY_PARSE_SYSTEM, raw_text)
    parsed_dict = _parse_json_response(raw_response)
    result = ParsedQuery(**parsed_dict)

    # Cache result
    try:
        r = _get_redis()
        r.setex(cache_key, _NLP_CACHE_TTL, result.model_dump_json())
    except redis.ConnectionError:
        pass

    logger.info(f"Parsed query: type={result.query_type}, artists={result.artist_names}")
    return result


# ---------------------------------------------------------------------------
# 2.3 — Discovery mode: abstract modifiers → concrete search params
# ---------------------------------------------------------------------------
def resolve_discovery(parsed: ParsedQuery) -> dict:
    """
    Takes a ParsedQuery (typically a discovery query) and returns concrete
    search parameters — tags, seed artists, popularity range, etc.
    """
    # Build context string from the parsed query
    context_parts = []
    if parsed.artist_names:
        context_parts.append(f"Similar to: {', '.join(parsed.artist_names)}")
    if parsed.musical_characteristics:
        context_parts.append(f"Genres/styles: {', '.join(parsed.musical_characteristics)}")
    if parsed.mood_descriptors:
        context_parts.append(f"Mood: {', '.join(parsed.mood_descriptors)}")
    if parsed.modifiers:
        context_parts.append(f"Modifiers: {', '.join(parsed.modifiers)}")
    if parsed.era_filter:
        context_parts.append(f"Era: {parsed.era_filter}")
    if parsed.geo_filter:
        context_parts.append(f"Region: {parsed.geo_filter}")
    context_parts.append(f"Underground preference: {parsed.underground_preference}")

    user_message = "\n".join(context_parts)

    # Check cache
    cache_key = _cache_key("discovery", user_message)
    try:
        r = _get_redis()
        cached = r.get(cache_key)
        if cached:
            logger.info(f"Discovery cache hit: {cache_key}")
            return json.loads(cached)
    except redis.ConnectionError:
        pass

    raw_response = _call_claude(DISCOVERY_SYSTEM, user_message)
    result = _parse_json_response(raw_response)

    # Cache
    try:
        r = _get_redis()
        r.setex(cache_key, _NLP_CACHE_TTL, json.dumps(result))
    except redis.ConnectionError:
        pass

    logger.info(f"Discovery resolved: tags={result.get('search_tags', [])}")
    return result


# ---------------------------------------------------------------------------
# 2.4 — Clarification follow-up
# ---------------------------------------------------------------------------
def parse_clarification(
    original_query: str,
    clarification_question: str,
    user_response: str,
) -> ParsedQuery:
    """
    Resolve a clarification exchange into a final ParsedQuery.
    Called when the first parse returned clarification_needed and the user replied.
    """
    user_message = (
        f"Original query: {original_query}\n"
        f"Clarification asked: {clarification_question}\n"
        f"User's response: {user_response}"
    )

    raw_response = _call_claude(CLARIFICATION_SYSTEM, user_message)
    parsed_dict = _parse_json_response(raw_response)
    return ParsedQuery(**parsed_dict)

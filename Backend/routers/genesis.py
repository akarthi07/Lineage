"""Genesis Mode endpoints — curated proto-genre showcase."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"


@router.get(
    "/featured",
    summary="Get the curated featured proto-genre showcase",
)
async def get_featured_genesis():
    """
    Returns the manually curated Genesis Mode showcase —
    an emerging proto-genre with artists, geography, timeline, and lineage roots.
    """
    path = _DATA_DIR / "featured_genesis.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Genesis data not yet available.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"Failed to read featured_genesis.json: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load genesis data.")

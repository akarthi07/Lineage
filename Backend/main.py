"""
Lineage — FastAPI application entry point.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import query, artists, genesis, search
from services import graph_manager as gm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lineage")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Lineage API...")
    try:
        gm.ensure_indexes()
        logger.info("Neo4j indexes OK")
    except Exception as exc:
        logger.warning(f"Neo4j not reachable at startup: {exc}")
    yield
    logger.info("Shutting down — closing Neo4j driver")
    gm.close_driver()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Lineage API",
    description="Music genealogy and underground discovery platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path}  {response.status_code}  {duration:.0f}ms")
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(query.router,   prefix="/api/query",   tags=["Query"])
app.include_router(artists.router, prefix="/api/artist",  tags=["Artists"])
app.include_router(genesis.router, prefix="/api/genesis", tags=["Genesis"])
app.include_router(search.router,  prefix="/api/search",  tags=["Search"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["Health"])
async def health():
    """Returns service status and basic connectivity checks."""
    neo4j_ok = False
    try:
        driver = gm.get_driver()
        with driver.session() as session:
            session.run("RETURN 1")
        neo4j_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if neo4j_ok else "degraded",
        "version": "0.1.0",
        "services": {
            "neo4j": "ok" if neo4j_ok else "unreachable",
        },
    }

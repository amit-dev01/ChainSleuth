"""
ChainSleuth - Real-Time Cryptocurrency Fraud Tracing & Attribution System
Smart India Hackathon 2026 (SIH26183) &bull; Law Enforcement Edition

FastAPI application entrypoint with lifespan event management, CORS, and REST routers.
"""

from contextlib import asynccontextmanager
import logging
import sys
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.api.routes import trace, wallet, exchange, report, dashboard
from backend.config.settings import get_settings
from backend.storage.neo4j_client import neo4j_client
from backend.storage.postgres_client import init_db, engine
from backend.storage.redis_client import redis_client

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("chainsleuth")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup, database connection verifications, and graceful shutdown."""
    logger.info("Initializing ChainSleuth Backend services...")

    # 1. Initialize PostgreSQL schemas and verify connectivity
    try:
        await init_db()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL database connection verified successfully.")
    except Exception as exc:
        logger.warning("PostgreSQL verification notice: %s. Using local fallback.", exc)

    # 2. Connect to Redis cache & verify
    try:
        await redis_client.connect()
        logger.info("Redis cache connection verified successfully.")
    except Exception as exc:
        logger.warning("Redis verification notice: %s. Using in-memory fallback.", exc)

    # 3. Connect to Neo4j graph engine & verify
    try:
        await neo4j_client.connect()
        logger.info("Neo4j graph database connection verified successfully.")
    except Exception as exc:
        logger.warning("Neo4j verification notice: %s. Using in-memory fallback.", exc)

    logger.info("ChainSleuth Backend is ready for Law Enforcement operations.")
    yield

    logger.info("Shutting down ChainSleuth services...")
    await redis_client.close()
    await neo4j_client.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="ChainSleuth API",
    description=(
        "Real-Time Cryptocurrency Fraud Tracing & Attribution System for Indian Law Enforcement Agencies. "
        "Built for Smart India Hackathon 2026 (SIH26183)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api/v1 prefix
app.include_router(trace.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(exchange.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/", tags=["System"])
async def root() -> dict:
    """System identification endpoint."""
    return {
        "system": "ChainSleuth",
        "description": "Cryptocurrency Fraud Tracing & Attribution System for Indian LEAs",
        "hackathon": "Smart India Hackathon 2026 (SIH26183)",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "documentation": "/docs"
    }


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness and database connection verification check."""
    postgres_status = "DOWN"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        postgres_status = "UP"
    except Exception as exc:
        postgres_status = f"FALLBACK_OR_OFFLINE ({type(exc).__name__})"

    redis_status = "UP" if redis_client._connected else "IN_MEMORY_FALLBACK"
    neo4j_status = "UP" if neo4j_client._connected else "IN_MEMORY_FALLBACK"

    return {
        "status": "UP",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "services": {
            "api": "UP",
            "postgres": postgres_status,
            "neo4j": neo4j_status,
            "redis": redis_status
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unhandled exception fallback handler."""
    logger.error("Unhandled server exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred processing the blockchain intelligence request.",
            "path": request.url.path
        }
    )

"""
app/main.py
────────────
CLINICORE Backend — Main FastAPI Application

This is the entry point. It:
1. Creates the FastAPI app with metadata
2. Configures CORS (allowing the React frontend)
3. Adds security headers middleware
4. Registers all routers
5. Runs startup tasks (DB, storage, vector DB initialization)
6. Provides health check and API info endpoints

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
import asyncio
from loguru import logger

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import create_tables
from app.services.rag_service import ensure_collections_exist
from app.services.storage_service import ensure_bucket_exists

# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers import auth, folders, chats, messages, shares, research, audit


# ── Lifespan (startup + shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run startup tasks before accepting requests.
    Runs shutdown tasks when the server stops.
    """
    logger.info(f"🚀 Starting CLINICORE Backend ({settings.APP_ENV})")

    # ── Startup ───────────────────────────────────────────────────────────────

    # 1. Create database tables (with timeout to avoid blocking)
    logger.info("Creating database tables...")
    try:
        await asyncio.wait_for(create_tables(), timeout=10.0)
        logger.info("✅ Database ready")
    except asyncio.TimeoutError:
        logger.warning("⚠️  Database init timed out (will retry on first use)")
    except Exception as e:
        logger.warning(f"⚠️  Database init failed (will retry on first use): {e}")

    # 2. Create Qdrant collections if needed (with timeout)
    logger.info("Initializing Qdrant vector collections...")
    try:
        await asyncio.wait_for(asyncio.to_thread(ensure_collections_exist), timeout=5.0)
        logger.info("✅ Qdrant ready")
    except asyncio.TimeoutError:
        logger.warning("⚠️  Qdrant init timed out (will retry on first use)")
    except Exception as e:
        logger.warning(f"⚠️  Qdrant init failed (will retry on first use): {e}")

    # 3. Create MinIO bucket if needed (with timeout)
    logger.info("Initializing MinIO storage...")
    try:
        await asyncio.wait_for(asyncio.to_thread(ensure_bucket_exists), timeout=5.0)
        logger.info("✅ MinIO ready")
    except asyncio.TimeoutError:
        logger.warning("⚠️  MinIO init timed out (will retry on first use)")
    except Exception as e:
        logger.warning(f"⚠️  MinIO init failed (will retry on first use): {e}")

    logger.info("✅ CLINICORE Backend is ready to serve requests")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down CLINICORE Backend...")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="CLINICORE API",
    description=(
        "Secure, explainable medical AI agent for clinical decision support. "
        "Accepts text and images, provides structured diagnostic reasoning, "
        "research suggestions, and secure collaboration workflows."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,  # Disable Swagger in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ── Middleware ─────────────────────────────────────────────────────────────────

# CORS — allow the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-ID", "X-Request-ID"],
)

# Compression — gzip responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add HIPAA/security-relevant HTTP headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Request ID middleware (for distributed tracing)
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler.
    In production: logs full traceback, returns safe error message.
    In development: returns full error details.
    """
    logger.exception(f"Unhandled exception on {request.method} {request.url}: {exc}")

    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ── Prometheus Metrics ────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(folders.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(shares.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


# ── Health Checks ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check — returns 200 if the app is running."""
    return {"status": "healthy", "version": "1.0.0", "env": settings.APP_ENV}


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """
    Detailed health check — verifies all dependent services.
    Use this for load balancer health checks in production.
    """
    health = {
        "status": "healthy",
        "services": {},
    }

    # Check PostgreSQL
    try:
        from app.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health["services"]["postgresql"] = "healthy"
    except Exception as e:
        health["services"]["postgresql"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        health["services"]["redis"] = "healthy"
        await r.aclose()
    except Exception as e:
        health["services"]["redis"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check Qdrant
    try:
        from app.services.rag_service import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        health["services"]["qdrant"] = "healthy"
    except Exception as e:
        health["services"]["qdrant"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check MinIO
    try:
        from app.services.storage_service import get_minio_client
        client = get_minio_client()
        client.list_buckets()
        health["services"]["minio"] = "healthy"
    except Exception as e:
        health["services"]["minio"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    return health


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    return {
        "name": "CLINICORE API",
        "version": "1.0.0",
        "tagline": "Secure. Explainable. Always learning.",
        "docs": "/docs",
        "health": "/health",
    }

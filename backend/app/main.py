"""
AI Marketing Platform - FastAPI Application Entry Point

This is the main application file that configures and runs the FastAPI server.
"""

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from prometheus_client import make_asgi_app

from app.config import settings
from app.core.database import close_db, init_db
from app.middleware.security import setup_security_middleware

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# =============================================================================
# Sentry Error Tracking
# =============================================================================

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        profiles_sample_rate=0.1 if settings.is_production else 1.0,
        enable_tracing=True,
    )
    logger.info("sentry_initialized", environment=settings.environment)


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler for startup and shutdown events.
    """
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Initialize database connection pool
    # Note: In production, use Alembic migrations instead of init_db()
    # await init_db()
    logger.info("database_connected")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await close_db()
    logger.info("database_disconnected")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered marketing automation platform for Google, Meta, and TikTok Ads",
    docs_url="/api/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
    default_response_class=ORJSONResponse,  # Faster JSON serialization
    lifespan=lifespan,
)

# Setup security middleware (rate limiting, CORS, headers, logging)
setup_security_middleware(app)


# =============================================================================
# Prometheus Metrics
# =============================================================================

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic health check endpoint for load balancer and orchestration.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check - verifies the application can handle requests.

    Checks:
    - Database connectivity
    - Redis connectivity
    """
    from app.core.database import engine
    import redis.asyncio as redis

    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))

    # Check Redis
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))

    # Determine overall status
    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check - verifies the application process is running.

    This is a simple check that always returns healthy if the process is alive.
    """
    return {"status": "alive"}


# =============================================================================
# API Routers
# =============================================================================

# Import and include API routers
from app.api.v1 import router as api_v1_router

app.include_router(api_v1_router, prefix="/api/v1")


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.

    Logs the error and returns a generic error response.
    Never expose internal error details to clients.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return ORJSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )

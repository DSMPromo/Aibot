"""
Security middleware for the AI Marketing Platform.

Implements:
- Secure HTTP headers (SEC-013, SEC-014)
- Rate limiting (SEC-011, SEC-012)
- Request logging (SEC-034)
- CORS configuration

SECURITY CRITICAL: Changes require security review.
"""

import time
from typing import Callable

import secure
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = structlog.get_logger()


# =============================================================================
# Rate Limiting Setup (SEC-011, SEC-012)
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Get the real client IP, considering reverse proxy headers.

    Args:
        request: FastAPI request

    Returns:
        Client IP address
    """
    # Check X-Forwarded-For header (set by Caddy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct connection IP
    return get_remote_address(request)


# Create rate limiter with Redis backend for distributed limiting
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.rate_limit_api],
    storage_uri=settings.redis_url,
    strategy="fixed-window",  # or "moving-window" for stricter limiting
)


# =============================================================================
# Secure Headers Setup (SEC-013, SEC-014)
# =============================================================================

# Configure secure headers using the 'secure' library
secure_headers = secure.Secure(
    # Strict-Transport-Security
    hsts=secure.StrictTransportSecurity()
    .max_age(31536000)  # 1 year
    .include_subdomains()
    .preload(),

    # X-Frame-Options
    xfo=secure.XFrameOptions().deny(),

    # X-Content-Type-Options
    xxp=secure.XXSSProtection().set("1; mode=block"),

    # Content-Security-Policy
    csp=secure.ContentSecurityPolicy()
    .default_src("'self'")
    .script_src("'self'", "'unsafe-inline'", "'unsafe-eval'")  # Needed for React
    .style_src("'self'", "'unsafe-inline'")  # Needed for styled-components
    .img_src("'self'", "data:", "https:")
    .font_src("'self'", "data:")
    .connect_src("'self'", "https://api.stripe.com", "wss:")
    .frame_ancestors("'none'")
    .base_uri("'self'")
    .form_action("'self'"),

    # Referrer-Policy
    referrer=secure.ReferrerPolicy().strict_origin_when_cross_origin(),

    # Permissions-Policy (formerly Feature-Policy)
    permissions=secure.PermissionsPolicy()
    .geolocation("'none'")
    .camera("'none'")
    .microphone("'none'"),

    # Cache-Control for API responses
    cache=secure.CacheControl().no_store(),
)


# =============================================================================
# Request Logging Middleware (SEC-034)
# =============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests for security auditing.

    Logs:
    - Request method and path
    - Client IP
    - Response status code
    - Request duration
    - User agent
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timing
        start_time = time.time()

        # Get request details
        client_ip = get_client_ip(request)
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("User-Agent", "")

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log request (don't log health checks to reduce noise)
        if path != "/health":
            logger.info(
                "request",
                method=method,
                path=path,
                status=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=user_agent[:100],  # Truncate long user agents
            )

        return response


# =============================================================================
# Security Headers Middleware
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Apply secure headers
        secure_headers.framework.fastapi(response)

        # Additional headers not covered by secure library
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        return response


# =============================================================================
# Setup Function
# =============================================================================

def setup_security_middleware(app: FastAPI) -> None:
    """
    Configure all security middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Add rate limiter state
    app.state.limiter = limiter

    # Add rate limit exceeded handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add CORS middleware (must be added before other middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    logger.info(
        "security_middleware_configured",
        cors_origins=settings.cors_origins,
        rate_limit_api=settings.rate_limit_api,
        rate_limit_auth=settings.rate_limit_auth,
    )

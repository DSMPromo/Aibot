"""
Per-endpoint rate limiting utilities.

Provides decorators and helpers for applying specific rate limits
to sensitive endpoints like authentication, AI generation, etc.

Uses the global rate limiter from security middleware.
"""

from functools import wraps
from typing import Callable, Optional

import structlog
from fastapi import HTTPException, Request, status

from app.config import settings
from app.middleware.security import limiter, get_client_ip

logger = structlog.get_logger()


# =============================================================================
# Rate Limit Decorators
# =============================================================================


def rate_limit_auth(func: Callable) -> Callable:
    """
    Apply authentication-specific rate limiting.

    Uses settings.rate_limit_auth (default: 5/minute)
    Stricter than general API limits to prevent brute force.
    """
    @wraps(func)
    @limiter.limit(settings.rate_limit_auth)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def rate_limit_ai(func: Callable) -> Callable:
    """
    Apply AI endpoint rate limiting.

    Uses settings.rate_limit_ai (default: 10/minute)
    Protects expensive AI operations.
    """
    @wraps(func)
    @limiter.limit(settings.rate_limit_ai)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def rate_limit_export(func: Callable) -> Callable:
    """
    Apply export endpoint rate limiting.

    Protects resource-intensive export operations.
    """
    @wraps(func)
    @limiter.limit("5/minute")
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def rate_limit_webhook(func: Callable) -> Callable:
    """
    Apply webhook endpoint rate limiting.

    Higher limit for incoming webhooks from external services.
    """
    @wraps(func)
    @limiter.limit("100/minute")
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def rate_limit_strict(limit: str) -> Callable:
    """
    Apply a custom strict rate limit.

    Args:
        limit: Rate limit string (e.g., "3/minute", "10/hour")

    Usage:
        @router.post("/sensitive")
        @rate_limit_strict("3/minute")
        async def sensitive_endpoint():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @limiter.limit(limit)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# IP-Based Blocking
# =============================================================================


class IPBlocker:
    """
    Temporary IP blocking for suspicious activity.

    Works with Redis to maintain a blocklist.
    """

    BLOCK_KEY_PREFIX = "ip_block"
    DEFAULT_BLOCK_DURATION = 3600  # 1 hour

    def __init__(self):
        self._local_blocklist: set[str] = set()

    async def is_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked."""
        if ip in self._local_blocklist:
            return True

        try:
            from app.services.cache_service import cache_exists, CacheKey
            key = CacheKey.build(self.BLOCK_KEY_PREFIX, ip)
            return await cache_exists(key)
        except Exception:
            return False

    async def block_ip(
        self,
        ip: str,
        duration: int = DEFAULT_BLOCK_DURATION,
        reason: Optional[str] = None,
    ) -> None:
        """Block an IP address temporarily."""
        try:
            from app.services.cache_service import cache_set, CacheKey
            key = CacheKey.build(self.BLOCK_KEY_PREFIX, ip)
            await cache_set(key, {"reason": reason or "suspicious_activity"}, duration)
            logger.warning("ip_blocked", ip=ip, duration=duration, reason=reason)
        except Exception as e:
            logger.error("ip_block_failed", ip=ip, error=str(e))
            # Fallback to local blocklist
            self._local_blocklist.add(ip)

    async def unblock_ip(self, ip: str) -> None:
        """Unblock an IP address."""
        try:
            from app.services.cache_service import cache_delete, CacheKey
            key = CacheKey.build(self.BLOCK_KEY_PREFIX, ip)
            await cache_delete(key)
            self._local_blocklist.discard(ip)
            logger.info("ip_unblocked", ip=ip)
        except Exception as e:
            logger.error("ip_unblock_failed", ip=ip, error=str(e))


# Global IP blocker instance
ip_blocker = IPBlocker()


# =============================================================================
# Request Throttling Middleware
# =============================================================================


async def check_ip_block(request: Request) -> None:
    """
    Dependency to check if request IP is blocked.

    Usage:
        @router.post("/login")
        async def login(_: None = Depends(check_ip_block)):
            ...
    """
    ip = get_client_ip(request)
    if await ip_blocker.is_blocked(ip):
        logger.warning("blocked_ip_request", ip=ip, path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access temporarily blocked. Please try again later.",
        )


# =============================================================================
# Failed Attempt Tracking
# =============================================================================


class FailedAttemptTracker:
    """
    Track failed authentication attempts and auto-block after threshold.
    """

    ATTEMPT_KEY_PREFIX = "failed_attempts"
    MAX_ATTEMPTS = 5
    ATTEMPT_WINDOW = 900  # 15 minutes
    BLOCK_DURATION = 1800  # 30 minutes

    async def record_failure(self, ip: str, endpoint: str = "auth") -> bool:
        """
        Record a failed attempt.

        Returns True if IP should be blocked.
        """
        try:
            from app.services.cache_service import cache_get, cache_set, CacheKey
            from datetime import timedelta

            key = CacheKey.build(self.ATTEMPT_KEY_PREFIX, endpoint, ip)
            current = await cache_get(key)

            if current is None:
                attempts = 1
            else:
                attempts = int(current) + 1

            await cache_set(key, attempts, timedelta(seconds=self.ATTEMPT_WINDOW))

            if attempts >= self.MAX_ATTEMPTS:
                await ip_blocker.block_ip(
                    ip,
                    self.BLOCK_DURATION,
                    f"too_many_failed_{endpoint}_attempts",
                )
                logger.warning(
                    "ip_auto_blocked",
                    ip=ip,
                    endpoint=endpoint,
                    attempts=attempts,
                )
                return True

            return False

        except Exception as e:
            logger.error("failed_attempt_tracking_error", error=str(e))
            return False

    async def clear_attempts(self, ip: str, endpoint: str = "auth") -> None:
        """Clear failed attempts after successful authentication."""
        try:
            from app.services.cache_service import cache_delete, CacheKey
            key = CacheKey.build(self.ATTEMPT_KEY_PREFIX, endpoint, ip)
            await cache_delete(key)
        except Exception:
            pass


# Global failed attempt tracker
failed_attempts = FailedAttemptTracker()

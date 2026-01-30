"""
Redis caching service for production performance.

Provides:
- Key-value caching with TTL
- Cached query results for frequently accessed data
- Cache invalidation patterns
- Connection pooling for high throughput
"""

import json
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

import redis.asyncio as redis
import structlog

from app.config import settings

logger = structlog.get_logger()

T = TypeVar("T")

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


# =============================================================================
# Connection Management
# =============================================================================


async def get_redis() -> redis.Redis:
    """
    Get the Redis client instance.

    Returns:
        Redis client

    Raises:
        RuntimeError: If Redis is not initialized
    """
    global _redis_client
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def init_redis() -> None:
    """
    Initialize Redis connection pool.

    Should be called during application startup.
    """
    global _redis_client

    _redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )

    # Test connection
    try:
        await _redis_client.ping()
        logger.info("redis_connected", url=settings.redis_url.split("@")[-1])
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
        raise


async def close_redis() -> None:
    """
    Close Redis connection pool.

    Should be called during application shutdown.
    """
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_disconnected")


# =============================================================================
# Cache Operations
# =============================================================================


class CacheKey:
    """
    Cache key prefixes for different data types.

    Using consistent prefixes helps with:
    - Key organization
    - Pattern-based invalidation
    - Monitoring and debugging
    """

    # User data
    USER = "user"
    USER_SESSION = "user:session"
    USER_PERMISSIONS = "user:perms"

    # Organization data
    ORG = "org"
    ORG_LIMITS = "org:limits"
    ORG_SETTINGS = "org:settings"

    # Campaign data
    CAMPAIGN = "campaign"
    CAMPAIGN_LIST = "campaign:list"
    CAMPAIGN_METRICS = "campaign:metrics"

    # Analytics
    ANALYTICS = "analytics"
    DASHBOARD = "dashboard"

    # Rate limiting (used by slowapi)
    RATE_LIMIT = "ratelimit"

    # Billing
    SUBSCRIPTION = "subscription"
    USAGE = "usage"

    @staticmethod
    def build(*parts: str) -> str:
        """Build a cache key from parts."""
        return ":".join(str(p) for p in parts)


# Default TTLs for different cache types
class CacheTTL:
    """Default cache TTL values."""

    SHORT = timedelta(seconds=30)        # Rapidly changing data
    MEDIUM = timedelta(minutes=5)        # Moderately stable data
    LONG = timedelta(minutes=30)         # Stable data
    VERY_LONG = timedelta(hours=2)       # Rarely changing data
    DAY = timedelta(hours=24)            # Daily refreshed data

    # Specific TTLs
    SESSION = timedelta(hours=24)
    METRICS = timedelta(minutes=5)
    ANALYTICS_DASHBOARD = timedelta(minutes=2)
    SUBSCRIPTION = timedelta(hours=1)
    USAGE_LIMITS = timedelta(minutes=10)


async def cache_get(key: str) -> Optional[Any]:
    """
    Get a value from cache.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    try:
        client = await get_redis()
        value = await client.get(key)

        if value is None:
            return None

        # Try to parse as JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    except Exception as e:
        logger.warning("cache_get_error", key=key, error=str(e))
        return None


async def cache_set(
    key: str,
    value: Any,
    ttl: Optional[Union[int, timedelta]] = None,
) -> bool:
    """
    Set a value in cache.

    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized if not a string)
        ttl: Time to live in seconds or timedelta

    Returns:
        True if successful, False otherwise
    """
    try:
        client = await get_redis()

        # Serialize value
        if isinstance(value, str):
            serialized = value
        else:
            serialized = json.dumps(value, default=str)

        # Convert timedelta to seconds
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())

        # Set with optional TTL
        if ttl:
            await client.setex(key, ttl, serialized)
        else:
            await client.set(key, serialized)

        return True

    except Exception as e:
        logger.warning("cache_set_error", key=key, error=str(e))
        return False


async def cache_delete(key: str) -> bool:
    """
    Delete a key from cache.

    Args:
        key: Cache key

    Returns:
        True if key was deleted, False otherwise
    """
    try:
        client = await get_redis()
        result = await client.delete(key)
        return result > 0
    except Exception as e:
        logger.warning("cache_delete_error", key=key, error=str(e))
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.

    Args:
        pattern: Key pattern (e.g., "user:123:*")

    Returns:
        Number of keys deleted
    """
    try:
        client = await get_redis()
        deleted = 0

        # Use SCAN to find matching keys (safer than KEYS for production)
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1

        if deleted > 0:
            logger.info("cache_pattern_deleted", pattern=pattern, count=deleted)

        return deleted

    except Exception as e:
        logger.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
        return 0


async def cache_exists(key: str) -> bool:
    """
    Check if a key exists in cache.

    Args:
        key: Cache key

    Returns:
        True if key exists, False otherwise
    """
    try:
        client = await get_redis()
        return await client.exists(key) > 0
    except Exception as e:
        logger.warning("cache_exists_error", key=key, error=str(e))
        return False


async def cache_increment(key: str, amount: int = 1) -> Optional[int]:
    """
    Increment a counter in cache.

    Args:
        key: Cache key
        amount: Amount to increment by

    Returns:
        New value or None on error
    """
    try:
        client = await get_redis()
        return await client.incrby(key, amount)
    except Exception as e:
        logger.warning("cache_increment_error", key=key, error=str(e))
        return None


# =============================================================================
# Cache Decorator
# =============================================================================


def cached(
    key_prefix: str,
    ttl: Union[int, timedelta] = CacheTTL.MEDIUM,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for the cache key
        ttl: Time to live for cached value
        key_builder: Optional function to build cache key from args

    Usage:
        @cached("user", ttl=CacheTTL.LONG)
        async def get_user(user_id: str) -> User:
            ...

        @cached("analytics", key_builder=lambda org_id, date_range: f"{org_id}:{date_range}")
        async def get_analytics(org_id: str, date_range: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                key_suffix = key_builder(*args, **kwargs)
            else:
                # Default: use all args as key parts
                key_parts = [str(arg) for arg in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                key_suffix = ":".join(key_parts) if key_parts else "default"

            cache_key = CacheKey.build(key_prefix, key_suffix)

            # Try to get from cache
            cached_value = await cache_get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await cache_set(cache_key, result, ttl)
                logger.debug("cache_miss_stored", key=cache_key)

            return result

        return wrapper
    return decorator


# =============================================================================
# Cache Invalidation Helpers
# =============================================================================


async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate all cache entries for a user."""
    await cache_delete_pattern(f"{CacheKey.USER}:{user_id}:*")
    await cache_delete(CacheKey.build(CacheKey.USER, user_id))


async def invalidate_org_cache(org_id: str) -> None:
    """Invalidate all cache entries for an organization."""
    await cache_delete_pattern(f"{CacheKey.ORG}:{org_id}:*")
    await cache_delete_pattern(f"{CacheKey.CAMPAIGN_LIST}:{org_id}:*")
    await cache_delete_pattern(f"{CacheKey.ANALYTICS}:{org_id}:*")
    await cache_delete_pattern(f"{CacheKey.DASHBOARD}:{org_id}:*")


async def invalidate_campaign_cache(org_id: str, campaign_id: Optional[str] = None) -> None:
    """Invalidate campaign cache entries."""
    if campaign_id:
        await cache_delete(CacheKey.build(CacheKey.CAMPAIGN, campaign_id))
        await cache_delete_pattern(f"{CacheKey.CAMPAIGN_METRICS}:{campaign_id}:*")

    # Always invalidate list cache when campaigns change
    await cache_delete_pattern(f"{CacheKey.CAMPAIGN_LIST}:{org_id}:*")


async def invalidate_subscription_cache(org_id: str) -> None:
    """Invalidate subscription and usage cache."""
    await cache_delete(CacheKey.build(CacheKey.SUBSCRIPTION, org_id))
    await cache_delete(CacheKey.build(CacheKey.ORG_LIMITS, org_id))
    await cache_delete_pattern(f"{CacheKey.USAGE}:{org_id}:*")


# =============================================================================
# Cached Query Helpers
# =============================================================================


async def get_cached_subscription(org_id: str) -> Optional[dict]:
    """Get cached subscription data for an organization."""
    key = CacheKey.build(CacheKey.SUBSCRIPTION, org_id)
    return await cache_get(key)


async def cache_subscription(org_id: str, subscription_data: dict) -> None:
    """Cache subscription data for an organization."""
    key = CacheKey.build(CacheKey.SUBSCRIPTION, org_id)
    await cache_set(key, subscription_data, CacheTTL.SUBSCRIPTION)


async def get_cached_usage_limits(org_id: str) -> Optional[dict]:
    """Get cached usage limits for an organization."""
    key = CacheKey.build(CacheKey.ORG_LIMITS, org_id)
    return await cache_get(key)


async def cache_usage_limits(org_id: str, limits: dict) -> None:
    """Cache usage limits for an organization."""
    key = CacheKey.build(CacheKey.ORG_LIMITS, org_id)
    await cache_set(key, limits, CacheTTL.USAGE_LIMITS)


async def get_cached_dashboard(org_id: str, date_range: str) -> Optional[dict]:
    """Get cached dashboard data."""
    key = CacheKey.build(CacheKey.DASHBOARD, org_id, date_range)
    return await cache_get(key)


async def cache_dashboard(org_id: str, date_range: str, data: dict) -> None:
    """Cache dashboard data."""
    key = CacheKey.build(CacheKey.DASHBOARD, org_id, date_range)
    await cache_set(key, data, CacheTTL.ANALYTICS_DASHBOARD)

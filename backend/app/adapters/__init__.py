"""
Ad Platform Adapters

Factory pattern for creating platform-specific adapters.
Each adapter implements the BaseAdPlatformAdapter interface.
"""

from typing import Optional

from app.adapters.base import (
    AdAccountInfo,
    BaseAdPlatformAdapter,
    CampaignCreateRequest,
    CampaignInfo,
    CampaignMetrics,
    CampaignObjective,
    CampaignStatus,
    CampaignUpdateRequest,
    AdapterError,
    AuthenticationError,
    PlatformError,
    RateLimitError,
    ValidationError,
)
from app.adapters.google_ads import GoogleAdsAdapter
from app.adapters.meta_ads import MetaAdsAdapter
from app.adapters.tiktok_ads import TikTokAdsAdapter


# Adapter registry
_adapters: dict[str, type[BaseAdPlatformAdapter]] = {
    "google": GoogleAdsAdapter,
    "meta": MetaAdsAdapter,
    "tiktok": TikTokAdsAdapter,
}


def get_adapter(platform: str) -> BaseAdPlatformAdapter:
    """
    Get an adapter instance for a platform.

    Args:
        platform: Platform name (google, meta, tiktok)

    Returns:
        Configured adapter instance

    Raises:
        ValueError: If platform is not supported
    """
    adapter_class = _adapters.get(platform)
    if not adapter_class:
        raise ValueError(f"Unsupported platform: {platform}")

    return adapter_class()


def get_supported_platforms() -> list[str]:
    """Get list of supported platforms."""
    return list(_adapters.keys())


__all__ = [
    # Factory
    "get_adapter",
    "get_supported_platforms",
    # Base types
    "BaseAdPlatformAdapter",
    "AdAccountInfo",
    "CampaignInfo",
    "CampaignMetrics",
    "CampaignCreateRequest",
    "CampaignUpdateRequest",
    "CampaignStatus",
    "CampaignObjective",
    # Errors
    "AdapterError",
    "AuthenticationError",
    "PlatformError",
    "RateLimitError",
    "ValidationError",
    # Adapters
    "GoogleAdsAdapter",
    "MetaAdsAdapter",
    "TikTokAdsAdapter",
]

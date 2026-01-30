"""
Base Ad Platform Adapter

Abstract base class defining the interface for all ad platform integrations.
Each platform (Google, Meta, TikTok) implements this interface.

Design principles:
- Platform-agnostic interface
- Async-first for non-blocking operations
- Comprehensive error handling
- Retry logic for transient failures
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

import structlog

logger = structlog.get_logger()


# =============================================================================
# Data Types
# =============================================================================

class CampaignStatus(str, Enum):
    """Unified campaign status across platforms."""
    ENABLED = "enabled"
    PAUSED = "paused"
    REMOVED = "removed"
    UNKNOWN = "unknown"


class CampaignObjective(str, Enum):
    """Unified campaign objectives."""
    AWARENESS = "awareness"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    LEADS = "leads"
    SALES = "sales"
    APP_PROMOTION = "app_promotion"


@dataclass
class AdAccountInfo:
    """Platform ad account information."""
    account_id: str
    account_name: str
    currency: str
    timezone: str
    status: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CampaignInfo:
    """Unified campaign information."""
    campaign_id: str
    name: str
    status: CampaignStatus
    objective: Optional[CampaignObjective]
    budget_amount: Optional[float]
    budget_type: Optional[str]  # daily, lifetime
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    platform_data: dict[str, Any] = None

    def __post_init__(self):
        if self.platform_data is None:
            self.platform_data = {}


@dataclass
class CampaignMetrics:
    """Unified campaign performance metrics."""
    campaign_id: str
    date: date
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    conversion_value: float = 0.0

    @property
    def ctr(self) -> float:
        """Click-through rate."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def cpc(self) -> float:
        """Cost per click."""
        return self.spend / self.clicks if self.clicks > 0 else 0.0

    @property
    def cpa(self) -> float:
        """Cost per acquisition."""
        return self.spend / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        """Return on ad spend."""
        return self.conversion_value / self.spend if self.spend > 0 else 0.0


@dataclass
class CampaignCreateRequest:
    """Request to create a campaign."""
    name: str
    objective: CampaignObjective
    budget_amount: float
    budget_type: str = "daily"  # daily, lifetime
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    targeting: dict[str, Any] = None
    ad_copy: dict[str, Any] = None

    def __post_init__(self):
        if self.targeting is None:
            self.targeting = {}
        if self.ad_copy is None:
            self.ad_copy = {}


@dataclass
class CampaignUpdateRequest:
    """Request to update a campaign."""
    name: Optional[str] = None
    status: Optional[CampaignStatus] = None
    budget_amount: Optional[float] = None
    end_date: Optional[date] = None


# =============================================================================
# Error Types
# =============================================================================

class AdapterError(Exception):
    """Base exception for adapter errors."""
    def __init__(self, message: str, platform: str, details: dict = None):
        self.message = message
        self.platform = platform
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(AdapterError):
    """OAuth token is invalid or expired."""
    pass


class RateLimitError(AdapterError):
    """Platform rate limit exceeded."""
    def __init__(self, message: str, platform: str, retry_after: int = 60):
        super().__init__(message, platform)
        self.retry_after = retry_after


class ValidationError(AdapterError):
    """Request validation failed."""
    pass


class PlatformError(AdapterError):
    """Platform-specific error."""
    pass


# =============================================================================
# Base Adapter
# =============================================================================

T = TypeVar("T")


class BaseAdPlatformAdapter(ABC, Generic[T]):
    """
    Abstract base class for ad platform adapters.

    All platform-specific adapters must implement these methods.
    Methods are async to support non-blocking I/O.
    """

    def __init__(self, platform: str):
        self.platform = platform
        self.logger = logger.bind(platform=platform)

    # =========================================================================
    # Authentication
    # =========================================================================

    @abstractmethod
    async def validate_credentials(self, access_token: str) -> bool:
        """
        Validate that credentials are still valid.

        Args:
            access_token: OAuth access token

        Returns:
            True if credentials are valid

        Raises:
            AuthenticationError: If credentials are invalid
        """
        pass

    # =========================================================================
    # Account Operations
    # =========================================================================

    @abstractmethod
    async def list_accounts(self, access_token: str) -> list[AdAccountInfo]:
        """
        List all accessible ad accounts.

        Args:
            access_token: OAuth access token

        Returns:
            List of ad accounts the user has access to
        """
        pass

    @abstractmethod
    async def get_account(
        self, access_token: str, account_id: str
    ) -> AdAccountInfo:
        """
        Get details of a specific ad account.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID

        Returns:
            Account details
        """
        pass

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    @abstractmethod
    async def list_campaigns(
        self,
        access_token: str,
        account_id: str,
        status_filter: Optional[list[CampaignStatus]] = None,
    ) -> list[CampaignInfo]:
        """
        List campaigns in an ad account.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            status_filter: Optional filter by status

        Returns:
            List of campaigns
        """
        pass

    @abstractmethod
    async def get_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> CampaignInfo:
        """
        Get details of a specific campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            campaign_id: Platform campaign ID

        Returns:
            Campaign details
        """
        pass

    @abstractmethod
    async def create_campaign(
        self,
        access_token: str,
        account_id: str,
        request: CampaignCreateRequest,
    ) -> str:
        """
        Create a new campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            request: Campaign creation details

        Returns:
            Platform campaign ID
        """
        pass

    @abstractmethod
    async def update_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
        request: CampaignUpdateRequest,
    ) -> bool:
        """
        Update an existing campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            campaign_id: Platform campaign ID
            request: Fields to update

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def pause_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> bool:
        """
        Pause a campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            campaign_id: Platform campaign ID

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def resume_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> bool:
        """
        Resume a paused campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            campaign_id: Platform campaign ID

        Returns:
            True if successful
        """
        pass

    # =========================================================================
    # Metrics Operations
    # =========================================================================

    @abstractmethod
    async def get_campaign_metrics(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[CampaignMetrics]:
        """
        Get performance metrics for a campaign.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            campaign_id: Platform campaign ID
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of daily metrics
        """
        pass

    @abstractmethod
    async def get_account_metrics(
        self,
        access_token: str,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> list[CampaignMetrics]:
        """
        Get aggregated metrics for an entire account.

        Args:
            access_token: OAuth access token
            account_id: Platform account ID
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of daily metrics (aggregated across campaigns)
        """
        pass

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _log_operation(self, operation: str, **kwargs):
        """Log an adapter operation."""
        self.logger.info(f"adapter_{operation}", **kwargs)

    def _log_error(self, operation: str, error: Exception, **kwargs):
        """Log an adapter error."""
        self.logger.error(
            f"adapter_{operation}_error",
            error=str(error),
            error_type=type(error).__name__,
            **kwargs,
        )

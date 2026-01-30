"""
TikTok Ads API Adapter

Implements the BaseAdPlatformAdapter interface for TikTok Ads.
Uses the TikTok Marketing API for campaign management.

API Documentation: https://business-api.tiktok.com/portal/docs
"""

from datetime import date, datetime, timezone
from typing import Optional

import httpx
import structlog

from app.adapters.base import (
    AdAccountInfo,
    AuthenticationError,
    BaseAdPlatformAdapter,
    CampaignCreateRequest,
    CampaignInfo,
    CampaignMetrics,
    CampaignObjective,
    CampaignStatus,
    CampaignUpdateRequest,
    PlatformError,
    RateLimitError,
    ValidationError,
)
from app.config import settings

logger = structlog.get_logger()

# TikTok API base URL
TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# Status mapping from TikTok to unified status
TIKTOK_STATUS_MAP = {
    "ENABLE": CampaignStatus.ENABLED,
    "DISABLE": CampaignStatus.PAUSED,
    "DELETE": CampaignStatus.REMOVED,
}

# Reverse status mapping
UNIFIED_TO_TIKTOK_STATUS = {
    CampaignStatus.ENABLED: "ENABLE",
    CampaignStatus.PAUSED: "DISABLE",
}

# Objective mapping from TikTok to unified
TIKTOK_OBJECTIVE_MAP = {
    "REACH": CampaignObjective.AWARENESS,
    "VIDEO_VIEWS": CampaignObjective.AWARENESS,
    "TRAFFIC": CampaignObjective.TRAFFIC,
    "ENGAGEMENT": CampaignObjective.ENGAGEMENT,
    "LEAD_GENERATION": CampaignObjective.LEADS,
    "WEB_CONVERSIONS": CampaignObjective.SALES,
    "PRODUCT_SALES": CampaignObjective.SALES,
    "APP_PROMOTION": CampaignObjective.APP_PROMOTION,
    "APP_INSTALL": CampaignObjective.APP_PROMOTION,
}

# Unified to TikTok objective mapping
UNIFIED_TO_TIKTOK_OBJECTIVE = {
    CampaignObjective.AWARENESS: "REACH",
    CampaignObjective.TRAFFIC: "TRAFFIC",
    CampaignObjective.ENGAGEMENT: "ENGAGEMENT",
    CampaignObjective.LEADS: "LEAD_GENERATION",
    CampaignObjective.SALES: "WEB_CONVERSIONS",
    CampaignObjective.APP_PROMOTION: "APP_PROMOTION",
}


class TikTokAdsAdapter(BaseAdPlatformAdapter):
    """
    TikTok Ads API adapter.

    Implements campaign management and metrics retrieval
    using the TikTok Marketing API.
    """

    def __init__(self):
        super().__init__(platform="tiktok")
        self.app_id = settings.tiktok_app_id
        self.app_secret = settings.tiktok_app_secret

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        params: dict = None,
        data: dict = None,
    ) -> dict:
        """
        Make a request to the TikTok API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            access_token: Access token
            params: Query parameters
            data: Request body for POST/PUT

        Returns:
            JSON response data

        Raises:
            Appropriate adapter error on failure
        """
        url = f"{TIKTOK_API_BASE}/{endpoint}"

        headers = {
            "Access-Token": access_token,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response_data = response.json()

                # TikTok uses code 0 for success
                if response_data.get("code") == 0:
                    return response_data.get("data", {})

                # Handle errors
                self._handle_tiktok_error(response_data)

            except httpx.RequestError as e:
                raise PlatformError(
                    message=f"Network error: {str(e)}",
                    platform="tiktok",
                )

    def _handle_tiktok_error(self, response_data: dict):
        """
        Convert TikTok API errors to adapter errors.

        Args:
            response_data: API response

        Raises:
            Appropriate adapter error
        """
        error_code = response_data.get("code", 0)
        error_message = response_data.get("message", "Unknown error")

        self._log_error(
            "tiktok_api_error",
            Exception(error_message),
            error_code=error_code,
        )

        # Authentication errors
        if error_code in [40001, 40002, 40100, 40101]:
            raise AuthenticationError(
                message=f"TikTok authentication failed: {error_message}",
                platform="tiktok",
                details={"error_code": error_code},
            )

        # Rate limit errors
        if error_code in [40200, 40201]:
            raise RateLimitError(
                message="TikTok API rate limit exceeded",
                platform="tiktok",
                retry_after=60,
            )

        # Validation errors
        if error_code in [40000, 40003]:
            raise ValidationError(
                message=f"Invalid request: {error_message}",
                platform="tiktok",
                details={"error_code": error_code},
            )

        # Generic error
        raise PlatformError(
            message=f"TikTok API error: {error_message}",
            platform="tiktok",
            details={"error_code": error_code},
        )

    # =========================================================================
    # Authentication
    # =========================================================================

    async def validate_credentials(self, access_token: str) -> bool:
        """Validate TikTok access token."""
        try:
            # Try to get user info
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{TIKTOK_API_BASE}/user/info/",
                    headers={"Access-Token": access_token},
                )

                data = response.json()
                return data.get("code") == 0

        except Exception as e:
            self._log_error("validate_credentials", e)
            return False

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def list_accounts(self, access_token: str) -> list[AdAccountInfo]:
        """List all accessible TikTok ad accounts."""
        self._log_operation("list_accounts")

        data = await self._make_request(
            "GET",
            "oauth2/advertiser/get/",
            access_token,
            params={"app_id": self.app_id},
        )

        accounts = []
        for advertiser in data.get("list", []):
            advertiser_id = advertiser.get("advertiser_id")

            # Get detailed account info
            try:
                account_info = await self.get_account(access_token, advertiser_id)
                accounts.append(account_info)
            except Exception as e:
                self.logger.warning(
                    "failed_to_get_account_details",
                    advertiser_id=advertiser_id,
                    error=str(e),
                )
                # Add basic info
                accounts.append(
                    AdAccountInfo(
                        account_id=str(advertiser_id),
                        account_name=advertiser.get("advertiser_name", f"Account {advertiser_id}"),
                        currency="USD",
                        timezone="UTC",
                        status="ACTIVE",
                    )
                )

        return accounts

    async def get_account(
        self, access_token: str, account_id: str
    ) -> AdAccountInfo:
        """Get details of a specific TikTok ad account."""
        self._log_operation("get_account", account_id=account_id)

        data = await self._make_request(
            "GET",
            "advertiser/info/",
            access_token,
            params={
                "advertiser_ids": f"[{account_id}]",
            },
        )

        advertisers = data.get("list", [])
        if not advertisers:
            raise PlatformError(
                message=f"Account {account_id} not found",
                platform="tiktok",
            )

        advertiser = advertisers[0]

        # Map status
        status = "ACTIVE"
        if advertiser.get("status") == "DISABLE":
            status = "DISABLED"
        elif advertiser.get("status") == "PENDING":
            status = "PENDING"

        return AdAccountInfo(
            account_id=str(advertiser.get("advertiser_id")),
            account_name=advertiser.get("name", f"Account {account_id}"),
            currency=advertiser.get("currency", "USD"),
            timezone=advertiser.get("timezone", "UTC"),
            status=status,
            metadata={
                "balance": advertiser.get("balance"),
                "company": advertiser.get("company"),
            },
        )

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    async def list_campaigns(
        self,
        access_token: str,
        account_id: str,
        status_filter: Optional[list[CampaignStatus]] = None,
    ) -> list[CampaignInfo]:
        """List campaigns in a TikTok ad account."""
        self._log_operation("list_campaigns", account_id=account_id)

        params = {
            "advertiser_id": account_id,
            "page_size": 100,
        }

        # Add status filter if provided
        if status_filter:
            tiktok_statuses = [
                UNIFIED_TO_TIKTOK_STATUS.get(s)
                for s in status_filter
                if s in UNIFIED_TO_TIKTOK_STATUS
            ]
            if tiktok_statuses:
                params["primary_status"] = tiktok_statuses[0]  # TikTok only supports single status filter

        data = await self._make_request(
            "GET",
            "campaign/get/",
            access_token,
            params=params,
        )

        campaigns = []
        for campaign in data.get("list", []):
            status = TIKTOK_STATUS_MAP.get(
                campaign.get("operation_status", ""), CampaignStatus.UNKNOWN
            )

            # Apply status filter if we couldn't use API filter
            if status_filter and status not in status_filter:
                continue

            objective = TIKTOK_OBJECTIVE_MAP.get(
                campaign.get("objective_type", ""), None
            )

            # Budget info
            budget_mode = campaign.get("budget_mode")
            budget = campaign.get("budget", 0)

            if budget_mode == "BUDGET_MODE_INFINITE":
                budget_amount = None
                budget_type = None
            elif budget_mode == "BUDGET_MODE_DAY":
                budget_amount = float(budget)
                budget_type = "daily"
            elif budget_mode == "BUDGET_MODE_TOTAL":
                budget_amount = float(budget)
                budget_type = "lifetime"
            else:
                budget_amount = float(budget) if budget else None
                budget_type = "daily"

            campaigns.append(
                CampaignInfo(
                    campaign_id=str(campaign.get("campaign_id")),
                    name=campaign.get("campaign_name", ""),
                    status=status,
                    objective=objective,
                    budget_amount=budget_amount,
                    budget_type=budget_type,
                    start_date=self._parse_tiktok_date(campaign.get("schedule_start_time")),
                    end_date=self._parse_tiktok_date(campaign.get("schedule_end_time")),
                    created_at=self._parse_tiktok_datetime(campaign.get("create_time")),
                    updated_at=self._parse_tiktok_datetime(campaign.get("modify_time")),
                    platform_data={
                        "objective_type": campaign.get("objective_type"),
                        "budget_mode": budget_mode,
                    },
                )
            )

        return campaigns

    async def get_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> CampaignInfo:
        """Get details of a specific campaign."""
        self._log_operation(
            "get_campaign", account_id=account_id, campaign_id=campaign_id
        )

        data = await self._make_request(
            "GET",
            "campaign/get/",
            access_token,
            params={
                "advertiser_id": account_id,
                "campaign_ids": f"[{campaign_id}]",
            },
        )

        campaigns = data.get("list", [])
        if not campaigns:
            raise PlatformError(
                message=f"Campaign {campaign_id} not found",
                platform="tiktok",
            )

        campaign = campaigns[0]

        status = TIKTOK_STATUS_MAP.get(
            campaign.get("operation_status", ""), CampaignStatus.UNKNOWN
        )
        objective = TIKTOK_OBJECTIVE_MAP.get(
            campaign.get("objective_type", ""), None
        )

        budget_mode = campaign.get("budget_mode")
        budget = campaign.get("budget", 0)

        if budget_mode == "BUDGET_MODE_INFINITE":
            budget_amount = None
            budget_type = None
        elif budget_mode == "BUDGET_MODE_DAY":
            budget_amount = float(budget)
            budget_type = "daily"
        else:
            budget_amount = float(budget) if budget else None
            budget_type = "lifetime"

        return CampaignInfo(
            campaign_id=str(campaign.get("campaign_id")),
            name=campaign.get("campaign_name", ""),
            status=status,
            objective=objective,
            budget_amount=budget_amount,
            budget_type=budget_type,
            start_date=self._parse_tiktok_date(campaign.get("schedule_start_time")),
            end_date=self._parse_tiktok_date(campaign.get("schedule_end_time")),
            created_at=self._parse_tiktok_datetime(campaign.get("create_time")),
            updated_at=self._parse_tiktok_datetime(campaign.get("modify_time")),
            platform_data={
                "objective_type": campaign.get("objective_type"),
                "budget_mode": budget_mode,
            },
        )

    async def create_campaign(
        self,
        access_token: str,
        account_id: str,
        request: CampaignCreateRequest,
    ) -> str:
        """Create a new TikTok campaign."""
        self._log_operation("create_campaign", account_id=account_id, name=request.name)

        # Map objective
        tiktok_objective = UNIFIED_TO_TIKTOK_OBJECTIVE.get(
            request.objective, "TRAFFIC"
        )

        # Prepare campaign data
        campaign_data = {
            "advertiser_id": account_id,
            "campaign_name": request.name,
            "objective_type": tiktok_objective,
            "operation_status": "DISABLE",  # Start paused for safety
        }

        # Set budget
        if request.budget_type == "lifetime":
            campaign_data["budget_mode"] = "BUDGET_MODE_TOTAL"
            campaign_data["budget"] = request.budget_amount
        else:
            campaign_data["budget_mode"] = "BUDGET_MODE_DAY"
            campaign_data["budget"] = request.budget_amount

        data = await self._make_request(
            "POST",
            "campaign/create/",
            access_token,
            data=campaign_data,
        )

        campaign_id = str(data.get("campaign_id"))
        self._log_operation(
            "create_campaign_success",
            account_id=account_id,
            campaign_id=campaign_id,
        )

        return campaign_id

    async def update_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
        request: CampaignUpdateRequest,
    ) -> bool:
        """Update an existing campaign."""
        self._log_operation(
            "update_campaign", account_id=account_id, campaign_id=campaign_id
        )

        update_data = {
            "advertiser_id": account_id,
            "campaign_id": campaign_id,
        }

        if request.name is not None:
            update_data["campaign_name"] = request.name

        if request.status is not None:
            tiktok_status = UNIFIED_TO_TIKTOK_STATUS.get(request.status)
            if tiktok_status:
                update_data["operation_status"] = tiktok_status

        if request.budget_amount is not None:
            update_data["budget"] = request.budget_amount

        if len(update_data) <= 2:  # Only has advertiser_id and campaign_id
            return True  # Nothing to update

        await self._make_request(
            "POST",
            "campaign/update/",
            access_token,
            data=update_data,
        )

        return True

    async def pause_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> bool:
        """Pause a campaign."""
        return await self.update_campaign(
            access_token=access_token,
            account_id=account_id,
            campaign_id=campaign_id,
            request=CampaignUpdateRequest(status=CampaignStatus.PAUSED),
        )

    async def resume_campaign(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
    ) -> bool:
        """Resume a paused campaign."""
        return await self.update_campaign(
            access_token=access_token,
            account_id=account_id,
            campaign_id=campaign_id,
            request=CampaignUpdateRequest(status=CampaignStatus.ENABLED),
        )

    # =========================================================================
    # Metrics Operations
    # =========================================================================

    async def get_campaign_metrics(
        self,
        access_token: str,
        account_id: str,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[CampaignMetrics]:
        """Get daily metrics for a campaign."""
        self._log_operation(
            "get_campaign_metrics",
            account_id=account_id,
            campaign_id=campaign_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        data = await self._make_request(
            "GET",
            "report/integrated/get/",
            access_token,
            params={
                "advertiser_id": account_id,
                "report_type": "BASIC",
                "dimensions": '["campaign_id", "stat_time_day"]',
                "metrics": '["spend", "impressions", "clicks", "conversion", "total_complete_payment_rate"]',
                "data_level": "AUCTION_CAMPAIGN",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "filters": f'[{{"field_name": "campaign_id", "filter_type": "IN", "filter_value": "[\\"{campaign_id}\\"]"}}]',
            },
        )

        metrics = []
        for row in data.get("list", []):
            dimensions = row.get("dimensions", {})
            metric_values = row.get("metrics", {})

            stat_date = dimensions.get("stat_time_day", str(start_date))

            metrics.append(
                CampaignMetrics(
                    campaign_id=campaign_id,
                    date=date.fromisoformat(stat_date),
                    impressions=int(metric_values.get("impressions", 0)),
                    clicks=int(metric_values.get("clicks", 0)),
                    spend=float(metric_values.get("spend", 0)),
                    conversions=int(metric_values.get("conversion", 0)),
                    conversion_value=float(metric_values.get("total_complete_payment_rate", 0)),
                )
            )

        return metrics

    async def get_account_metrics(
        self,
        access_token: str,
        account_id: str,
        start_date: date,
        end_date: date,
    ) -> list[CampaignMetrics]:
        """Get aggregated daily metrics for an account."""
        self._log_operation(
            "get_account_metrics",
            account_id=account_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        data = await self._make_request(
            "GET",
            "report/integrated/get/",
            access_token,
            params={
                "advertiser_id": account_id,
                "report_type": "BASIC",
                "dimensions": '["stat_time_day"]',
                "metrics": '["spend", "impressions", "clicks", "conversion", "total_complete_payment_rate"]',
                "data_level": "AUCTION_ADVERTISER",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )

        metrics = []
        for row in data.get("list", []):
            dimensions = row.get("dimensions", {})
            metric_values = row.get("metrics", {})

            stat_date = dimensions.get("stat_time_day", str(start_date))

            metrics.append(
                CampaignMetrics(
                    campaign_id="",  # Account-level
                    date=date.fromisoformat(stat_date),
                    impressions=int(metric_values.get("impressions", 0)),
                    clicks=int(metric_values.get("clicks", 0)),
                    spend=float(metric_values.get("spend", 0)),
                    conversions=int(metric_values.get("conversion", 0)),
                    conversion_value=float(metric_values.get("total_complete_payment_rate", 0)),
                )
            )

        return metrics

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_tiktok_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse a TikTok date string to date."""
        if not date_str or date_str == "0":
            return None
        try:
            # TikTok uses YYYY-MM-DD HH:MM:SS or timestamp
            if date_str.isdigit():
                # Unix timestamp
                return datetime.fromtimestamp(int(date_str), tz=timezone.utc).date()
            return datetime.strptime(date_str.split()[0], "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_tiktok_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse a TikTok datetime string to datetime."""
        if not dt_str or dt_str == "0":
            return None
        try:
            if dt_str.isdigit():
                return datetime.fromtimestamp(int(dt_str), tz=timezone.utc)
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

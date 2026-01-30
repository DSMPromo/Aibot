"""
Meta (Facebook) Ads API Adapter

Implements the BaseAdPlatformAdapter interface for Meta Ads.
Uses the Facebook Marketing API for campaign management.

API Documentation: https://developers.facebook.com/docs/marketing-apis
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

# Meta API version
META_API_VERSION = "v19.0"
META_API_BASE = f"https://graph.facebook.com/{META_API_VERSION}"

# Status mapping from Meta to unified status
META_STATUS_MAP = {
    "ACTIVE": CampaignStatus.ENABLED,
    "PAUSED": CampaignStatus.PAUSED,
    "DELETED": CampaignStatus.REMOVED,
    "ARCHIVED": CampaignStatus.REMOVED,
}

# Reverse status mapping
UNIFIED_TO_META_STATUS = {
    CampaignStatus.ENABLED: "ACTIVE",
    CampaignStatus.PAUSED: "PAUSED",
}

# Objective mapping from Meta to unified
META_OBJECTIVE_MAP = {
    "OUTCOME_AWARENESS": CampaignObjective.AWARENESS,
    "OUTCOME_TRAFFIC": CampaignObjective.TRAFFIC,
    "OUTCOME_ENGAGEMENT": CampaignObjective.ENGAGEMENT,
    "OUTCOME_LEADS": CampaignObjective.LEADS,
    "OUTCOME_SALES": CampaignObjective.SALES,
    "OUTCOME_APP_PROMOTION": CampaignObjective.APP_PROMOTION,
    # Legacy objectives (v18 and earlier)
    "BRAND_AWARENESS": CampaignObjective.AWARENESS,
    "REACH": CampaignObjective.AWARENESS,
    "LINK_CLICKS": CampaignObjective.TRAFFIC,
    "POST_ENGAGEMENT": CampaignObjective.ENGAGEMENT,
    "PAGE_LIKES": CampaignObjective.ENGAGEMENT,
    "LEAD_GENERATION": CampaignObjective.LEADS,
    "CONVERSIONS": CampaignObjective.SALES,
    "PRODUCT_CATALOG_SALES": CampaignObjective.SALES,
    "APP_INSTALLS": CampaignObjective.APP_PROMOTION,
}

# Unified to Meta objective mapping (using ODAX objectives)
UNIFIED_TO_META_OBJECTIVE = {
    CampaignObjective.AWARENESS: "OUTCOME_AWARENESS",
    CampaignObjective.TRAFFIC: "OUTCOME_TRAFFIC",
    CampaignObjective.ENGAGEMENT: "OUTCOME_ENGAGEMENT",
    CampaignObjective.LEADS: "OUTCOME_LEADS",
    CampaignObjective.SALES: "OUTCOME_SALES",
    CampaignObjective.APP_PROMOTION: "OUTCOME_APP_PROMOTION",
}


class MetaAdsAdapter(BaseAdPlatformAdapter):
    """
    Meta (Facebook) Ads API adapter.

    Implements campaign management and metrics retrieval
    using the Facebook Marketing API.
    """

    def __init__(self):
        super().__init__(platform="meta")
        self.app_id = settings.meta_app_id
        self.app_secret = settings.meta_app_secret

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        params: dict = None,
        data: dict = None,
    ) -> dict:
        """
        Make a request to the Meta API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            access_token: User access token
            params: Query parameters
            data: Request body for POST/PUT

        Returns:
            JSON response

        Raises:
            Appropriate adapter error on failure
        """
        url = f"{META_API_BASE}/{endpoint}"

        if params is None:
            params = {}
        params["access_token"] = access_token

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, params=params, data=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == 200:
                    return response.json()

                # Handle errors
                error_data = response.json() if response.text else {}
                self._handle_meta_error(response.status_code, error_data)

            except httpx.RequestError as e:
                raise PlatformError(
                    message=f"Network error: {str(e)}",
                    platform="meta",
                )

    def _handle_meta_error(self, status_code: int, error_data: dict):
        """
        Convert Meta API errors to adapter errors.

        Args:
            status_code: HTTP status code
            error_data: Error response from API

        Raises:
            Appropriate adapter error
        """
        error = error_data.get("error", {})
        error_code = error.get("code", 0)
        error_message = error.get("message", "Unknown error")
        error_type = error.get("type", "OAuthException")

        self._log_error(
            "meta_api_error",
            Exception(error_message),
            status_code=status_code,
            error_code=error_code,
            error_type=error_type,
        )

        # Authentication errors
        if error_code in [190, 102, 104]:
            raise AuthenticationError(
                message=f"Meta authentication failed: {error_message}",
                platform="meta",
                details={"error_code": error_code},
            )

        # Rate limit errors
        if error_code in [4, 17, 32, 613]:
            raise RateLimitError(
                message="Meta API rate limit exceeded",
                platform="meta",
                retry_after=60,
            )

        # Validation errors
        if error_code in [100, 200]:
            raise ValidationError(
                message=f"Invalid request: {error_message}",
                platform="meta",
                details={"error_code": error_code},
            )

        # Generic error
        raise PlatformError(
            message=f"Meta API error: {error_message}",
            platform="meta",
            details={"error_code": error_code, "error_type": error_type},
        )

    # =========================================================================
    # Authentication
    # =========================================================================

    async def validate_credentials(self, access_token: str) -> bool:
        """Validate Meta access token by making a debug request."""
        try:
            # Debug token endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{META_API_BASE}/debug_token",
                    params={
                        "input_token": access_token,
                        "access_token": f"{self.app_id}|{self.app_secret}",
                    },
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    return data.get("is_valid", False)

                return False

        except Exception as e:
            self._log_error("validate_credentials", e)
            return False

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def list_accounts(self, access_token: str) -> list[AdAccountInfo]:
        """List all accessible Meta ad accounts."""
        self._log_operation("list_accounts")

        # First get the user's ID
        me_data = await self._make_request("GET", "me", access_token)
        user_id = me_data.get("id")

        # Get ad accounts
        accounts_data = await self._make_request(
            "GET",
            f"{user_id}/adaccounts",
            access_token,
            params={
                "fields": "id,name,currency,timezone_name,account_status,amount_spent",
                "limit": 100,
            },
        )

        accounts = []
        for account in accounts_data.get("data", []):
            # Meta returns account_id with "act_" prefix
            account_id = account["id"].replace("act_", "")

            status_code = account.get("account_status", 0)
            status = self._map_account_status(status_code)

            accounts.append(
                AdAccountInfo(
                    account_id=account_id,
                    account_name=account.get("name", f"Account {account_id}"),
                    currency=account.get("currency", "USD"),
                    timezone=account.get("timezone_name", "UTC"),
                    status=status,
                    metadata={
                        "amount_spent": account.get("amount_spent"),
                    },
                )
            )

        return accounts

    def _map_account_status(self, status_code: int) -> str:
        """Map Meta account status code to string."""
        status_map = {
            1: "ACTIVE",
            2: "DISABLED",
            3: "UNSETTLED",
            7: "PENDING_RISK_REVIEW",
            8: "PENDING_SETTLEMENT",
            9: "IN_GRACE_PERIOD",
            100: "PENDING_CLOSURE",
            101: "CLOSED",
            201: "ANY_ACTIVE",
            202: "ANY_CLOSED",
        }
        return status_map.get(status_code, "UNKNOWN")

    async def get_account(
        self, access_token: str, account_id: str
    ) -> AdAccountInfo:
        """Get details of a specific Meta ad account."""
        self._log_operation("get_account", account_id=account_id)

        data = await self._make_request(
            "GET",
            f"act_{account_id}",
            access_token,
            params={
                "fields": "id,name,currency,timezone_name,account_status,amount_spent",
            },
        )

        status_code = data.get("account_status", 0)
        status = self._map_account_status(status_code)

        return AdAccountInfo(
            account_id=account_id,
            account_name=data.get("name", f"Account {account_id}"),
            currency=data.get("currency", "USD"),
            timezone=data.get("timezone_name", "UTC"),
            status=status,
            metadata={
                "amount_spent": data.get("amount_spent"),
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
        """List campaigns in a Meta ad account."""
        self._log_operation("list_campaigns", account_id=account_id)

        # Build effective status filter
        effective_status = None
        if status_filter:
            effective_status = [
                UNIFIED_TO_META_STATUS.get(s) for s in status_filter
                if s in UNIFIED_TO_META_STATUS
            ]

        params = {
            "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time",
            "limit": 100,
        }

        if effective_status:
            params["effective_status"] = str(effective_status)

        data = await self._make_request(
            "GET",
            f"act_{account_id}/campaigns",
            access_token,
            params=params,
        )

        campaigns = []
        for campaign in data.get("data", []):
            status = META_STATUS_MAP.get(
                campaign.get("status", ""), CampaignStatus.UNKNOWN
            )

            # Apply status filter if provided and we couldn't use API filter
            if status_filter and status not in status_filter:
                continue

            objective = META_OBJECTIVE_MAP.get(
                campaign.get("objective", ""), None
            )

            # Determine budget type and amount
            daily_budget = campaign.get("daily_budget")
            lifetime_budget = campaign.get("lifetime_budget")

            if daily_budget:
                budget_amount = int(daily_budget) / 100  # Cents to dollars
                budget_type = "daily"
            elif lifetime_budget:
                budget_amount = int(lifetime_budget) / 100
                budget_type = "lifetime"
            else:
                budget_amount = None
                budget_type = None

            campaigns.append(
                CampaignInfo(
                    campaign_id=campaign["id"],
                    name=campaign["name"],
                    status=status,
                    objective=objective,
                    budget_amount=budget_amount,
                    budget_type=budget_type,
                    start_date=self._parse_meta_datetime(campaign.get("start_time")),
                    end_date=self._parse_meta_datetime(campaign.get("stop_time")),
                    created_at=self._parse_meta_datetime_full(campaign.get("created_time")),
                    updated_at=self._parse_meta_datetime_full(campaign.get("updated_time")),
                    platform_data={
                        "meta_objective": campaign.get("objective"),
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
            campaign_id,
            access_token,
            params={
                "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time",
            },
        )

        status = META_STATUS_MAP.get(
            data.get("status", ""), CampaignStatus.UNKNOWN
        )
        objective = META_OBJECTIVE_MAP.get(data.get("objective", ""), None)

        daily_budget = data.get("daily_budget")
        lifetime_budget = data.get("lifetime_budget")

        if daily_budget:
            budget_amount = int(daily_budget) / 100
            budget_type = "daily"
        elif lifetime_budget:
            budget_amount = int(lifetime_budget) / 100
            budget_type = "lifetime"
        else:
            budget_amount = None
            budget_type = None

        return CampaignInfo(
            campaign_id=data["id"],
            name=data["name"],
            status=status,
            objective=objective,
            budget_amount=budget_amount,
            budget_type=budget_type,
            start_date=self._parse_meta_datetime(data.get("start_time")),
            end_date=self._parse_meta_datetime(data.get("stop_time")),
            created_at=self._parse_meta_datetime_full(data.get("created_time")),
            updated_at=self._parse_meta_datetime_full(data.get("updated_time")),
            platform_data={
                "meta_objective": data.get("objective"),
            },
        )

    async def create_campaign(
        self,
        access_token: str,
        account_id: str,
        request: CampaignCreateRequest,
    ) -> str:
        """Create a new Meta campaign."""
        self._log_operation("create_campaign", account_id=account_id, name=request.name)

        # Map objective
        meta_objective = UNIFIED_TO_META_OBJECTIVE.get(
            request.objective, "OUTCOME_TRAFFIC"
        )

        # Prepare campaign data
        campaign_data = {
            "name": request.name,
            "objective": meta_objective,
            "status": "PAUSED",  # Start paused for safety
            "special_ad_categories": "[]",  # Required field
        }

        # Set budget
        if request.budget_type == "lifetime" and request.end_date:
            campaign_data["lifetime_budget"] = int(request.budget_amount * 100)
        else:
            campaign_data["daily_budget"] = int(request.budget_amount * 100)

        # Set dates if provided
        if request.start_date:
            campaign_data["start_time"] = request.start_date.isoformat()
        if request.end_date:
            campaign_data["stop_time"] = request.end_date.isoformat()

        data = await self._make_request(
            "POST",
            f"act_{account_id}/campaigns",
            access_token,
            data=campaign_data,
        )

        campaign_id = data.get("id")
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

        update_data = {}

        if request.name is not None:
            update_data["name"] = request.name

        if request.status is not None:
            meta_status = UNIFIED_TO_META_STATUS.get(request.status)
            if meta_status:
                update_data["status"] = meta_status

        if request.budget_amount is not None:
            # Default to daily budget
            update_data["daily_budget"] = int(request.budget_amount * 100)

        if request.end_date is not None:
            update_data["stop_time"] = request.end_date.isoformat()

        if not update_data:
            return True  # Nothing to update

        await self._make_request(
            "POST",
            campaign_id,
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
            f"{campaign_id}/insights",
            access_token,
            params={
                "fields": "impressions,clicks,spend,actions,action_values",
                "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
                "time_increment": 1,  # Daily breakdown
                "level": "campaign",
            },
        )

        metrics = []
        for row in data.get("data", []):
            # Parse conversions from actions
            conversions = 0
            conversion_value = 0.0

            actions = row.get("actions", [])
            for action in actions:
                if action.get("action_type") in ["purchase", "lead", "complete_registration"]:
                    conversions += int(action.get("value", 0))

            action_values = row.get("action_values", [])
            for av in action_values:
                if av.get("action_type") == "purchase":
                    conversion_value += float(av.get("value", 0))

            metrics.append(
                CampaignMetrics(
                    campaign_id=campaign_id,
                    date=date.fromisoformat(row.get("date_start", str(start_date))),
                    impressions=int(row.get("impressions", 0)),
                    clicks=int(row.get("clicks", 0)),
                    spend=float(row.get("spend", 0)),
                    conversions=conversions,
                    conversion_value=conversion_value,
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
            f"act_{account_id}/insights",
            access_token,
            params={
                "fields": "impressions,clicks,spend,actions,action_values",
                "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
                "time_increment": 1,  # Daily breakdown
                "level": "account",
            },
        )

        metrics = []
        for row in data.get("data", []):
            conversions = 0
            conversion_value = 0.0

            actions = row.get("actions", [])
            for action in actions:
                if action.get("action_type") in ["purchase", "lead", "complete_registration"]:
                    conversions += int(action.get("value", 0))

            action_values = row.get("action_values", [])
            for av in action_values:
                if av.get("action_type") == "purchase":
                    conversion_value += float(av.get("value", 0))

            metrics.append(
                CampaignMetrics(
                    campaign_id="",  # Account-level
                    date=date.fromisoformat(row.get("date_start", str(start_date))),
                    impressions=int(row.get("impressions", 0)),
                    clicks=int(row.get("clicks", 0)),
                    spend=float(row.get("spend", 0)),
                    conversions=conversions,
                    conversion_value=conversion_value,
                )
            )

        return metrics

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_meta_datetime(self, dt_str: Optional[str]) -> Optional[date]:
        """Parse a Meta datetime string to date."""
        if not dt_str:
            return None
        try:
            # Meta uses ISO 8601 format
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.date()
        except ValueError:
            return None

    def _parse_meta_datetime_full(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse a Meta datetime string to datetime."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None

"""
Google Ads API Adapter

Implements the BaseAdPlatformAdapter interface for Google Ads.
Uses the google-ads Python library for API interactions.

API Documentation: https://developers.google.com/google-ads/api/docs/start
"""

from datetime import date, datetime, timezone
from typing import Optional

import structlog
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf import field_mask_pb2

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


# Status mapping from Google Ads to unified status
GOOGLE_STATUS_MAP = {
    "ENABLED": CampaignStatus.ENABLED,
    "PAUSED": CampaignStatus.PAUSED,
    "REMOVED": CampaignStatus.REMOVED,
}

# Objective mapping
GOOGLE_OBJECTIVE_MAP = {
    "BRAND_AWARENESS": CampaignObjective.AWARENESS,
    "WEBSITE_TRAFFIC": CampaignObjective.TRAFFIC,
    "PRODUCT_AND_BRAND_CONSIDERATION": CampaignObjective.ENGAGEMENT,
    "LEAD_GENERATION": CampaignObjective.LEADS,
    "ONLINE_SALES": CampaignObjective.SALES,
    "APP_PROMOTION": CampaignObjective.APP_PROMOTION,
}


class GoogleAdsAdapter(BaseAdPlatformAdapter):
    """
    Google Ads API adapter.

    Implements campaign management and metrics retrieval
    using the Google Ads API v15+.
    """

    def __init__(self):
        super().__init__(platform="google")
        self.developer_token = settings.google_ads_developer_token

    def _create_client(self, refresh_token: str) -> GoogleAdsClient:
        """
        Create a Google Ads client with the provided credentials.

        Args:
            refresh_token: OAuth refresh token

        Returns:
            Configured GoogleAdsClient
        """
        credentials = {
            "developer_token": self.developer_token,
            "client_id": settings.google_ads_client_id,
            "client_secret": settings.google_ads_client_secret,
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }

        return GoogleAdsClient.load_from_dict(credentials)

    def _handle_google_error(self, error: GoogleAdsException, operation: str):
        """
        Convert Google Ads errors to adapter errors.

        Args:
            error: Google Ads exception
            operation: Operation that failed

        Raises:
            Appropriate adapter error
        """
        self._log_error(operation, error)

        # Check for specific error types
        for error_detail in error.failure.errors:
            error_code = error_detail.error_code

            # Authentication errors
            if hasattr(error_code, "authentication_error"):
                raise AuthenticationError(
                    message="Google Ads authentication failed",
                    platform="google",
                    details={"error": str(error_detail.message)},
                )

            # Rate limit errors
            if hasattr(error_code, "quota_error"):
                raise RateLimitError(
                    message="Google Ads rate limit exceeded",
                    platform="google",
                    retry_after=60,
                )

            # Validation errors
            if hasattr(error_code, "request_error"):
                raise ValidationError(
                    message=f"Invalid request: {error_detail.message}",
                    platform="google",
                    details={"field": error_detail.location.field_path_elements},
                )

        # Generic platform error
        raise PlatformError(
            message=f"Google Ads error: {error.failure.errors[0].message}",
            platform="google",
            details={"request_id": error.request_id},
        )

    # =========================================================================
    # Authentication
    # =========================================================================

    async def validate_credentials(self, access_token: str) -> bool:
        """Validate Google Ads credentials by making a simple API call."""
        try:
            client = self._create_client(access_token)
            # Try to get accessible customers
            customer_service = client.get_service("CustomerService")
            customer_service.list_accessible_customers()
            return True
        except GoogleAdsException as e:
            self._log_error("validate_credentials", e)
            return False
        except Exception as e:
            self._log_error("validate_credentials", e)
            return False

    # =========================================================================
    # Account Operations
    # =========================================================================

    async def list_accounts(self, access_token: str) -> list[AdAccountInfo]:
        """List all accessible Google Ads accounts."""
        self._log_operation("list_accounts")

        try:
            client = self._create_client(access_token)
            customer_service = client.get_service("CustomerService")

            # Get accessible customer IDs
            response = customer_service.list_accessible_customers()

            accounts = []
            for resource_name in response.resource_names:
                customer_id = resource_name.split("/")[-1]

                try:
                    # Get account details
                    account_info = await self.get_account(access_token, customer_id)
                    accounts.append(account_info)
                except Exception as e:
                    self.logger.warning(
                        "failed_to_get_account_details",
                        customer_id=customer_id,
                        error=str(e),
                    )

            return accounts

        except GoogleAdsException as e:
            self._handle_google_error(e, "list_accounts")

    async def get_account(
        self, access_token: str, account_id: str
    ) -> AdAccountInfo:
        """Get details of a specific Google Ads account."""
        self._log_operation("get_account", account_id=account_id)

        try:
            client = self._create_client(access_token)
            ga_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    customer.id,
                    customer.descriptive_name,
                    customer.currency_code,
                    customer.time_zone,
                    customer.status
                FROM customer
                WHERE customer.id = {account_id}
            """

            response = ga_service.search(customer_id=account_id, query=query)

            for row in response:
                customer = row.customer
                return AdAccountInfo(
                    account_id=str(customer.id),
                    account_name=customer.descriptive_name or f"Account {customer.id}",
                    currency=customer.currency_code,
                    timezone=customer.time_zone,
                    status=customer.status.name,
                )

            raise PlatformError(
                message=f"Account {account_id} not found",
                platform="google",
            )

        except GoogleAdsException as e:
            self._handle_google_error(e, "get_account")

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    async def list_campaigns(
        self,
        access_token: str,
        account_id: str,
        status_filter: Optional[list[CampaignStatus]] = None,
    ) -> list[CampaignInfo]:
        """List campaigns in a Google Ads account."""
        self._log_operation("list_campaigns", account_id=account_id)

        try:
            client = self._create_client(access_token)
            ga_service = client.get_service("GoogleAdsService")

            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    campaign.campaign_budget,
                    campaign.start_date,
                    campaign.end_date
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                ORDER BY campaign.name
            """

            response = ga_service.search(customer_id=account_id, query=query)

            campaigns = []
            for row in response:
                campaign = row.campaign
                status = GOOGLE_STATUS_MAP.get(
                    campaign.status.name, CampaignStatus.UNKNOWN
                )

                # Apply status filter if provided
                if status_filter and status not in status_filter:
                    continue

                campaigns.append(
                    CampaignInfo(
                        campaign_id=str(campaign.id),
                        name=campaign.name,
                        status=status,
                        objective=None,  # Would need additional query for bidding strategy
                        budget_amount=None,  # Separate budget resource
                        budget_type="daily",
                        start_date=self._parse_google_date(campaign.start_date),
                        end_date=self._parse_google_date(campaign.end_date),
                        created_at=None,
                        updated_at=None,
                        platform_data={
                            "channel_type": campaign.advertising_channel_type.name,
                        },
                    )
                )

            return campaigns

        except GoogleAdsException as e:
            self._handle_google_error(e, "list_campaigns")

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

        try:
            client = self._create_client(access_token)
            ga_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    campaign.start_date,
                    campaign.end_date,
                    campaign_budget.amount_micros,
                    campaign_budget.delivery_method
                FROM campaign
                WHERE campaign.id = {campaign_id}
            """

            response = ga_service.search(customer_id=account_id, query=query)

            for row in response:
                campaign = row.campaign
                budget = row.campaign_budget

                return CampaignInfo(
                    campaign_id=str(campaign.id),
                    name=campaign.name,
                    status=GOOGLE_STATUS_MAP.get(
                        campaign.status.name, CampaignStatus.UNKNOWN
                    ),
                    objective=None,
                    budget_amount=budget.amount_micros / 1_000_000 if budget.amount_micros else None,
                    budget_type="daily",
                    start_date=self._parse_google_date(campaign.start_date),
                    end_date=self._parse_google_date(campaign.end_date),
                    created_at=None,
                    updated_at=None,
                    platform_data={
                        "channel_type": campaign.advertising_channel_type.name,
                    },
                )

            raise PlatformError(
                message=f"Campaign {campaign_id} not found",
                platform="google",
            )

        except GoogleAdsException as e:
            self._handle_google_error(e, "get_campaign")

    async def create_campaign(
        self,
        access_token: str,
        account_id: str,
        request: CampaignCreateRequest,
    ) -> str:
        """Create a new Google Ads campaign."""
        self._log_operation("create_campaign", account_id=account_id, name=request.name)

        try:
            client = self._create_client(access_token)
            campaign_service = client.get_service("CampaignService")
            campaign_budget_service = client.get_service("CampaignBudgetService")

            # First, create a campaign budget
            budget_operation = client.get_type("CampaignBudgetOperation")
            budget = budget_operation.create
            budget.name = f"Budget for {request.name}"
            budget.amount_micros = int(request.budget_amount * 1_000_000)
            budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD

            budget_response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=account_id, operations=[budget_operation]
            )
            budget_resource_name = budget_response.results[0].resource_name

            # Now create the campaign
            campaign_operation = client.get_type("CampaignOperation")
            campaign = campaign_operation.create
            campaign.name = request.name
            campaign.campaign_budget = budget_resource_name
            campaign.advertising_channel_type = (
                client.enums.AdvertisingChannelTypeEnum.SEARCH
            )
            campaign.status = client.enums.CampaignStatusEnum.PAUSED  # Start paused

            if request.start_date:
                campaign.start_date = request.start_date.strftime("%Y-%m-%d")
            if request.end_date:
                campaign.end_date = request.end_date.strftime("%Y-%m-%d")

            # Set bidding strategy (simplified - maximize clicks)
            campaign.maximize_clicks.cpc_bid_ceiling_micros = 1_000_000  # $1 max CPC

            response = campaign_service.mutate_campaigns(
                customer_id=account_id, operations=[campaign_operation]
            )

            campaign_resource = response.results[0].resource_name
            campaign_id = campaign_resource.split("/")[-1]

            self._log_operation(
                "create_campaign_success",
                account_id=account_id,
                campaign_id=campaign_id,
            )

            return campaign_id

        except GoogleAdsException as e:
            self._handle_google_error(e, "create_campaign")

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

        try:
            client = self._create_client(access_token)
            campaign_service = client.get_service("CampaignService")

            campaign_operation = client.get_type("CampaignOperation")
            campaign = campaign_operation.update
            campaign.resource_name = (
                f"customers/{account_id}/campaigns/{campaign_id}"
            )

            # Build field mask for fields to update
            field_mask_paths = []

            if request.name is not None:
                campaign.name = request.name
                field_mask_paths.append("name")

            if request.status is not None:
                status_enum = client.enums.CampaignStatusEnum
                if request.status == CampaignStatus.ENABLED:
                    campaign.status = status_enum.ENABLED
                elif request.status == CampaignStatus.PAUSED:
                    campaign.status = status_enum.PAUSED
                field_mask_paths.append("status")

            if request.end_date is not None:
                campaign.end_date = request.end_date.strftime("%Y-%m-%d")
                field_mask_paths.append("end_date")

            if not field_mask_paths:
                return True  # Nothing to update

            campaign_operation.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=field_mask_paths)
            )

            campaign_service.mutate_campaigns(
                customer_id=account_id, operations=[campaign_operation]
            )

            return True

        except GoogleAdsException as e:
            self._handle_google_error(e, "update_campaign")

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

        try:
            client = self._create_client(access_token)
            ga_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM campaign
                WHERE campaign.id = {campaign_id}
                AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY segments.date
            """

            response = ga_service.search(customer_id=account_id, query=query)

            metrics = []
            for row in response:
                metrics.append(
                    CampaignMetrics(
                        campaign_id=campaign_id,
                        date=date.fromisoformat(row.segments.date),
                        impressions=row.metrics.impressions,
                        clicks=row.metrics.clicks,
                        spend=row.metrics.cost_micros / 1_000_000,
                        conversions=int(row.metrics.conversions),
                        conversion_value=row.metrics.conversions_value,
                    )
                )

            return metrics

        except GoogleAdsException as e:
            self._handle_google_error(e, "get_campaign_metrics")

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

        try:
            client = self._create_client(access_token)
            ga_service = client.get_service("GoogleAdsService")

            query = f"""
                SELECT
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM customer
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY segments.date
            """

            response = ga_service.search(customer_id=account_id, query=query)

            metrics = []
            for row in response:
                metrics.append(
                    CampaignMetrics(
                        campaign_id="",  # Account-level metrics
                        date=date.fromisoformat(row.segments.date),
                        impressions=row.metrics.impressions,
                        clicks=row.metrics.clicks,
                        spend=row.metrics.cost_micros / 1_000_000,
                        conversions=int(row.metrics.conversions),
                        conversion_value=row.metrics.conversions_value,
                    )
                )

            return metrics

        except GoogleAdsException as e:
            self._handle_google_error(e, "get_account_metrics")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_google_date(self, date_str: str) -> Optional[date]:
        """Parse a Google Ads date string (YYYY-MM-DD)."""
        if not date_str or date_str == "0000-00-00":
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

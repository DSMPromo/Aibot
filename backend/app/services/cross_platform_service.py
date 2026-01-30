"""
Cross-Platform Campaign Service

Provides unified operations across multiple ad platforms:
- Multi-platform campaign creation
- UTM parameter generation
- Unified metrics aggregation
- Platform comparison analysis
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from uuid import uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, AdCopy
from app.models.ad_account import AdAccount
from app.models.metrics import CampaignMetrics

logger = structlog.get_logger()


# =============================================================================
# UTM Parameter Generation
# =============================================================================

def generate_utm_parameters(
    campaign_name: str,
    platform: str,
    source: Optional[str] = None,
    medium: str = "cpc",
    content: Optional[str] = None,
    term: Optional[str] = None,
) -> dict[str, str]:
    """
    Generate UTM tracking parameters for a campaign.

    Args:
        campaign_name: Campaign name (will be sanitized)
        platform: Ad platform (google, meta, tiktok)
        source: Traffic source (defaults to platform)
        medium: Marketing medium (defaults to cpc)
        content: Ad content identifier
        term: Keyword term

    Returns:
        Dictionary of UTM parameters
    """
    # Sanitize campaign name for URL
    sanitized_name = campaign_name.lower().replace(" ", "_").replace("-", "_")
    sanitized_name = "".join(c for c in sanitized_name if c.isalnum() or c == "_")

    # Map platform to source
    source_map = {
        "google": "google",
        "meta": "facebook",
        "tiktok": "tiktok",
    }

    params = {
        "utm_source": source or source_map.get(platform, platform),
        "utm_medium": medium,
        "utm_campaign": sanitized_name,
    }

    if content:
        params["utm_content"] = content

    if term:
        params["utm_term"] = term

    return params


def append_utm_to_url(url: str, utm_params: dict[str, str]) -> str:
    """
    Append UTM parameters to a URL.

    Args:
        url: Base URL
        utm_params: UTM parameters to append

    Returns:
        URL with UTM parameters
    """
    parsed = urlparse(url)
    existing_params = parse_qs(parsed.query)

    # Merge existing params with UTM params
    for key, value in utm_params.items():
        existing_params[key] = [value]

    # Reconstruct URL
    new_query = urlencode(existing_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)

    return urlunparse(new_parsed)


# =============================================================================
# Cross-Platform Campaign Creation
# =============================================================================

async def create_multi_platform_campaign(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    name: str,
    objective: str,
    budget_amount: Decimal,
    budget_type: str,
    platform_account_ids: dict[str, str],  # platform -> ad_account_id
    description: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_ongoing: bool = False,
    targeting: Optional[dict] = None,
    ad_copies: Optional[list[dict]] = None,
    add_utm_tracking: bool = True,
) -> dict[str, Campaign]:
    """
    Create a campaign across multiple platforms.

    Creates separate Campaign records for each platform with
    consistent settings and optional UTM tracking.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: Creating user ID
        name: Campaign name (will be suffixed with platform)
        objective: Campaign objective
        budget_amount: Budget per platform
        budget_type: daily or lifetime
        platform_account_ids: Map of platform to ad account ID
        description: Campaign description
        start_date: Start date
        end_date: End date
        is_ongoing: Whether campaign is ongoing
        targeting: Targeting configuration
        ad_copies: Ad copy templates
        add_utm_tracking: Whether to add UTM parameters to URLs

    Returns:
        Dictionary mapping platform to created Campaign
    """
    created_campaigns = {}

    for platform, ad_account_id in platform_account_ids.items():
        # Verify ad account exists and belongs to org
        result = await db.execute(
            select(AdAccount).where(
                AdAccount.id == ad_account_id,
                AdAccount.org_id == org_id,
                AdAccount.platform == platform,
                AdAccount.is_active == True,
            )
        )
        ad_account = result.scalar_one_or_none()

        if not ad_account:
            logger.warning(
                "skip_platform_no_account",
                platform=platform,
                ad_account_id=ad_account_id,
            )
            continue

        # Create platform-specific campaign name
        platform_name = f"{name} - {platform.title()}"

        # Create campaign
        campaign = Campaign(
            id=str(uuid4()),
            org_id=org_id,
            ad_account_id=ad_account_id,
            name=platform_name,
            description=description,
            platform=platform,
            objective=objective,
            status="draft",
            budget_type=budget_type,
            budget_amount=budget_amount,
            budget_currency=ad_account.metadata.get("currency", "USD") if ad_account.metadata else "USD",
            start_date=start_date,
            end_date=end_date,
            is_ongoing=is_ongoing,
            targeting=targeting,
            created_by_id=user_id,
        )
        db.add(campaign)

        # Add ad copies with UTM tracking
        if ad_copies:
            for copy_data in ad_copies:
                final_url = copy_data.get("final_url", "")

                # Add UTM parameters if requested
                if add_utm_tracking and final_url:
                    utm_params = generate_utm_parameters(
                        campaign_name=name,
                        platform=platform,
                        content=copy_data.get("variation_name"),
                    )
                    final_url = append_utm_to_url(final_url, utm_params)

                ad_copy = AdCopy(
                    id=str(uuid4()),
                    campaign_id=campaign.id,
                    headline_1=copy_data.get("headline_1", ""),
                    headline_2=copy_data.get("headline_2"),
                    headline_3=copy_data.get("headline_3"),
                    description_1=copy_data.get("description_1", ""),
                    description_2=copy_data.get("description_2"),
                    path_1=copy_data.get("path_1"),
                    path_2=copy_data.get("path_2"),
                    final_url=final_url,
                    call_to_action=copy_data.get("call_to_action"),
                    variation_name=copy_data.get("variation_name"),
                    is_primary=copy_data.get("is_primary", False),
                    is_ai_generated=copy_data.get("is_ai_generated", False),
                )
                db.add(ad_copy)

        created_campaigns[platform] = campaign

    await db.commit()

    logger.info(
        "multi_platform_campaign_created",
        campaign_name=name,
        platforms=list(created_campaigns.keys()),
        org_id=org_id,
    )

    return created_campaigns


# =============================================================================
# Platform Comparison Analytics
# =============================================================================

async def get_platform_comparison(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Get performance comparison across platforms.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start date
        end_date: End date

    Returns:
        Comparison data by platform
    """
    # Get campaigns by platform
    campaigns_result = await db.execute(
        select(Campaign.platform, func.count(Campaign.id))
        .where(
            Campaign.org_id == org_id,
            Campaign.status.in_(["active", "paused"]),
        )
        .group_by(Campaign.platform)
    )
    campaigns_by_platform = {row[0]: row[1] for row in campaigns_result.all()}

    # Get metrics by platform
    metrics_result = await db.execute(
        select(
            Campaign.platform,
            func.sum(CampaignMetrics.impressions).label("impressions"),
            func.sum(CampaignMetrics.clicks).label("clicks"),
            func.sum(CampaignMetrics.spend).label("spend"),
            func.sum(CampaignMetrics.conversions).label("conversions"),
            func.sum(CampaignMetrics.conversion_value).label("conversion_value"),
        )
        .join(Campaign, CampaignMetrics.campaign_id == Campaign.id)
        .where(
            Campaign.org_id == org_id,
            func.date(CampaignMetrics.timestamp) >= start_date,
            func.date(CampaignMetrics.timestamp) <= end_date,
        )
        .group_by(Campaign.platform)
    )

    platform_data = {}
    for row in metrics_result.all():
        platform = row.platform
        impressions = int(row.impressions or 0)
        clicks = int(row.clicks or 0)
        spend = float(row.spend or 0)
        conversions = int(row.conversions or 0)
        conversion_value = float(row.conversion_value or 0)

        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = spend / clicks if clicks > 0 else 0
        cpa = spend / conversions if conversions > 0 else 0
        roas = conversion_value / spend if spend > 0 else 0

        platform_data[platform] = {
            "campaign_count": campaigns_by_platform.get(platform, 0),
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": conversions,
            "conversion_value": conversion_value,
            "ctr": round(ctr, 2),
            "cpc": round(cpc, 2),
            "cpa": round(cpa, 2),
            "roas": round(roas, 2),
        }

    # Calculate totals
    total_spend = sum(p["spend"] for p in platform_data.values())
    totals = {
        "campaign_count": sum(p["campaign_count"] for p in platform_data.values()),
        "impressions": sum(p["impressions"] for p in platform_data.values()),
        "clicks": sum(p["clicks"] for p in platform_data.values()),
        "spend": total_spend,
        "conversions": sum(p["conversions"] for p in platform_data.values()),
        "conversion_value": sum(p["conversion_value"] for p in platform_data.values()),
    }

    # Add spend share
    for platform, data in platform_data.items():
        data["spend_share"] = round((data["spend"] / total_spend * 100) if total_spend > 0 else 0, 1)

    return {
        "platforms": platform_data,
        "totals": totals,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    }


async def get_unified_metrics_summary(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Get unified metrics across all platforms.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start date
        end_date: End date

    Returns:
        Aggregated metrics summary
    """
    result = await db.execute(
        select(
            func.sum(CampaignMetrics.impressions).label("impressions"),
            func.sum(CampaignMetrics.clicks).label("clicks"),
            func.sum(CampaignMetrics.spend).label("spend"),
            func.sum(CampaignMetrics.conversions).label("conversions"),
            func.sum(CampaignMetrics.conversion_value).label("conversion_value"),
        )
        .join(Campaign, CampaignMetrics.campaign_id == Campaign.id)
        .where(
            Campaign.org_id == org_id,
            func.date(CampaignMetrics.timestamp) >= start_date,
            func.date(CampaignMetrics.timestamp) <= end_date,
        )
    )

    row = result.first()
    if not row:
        return {
            "impressions": 0,
            "clicks": 0,
            "spend": 0,
            "conversions": 0,
            "conversion_value": 0,
            "ctr": 0,
            "cpc": 0,
            "cpa": 0,
            "roas": 0,
        }

    impressions = int(row.impressions or 0)
    clicks = int(row.clicks or 0)
    spend = float(row.spend or 0)
    conversions = int(row.conversions or 0)
    conversion_value = float(row.conversion_value or 0)

    return {
        "impressions": impressions,
        "clicks": clicks,
        "spend": round(spend, 2),
        "conversions": conversions,
        "conversion_value": round(conversion_value, 2),
        "ctr": round((clicks / impressions * 100) if impressions > 0 else 0, 2),
        "cpc": round(spend / clicks if clicks > 0 else 0, 2),
        "cpa": round(spend / conversions if conversions > 0 else 0, 2),
        "roas": round(conversion_value / spend if spend > 0 else 0, 2),
    }

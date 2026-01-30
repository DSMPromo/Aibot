"""
Analytics API endpoints.

Provides analytics data for dashboards and reports:
- Overview metrics aggregation
- Campaign-level metrics breakdown
- Time series data for charts
- Period-over-period comparison
"""

from datetime import date, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


def get_date_range(start_date: Optional[date], end_date: Optional[date]) -> tuple[date, date]:
    """Get date range with defaults if not provided."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    return start_date, end_date


from app.services.analytics_service import (
    get_overview_metrics,
    get_campaign_metrics_summary,
    get_single_campaign_metrics,
    get_time_series_metrics,
    get_today_metrics,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class MetricsSummaryResponse(BaseModel):
    """Aggregated metrics summary."""
    impressions: int
    clicks: int
    ctr: float
    spend: float
    conversions: int
    conversion_value: float
    cpa: float
    roas: float
    avg_cpc: float
    avg_cpm: float


class MetricsComparisonResponse(BaseModel):
    """Metrics with period comparison."""
    current: MetricsSummaryResponse
    previous: Optional[MetricsSummaryResponse] = None
    change_percent: dict = Field(default_factory=dict)


class CampaignMetricsResponse(BaseModel):
    """Metrics for a single campaign."""
    campaign_id: str
    campaign_name: str
    platform: str
    status: str
    metrics: MetricsSummaryResponse


class CampaignMetricsListResponse(BaseModel):
    """List of campaign metrics."""
    campaigns: list[CampaignMetricsResponse]
    total: int
    page: int
    page_size: int


class TimeSeriesPointResponse(BaseModel):
    """Single time series data point."""
    timestamp: str
    impressions: int
    clicks: int
    spend: float
    conversions: int
    conversion_value: float


class TimeSeriesResponse(BaseModel):
    """Time series data."""
    data: list[TimeSeriesPointResponse]
    granularity: str
    start_date: str
    end_date: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/overview", response_model=MetricsComparisonResponse)
async def get_analytics_overview(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    compare_previous: bool = Query(default=False, description="Include previous period comparison"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated overview metrics for all campaigns.

    Returns total impressions, clicks, spend, conversions, and calculated
    metrics like CTR, CPA, and ROAS for the specified date range.

    Optionally includes comparison with the previous period of equal length.
    """
    # Set defaults if not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    # Limit date range to 90 days
    if (end_date - start_date).days > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 90 days",
        )

    comparison = await get_overview_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        compare_previous=compare_previous,
    )

    return MetricsComparisonResponse(
        current=MetricsSummaryResponse(
            impressions=comparison.current.impressions,
            clicks=comparison.current.clicks,
            ctr=comparison.current.ctr,
            spend=float(comparison.current.spend),
            conversions=comparison.current.conversions,
            conversion_value=float(comparison.current.conversion_value),
            cpa=float(comparison.current.cpa),
            roas=comparison.current.roas,
            avg_cpc=float(comparison.current.avg_cpc),
            avg_cpm=float(comparison.current.avg_cpm),
        ),
        previous=MetricsSummaryResponse(
            impressions=comparison.previous.impressions,
            clicks=comparison.previous.clicks,
            ctr=comparison.previous.ctr,
            spend=float(comparison.previous.spend),
            conversions=comparison.previous.conversions,
            conversion_value=float(comparison.previous.conversion_value),
            cpa=float(comparison.previous.cpa),
            roas=comparison.previous.roas,
            avg_cpc=float(comparison.previous.avg_cpc),
            avg_cpm=float(comparison.previous.avg_cpm),
        ) if comparison.previous else None,
        change_percent=comparison.change_percent,
    )


@router.get("/today", response_model=MetricsSummaryResponse)
async def get_today_overview(
    db: AsyncSession = Depends(get_db),
):
    """
    Get today's metrics (real-time tracking).

    Returns current day's aggregated metrics for live monitoring.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    summary = await get_today_metrics(db=db, org_id=org_id)

    return MetricsSummaryResponse(
        impressions=summary.impressions,
        clicks=summary.clicks,
        ctr=summary.ctr,
        spend=float(summary.spend),
        conversions=summary.conversions,
        conversion_value=float(summary.conversion_value),
        cpa=float(summary.cpa),
        roas=summary.roas,
        avg_cpc=float(summary.avg_cpc),
        avg_cpm=float(summary.avg_cpm),
    )


@router.get("/campaigns", response_model=CampaignMetricsListResponse)
async def get_campaigns_metrics(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get metrics breakdown by campaign.

    Returns a list of campaigns with their metrics for the specified
    date range. Supports pagination.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    # Set defaults if not provided
    start_date, end_date = get_date_range(start_date, end_date)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    offset = (page - 1) * page_size

    summaries, total = await get_campaign_metrics_summary(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        limit=page_size,
        offset=offset,
    )

    return CampaignMetricsListResponse(
        campaigns=[
            CampaignMetricsResponse(
                campaign_id=s.campaign_id,
                campaign_name=s.campaign_name,
                platform=s.platform,
                status=s.status,
                metrics=MetricsSummaryResponse(
                    impressions=s.metrics.impressions,
                    clicks=s.metrics.clicks,
                    ctr=s.metrics.ctr,
                    spend=float(s.metrics.spend),
                    conversions=s.metrics.conversions,
                    conversion_value=float(s.metrics.conversion_value),
                    cpa=float(s.metrics.cpa),
                    roas=s.metrics.roas,
                    avg_cpc=float(s.metrics.avg_cpc),
                    avg_cpm=float(s.metrics.avg_cpm),
                ),
            )
            for s in summaries
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/campaigns/{campaign_id}", response_model=MetricsComparisonResponse)
async def get_campaign_metrics(
    campaign_id: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    compare_previous: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed metrics for a specific campaign.

    Returns metrics with optional period-over-period comparison.
    """
    # Set defaults if not provided
    start_date, end_date = get_date_range(start_date, end_date)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    comparison = await get_single_campaign_metrics(
        db=db,
        campaign_id=campaign_id,
        start_date=start_date,
        end_date=end_date,
        compare_previous=compare_previous,
    )

    return MetricsComparisonResponse(
        current=MetricsSummaryResponse(
            impressions=comparison.current.impressions,
            clicks=comparison.current.clicks,
            ctr=comparison.current.ctr,
            spend=float(comparison.current.spend),
            conversions=comparison.current.conversions,
            conversion_value=float(comparison.current.conversion_value),
            cpa=float(comparison.current.cpa),
            roas=comparison.current.roas,
            avg_cpc=float(comparison.current.avg_cpc),
            avg_cpm=float(comparison.current.avg_cpm),
        ),
        previous=MetricsSummaryResponse(
            impressions=comparison.previous.impressions,
            clicks=comparison.previous.clicks,
            ctr=comparison.previous.ctr,
            spend=float(comparison.previous.spend),
            conversions=comparison.previous.conversions,
            conversion_value=float(comparison.previous.conversion_value),
            cpa=float(comparison.previous.cpa),
            roas=comparison.previous.roas,
            avg_cpc=float(comparison.previous.avg_cpc),
            avg_cpm=float(comparison.previous.avg_cpm),
        ) if comparison.previous else None,
        change_percent=comparison.change_percent,
    )


@router.get("/time-series", response_model=TimeSeriesResponse)
async def get_analytics_time_series(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    granularity: str = Query(default="daily", pattern="^(hourly|daily|weekly)$"),
    campaign_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get time series metrics data for charts.

    Returns metrics aggregated by the specified granularity (hourly, daily, weekly).
    Can be filtered to a specific campaign or show all campaigns.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    # Set defaults if not provided
    start_date, end_date = get_date_range(start_date, end_date)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    # Validate granularity based on date range
    days = (end_date - start_date).days
    if granularity == "hourly" and days > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hourly granularity is only available for date ranges up to 7 days",
        )

    points = await get_time_series_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        campaign_id=campaign_id,
    )

    return TimeSeriesResponse(
        data=[
            TimeSeriesPointResponse(
                timestamp=p.timestamp.isoformat(),
                impressions=p.impressions,
                clicks=p.clicks,
                spend=float(p.spend),
                conversions=p.conversions,
                conversion_value=float(p.conversion_value),
            )
            for p in points
        ],
        granularity=granularity,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )


# =============================================================================
# Cross-Platform Comparison
# =============================================================================

class PlatformMetricsResponse(BaseModel):
    """Metrics for a single platform."""
    campaign_count: int
    impressions: int
    clicks: int
    spend: float
    conversions: int
    conversion_value: float
    ctr: float
    cpc: float
    cpa: float
    roas: float
    spend_share: float


class PlatformComparisonResponse(BaseModel):
    """Cross-platform performance comparison."""
    platforms: dict[str, PlatformMetricsResponse]
    totals: dict
    period: dict


@router.get("/platform-comparison", response_model=PlatformComparisonResponse)
async def get_platform_comparison_endpoint(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare performance across all connected ad platforms.

    Returns aggregated metrics for each platform (Google Ads, Meta Ads, TikTok Ads)
    along with spend share and performance indicators.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    # Set defaults if not provided
    start_date, end_date = get_date_range(start_date, end_date)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    from app.services.cross_platform_service import get_platform_comparison

    comparison = await get_platform_comparison(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
    )

    return PlatformComparisonResponse(
        platforms={
            platform: PlatformMetricsResponse(**data)
            for platform, data in comparison["platforms"].items()
        },
        totals=comparison["totals"],
        period=comparison["period"],
    )


class UnifiedMetricsResponse(BaseModel):
    """Unified metrics across all platforms."""
    impressions: int
    clicks: int
    spend: float
    conversions: int
    conversion_value: float
    ctr: float
    cpc: float
    cpa: float
    roas: float


@router.get("/unified", response_model=UnifiedMetricsResponse)
async def get_unified_metrics_endpoint(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get unified metrics aggregated across all connected platforms.

    Provides a single view of total advertising performance regardless of platform.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    # Set defaults if not provided
    start_date, end_date = get_date_range(start_date, end_date)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    from app.services.cross_platform_service import get_unified_metrics_summary

    metrics = await get_unified_metrics_summary(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
    )

    return UnifiedMetricsResponse(**metrics)

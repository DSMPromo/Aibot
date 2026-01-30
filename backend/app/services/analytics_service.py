"""
Analytics Service

Provides analytics data aggregation and calculations.

Features:
- Overview metrics aggregation
- Campaign-level metrics
- Period-over-period comparison
- Date range filtering
- Granularity selection (hourly/daily/weekly)
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

import structlog
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import CampaignMetrics
from app.models.campaign import Campaign

logger = structlog.get_logger()


@dataclass
class MetricsSummary:
    """Summary of metrics for a period."""
    impressions: int
    clicks: int
    ctr: float
    spend: Decimal
    conversions: int
    conversion_value: Decimal
    cpa: Decimal
    roas: float
    avg_cpc: Decimal
    avg_cpm: Decimal


@dataclass
class MetricsComparison:
    """Metrics with period-over-period comparison."""
    current: MetricsSummary
    previous: Optional[MetricsSummary]
    change_percent: dict  # Percentage change for each metric


@dataclass
class CampaignMetricsSummary:
    """Metrics summary for a single campaign."""
    campaign_id: str
    campaign_name: str
    platform: str
    status: str
    metrics: MetricsSummary


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    impressions: int
    clicks: int
    spend: Decimal
    conversions: int
    conversion_value: Decimal


def calculate_change_percent(current: float, previous: float) -> Optional[float]:
    """Calculate percentage change between two values."""
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 2)


def calculate_summary_from_rows(rows) -> MetricsSummary:
    """Calculate summary metrics from database rows."""
    total_impressions = sum(r.impressions or 0 for r in rows)
    total_clicks = sum(r.clicks or 0 for r in rows)
    total_spend = sum(Decimal(str(r.spend or 0)) for r in rows)
    total_conversions = sum(r.conversions or 0 for r in rows)
    total_conversion_value = sum(Decimal(str(r.conversion_value or 0)) for r in rows)

    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else Decimal("0")
    avg_cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else Decimal("0")
    cpa = (total_spend / total_conversions) if total_conversions > 0 else Decimal("0")
    roas = float(total_conversion_value / total_spend) if total_spend > 0 else 0

    return MetricsSummary(
        impressions=total_impressions,
        clicks=total_clicks,
        ctr=round(ctr, 4),
        spend=round(total_spend, 2),
        conversions=total_conversions,
        conversion_value=round(total_conversion_value, 2),
        cpa=round(cpa, 2),
        roas=round(roas, 4),
        avg_cpc=round(avg_cpc, 4),
        avg_cpm=round(avg_cpm, 4),
    )


async def get_overview_metrics(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    compare_previous: bool = False,
) -> MetricsComparison:
    """
    Get aggregated overview metrics for all campaigns in an organization.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        compare_previous: Whether to include previous period comparison

    Returns:
        MetricsComparison with current and optional previous period
    """
    # Get campaign IDs for this org
    campaign_query = select(Campaign.id).where(Campaign.org_id == org_id)
    campaign_result = await db.execute(campaign_query)
    campaign_ids = [str(c) for c in campaign_result.scalars().all()]

    if not campaign_ids:
        empty_summary = MetricsSummary(
            impressions=0,
            clicks=0,
            ctr=0,
            spend=Decimal("0"),
            conversions=0,
            conversion_value=Decimal("0"),
            cpa=Decimal("0"),
            roas=0,
            avg_cpc=Decimal("0"),
            avg_cpm=Decimal("0"),
        )
        return MetricsComparison(current=empty_summary, previous=None, change_percent={})

    # Get current period metrics
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    current_query = (
        select(CampaignMetrics)
        .where(
            CampaignMetrics.campaign_id.in_(campaign_ids),
            CampaignMetrics.timestamp >= start_datetime,
            CampaignMetrics.timestamp <= end_datetime,
            CampaignMetrics.granularity == "raw",
        )
    )

    current_result = await db.execute(current_query)
    current_rows = current_result.scalars().all()
    current_summary = calculate_summary_from_rows(current_rows)

    # Get previous period if requested
    previous_summary = None
    change_percent = {}

    if compare_previous:
        period_length = (end_date - start_date).days + 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=period_length - 1)

        prev_start_datetime = datetime.combine(prev_start_date, datetime.min.time(), tzinfo=timezone.utc)
        prev_end_datetime = datetime.combine(prev_end_date, datetime.max.time(), tzinfo=timezone.utc)

        prev_query = (
            select(CampaignMetrics)
            .where(
                CampaignMetrics.campaign_id.in_(campaign_ids),
                CampaignMetrics.timestamp >= prev_start_datetime,
                CampaignMetrics.timestamp <= prev_end_datetime,
                CampaignMetrics.granularity == "raw",
            )
        )

        prev_result = await db.execute(prev_query)
        prev_rows = prev_result.scalars().all()
        previous_summary = calculate_summary_from_rows(prev_rows)

        # Calculate changes
        change_percent = {
            "impressions": calculate_change_percent(current_summary.impressions, previous_summary.impressions),
            "clicks": calculate_change_percent(current_summary.clicks, previous_summary.clicks),
            "ctr": calculate_change_percent(current_summary.ctr, previous_summary.ctr),
            "spend": calculate_change_percent(float(current_summary.spend), float(previous_summary.spend)),
            "conversions": calculate_change_percent(current_summary.conversions, previous_summary.conversions),
            "conversion_value": calculate_change_percent(
                float(current_summary.conversion_value),
                float(previous_summary.conversion_value),
            ),
            "cpa": calculate_change_percent(float(current_summary.cpa), float(previous_summary.cpa)),
            "roas": calculate_change_percent(current_summary.roas, previous_summary.roas),
        }

    return MetricsComparison(
        current=current_summary,
        previous=previous_summary,
        change_percent=change_percent,
    )


async def get_campaign_metrics_summary(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CampaignMetricsSummary], int]:
    """
    Get metrics summary for each campaign.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        limit: Max number of results
        offset: Result offset for pagination

    Returns:
        Tuple of (list of campaign summaries, total count)
    """
    # Get campaigns with their metrics
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Count total campaigns
    count_query = select(func.count(Campaign.id)).where(Campaign.org_id == org_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get campaigns
    campaigns_query = (
        select(Campaign)
        .where(Campaign.org_id == org_id)
        .order_by(Campaign.name)
        .limit(limit)
        .offset(offset)
    )

    campaigns_result = await db.execute(campaigns_query)
    campaigns = campaigns_result.scalars().all()

    summaries = []
    for campaign in campaigns:
        # Get metrics for this campaign
        metrics_query = (
            select(CampaignMetrics)
            .where(
                CampaignMetrics.campaign_id == campaign.id,
                CampaignMetrics.timestamp >= start_datetime,
                CampaignMetrics.timestamp <= end_datetime,
                CampaignMetrics.granularity == "raw",
            )
        )

        metrics_result = await db.execute(metrics_query)
        metrics_rows = metrics_result.scalars().all()

        metrics_summary = calculate_summary_from_rows(metrics_rows)

        summaries.append(CampaignMetricsSummary(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            platform=campaign.platform,
            status=campaign.status,
            metrics=metrics_summary,
        ))

    return summaries, total


async def get_single_campaign_metrics(
    db: AsyncSession,
    campaign_id: str,
    start_date: date,
    end_date: date,
    compare_previous: bool = False,
) -> MetricsComparison:
    """
    Get metrics for a single campaign.

    Args:
        db: Database session
        campaign_id: Campaign ID
        start_date: Start of date range
        end_date: End of date range
        compare_previous: Whether to include previous period comparison

    Returns:
        MetricsComparison with current and optional previous period
    """
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Get current period metrics
    current_query = (
        select(CampaignMetrics)
        .where(
            CampaignMetrics.campaign_id == campaign_id,
            CampaignMetrics.timestamp >= start_datetime,
            CampaignMetrics.timestamp <= end_datetime,
            CampaignMetrics.granularity == "raw",
        )
    )

    current_result = await db.execute(current_query)
    current_rows = current_result.scalars().all()
    current_summary = calculate_summary_from_rows(current_rows)

    previous_summary = None
    change_percent = {}

    if compare_previous:
        period_length = (end_date - start_date).days + 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=period_length - 1)

        prev_start_datetime = datetime.combine(prev_start_date, datetime.min.time(), tzinfo=timezone.utc)
        prev_end_datetime = datetime.combine(prev_end_date, datetime.max.time(), tzinfo=timezone.utc)

        prev_query = (
            select(CampaignMetrics)
            .where(
                CampaignMetrics.campaign_id == campaign_id,
                CampaignMetrics.timestamp >= prev_start_datetime,
                CampaignMetrics.timestamp <= prev_end_datetime,
                CampaignMetrics.granularity == "raw",
            )
        )

        prev_result = await db.execute(prev_query)
        prev_rows = prev_result.scalars().all()
        previous_summary = calculate_summary_from_rows(prev_rows)

        change_percent = {
            "impressions": calculate_change_percent(current_summary.impressions, previous_summary.impressions),
            "clicks": calculate_change_percent(current_summary.clicks, previous_summary.clicks),
            "ctr": calculate_change_percent(current_summary.ctr, previous_summary.ctr),
            "spend": calculate_change_percent(float(current_summary.spend), float(previous_summary.spend)),
            "conversions": calculate_change_percent(current_summary.conversions, previous_summary.conversions),
            "roas": calculate_change_percent(current_summary.roas, previous_summary.roas),
        }

    return MetricsComparison(
        current=current_summary,
        previous=previous_summary,
        change_percent=change_percent,
    )


async def get_time_series_metrics(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    granularity: str = "daily",
    campaign_id: Optional[str] = None,
) -> list[TimeSeriesPoint]:
    """
    Get time series metrics data.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        granularity: Time granularity (hourly, daily, weekly)
        campaign_id: Optional campaign filter

    Returns:
        List of time series points
    """
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Determine time bucket based on granularity
    if granularity == "hourly":
        time_bucket = "1 hour"
    elif granularity == "weekly":
        time_bucket = "1 week"
    else:
        time_bucket = "1 day"

    # Build campaign filter
    if campaign_id:
        campaign_filter = CampaignMetrics.campaign_id == campaign_id
    else:
        # Get all campaign IDs for this org
        campaign_query = select(Campaign.id).where(Campaign.org_id == org_id)
        campaign_result = await db.execute(campaign_query)
        campaign_ids = [str(c) for c in campaign_result.scalars().all()]

        if not campaign_ids:
            return []

        campaign_filter = CampaignMetrics.campaign_id.in_(campaign_ids)

    # Use raw SQL for time_bucket function (TimescaleDB)
    query = text(f"""
        SELECT
            time_bucket('{time_bucket}', timestamp) AS bucket,
            SUM(impressions) AS impressions,
            SUM(clicks) AS clicks,
            SUM(spend) AS spend,
            SUM(conversions) AS conversions,
            SUM(conversion_value) AS conversion_value
        FROM campaign_metrics
        WHERE campaign_id IN (SELECT id FROM campaigns WHERE org_id = :org_id)
        AND timestamp >= :start_datetime
        AND timestamp <= :end_datetime
        AND granularity = 'raw'
        GROUP BY bucket
        ORDER BY bucket
    """)

    result = await db.execute(
        query,
        {
            "org_id": org_id,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
        },
    )

    points = []
    for row in result:
        points.append(TimeSeriesPoint(
            timestamp=row.bucket,
            impressions=row.impressions or 0,
            clicks=row.clicks or 0,
            spend=Decimal(str(row.spend or 0)),
            conversions=row.conversions or 0,
            conversion_value=Decimal(str(row.conversion_value or 0)),
        ))

    return points


async def get_today_metrics(
    db: AsyncSession,
    org_id: str,
) -> MetricsSummary:
    """
    Get metrics for today (real-time tracking).

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        Today's metrics summary
    """
    today = date.today()
    start_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.now(timezone.utc)

    # Get campaign IDs for this org
    campaign_query = select(Campaign.id).where(Campaign.org_id == org_id)
    campaign_result = await db.execute(campaign_query)
    campaign_ids = [str(c) for c in campaign_result.scalars().all()]

    if not campaign_ids:
        return MetricsSummary(
            impressions=0,
            clicks=0,
            ctr=0,
            spend=Decimal("0"),
            conversions=0,
            conversion_value=Decimal("0"),
            cpa=Decimal("0"),
            roas=0,
            avg_cpc=Decimal("0"),
            avg_cpm=Decimal("0"),
        )

    # Get today's metrics
    query = (
        select(CampaignMetrics)
        .where(
            CampaignMetrics.campaign_id.in_(campaign_ids),
            CampaignMetrics.timestamp >= start_datetime,
            CampaignMetrics.timestamp <= end_datetime,
            CampaignMetrics.granularity == "raw",
        )
    )

    result = await db.execute(query)
    rows = result.scalars().all()

    return calculate_summary_from_rows(rows)

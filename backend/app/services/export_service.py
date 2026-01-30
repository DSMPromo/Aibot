"""
Export Service

Provides functionality for exporting analytics data in various formats:
- CSV: Tabular data export
- PDF: Formatted reports with charts

Used for both on-demand exports and scheduled reports.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Any
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import (
    get_overview_metrics,
    get_campaign_metrics_summary,
    get_time_series_metrics,
    MetricsSummary,
    MetricsComparison,
    CampaignMetricsSummary,
    TimeSeriesPoint,
)

logger = structlog.get_logger()


@dataclass
class ExportResult:
    """Result of an export operation."""
    content: bytes
    filename: str
    content_type: str


# Default metrics to include in exports
DEFAULT_METRICS = [
    "impressions",
    "clicks",
    "ctr",
    "spend",
    "conversions",
    "conversion_value",
    "cpa",
    "roas",
]

METRIC_LABELS = {
    "impressions": "Impressions",
    "clicks": "Clicks",
    "ctr": "CTR (%)",
    "spend": "Spend ($)",
    "conversions": "Conversions",
    "conversion_value": "Conversion Value ($)",
    "cpa": "CPA ($)",
    "roas": "ROAS",
    "avg_cpc": "Avg CPC ($)",
    "avg_cpm": "Avg CPM ($)",
}


def format_metric_value(value: Any, metric: str) -> str:
    """Format a metric value for display."""
    if value is None:
        return ""

    if metric in ("spend", "conversion_value", "cpa", "avg_cpc", "avg_cpm"):
        if isinstance(value, Decimal):
            return f"${float(value):.2f}"
        return f"${value:.2f}"
    elif metric == "ctr":
        if isinstance(value, Decimal):
            return f"{float(value):.2f}%"
        return f"{value:.2f}%"
    elif metric == "roas":
        if isinstance(value, Decimal):
            return f"{float(value):.2f}x"
        return f"{value:.2f}x"
    elif metric in ("impressions", "clicks", "conversions"):
        return f"{int(value):,}"
    else:
        return str(value)


def format_metric_value_raw(value: Any, metric: str) -> str:
    """Format a metric value for CSV (raw numbers)."""
    if value is None:
        return ""

    if isinstance(value, Decimal):
        return str(float(value))
    return str(value)


async def export_overview_csv(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    metrics: Optional[list[str]] = None,
    include_comparison: bool = True,
) -> ExportResult:
    """
    Export overview metrics as CSV.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        metrics: List of metrics to include (defaults to all)
        include_comparison: Whether to include previous period comparison

    Returns:
        ExportResult with CSV content
    """
    metrics = metrics or DEFAULT_METRICS

    comparison = await get_overview_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        compare_previous=include_comparison,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    header = ["Metric", "Current Period"]
    if include_comparison and comparison.previous:
        header.extend(["Previous Period", "Change (%)"])
    writer.writerow(header)

    # Write metrics
    for metric in metrics:
        current_value = getattr(comparison.current, metric, None)
        row = [METRIC_LABELS.get(metric, metric), format_metric_value_raw(current_value, metric)]

        if include_comparison and comparison.previous:
            previous_value = getattr(comparison.previous, metric, None)
            change = comparison.change_percent.get(metric)
            row.append(format_metric_value_raw(previous_value, metric))
            row.append(f"{change:.2f}" if change is not None else "")

        writer.writerow(row)

    content = output.getvalue().encode("utf-8")
    filename = f"analytics_overview_{start_date.isoformat()}_{end_date.isoformat()}.csv"

    return ExportResult(
        content=content,
        filename=filename,
        content_type="text/csv",
    )


async def export_campaigns_csv(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    metrics: Optional[list[str]] = None,
) -> ExportResult:
    """
    Export campaign metrics as CSV.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        metrics: List of metrics to include (defaults to all)

    Returns:
        ExportResult with CSV content
    """
    metrics = metrics or DEFAULT_METRICS

    # Get all campaigns (paginate through if needed)
    all_campaigns = []
    page = 1
    page_size = 100

    while True:
        offset = (page - 1) * page_size
        summaries, total = await get_campaign_metrics_summary(
            db=db,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            limit=page_size,
            offset=offset,
        )
        all_campaigns.extend(summaries)

        if len(all_campaigns) >= total:
            break
        page += 1

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    header = ["Campaign ID", "Campaign Name", "Platform", "Status"]
    header.extend([METRIC_LABELS.get(m, m) for m in metrics])
    writer.writerow(header)

    # Write campaign data
    for campaign in all_campaigns:
        row = [
            campaign.campaign_id,
            campaign.campaign_name,
            campaign.platform,
            campaign.status,
        ]
        for metric in metrics:
            value = getattr(campaign.metrics, metric, None)
            row.append(format_metric_value_raw(value, metric))
        writer.writerow(row)

    content = output.getvalue().encode("utf-8")
    filename = f"campaigns_metrics_{start_date.isoformat()}_{end_date.isoformat()}.csv"

    return ExportResult(
        content=content,
        filename=filename,
        content_type="text/csv",
    )


async def export_timeseries_csv(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    granularity: str = "daily",
    campaign_id: Optional[str] = None,
) -> ExportResult:
    """
    Export time series metrics as CSV.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        granularity: Time granularity (hourly, daily, weekly)
        campaign_id: Optional campaign filter

    Returns:
        ExportResult with CSV content
    """
    points = await get_time_series_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        campaign_id=campaign_id,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Timestamp",
        "Impressions",
        "Clicks",
        "Spend",
        "Conversions",
        "Conversion Value",
    ])

    # Write data points
    for point in points:
        writer.writerow([
            point.timestamp.isoformat(),
            point.impressions,
            point.clicks,
            float(point.spend),
            point.conversions,
            float(point.conversion_value),
        ])

    content = output.getvalue().encode("utf-8")
    campaign_suffix = f"_{campaign_id}" if campaign_id else ""
    filename = f"timeseries_{granularity}{campaign_suffix}_{start_date.isoformat()}_{end_date.isoformat()}.csv"

    return ExportResult(
        content=content,
        filename=filename,
        content_type="text/csv",
    )


def generate_pdf_report(
    title: str,
    date_range: str,
    overview: MetricsComparison,
    campaigns: list[CampaignMetricsSummary],
    time_series: list[TimeSeriesPoint],
    metrics: Optional[list[str]] = None,
) -> bytes:
    """
    Generate a PDF report.

    This creates a simple text-based PDF. For production, you would want to use
    a library like reportlab or weasyprint for better formatting.

    Args:
        title: Report title
        date_range: Date range description
        overview: Overview metrics
        campaigns: Campaign metrics
        time_series: Time series data
        metrics: Metrics to include

    Returns:
        PDF content as bytes
    """
    metrics = metrics or DEFAULT_METRICS

    # Build simple PDF content
    # Note: This is a placeholder implementation
    # In production, use reportlab or weasyprint for proper PDF generation

    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"{title.center(60)}")
    lines.append(f"{'=' * 60}")
    lines.append(f"")
    lines.append(f"Date Range: {date_range}")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"")
    lines.append(f"{'-' * 60}")
    lines.append(f"OVERVIEW METRICS")
    lines.append(f"{'-' * 60}")
    lines.append(f"")

    for metric in metrics:
        current_value = getattr(overview.current, metric, None)
        formatted = format_metric_value(current_value, metric)
        label = METRIC_LABELS.get(metric, metric)

        if overview.previous:
            change = overview.change_percent.get(metric)
            change_str = f" ({change:+.1f}%)" if change is not None else ""
            lines.append(f"  {label}: {formatted}{change_str}")
        else:
            lines.append(f"  {label}: {formatted}")

    lines.append(f"")
    lines.append(f"{'-' * 60}")
    lines.append(f"CAMPAIGN BREAKDOWN (Top 10)")
    lines.append(f"{'-' * 60}")
    lines.append(f"")

    for campaign in campaigns[:10]:
        lines.append(f"  {campaign.campaign_name}")
        lines.append(f"    Platform: {campaign.platform} | Status: {campaign.status}")
        lines.append(f"    Spend: {format_metric_value(campaign.metrics.spend, 'spend')} | "
                    f"Conversions: {campaign.metrics.conversions} | "
                    f"ROAS: {format_metric_value(campaign.metrics.roas, 'roas')}")
        lines.append(f"")

    lines.append(f"{'-' * 60}")
    lines.append(f"TIME SERIES SUMMARY")
    lines.append(f"{'-' * 60}")
    lines.append(f"")
    lines.append(f"  Data points: {len(time_series)}")

    if time_series:
        total_spend = sum(float(p.spend) for p in time_series)
        total_conversions = sum(p.conversions for p in time_series)
        lines.append(f"  Total spend: ${total_spend:,.2f}")
        lines.append(f"  Total conversions: {total_conversions:,}")

    lines.append(f"")
    lines.append(f"{'=' * 60}")
    lines.append(f"End of Report")
    lines.append(f"{'=' * 60}")

    # Join lines and encode
    content = "\n".join(lines)

    # For a simple text-based "PDF", we'll use a basic PDF structure
    # In production, use reportlab for proper PDF generation
    pdf_content = create_simple_pdf(content)

    return pdf_content


def create_simple_pdf(text_content: str) -> bytes:
    """
    Create a simple PDF from text content.

    This is a minimal PDF implementation. For production use,
    consider using reportlab or weasyprint.
    """
    # Escape special PDF characters
    text = text_content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # Simple PDF structure
    pdf_parts = []

    # PDF header
    pdf_parts.append(b"%PDF-1.4\n")

    # Catalog
    pdf_parts.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Pages
    pdf_parts.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    # Page
    pdf_parts.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")

    # Font
    pdf_parts.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n")

    # Content stream - split text into lines and position them
    lines = text_content.split("\n")
    content_lines = ["BT", "/F1 10 Tf", "50 750 Td", "12 TL"]

    for line in lines:
        # Escape special characters
        escaped_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({escaped_line}) '")

    content_lines.append("ET")
    stream_content = "\n".join(content_lines)
    stream_bytes = stream_content.encode("latin-1", errors="replace")

    pdf_parts.append(f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode())
    pdf_parts.append(stream_bytes)
    pdf_parts.append(b"\nendstream\nendobj\n")

    # Cross-reference table
    xref_offset = sum(len(p) for p in pdf_parts)
    pdf_parts.append(b"xref\n0 6\n")
    pdf_parts.append(b"0000000000 65535 f \n")
    pdf_parts.append(b"0000000009 00000 n \n")
    pdf_parts.append(b"0000000058 00000 n \n")
    pdf_parts.append(b"0000000115 00000 n \n")
    pdf_parts.append(b"0000000270 00000 n \n")
    pdf_parts.append(b"0000000350 00000 n \n")

    # Trailer
    pdf_parts.append(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())

    return b"".join(pdf_parts)


async def export_full_report_pdf(
    db: AsyncSession,
    org_id: str,
    start_date: date,
    end_date: date,
    title: Optional[str] = None,
    metrics: Optional[list[str]] = None,
) -> ExportResult:
    """
    Export a full PDF report with overview, campaigns, and time series.

    Args:
        db: Database session
        org_id: Organization ID
        start_date: Start of date range
        end_date: End of date range
        title: Optional report title
        metrics: List of metrics to include

    Returns:
        ExportResult with PDF content
    """
    metrics = metrics or DEFAULT_METRICS
    title = title or "Analytics Report"

    # Fetch all data
    overview = await get_overview_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        compare_previous=True,
    )

    campaigns, _ = await get_campaign_metrics_summary(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        limit=50,
        offset=0,
    )

    time_series = await get_time_series_metrics(
        db=db,
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        granularity="daily",
    )

    date_range = f"{start_date.isoformat()} to {end_date.isoformat()}"

    pdf_content = generate_pdf_report(
        title=title,
        date_range=date_range,
        overview=overview,
        campaigns=campaigns,
        time_series=time_series,
        metrics=metrics,
    )

    filename = f"report_{start_date.isoformat()}_{end_date.isoformat()}.pdf"

    return ExportResult(
        content=pdf_content,
        filename=filename,
        content_type="application/pdf",
    )


# Date range helpers for scheduled reports
def get_date_range_for_preset(preset: str) -> tuple[date, date]:
    """
    Get date range for a preset value.

    Args:
        preset: Preset name (last_7_days, last_30_days, last_month, etc.)

    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()

    if preset == "last_7_days":
        return today - timedelta(days=7), today - timedelta(days=1)
    elif preset == "last_14_days":
        return today - timedelta(days=14), today - timedelta(days=1)
    elif preset == "last_30_days":
        return today - timedelta(days=30), today - timedelta(days=1)
    elif preset == "last_month":
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    elif preset == "this_month":
        first_of_month = today.replace(day=1)
        return first_of_month, today - timedelta(days=1)
    else:
        # Default to last 30 days
        return today - timedelta(days=30), today - timedelta(days=1)

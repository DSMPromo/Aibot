"""
Exports API endpoints.

Provides endpoints for exporting analytics data in various formats:
- CSV exports (overview, campaigns, time series)
- PDF reports (full analytics report)
- Scheduled reports management
"""

from datetime import date, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.metrics import ReportSchedule
from app.services.export_service import (
    export_overview_csv,
    export_campaigns_csv,
    export_timeseries_csv,
    export_full_report_pdf,
    get_date_range_for_preset,
    DEFAULT_METRICS,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ReportScheduleCreate(BaseModel):
    """Request to create a scheduled report."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    report_type: str = Field(..., pattern="^(performance_summary|campaign_breakdown|spend_analysis|custom)$")
    format: str = Field(default="pdf", pattern="^(pdf|csv)$")
    frequency: str = Field(..., pattern="^(daily|weekly|monthly)$")
    schedule_config: dict
    report_config: dict
    recipients: list[dict]


class ReportScheduleUpdate(BaseModel):
    """Request to update a scheduled report."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    format: Optional[str] = Field(None, pattern="^(pdf|csv)$")
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")
    schedule_config: Optional[dict] = None
    report_config: Optional[dict] = None
    recipients: Optional[list[dict]] = None
    is_enabled: Optional[bool] = None


class ReportScheduleResponse(BaseModel):
    """Response for a scheduled report."""
    id: str
    name: str
    description: Optional[str]
    report_type: str
    format: str
    frequency: str
    schedule_config: dict
    report_config: dict
    recipients: list
    is_enabled: bool
    last_run_at: Optional[str]
    last_run_status: Optional[str]
    next_run_at: Optional[str]
    created_at: str


class ReportScheduleListResponse(BaseModel):
    """Response for list of scheduled reports."""
    schedules: list[ReportScheduleResponse]
    total: int


# =============================================================================
# CSV Export Endpoints
# =============================================================================

@router.get("/csv/overview")
async def export_overview_metrics_csv(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    include_comparison: bool = Query(default=True),
    metrics: Optional[str] = Query(default=None, description="Comma-separated list of metrics"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export overview metrics as CSV.

    Returns a CSV file with aggregated metrics for the specified date range.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    # Parse metrics list
    metric_list = metrics.split(",") if metrics else None

    try:
        result = await export_overview_csv(
            db=db,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metric_list,
            include_comparison=include_comparison,
        )

        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
            },
        )
    except Exception as e:
        logger.error("Failed to export overview CSV", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate export",
        )


@router.get("/csv/campaigns")
async def export_campaign_metrics_csv(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    metrics: Optional[str] = Query(default=None, description="Comma-separated list of metrics"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export campaign metrics as CSV.

    Returns a CSV file with per-campaign metrics for the specified date range.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    # Parse metrics list
    metric_list = metrics.split(",") if metrics else None

    try:
        result = await export_campaigns_csv(
            db=db,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metric_list,
        )

        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
            },
        )
    except Exception as e:
        logger.error("Failed to export campaigns CSV", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate export",
        )


@router.get("/csv/timeseries")
async def export_time_series_csv(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    granularity: str = Query(default="daily", pattern="^(hourly|daily|weekly)$"),
    campaign_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export time series metrics as CSV.

    Returns a CSV file with time series data for the specified date range and granularity.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    try:
        result = await export_timeseries_csv(
            db=db,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            campaign_id=campaign_id,
        )

        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
            },
        )
    except Exception as e:
        logger.error("Failed to export time series CSV", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate export",
        )


# =============================================================================
# PDF Export Endpoints
# =============================================================================

@router.get("/pdf/report")
async def export_full_pdf_report(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    title: Optional[str] = Query(default=None),
    metrics: Optional[str] = Query(default=None, description="Comma-separated list of metrics"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a full PDF report.

    Returns a PDF file with overview metrics, campaign breakdown, and time series summary.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    # Parse metrics list
    metric_list = metrics.split(",") if metrics else None

    try:
        result = await export_full_report_pdf(
            db=db,
            org_id=org_id,
            start_date=start_date,
            end_date=end_date,
            title=title,
            metrics=metric_list,
        )

        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
            },
        )
    except Exception as e:
        logger.error("Failed to export PDF report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate export",
        )


# =============================================================================
# Scheduled Reports Endpoints
# =============================================================================

@router.get("/schedules", response_model=ReportScheduleListResponse)
async def list_report_schedules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List all scheduled reports for the organization.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    # Count total
    count_query = select(func.count(ReportSchedule.id)).where(
        ReportSchedule.org_id == org_id
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get schedules
    offset = (page - 1) * page_size
    query = (
        select(ReportSchedule)
        .where(ReportSchedule.org_id == org_id)
        .order_by(ReportSchedule.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )

    result = await db.execute(query)
    schedules = result.scalars().all()

    return ReportScheduleListResponse(
        schedules=[
            ReportScheduleResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                report_type=s.report_type,
                format=s.format,
                frequency=s.frequency,
                schedule_config=s.schedule_config,
                report_config=s.report_config,
                recipients=s.recipients,
                is_enabled=s.is_enabled,
                last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
                last_run_status=s.last_run_status,
                next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
                created_at=s.created_at.isoformat(),
            )
            for s in schedules
        ],
        total=total,
    )


@router.post("/schedules", response_model=ReportScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_report_schedule(
    request: ReportScheduleCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new scheduled report.
    """
    # TODO: Get current user's org_id and user_id from auth
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    # Create the schedule
    schedule = ReportSchedule(
        org_id=org_id,
        name=request.name,
        description=request.description,
        report_type=request.report_type,
        format=request.format,
        frequency=request.frequency,
        schedule_config=request.schedule_config,
        report_config=request.report_config,
        recipients=request.recipients,
        created_by_id=user_id,
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    return ReportScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        report_type=schedule.report_type,
        format=schedule.format,
        frequency=schedule.frequency,
        schedule_config=schedule.schedule_config,
        report_config=schedule.report_config,
        recipients=schedule.recipients,
        is_enabled=schedule.is_enabled,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        last_run_status=schedule.last_run_status,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        created_at=schedule.created_at.isoformat(),
    )


@router.get("/schedules/{schedule_id}", response_model=ReportScheduleResponse)
async def get_report_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific scheduled report.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    query = select(ReportSchedule).where(
        ReportSchedule.id == schedule_id,
        ReportSchedule.org_id == org_id,
    )
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report schedule not found",
        )

    return ReportScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        report_type=schedule.report_type,
        format=schedule.format,
        frequency=schedule.frequency,
        schedule_config=schedule.schedule_config,
        report_config=schedule.report_config,
        recipients=schedule.recipients,
        is_enabled=schedule.is_enabled,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        last_run_status=schedule.last_run_status,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        created_at=schedule.created_at.isoformat(),
    )


@router.patch("/schedules/{schedule_id}", response_model=ReportScheduleResponse)
async def update_report_schedule(
    schedule_id: str,
    request: ReportScheduleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a scheduled report.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    query = select(ReportSchedule).where(
        ReportSchedule.id == schedule_id,
        ReportSchedule.org_id == org_id,
    )
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report schedule not found",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)

    return ReportScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        report_type=schedule.report_type,
        format=schedule.format,
        frequency=schedule.frequency,
        schedule_config=schedule.schedule_config,
        report_config=schedule.report_config,
        recipients=schedule.recipients,
        is_enabled=schedule.is_enabled,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        last_run_status=schedule.last_run_status,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        created_at=schedule.created_at.isoformat(),
    )


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a scheduled report.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    query = select(ReportSchedule).where(
        ReportSchedule.id == schedule_id,
        ReportSchedule.org_id == org_id,
    )
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report schedule not found",
        )

    await db.delete(schedule)
    await db.commit()


@router.post("/schedules/{schedule_id}/run")
async def run_report_now(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a scheduled report immediately.

    This generates and returns the report without waiting for the scheduled time.
    """
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    query = select(ReportSchedule).where(
        ReportSchedule.id == schedule_id,
        ReportSchedule.org_id == org_id,
    )
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report schedule not found",
        )

    # Get date range from config
    date_range_preset = schedule.report_config.get("date_range", "last_30_days")
    start_date, end_date = get_date_range_for_preset(date_range_preset)
    metrics = schedule.report_config.get("metrics")

    try:
        if schedule.format == "csv":
            result = await export_campaigns_csv(
                db=db,
                org_id=org_id,
                start_date=start_date,
                end_date=end_date,
                metrics=metrics,
            )
        else:
            result = await export_full_report_pdf(
                db=db,
                org_id=org_id,
                start_date=start_date,
                end_date=end_date,
                title=schedule.name,
                metrics=metrics,
            )

        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
            },
        )
    except Exception as e:
        logger.error("Failed to run report", schedule_id=schedule_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )

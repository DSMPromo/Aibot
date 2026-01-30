"""
Alerts API endpoints.

Provides endpoints for managing budget and performance alerts:
- CRUD operations for alerts
- Alert history
- Notifications management
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.metrics import Alert, AlertHistory, Notification
from app.services.alerts_service import (
    get_alerts,
    create_alert,
    update_alert,
    delete_alert,
    evaluate_alert,
    check_and_trigger_alerts,
    get_alert_history,
    acknowledge_alert,
    get_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class AlertConfigBudget(BaseModel):
    """Budget alert configuration."""
    threshold_percent: float = Field(..., ge=0, le=100, description="Trigger at this % of budget")
    budget_type: str = Field(..., pattern="^(daily|weekly|monthly)$")
    budget_amount: float = Field(..., gt=0, description="Budget amount")


class AlertConfigMetric(BaseModel):
    """Metric alert configuration."""
    metric: str = Field(..., pattern="^(cpa|roas|ctr|cpc)$")
    operator: str = Field(..., pattern="^(gt|lt|gte|lte)$")
    threshold: float = Field(..., description="Threshold value")
    lookback_days: int = Field(default=7, ge=1, le=90)


class AlertCreate(BaseModel):
    """Request to create an alert."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    alert_type: str = Field(..., pattern="^(budget_threshold|cpa_threshold|roas_threshold|ctr_threshold)$")
    config: dict
    scope_type: str = Field(default="org", pattern="^(org|campaign)$")
    campaign_id: Optional[str] = None
    notification_channels: Optional[dict] = None
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)


class AlertUpdate(BaseModel):
    """Request to update an alert."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    config: Optional[dict] = None
    notification_channels: Optional[dict] = None
    cooldown_minutes: Optional[int] = Field(None, ge=5, le=1440)
    is_enabled: Optional[bool] = None


class AlertResponse(BaseModel):
    """Response for an alert."""
    id: str
    name: str
    description: Optional[str]
    alert_type: str
    config: dict
    scope_type: str
    campaign_id: Optional[str]
    notification_channels: dict
    is_enabled: bool
    is_triggered: bool
    last_triggered_at: Optional[str]
    cooldown_minutes: int
    created_at: str


class AlertListResponse(BaseModel):
    """Response for list of alerts."""
    alerts: list[AlertResponse]
    total: int


class AlertHistoryResponse(BaseModel):
    """Response for alert history entry."""
    id: str
    alert_id: str
    campaign_id: Optional[str]
    alert_type: str
    message: str
    metric_value: Optional[float]
    threshold_value: Optional[float]
    status: str
    triggered_at: str
    acknowledged_by_id: Optional[str]
    acknowledged_at: Optional[str]
    resolution_note: Optional[str]


class AlertHistoryListResponse(BaseModel):
    """Response for alert history list."""
    history: list[AlertHistoryResponse]
    total: int


class NotificationResponse(BaseModel):
    """Response for a notification."""
    id: str
    title: str
    message: str
    notification_type: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    data: Optional[dict]
    is_read: bool
    read_at: Optional[str]
    created_at: str


class NotificationListResponse(BaseModel):
    """Response for notification list."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class AcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""
    resolution_note: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Response for alert evaluation."""
    alert_id: str
    is_triggered: bool
    current_value: float
    threshold_value: float
    message: str


# =============================================================================
# Alert Endpoints
# =============================================================================

@router.get("", response_model=AlertListResponse)
async def list_alerts(
    is_enabled: Optional[bool] = Query(default=None),
    alert_type: Optional[str] = Query(default=None),
    campaign_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List all alerts for the organization.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    offset = (page - 1) * page_size
    alerts, total = await get_alerts(
        db=db,
        org_id=org_id,
        is_enabled=is_enabled,
        alert_type=alert_type,
        campaign_id=campaign_id,
        limit=page_size,
        offset=offset,
    )

    return AlertListResponse(
        alerts=[
            AlertResponse(
                id=a.id,
                name=a.name,
                description=a.description,
                alert_type=a.alert_type,
                config=a.config,
                scope_type=a.scope_type,
                campaign_id=a.campaign_id,
                notification_channels=a.notification_channels,
                is_enabled=a.is_enabled,
                is_triggered=a.is_triggered,
                last_triggered_at=a.last_triggered_at.isoformat() if a.last_triggered_at else None,
                cooldown_minutes=a.cooldown_minutes,
                created_at=a.created_at.isoformat(),
            )
            for a in alerts
        ],
        total=total,
    )


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_new_alert(
    request: AlertCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new alert.
    """
    # TODO: Get current user's org_id and user_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    # Validate scope
    if request.scope_type == "campaign" and not request.campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campaign_id is required when scope_type is 'campaign'",
        )

    alert = await create_alert(
        db=db,
        org_id=org_id,
        name=request.name,
        description=request.description,
        alert_type=request.alert_type,
        config=request.config,
        scope_type=request.scope_type,
        campaign_id=request.campaign_id,
        notification_channels=request.notification_channels,
        cooldown_minutes=request.cooldown_minutes,
        created_by_id=user_id,
    )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        description=alert.description,
        alert_type=alert.alert_type,
        config=alert.config,
        scope_type=alert.scope_type,
        campaign_id=alert.campaign_id,
        notification_channels=alert.notification_channels,
        is_enabled=alert.is_enabled,
        is_triggered=alert.is_triggered,
        last_triggered_at=alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        cooldown_minutes=alert.cooldown_minutes,
        created_at=alert.created_at.isoformat(),
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific alert.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    query = select(Alert).where(Alert.id == alert_id, Alert.org_id == org_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        description=alert.description,
        alert_type=alert.alert_type,
        config=alert.config,
        scope_type=alert.scope_type,
        campaign_id=alert.campaign_id,
        notification_channels=alert.notification_channels,
        is_enabled=alert.is_enabled,
        is_triggered=alert.is_triggered,
        last_triggered_at=alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        cooldown_minutes=alert.cooldown_minutes,
        created_at=alert.created_at.isoformat(),
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_existing_alert(
    alert_id: str,
    request: AlertUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an alert.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    query = select(Alert).where(Alert.id == alert_id, Alert.org_id == org_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    update_data = request.model_dump(exclude_unset=True)
    alert = await update_alert(db, alert, **update_data)

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        description=alert.description,
        alert_type=alert.alert_type,
        config=alert.config,
        scope_type=alert.scope_type,
        campaign_id=alert.campaign_id,
        notification_channels=alert.notification_channels,
        is_enabled=alert.is_enabled,
        is_triggered=alert.is_triggered,
        last_triggered_at=alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        cooldown_minutes=alert.cooldown_minutes,
        created_at=alert.created_at.isoformat(),
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an alert.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    query = select(Alert).where(Alert.id == alert_id, Alert.org_id == org_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await delete_alert(db, alert)


@router.post("/{alert_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_single_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate an alert and return the result (without triggering notifications).
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    query = select(Alert).where(Alert.id == alert_id, Alert.org_id == org_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    evaluation = await evaluate_alert(db, alert)

    return EvaluationResponse(
        alert_id=evaluation.alert_id,
        is_triggered=evaluation.is_triggered,
        current_value=evaluation.current_value,
        threshold_value=evaluation.threshold_value,
        message=evaluation.message,
    )


@router.post("/check-all", response_model=list[EvaluationResponse])
async def check_all_alerts(
    db: AsyncSession = Depends(get_db),
):
    """
    Check all enabled alerts and trigger notifications where needed.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    evaluations = await check_and_trigger_alerts(db, org_id)

    return [
        EvaluationResponse(
            alert_id=e.alert_id,
            is_triggered=e.is_triggered,
            current_value=e.current_value,
            threshold_value=e.threshold_value,
            message=e.message,
        )
        for e in evaluations
    ]


# =============================================================================
# Alert History Endpoints
# =============================================================================

@router.get("/history", response_model=AlertHistoryListResponse)
async def list_alert_history(
    alert_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, pattern="^(triggered|acknowledged|resolved)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get alert history.
    """
    # TODO: Get current user's org_id from auth
    org_id = "00000000-0000-0000-0000-000000000001"

    offset = (page - 1) * page_size
    history, total = await get_alert_history(
        db=db,
        org_id=org_id,
        alert_id=alert_id,
        status=status,
        limit=page_size,
        offset=offset,
    )

    return AlertHistoryListResponse(
        history=[
            AlertHistoryResponse(
                id=h.id,
                alert_id=h.alert_id,
                campaign_id=h.campaign_id,
                alert_type=h.alert_type,
                message=h.message,
                metric_value=float(h.metric_value) if h.metric_value else None,
                threshold_value=float(h.threshold_value) if h.threshold_value else None,
                status=h.status,
                triggered_at=h.triggered_at.isoformat(),
                acknowledged_by_id=h.acknowledged_by_id,
                acknowledged_at=h.acknowledged_at.isoformat() if h.acknowledged_at else None,
                resolution_note=h.resolution_note,
            )
            for h in history
        ],
        total=total,
    )


@router.post("/history/{history_id}/acknowledge", response_model=AlertHistoryResponse)
async def acknowledge_alert_history(
    history_id: str,
    request: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Acknowledge an alert from history.
    """
    # TODO: Get current user_id from auth
    user_id = "00000000-0000-0000-0000-000000000002"

    history = await acknowledge_alert(
        db=db,
        history_id=history_id,
        user_id=user_id,
        resolution_note=request.resolution_note,
    )

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert history entry not found",
        )

    return AlertHistoryResponse(
        id=history.id,
        alert_id=history.alert_id,
        campaign_id=history.campaign_id,
        alert_type=history.alert_type,
        message=history.message,
        metric_value=float(history.metric_value) if history.metric_value else None,
        threshold_value=float(history.threshold_value) if history.threshold_value else None,
        status=history.status,
        triggered_at=history.triggered_at.isoformat(),
        acknowledged_by_id=history.acknowledged_by_id,
        acknowledged_at=history.acknowledged_at.isoformat() if history.acknowledged_at else None,
        resolution_note=history.resolution_note,
    )


# =============================================================================
# Notifications Endpoints
# =============================================================================

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notifications for the current user.
    """
    # TODO: Get current user_id from auth
    user_id = "00000000-0000-0000-0000-000000000002"

    offset = (page - 1) * page_size
    notifications, total = await get_notifications(
        db=db,
        user_id=user_id,
        is_read=is_read,
        limit=page_size,
        offset=offset,
    )

    # Get unread count
    _, unread_count = await get_notifications(db=db, user_id=user_id, is_read=False, limit=1)

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                notification_type=n.notification_type,
                related_entity_type=n.related_entity_type,
                related_entity_id=n.related_entity_id,
                data=n.data,
                is_read=n.is_read,
                read_at=n.read_at.isoformat() if n.read_at else None,
                created_at=n.created_at.isoformat(),
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread_count,
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a notification as read.
    """
    # TODO: Get current user_id from auth
    user_id = "00000000-0000-0000-0000-000000000002"

    notification = await mark_notification_read(db, notification_id, user_id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
        data=notification.data,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        created_at=notification.created_at.isoformat(),
    )


@router.post("/notifications/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all notifications as read.
    """
    # TODO: Get current user_id from auth
    user_id = "00000000-0000-0000-0000-000000000002"

    count = await mark_all_notifications_read(db, user_id)

    return {"marked_read": count}

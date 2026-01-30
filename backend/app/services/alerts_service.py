"""
Alerts Service

Provides functionality for managing and evaluating budget and performance alerts:
- Creating and managing alert configurations
- Evaluating alert conditions
- Triggering notifications when thresholds are exceeded
"""

from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

import structlog
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import Alert, AlertHistory, Notification, CampaignMetrics
from app.models.campaign import Campaign

logger = structlog.get_logger()


@dataclass
class AlertEvaluation:
    """Result of evaluating an alert condition."""
    alert_id: str
    is_triggered: bool
    current_value: float
    threshold_value: float
    message: str
    campaign_id: Optional[str] = None


async def get_alerts(
    db: AsyncSession,
    org_id: str,
    is_enabled: Optional[bool] = None,
    alert_type: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Alert], int]:
    """
    Get alerts for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        is_enabled: Filter by enabled status
        alert_type: Filter by alert type
        campaign_id: Filter by campaign
        limit: Max number of results
        offset: Result offset

    Returns:
        Tuple of (alerts list, total count)
    """
    # Build base query
    conditions = [Alert.org_id == org_id]

    if is_enabled is not None:
        conditions.append(Alert.is_enabled == is_enabled)
    if alert_type:
        conditions.append(Alert.alert_type == alert_type)
    if campaign_id:
        conditions.append(Alert.campaign_id == campaign_id)

    # Count total
    count_query = select(func.count(Alert.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get alerts
    query = (
        select(Alert)
        .where(and_(*conditions))
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    alerts = list(result.scalars().all())

    return alerts, total


async def create_alert(
    db: AsyncSession,
    org_id: str,
    name: str,
    alert_type: str,
    config: dict,
    description: Optional[str] = None,
    scope_type: str = "org",
    campaign_id: Optional[str] = None,
    notification_channels: Optional[dict] = None,
    cooldown_minutes: int = 60,
    created_by_id: Optional[str] = None,
) -> Alert:
    """
    Create a new alert.

    Args:
        db: Database session
        org_id: Organization ID
        name: Alert name
        alert_type: Type of alert (budget_threshold, cpa_threshold, etc.)
        config: Alert configuration
        description: Optional description
        scope_type: Scope type (org, campaign)
        campaign_id: Campaign ID if scope is campaign
        notification_channels: Notification channel settings
        cooldown_minutes: Cooldown between alerts
        created_by_id: User ID who created the alert

    Returns:
        Created alert
    """
    alert = Alert(
        org_id=org_id,
        name=name,
        description=description,
        alert_type=alert_type,
        config=config,
        scope_type=scope_type,
        campaign_id=campaign_id,
        notification_channels=notification_channels or {"email": True, "in_app": True},
        cooldown_minutes=cooldown_minutes,
        created_by_id=created_by_id,
    )

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return alert


async def update_alert(
    db: AsyncSession,
    alert: Alert,
    **kwargs,
) -> Alert:
    """
    Update an alert.

    Args:
        db: Database session
        alert: Alert to update
        **kwargs: Fields to update

    Returns:
        Updated alert
    """
    for field, value in kwargs.items():
        if hasattr(alert, field):
            setattr(alert, field, value)

    await db.commit()
    await db.refresh(alert)

    return alert


async def delete_alert(
    db: AsyncSession,
    alert: Alert,
) -> None:
    """
    Delete an alert.

    Args:
        db: Database session
        alert: Alert to delete
    """
    await db.delete(alert)
    await db.commit()


async def evaluate_budget_alert(
    db: AsyncSession,
    alert: Alert,
) -> AlertEvaluation:
    """
    Evaluate a budget threshold alert.

    Args:
        db: Database session
        alert: Alert to evaluate

    Returns:
        AlertEvaluation with results
    """
    config = alert.config
    threshold_percent = config.get("threshold_percent", 80)
    budget_type = config.get("budget_type", "daily")  # daily, weekly, monthly
    budget_amount = Decimal(str(config.get("budget_amount", 0)))

    if budget_amount <= 0:
        return AlertEvaluation(
            alert_id=alert.id,
            is_triggered=False,
            current_value=0,
            threshold_value=float(budget_amount),
            message="No budget configured",
        )

    # Determine date range based on budget type
    today = date.today()
    if budget_type == "daily":
        start_date = today
        end_date = today
    elif budget_type == "weekly":
        # Start of current week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    else:  # monthly
        start_date = today.replace(day=1)
        end_date = today

    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Get campaign IDs to check
    if alert.campaign_id:
        campaign_ids = [alert.campaign_id]
    else:
        # Get all campaigns for this org
        campaign_query = select(Campaign.id).where(Campaign.org_id == alert.org_id)
        campaign_result = await db.execute(campaign_query)
        campaign_ids = [str(c) for c in campaign_result.scalars().all()]

    if not campaign_ids:
        return AlertEvaluation(
            alert_id=alert.id,
            is_triggered=False,
            current_value=0,
            threshold_value=float(budget_amount),
            message="No campaigns found",
        )

    # Get current spend
    spend_query = (
        select(func.sum(CampaignMetrics.spend))
        .where(
            CampaignMetrics.campaign_id.in_(campaign_ids),
            CampaignMetrics.timestamp >= start_datetime,
            CampaignMetrics.timestamp <= end_datetime,
            CampaignMetrics.granularity == "raw",
        )
    )

    spend_result = await db.execute(spend_query)
    current_spend = spend_result.scalar() or Decimal("0")

    # Calculate threshold
    threshold_amount = budget_amount * Decimal(str(threshold_percent)) / 100
    is_triggered = current_spend >= threshold_amount

    spend_percent = (current_spend / budget_amount * 100) if budget_amount > 0 else Decimal("0")

    message = (
        f"Budget {budget_type} spend is at {float(spend_percent):.1f}% "
        f"(${float(current_spend):,.2f} of ${float(budget_amount):,.2f})"
    )

    return AlertEvaluation(
        alert_id=alert.id,
        is_triggered=is_triggered,
        current_value=float(current_spend),
        threshold_value=float(threshold_amount),
        message=message,
        campaign_id=alert.campaign_id,
    )


async def evaluate_metric_alert(
    db: AsyncSession,
    alert: Alert,
) -> AlertEvaluation:
    """
    Evaluate a metric threshold alert (CPA, ROAS, CTR, etc.).

    Args:
        db: Database session
        alert: Alert to evaluate

    Returns:
        AlertEvaluation with results
    """
    config = alert.config
    metric = config.get("metric", "cpa")
    operator = config.get("operator", "gt")  # gt, lt, gte, lte
    threshold = Decimal(str(config.get("threshold", 0)))
    lookback_days = config.get("lookback_days", 7)

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Get campaign IDs to check
    if alert.campaign_id:
        campaign_ids = [alert.campaign_id]
    else:
        campaign_query = select(Campaign.id).where(Campaign.org_id == alert.org_id)
        campaign_result = await db.execute(campaign_query)
        campaign_ids = [str(c) for c in campaign_result.scalars().all()]

    if not campaign_ids:
        return AlertEvaluation(
            alert_id=alert.id,
            is_triggered=False,
            current_value=0,
            threshold_value=float(threshold),
            message="No campaigns found",
        )

    # Get aggregated metrics
    metrics_query = select(CampaignMetrics).where(
        CampaignMetrics.campaign_id.in_(campaign_ids),
        CampaignMetrics.timestamp >= start_datetime,
        CampaignMetrics.timestamp <= end_datetime,
        CampaignMetrics.granularity == "raw",
    )

    metrics_result = await db.execute(metrics_query)
    metrics_rows = metrics_result.scalars().all()

    if not metrics_rows:
        return AlertEvaluation(
            alert_id=alert.id,
            is_triggered=False,
            current_value=0,
            threshold_value=float(threshold),
            message="No metrics data available",
        )

    # Calculate the metric
    total_impressions = sum(r.impressions or 0 for r in metrics_rows)
    total_clicks = sum(r.clicks or 0 for r in metrics_rows)
    total_spend = sum(Decimal(str(r.spend or 0)) for r in metrics_rows)
    total_conversions = sum(r.conversions or 0 for r in metrics_rows)
    total_conversion_value = sum(Decimal(str(r.conversion_value or 0)) for r in metrics_rows)

    if metric == "cpa":
        current_value = float(total_spend / total_conversions) if total_conversions > 0 else 0
    elif metric == "roas":
        current_value = float(total_conversion_value / total_spend) if total_spend > 0 else 0
    elif metric == "ctr":
        current_value = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    elif metric == "cpc":
        current_value = float(total_spend / total_clicks) if total_clicks > 0 else 0
    else:
        current_value = 0

    # Evaluate the condition
    threshold_float = float(threshold)
    if operator == "gt":
        is_triggered = current_value > threshold_float
        op_str = "above"
    elif operator == "lt":
        is_triggered = current_value < threshold_float
        op_str = "below"
    elif operator == "gte":
        is_triggered = current_value >= threshold_float
        op_str = "at or above"
    else:  # lte
        is_triggered = current_value <= threshold_float
        op_str = "at or below"

    metric_labels = {
        "cpa": "CPA",
        "roas": "ROAS",
        "ctr": "CTR",
        "cpc": "CPC",
    }

    message = (
        f"{metric_labels.get(metric, metric.upper())} is {op_str} threshold: "
        f"{current_value:.2f} vs {threshold_float:.2f}"
    )

    return AlertEvaluation(
        alert_id=alert.id,
        is_triggered=is_triggered,
        current_value=current_value,
        threshold_value=threshold_float,
        message=message,
        campaign_id=alert.campaign_id,
    )


async def evaluate_alert(
    db: AsyncSession,
    alert: Alert,
) -> AlertEvaluation:
    """
    Evaluate an alert based on its type.

    Args:
        db: Database session
        alert: Alert to evaluate

    Returns:
        AlertEvaluation with results
    """
    if alert.alert_type == "budget_threshold":
        return await evaluate_budget_alert(db, alert)
    elif alert.alert_type in ("cpa_threshold", "roas_threshold", "ctr_threshold"):
        return await evaluate_metric_alert(db, alert)
    else:
        return AlertEvaluation(
            alert_id=alert.id,
            is_triggered=False,
            current_value=0,
            threshold_value=0,
            message=f"Unknown alert type: {alert.alert_type}",
        )


async def check_and_trigger_alerts(
    db: AsyncSession,
    org_id: str,
) -> list[AlertEvaluation]:
    """
    Check all enabled alerts for an organization and trigger notifications.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        List of triggered AlertEvaluations
    """
    # Get all enabled alerts
    alerts, _ = await get_alerts(db, org_id, is_enabled=True)

    triggered = []

    for alert in alerts:
        # Check cooldown
        if alert.last_triggered_at:
            cooldown_end = alert.last_triggered_at + timedelta(minutes=alert.cooldown_minutes)
            if datetime.now(timezone.utc) < cooldown_end:
                continue

        # Evaluate the alert
        evaluation = await evaluate_alert(db, alert)

        if evaluation.is_triggered:
            # Create alert history entry
            history = AlertHistory(
                alert_id=alert.id,
                org_id=org_id,
                campaign_id=alert.campaign_id,
                alert_type=alert.alert_type,
                message=evaluation.message,
                metric_value=Decimal(str(evaluation.current_value)),
                threshold_value=Decimal(str(evaluation.threshold_value)),
            )
            db.add(history)

            # Update alert's last triggered time
            alert.is_triggered = True
            alert.last_triggered_at = datetime.now(timezone.utc)

            # Create notifications for in-app
            if alert.notification_channels.get("in_app"):
                # Get org members to notify
                # For now, create a single notification (in production, query org members)
                notification = Notification(
                    user_id=alert.created_by_id or "00000000-0000-0000-0000-000000000002",
                    org_id=org_id,
                    title=f"Alert: {alert.name}",
                    message=evaluation.message,
                    notification_type="alert",
                    related_entity_type="alert",
                    related_entity_id=alert.id,
                    data={
                        "alert_type": alert.alert_type,
                        "current_value": evaluation.current_value,
                        "threshold_value": evaluation.threshold_value,
                    },
                )
                db.add(notification)

            triggered.append(evaluation)

    await db.commit()

    return triggered


async def get_alert_history(
    db: AsyncSession,
    org_id: str,
    alert_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AlertHistory], int]:
    """
    Get alert history for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        alert_id: Filter by specific alert
        status: Filter by status
        limit: Max results
        offset: Result offset

    Returns:
        Tuple of (history list, total count)
    """
    conditions = [AlertHistory.org_id == org_id]

    if alert_id:
        conditions.append(AlertHistory.alert_id == alert_id)
    if status:
        conditions.append(AlertHistory.status == status)

    count_query = select(func.count(AlertHistory.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = (
        select(AlertHistory)
        .where(and_(*conditions))
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    history = list(result.scalars().all())

    return history, total


async def acknowledge_alert(
    db: AsyncSession,
    history_id: str,
    user_id: str,
    resolution_note: Optional[str] = None,
) -> Optional[AlertHistory]:
    """
    Acknowledge an alert in history.

    Args:
        db: Database session
        history_id: Alert history entry ID
        user_id: User ID acknowledging
        resolution_note: Optional resolution note

    Returns:
        Updated AlertHistory or None if not found
    """
    query = select(AlertHistory).where(AlertHistory.id == history_id)
    result = await db.execute(query)
    history = result.scalar_one_or_none()

    if not history:
        return None

    history.status = "acknowledged"
    history.acknowledged_by_id = user_id
    history.acknowledged_at = datetime.now(timezone.utc)
    if resolution_note:
        history.resolution_note = resolution_note

    await db.commit()
    await db.refresh(history)

    return history


async def get_notifications(
    db: AsyncSession,
    user_id: str,
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    """
    Get notifications for a user.

    Args:
        db: Database session
        user_id: User ID
        is_read: Filter by read status
        limit: Max results
        offset: Result offset

    Returns:
        Tuple of (notifications list, total count)
    """
    conditions = [Notification.user_id == user_id]

    if is_read is not None:
        conditions.append(Notification.is_read == is_read)

    count_query = select(func.count(Notification.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = (
        select(Notification)
        .where(and_(*conditions))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    notifications = list(result.scalars().all())

    return notifications, total


async def mark_notification_read(
    db: AsyncSession,
    notification_id: str,
    user_id: str,
) -> Optional[Notification]:
    """
    Mark a notification as read.

    Args:
        db: Database session
        notification_id: Notification ID
        user_id: User ID (for verification)

    Returns:
        Updated notification or None if not found
    """
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        return None

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(notification)

    return notification


async def mark_all_notifications_read(
    db: AsyncSession,
    user_id: str,
) -> int:
    """
    Mark all notifications as read for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of notifications marked as read
    """
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        .values(
            is_read=True,
            read_at=datetime.now(timezone.utc),
        )
    )

    result = await db.execute(stmt)
    await db.commit()

    return result.rowcount

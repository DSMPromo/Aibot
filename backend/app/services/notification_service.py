"""
Notification service for multi-channel notifications.

Provides functions for:
- Creating in-app notifications
- Sending Slack notifications
- Sending email notifications
- Managing notification preferences
- Broadcasting to multiple channels
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.metrics import Notification
from app.models.user import User, Organization

logger = structlog.get_logger()


# =============================================================================
# Notification Types
# =============================================================================

NOTIFICATION_TYPES = {
    "alert": {
        "title_template": "Alert: {name}",
        "default_channels": ["in_app", "email"],
    },
    "campaign_status": {
        "title_template": "Campaign Update: {name}",
        "default_channels": ["in_app"],
    },
    "approval_request": {
        "title_template": "Approval Required: {name}",
        "default_channels": ["in_app", "email"],
    },
    "approval_result": {
        "title_template": "Approval {result}: {name}",
        "default_channels": ["in_app"],
    },
    "automation_triggered": {
        "title_template": "Automation Triggered: {name}",
        "default_channels": ["in_app", "slack"],
    },
    "automation_pending": {
        "title_template": "Action Requires Approval: {name}",
        "default_channels": ["in_app", "email", "slack"],
    },
    "billing": {
        "title_template": "Billing Update",
        "default_channels": ["in_app", "email"],
    },
    "system": {
        "title_template": "System Notification",
        "default_channels": ["in_app"],
    },
}


# =============================================================================
# In-App Notifications
# =============================================================================


async def create_notification(
    db: AsyncSession,
    user_id: str,
    org_id: str,
    title: str,
    message: str,
    notification_type: str,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    data: Optional[dict] = None,
) -> Notification:
    """
    Create an in-app notification.

    Args:
        db: Database session
        user_id: User to notify
        org_id: Organization ID
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        related_entity_type: Type of related entity (campaign, alert, etc.)
        related_entity_id: ID of related entity
        data: Additional data

    Returns:
        Created notification
    """
    notification = Notification(
        user_id=user_id,
        org_id=org_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        data=data or {},
    )
    db.add(notification)

    logger.info(
        "notification_created",
        user_id=user_id,
        notification_type=notification_type,
        title=title,
    )

    return notification


async def create_notification_for_org(
    db: AsyncSession,
    org_id: str,
    title: str,
    message: str,
    notification_type: str,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    data: Optional[dict] = None,
    roles: Optional[list[str]] = None,
) -> list[Notification]:
    """
    Create notifications for all users in an organization.

    Args:
        db: Database session
        org_id: Organization ID
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        related_entity_type: Type of related entity
        related_entity_id: ID of related entity
        data: Additional data
        roles: Filter to specific roles (admin, manager, user)

    Returns:
        List of created notifications
    """
    query = select(User.id).where(
        User.org_id == org_id,
        User.is_active == True,
        User.deleted_at == None,
    )

    if roles:
        query = query.where(User.role.in_(roles))

    result = await db.execute(query)
    user_ids = [row[0] for row in result.all()]

    notifications = []
    for user_id in user_ids:
        notification = await create_notification(
            db=db,
            user_id=user_id,
            org_id=org_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            data=data,
        )
        notifications.append(notification)

    return notifications


async def get_notifications(
    db: AsyncSession,
    user_id: str,
    is_read: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Notification], int, int]:
    """
    Get notifications for a user.

    Returns:
        Tuple of (notifications, total_count, unread_count)
    """
    # Base query
    base_query = select(Notification).where(Notification.user_id == user_id)

    if is_read is not None:
        base_query = base_query.where(Notification.is_read == is_read)

    # Get total count
    count_result = await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user_id)
    )
    total = count_result.scalar() or 0

    # Get unread count
    unread_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    unread_count = unread_result.scalar() or 0

    # Get notifications
    result = await db.execute(
        base_query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    )
    notifications = list(result.scalars().all())

    return notifications, total, unread_count


async def mark_notification_read(
    db: AsyncSession,
    notification_id: str,
    user_id: str,
) -> Optional[Notification]:
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()

    if notification and not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)

    return notification


async def mark_all_notifications_read(
    db: AsyncSession,
    user_id: str,
) -> int:
    """Mark all notifications as read for a user."""
    result = await db.execute(
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
    return result.rowcount


async def delete_old_notifications(
    db: AsyncSession,
    days: int = 30,
) -> int:
    """Delete notifications older than specified days."""
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cutoff = cutoff.replace(day=cutoff.day - days)

    result = await db.execute(
        delete(Notification).where(Notification.created_at < cutoff)
    )
    return result.rowcount


# =============================================================================
# Slack Integration
# =============================================================================


async def send_slack_notification(
    webhook_url: str,
    title: str,
    message: str,
    color: str = "#36a64f",
    fields: Optional[list[dict]] = None,
    action_url: Optional[str] = None,
) -> bool:
    """
    Send a notification to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL
        title: Message title
        message: Message text
        color: Attachment color (hex)
        fields: Additional fields for the attachment
        action_url: URL for "View" button

    Returns:
        True if sent successfully
    """
    if not webhook_url:
        logger.warning("slack_notification_skipped", reason="no_webhook_url")
        return False

    attachment = {
        "color": color,
        "title": title,
        "text": message,
        "ts": int(datetime.now(timezone.utc).timestamp()),
    }

    if fields:
        attachment["fields"] = fields

    if action_url:
        attachment["actions"] = [
            {
                "type": "button",
                "text": "View Details",
                "url": action_url,
            }
        ]

    payload = {"attachments": [attachment]}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()

        logger.info("slack_notification_sent", title=title)
        return True

    except Exception as e:
        logger.error("slack_notification_failed", error=str(e), title=title)
        return False


async def send_slack_alert(
    webhook_url: str,
    alert_name: str,
    alert_message: str,
    campaign_name: Optional[str] = None,
    metric_value: Optional[float] = None,
    threshold_value: Optional[float] = None,
    action_url: Optional[str] = None,
) -> bool:
    """
    Send an alert notification to Slack.

    Args:
        webhook_url: Slack webhook URL
        alert_name: Name of the alert
        alert_message: Alert message
        campaign_name: Name of the campaign (if applicable)
        metric_value: Current metric value
        threshold_value: Threshold that was exceeded
        action_url: URL to view details

    Returns:
        True if sent successfully
    """
    fields = []

    if campaign_name:
        fields.append({"title": "Campaign", "value": campaign_name, "short": True})

    if metric_value is not None:
        fields.append(
            {"title": "Current Value", "value": str(metric_value), "short": True}
        )

    if threshold_value is not None:
        fields.append(
            {"title": "Threshold", "value": str(threshold_value), "short": True}
        )

    return await send_slack_notification(
        webhook_url=webhook_url,
        title=f":warning: {alert_name}",
        message=alert_message,
        color="#ff6b6b",  # Red for alerts
        fields=fields,
        action_url=action_url,
    )


# =============================================================================
# Email Notifications
# =============================================================================


async def send_email_notification(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """
    Send an email notification using Resend.

    Args:
        to_email: Recipient email
        subject: Email subject
        html_content: HTML email body
        text_content: Plain text email body (optional)

    Returns:
        True if sent successfully
    """
    if not settings.resend_api_key:
        logger.warning("email_notification_skipped", reason="no_resend_api_key")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.email_from,
                    "to": to_email,
                    "subject": subject,
                    "html": html_content,
                    "text": text_content,
                },
                timeout=10.0,
            )
            response.raise_for_status()

        logger.info("email_notification_sent", to=to_email, subject=subject)
        return True

    except Exception as e:
        logger.error("email_notification_failed", error=str(e), to=to_email)
        return False


# =============================================================================
# Multi-Channel Broadcasting
# =============================================================================


async def broadcast_notification(
    db: AsyncSession,
    org_id: str,
    user_ids: list[str],
    title: str,
    message: str,
    notification_type: str,
    channels: Optional[list[str]] = None,
    slack_webhook_url: Optional[str] = None,
    email_subject: Optional[str] = None,
    email_html: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    action_url: Optional[str] = None,
    data: Optional[dict] = None,
) -> dict:
    """
    Broadcast a notification across multiple channels.

    Args:
        db: Database session
        org_id: Organization ID
        user_ids: List of user IDs to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        channels: Channels to use (in_app, slack, email). If None, uses defaults.
        slack_webhook_url: Slack webhook URL for slack channel
        email_subject: Email subject (defaults to title)
        email_html: Email HTML content
        related_entity_type: Type of related entity
        related_entity_id: ID of related entity
        action_url: URL for action buttons
        data: Additional data

    Returns:
        Dict with results per channel
    """
    if channels is None:
        type_config = NOTIFICATION_TYPES.get(notification_type, {})
        channels = type_config.get("default_channels", ["in_app"])

    results = {
        "in_app": {"sent": 0, "failed": 0},
        "slack": {"sent": False, "error": None},
        "email": {"sent": 0, "failed": 0},
    }

    tasks = []

    # In-app notifications
    if "in_app" in channels:
        for user_id in user_ids:
            try:
                await create_notification(
                    db=db,
                    user_id=user_id,
                    org_id=org_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    related_entity_type=related_entity_type,
                    related_entity_id=related_entity_id,
                    data=data,
                )
                results["in_app"]["sent"] += 1
            except Exception as e:
                results["in_app"]["failed"] += 1
                logger.error("in_app_notification_failed", user_id=user_id, error=str(e))

    # Slack notification
    if "slack" in channels and slack_webhook_url:

        async def send_slack():
            success = await send_slack_notification(
                webhook_url=slack_webhook_url,
                title=title,
                message=message,
                action_url=action_url,
            )
            results["slack"]["sent"] = success

        tasks.append(send_slack())

    # Email notifications
    if "email" in channels and settings.resend_api_key:
        # Get user emails
        email_result = await db.execute(
            select(User.email).where(User.id.in_(user_ids), User.is_active == True)
        )
        emails = [row[0] for row in email_result.all()]

        async def send_emails():
            for email in emails:
                try:
                    success = await send_email_notification(
                        to_email=email,
                        subject=email_subject or title,
                        html_content=email_html or f"<p>{message}</p>",
                    )
                    if success:
                        results["email"]["sent"] += 1
                    else:
                        results["email"]["failed"] += 1
                except Exception:
                    results["email"]["failed"] += 1

        tasks.append(send_emails())

    # Execute async tasks
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(
        "notification_broadcast_complete",
        org_id=org_id,
        notification_type=notification_type,
        results=results,
    )

    return results


# =============================================================================
# Notification Preferences
# =============================================================================


async def get_notification_preferences(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """
    Get notification preferences for a user.

    Returns default preferences if not set.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return {}

    # Get org settings
    org_result = await db.execute(
        select(Organization.settings).where(Organization.id == user.org_id)
    )
    org_settings = org_result.scalar_one_or_none() or {}

    # Default preferences
    defaults = {
        "channels": {
            "in_app": True,
            "email": True,
            "slack": False,
        },
        "types": {
            "alert": {"in_app": True, "email": True, "slack": True},
            "campaign_status": {"in_app": True, "email": False, "slack": False},
            "approval_request": {"in_app": True, "email": True, "slack": True},
            "approval_result": {"in_app": True, "email": False, "slack": False},
            "automation_triggered": {"in_app": True, "email": False, "slack": True},
            "automation_pending": {"in_app": True, "email": True, "slack": True},
            "billing": {"in_app": True, "email": True, "slack": False},
            "system": {"in_app": True, "email": False, "slack": False},
        },
        "quiet_hours": {
            "enabled": False,
            "start": "22:00",
            "end": "08:00",
            "timezone": "America/New_York",
        },
        "slack_webhook_url": org_settings.get("slack_webhook_url"),
    }

    # Merge with user's stored preferences
    user_prefs = org_settings.get("notification_preferences", {})

    return {**defaults, **user_prefs}


async def update_notification_preferences(
    db: AsyncSession,
    org_id: str,
    preferences: dict,
) -> dict:
    """
    Update notification preferences for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        preferences: New preferences to merge

    Returns:
        Updated preferences
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise ValueError("Organization not found")

    current_settings = org.settings or {}
    current_prefs = current_settings.get("notification_preferences", {})

    # Merge preferences
    updated_prefs = {**current_prefs, **preferences}
    current_settings["notification_preferences"] = updated_prefs
    org.settings = current_settings

    logger.info(
        "notification_preferences_updated",
        org_id=org_id,
    )

    return updated_prefs


async def set_slack_webhook(
    db: AsyncSession,
    org_id: str,
    webhook_url: str,
) -> None:
    """Set the Slack webhook URL for an organization."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise ValueError("Organization not found")

    current_settings = org.settings or {}
    current_settings["slack_webhook_url"] = webhook_url
    org.settings = current_settings

    logger.info("slack_webhook_updated", org_id=org_id)


async def test_slack_webhook(webhook_url: str) -> bool:
    """
    Test a Slack webhook by sending a test message.

    Returns:
        True if webhook is valid and message sent
    """
    return await send_slack_notification(
        webhook_url=webhook_url,
        title="Test Notification",
        message="This is a test message from AI Marketing Platform. Your Slack integration is working!",
        color="#36a64f",
    )

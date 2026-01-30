"""
Notifications API endpoints.

Provides endpoints for:
- In-app notification management
- Notification preferences
- Slack integration configuration
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.notification_service import (
    get_notifications,
    mark_notification_read,
    mark_all_notifications_read,
    get_notification_preferences,
    update_notification_preferences,
    set_slack_webhook,
    test_slack_webhook,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class NotificationResponse(BaseModel):
    """Notification details response."""

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
    """List of notifications response."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences response."""

    channels: dict
    types: dict
    quiet_hours: dict
    slack_webhook_url: Optional[str]


class NotificationPreferencesUpdate(BaseModel):
    """Update notification preferences request."""

    channels: Optional[dict] = None
    types: Optional[dict] = None
    quiet_hours: Optional[dict] = None


class SlackWebhookRequest(BaseModel):
    """Request to set Slack webhook."""

    webhook_url: str = Field(..., description="Slack webhook URL")


class SlackTestRequest(BaseModel):
    """Request to test Slack webhook."""

    webhook_url: str = Field(..., description="Slack webhook URL to test")


# =============================================================================
# Notification Endpoints
# =============================================================================


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(default=None, description="Filter by read status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notifications for the current user.

    Returns a paginated list of notifications with unread count.
    """
    # TODO: Get user_id from authenticated user
    user_id = "00000000-0000-0000-0000-000000000002"

    offset = (page - 1) * page_size

    notifications, total, unread_count = await get_notifications(
        db=db,
        user_id=user_id,
        is_read=is_read,
        limit=page_size,
        offset=offset,
    )

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


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a notification as read.
    """
    # TODO: Get user_id from authenticated user
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


@router.post("/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all notifications as read for the current user.
    """
    # TODO: Get user_id from authenticated user
    user_id = "00000000-0000-0000-0000-000000000002"

    count = await mark_all_notifications_read(db, user_id)

    return {"marked_read": count}


# =============================================================================
# Notification Preferences Endpoints
# =============================================================================


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
):
    """
    Get notification preferences for the current user.

    Returns channel preferences, type-specific settings, and quiet hours.
    """
    # TODO: Get user_id from authenticated user
    user_id = "00000000-0000-0000-0000-000000000002"

    preferences = await get_notification_preferences(db, user_id)

    return NotificationPreferencesResponse(
        channels=preferences.get("channels", {}),
        types=preferences.get("types", {}),
        quiet_hours=preferences.get("quiet_hours", {}),
        slack_webhook_url=preferences.get("slack_webhook_url"),
    )


@router.patch("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    request: NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update notification preferences.

    Partial updates are supported - only provided fields will be updated.
    """
    # TODO: Get org_id from authenticated user
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    update_data = {}
    if request.channels is not None:
        update_data["channels"] = request.channels
    if request.types is not None:
        update_data["types"] = request.types
    if request.quiet_hours is not None:
        update_data["quiet_hours"] = request.quiet_hours

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    await update_notification_preferences(db, org_id, update_data)

    # Return updated preferences
    preferences = await get_notification_preferences(db, user_id)

    return NotificationPreferencesResponse(
        channels=preferences.get("channels", {}),
        types=preferences.get("types", {}),
        quiet_hours=preferences.get("quiet_hours", {}),
        slack_webhook_url=preferences.get("slack_webhook_url"),
    )


# =============================================================================
# Slack Integration Endpoints
# =============================================================================


@router.post("/slack/webhook")
async def set_slack_webhook_endpoint(
    request: SlackWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Set the Slack webhook URL for the organization.

    The webhook will be used for Slack notifications.
    """
    # TODO: Get org_id from authenticated user (admin only)
    org_id = "00000000-0000-0000-0000-000000000001"

    try:
        await set_slack_webhook(db, org_id, request.webhook_url)
        return {"message": "Slack webhook configured successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/slack/test")
async def test_slack_webhook_endpoint(
    request: SlackTestRequest,
):
    """
    Test a Slack webhook by sending a test message.

    Use this to verify the webhook is working before saving.
    """
    success = await test_slack_webhook(request.webhook_url)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send test message. Please check the webhook URL.",
        )

    return {"message": "Test message sent successfully"}


@router.delete("/slack/webhook")
async def remove_slack_webhook(
    db: AsyncSession = Depends(get_db),
):
    """
    Remove the Slack webhook for the organization.
    """
    # TODO: Get org_id from authenticated user (admin only)
    org_id = "00000000-0000-0000-0000-000000000001"

    try:
        await set_slack_webhook(db, org_id, "")
        return {"message": "Slack webhook removed"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

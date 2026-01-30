"""
Outbound webhook models.

Implements database schema for:
- Webhook endpoint configurations
- Delivery logs and retry tracking
- Event subscriptions
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Supported webhook event types
WEBHOOK_EVENT_TYPES = {
    # Campaign events
    "campaign.created": "When a new campaign is created",
    "campaign.updated": "When a campaign is updated",
    "campaign.status_changed": "When campaign status changes",
    "campaign.approved": "When a campaign is approved",
    "campaign.rejected": "When a campaign is rejected",
    "campaign.paused": "When a campaign is paused",
    "campaign.resumed": "When a campaign is resumed",
    # Alert events
    "alert.triggered": "When an alert is triggered",
    "alert.resolved": "When an alert is resolved",
    # Automation events
    "automation.triggered": "When an automation rule triggers",
    "automation.action_pending": "When an action requires approval",
    "automation.action_executed": "When an automation action is executed",
    # Metrics events
    "metrics.synced": "When metrics are synced from platforms",
    "metrics.anomaly_detected": "When a metrics anomaly is detected",
    # Billing events
    "billing.subscription_created": "When a subscription is created",
    "billing.subscription_updated": "When a subscription is updated",
    "billing.subscription_canceled": "When a subscription is canceled",
    "billing.invoice_paid": "When an invoice is paid",
    "billing.payment_failed": "When a payment fails",
}


class WebhookEndpoint(Base):
    """
    Webhook endpoint configuration.

    Users can configure webhook endpoints to receive events.
    """

    __tablename__ = "webhook_endpoints"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Organization reference
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Endpoint configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # Secret for HMAC signing
    secret: Mapped[str] = mapped_column(String(64), nullable=False)

    # Event subscriptions
    events: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Example: ["campaign.created", "campaign.updated", "alert.triggered"]

    # Headers to include with requests
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Example: {"X-Custom-Header": "value"}

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stats
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    successful_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    failed_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    last_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_delivery_status: Mapped[Optional[str]] = mapped_column(String(20))

    # Created by
    created_by_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="endpoint",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_webhook_endpoints_org_id", "org_id"),
        Index("ix_webhook_endpoints_is_enabled", "is_enabled"),
    )

    def __repr__(self) -> str:
        return f"<WebhookEndpoint {self.name} ({self.id})>"


class WebhookDelivery(Base):
    """
    Webhook delivery log.

    Tracks each delivery attempt for a webhook event.
    """

    __tablename__ = "webhook_deliveries"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Endpoint reference
    endpoint_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization reference (denormalized)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False)  # Unique event ID
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Delivery status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, delivered, failed, retrying

    # Response details
    response_status_code: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[str]] = mapped_column(Text)
    response_headers: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship(
        "WebhookEndpoint", back_populates="deliveries"
    )

    # Indexes
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_id", "endpoint_id"),
        Index("ix_webhook_deliveries_org_id", "org_id"),
        Index("ix_webhook_deliveries_event_type", "event_type"),
        Index("ix_webhook_deliveries_status", "status"),
        Index("ix_webhook_deliveries_created_at", "created_at"),
        Index("ix_webhook_deliveries_next_retry", "next_retry_at"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery {self.event_type} ({self.status})>"

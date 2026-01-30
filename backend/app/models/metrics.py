"""
Campaign metrics models for analytics and reporting.

Uses TimescaleDB hypertable for efficient time-series storage.
The hypertable conversion and continuous aggregates are set up
in the Alembic migration since they require raw SQL.

Metrics are synced from ad platforms every 15 minutes.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CampaignMetrics(Base):
    """
    Time-series metrics for campaigns.

    This table is converted to a TimescaleDB hypertable in the migration.
    Stores raw metrics synced from ad platforms at 15-minute intervals.

    Metrics include:
    - Performance: impressions, clicks, CTR
    - Spend: cost, average CPC
    - Conversions: conversions, conversion value, CPA, ROAS
    """

    __tablename__ = "campaign_metrics"

    # Composite primary key: campaign_id + timestamp
    # TimescaleDB hypertables require time column in primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Campaign reference
    campaign_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Timestamp for time-series partitioning
    # This is the "time" column for the hypertable
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Granularity of this data point
    granularity: Mapped[str] = mapped_column(
        String(10),
        default="raw",
        nullable=False,
    )  # raw, hourly, daily, weekly

    # Performance metrics
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        default=Decimal("0"),
        nullable=False,
    )  # Click-through rate as percentage (e.g., 2.5 = 2.5%)

    # Spend metrics
    spend: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    spend_currency: Mapped[str] = mapped_column(String(3), default="USD")
    avg_cpc: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
        nullable=False,
    )  # Average cost per click
    avg_cpm: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
        nullable=False,
    )  # Average cost per 1000 impressions

    # Conversion metrics
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    cpa: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=False,
    )  # Cost per acquisition
    roas: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
        nullable=False,
    )  # Return on ad spend

    # View-through conversions (if supported by platform)
    view_conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Additional platform-specific metrics (JSONB for flexibility)
    extra_metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example:
    # {
    #     "video_views": 1234,
    #     "video_view_rate": 0.45,
    #     "engagement_rate": 0.023,
    #     "quality_score": 8,
    # }

    # Sync metadata
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Indexes optimized for time-series queries
    # Note: Additional indexes are created by TimescaleDB automatically
    __table_args__ = (
        Index("ix_campaign_metrics_campaign_timestamp", "campaign_id", "timestamp"),
        Index("ix_campaign_metrics_granularity", "granularity"),
        # Unique constraint for upserts
        UniqueConstraint(
            "campaign_id",
            "timestamp",
            "granularity",
            name="uq_campaign_metrics_unique",
        ),
    )

    def __repr__(self) -> str:
        return f"<CampaignMetrics campaign={self.campaign_id} ts={self.timestamp}>"

    @classmethod
    def calculate_derived_metrics(
        cls,
        impressions: int,
        clicks: int,
        spend: Decimal,
        conversions: int,
        conversion_value: Decimal,
    ) -> dict:
        """Calculate derived metrics from raw values."""
        ctr = (clicks / impressions * 100) if impressions > 0 else Decimal("0")
        avg_cpc = (spend / clicks) if clicks > 0 else Decimal("0")
        avg_cpm = (spend / impressions * 1000) if impressions > 0 else Decimal("0")
        cpa = (spend / conversions) if conversions > 0 else Decimal("0")
        roas = (conversion_value / spend) if spend > 0 else Decimal("0")

        return {
            "ctr": Decimal(str(round(ctr, 4))),
            "avg_cpc": Decimal(str(round(avg_cpc, 4))),
            "avg_cpm": Decimal(str(round(avg_cpm, 4))),
            "cpa": Decimal(str(round(cpa, 2))),
            "roas": Decimal(str(round(roas, 4))),
        }


class MetricsSyncStatus(Base):
    """
    Tracks the sync status for each ad account's metrics.

    Used to determine what data to fetch on the next sync cycle.
    """

    __tablename__ = "metrics_sync_status"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Ad account reference
    ad_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Last successful sync
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )  # pending, syncing, success, error

    # Date range of synced data
    earliest_data_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    latest_data_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Sync configuration
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)

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

    __table_args__ = (
        Index("ix_metrics_sync_status_ad_account_id", "ad_account_id"),
        Index("ix_metrics_sync_status_last_sync_at", "last_sync_at"),
    )

    def __repr__(self) -> str:
        return f"<MetricsSyncStatus account={self.ad_account_id} status={self.last_sync_status}>"


class Alert(Base):
    """
    Configurable alerts for budget and performance thresholds.

    Users can set up alerts to be notified when certain conditions are met.
    """

    __tablename__ = "alerts"

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

    # Alert name and description
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Alert type
    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # budget_threshold, cpa_threshold, roas_threshold, ctr_threshold, anomaly

    # Alert configuration (JSONB for flexibility)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Examples:
    # Budget threshold: {"metric": "spend", "threshold_percent": 80, "budget_type": "daily"}
    # CPA threshold: {"metric": "cpa", "operator": "gt", "threshold": 50.00}
    # ROAS threshold: {"metric": "roas", "operator": "lt", "threshold": 2.0}

    # Scope - can be org-wide or specific campaigns
    scope_type: Mapped[str] = mapped_column(
        String(20),
        default="org",
    )  # org, campaign
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
    )

    # Notification settings
    notification_channels: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Example: {"email": true, "in_app": true, "slack": false}

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)  # Min time between alerts

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

    __table_args__ = (
        Index("ix_alerts_org_id", "org_id"),
        Index("ix_alerts_campaign_id", "campaign_id"),
        Index("ix_alerts_alert_type", "alert_type"),
        Index("ix_alerts_is_enabled", "is_enabled"),
    )

    def __repr__(self) -> str:
        return f"<Alert {self.name} ({self.alert_type})>"


class AlertHistory(Base):
    """
    History of triggered alerts.

    Records when alerts were triggered and their resolution.
    """

    __tablename__ = "alert_history"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Alert reference
    alert_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization reference (denormalized for faster queries)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign reference (if applicable)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )

    # When triggered
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Alert details at trigger time
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))

    # Resolution
    status: Mapped[str] = mapped_column(
        String(20),
        default="triggered",
    )  # triggered, acknowledged, resolved
    acknowledged_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    # Notification tracking
    notifications_sent: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Example: {"email": "2024-01-15T10:30:00Z", "in_app": "2024-01-15T10:30:00Z"}

    __table_args__ = (
        Index("ix_alert_history_alert_id", "alert_id"),
        Index("ix_alert_history_org_id", "org_id"),
        Index("ix_alert_history_campaign_id", "campaign_id"),
        Index("ix_alert_history_triggered_at", "triggered_at"),
        Index("ix_alert_history_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AlertHistory alert={self.alert_id} status={self.status}>"


class Notification(Base):
    """
    In-app notifications for users.

    Stores notifications to be displayed in the notification center.
    """

    __tablename__ = "notifications"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # User reference
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization reference
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Notification content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # alert, campaign_status, approval_request, system

    # Related entity (optional)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    related_entity_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    # Additional data
    data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_org_id", "org_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.title[:30]}... for user={self.user_id}>"


class ReportSchedule(Base):
    """
    Scheduled report configuration.

    Users can set up recurring reports to be generated and emailed
    automatically (daily, weekly, monthly).
    """

    __tablename__ = "report_schedules"

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

    # Report name and description
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Report type
    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # performance_summary, campaign_breakdown, spend_analysis, custom

    # Report format
    format: Mapped[str] = mapped_column(
        String(10),
        default="pdf",
    )  # pdf, csv, excel

    # Schedule configuration
    frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # daily, weekly, monthly
    schedule_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Examples:
    # Daily: {"time": "08:00", "timezone": "America/New_York"}
    # Weekly: {"day_of_week": 1, "time": "08:00", "timezone": "America/New_York"}
    # Monthly: {"day_of_month": 1, "time": "08:00", "timezone": "America/New_York"}

    # Report configuration
    report_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example:
    # {
    #     "date_range": "last_7_days",  # last_7_days, last_30_days, last_month, custom
    #     "metrics": ["impressions", "clicks", "spend", "conversions", "roas"],
    #     "breakdown_by": ["campaign", "platform"],
    #     "include_charts": true,
    #     "campaign_ids": null  # null means all campaigns
    # }

    # Recipients
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Example: [{"email": "user@example.com", "name": "John Doe"}]

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[Optional[str]] = mapped_column(String(20))  # success, error
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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

    __table_args__ = (
        Index("ix_report_schedules_org_id", "org_id"),
        Index("ix_report_schedules_is_enabled", "is_enabled"),
        Index("ix_report_schedules_next_run_at", "next_run_at"),
    )

    def __repr__(self) -> str:
        return f"<ReportSchedule {self.name} ({self.frequency})>"

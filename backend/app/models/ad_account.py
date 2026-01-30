"""
Ad Account model for connected advertising platforms.

Stores OAuth tokens (encrypted) and sync status for:
- Google Ads
- Meta (Facebook/Instagram) Ads
- TikTok Ads
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdAccount(Base):
    """
    Connected ad platform account.

    Each organization can connect multiple ad accounts from different platforms.
    OAuth tokens are encrypted at rest using Fernet.
    """

    __tablename__ = "ad_accounts"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to organization
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Platform and account identification
    platform: Mapped[str] = mapped_column(
        Enum("google", "meta", "tiktok", name="ad_platform"),
        nullable=False,
    )
    platform_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    platform_account_name: Mapped[Optional[str]] = mapped_column(String(255))

    # OAuth tokens (encrypted with Fernet)
    access_token_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    refresh_token_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    token_scopes: Mapped[Optional[list]] = mapped_column(JSONB)

    # Connection status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Sync status
    sync_status: Mapped[str] = mapped_column(
        Enum("pending", "syncing", "success", "error", "auth_error", name="sync_status"),
        default="pending",
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    # Platform-specific metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

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

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint(
            "org_id", "platform", "platform_account_id",
            name="uq_ad_account_org_platform_id"
        ),
        Index("ix_ad_accounts_org_id", "org_id"),
        Index("ix_ad_accounts_platform", "platform"),
        Index("ix_ad_accounts_sync_status", "sync_status"),
        Index("ix_ad_accounts_token_expires", "token_expires_at"),
    )

    def __repr__(self) -> str:
        return f"<AdAccount {self.platform}:{self.platform_account_id} ({self.id})>"

    @property
    def is_token_expired(self) -> bool:
        """Check if access token is expired or about to expire."""
        if not self.token_expires_at:
            return False
        # Consider expired if within 5 minutes of expiry
        buffer = datetime.now(timezone.utc)
        return self.token_expires_at <= buffer

    @property
    def needs_reauth(self) -> bool:
        """Check if account needs re-authentication."""
        return (
            self.sync_status == "auth_error"
            or self.consecutive_failures >= 3
            or (self.is_token_expired and not self.refresh_token_encrypted)
        )


class AdAccountSyncLog(Base):
    """
    Log of ad account sync attempts.

    Tracks sync history for debugging and monitoring.
    """

    __tablename__ = "ad_account_sync_logs"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to ad account
    ad_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Sync details
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)  # metrics, campaigns, etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, error
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Results
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Indexes
    __table_args__ = (
        Index("ix_sync_logs_ad_account", "ad_account_id"),
        Index("ix_sync_logs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<AdAccountSyncLog {self.sync_type} {self.status} ({self.id})>"

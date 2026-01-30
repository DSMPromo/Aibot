"""
Campaign models for unified campaign management across ad platforms.

Supports:
- Campaign CRUD with status workflow
- Version history tracking
- Platform-specific fields via JSONB
- Targeting and ad copy storage
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
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


# =============================================================================
# Campaign Status Workflow
# =============================================================================
# draft -> pending_review -> approved -> active -> paused -> archived
#                       \-> rejected
#
# Valid transitions:
# - draft: can move to pending_review or archived
# - pending_review: can move to approved, rejected, or draft (withdraw)
# - approved: can move to active (after platform push)
# - active: can move to paused or archived
# - paused: can move to active or archived
# - rejected: can move to draft (revise)
# - archived: terminal state

CAMPAIGN_STATUS_TRANSITIONS = {
    "draft": ["pending_review", "archived"],
    "pending_review": ["approved", "rejected", "draft"],
    "approved": ["active", "archived"],
    "active": ["paused", "archived"],
    "paused": ["active", "archived"],
    "rejected": ["draft", "archived"],
    "archived": [],
}


class Campaign(Base):
    """
    Unified campaign model across all ad platforms.

    Stores campaign configuration and tracks sync status with platforms.
    Platform-specific details stored in JSONB for flexibility.
    """

    __tablename__ = "campaigns"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Organization and account references
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ad_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ad_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Basic campaign info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(
        Enum("google", "meta", "tiktok", name="ad_platform", create_type=False),
        nullable=False,
    )

    # Campaign objective
    objective: Mapped[str] = mapped_column(
        Enum(
            "awareness",
            "traffic",
            "engagement",
            "leads",
            "sales",
            "app_promotion",
            name="campaign_objective",
        ),
        nullable=False,
    )

    # Status workflow
    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "pending_review",
            "approved",
            "rejected",
            "active",
            "paused",
            "archived",
            name="campaign_status",
        ),
        default="draft",
        nullable=False,
    )
    status_reason: Mapped[Optional[str]] = mapped_column(Text)  # Rejection reason, etc.

    # Budget configuration
    budget_type: Mapped[str] = mapped_column(
        Enum("daily", "lifetime", name="budget_type"),
        default="daily",
        nullable=False,
    )
    budget_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    budget_currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Schedule
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    is_ongoing: Mapped[bool] = mapped_column(Boolean, default=False)

    # Platform sync status
    platform_campaign_id: Mapped[Optional[str]] = mapped_column(String(100))
    platform_status: Mapped[Optional[str]] = mapped_column(String(50))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[Optional[str]] = mapped_column(Text)

    # Targeting configuration (JSONB for flexibility)
    targeting: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example structure:
    # {
    #     "locations": ["US", "CA"],
    #     "age_min": 18,
    #     "age_max": 65,
    #     "genders": ["all"],
    #     "interests": ["technology", "marketing"],
    #     "keywords": ["advertising", "marketing software"],
    #     "placements": ["search", "display"],
    # }

    # Platform-specific settings (JSONB)
    platform_settings: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example for Google Ads:
    # {
    #     "campaign_type": "SEARCH",
    #     "bidding_strategy": "MAXIMIZE_CONVERSIONS",
    #     "networks": ["SEARCH", "SEARCH_PARTNERS"],
    # }

    # Ownership and audit
    created_by_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    approved_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)

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
        Index("ix_campaigns_org_id", "org_id"),
        Index("ix_campaigns_ad_account_id", "ad_account_id"),
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_platform", "platform"),
        Index("ix_campaigns_created_at", "created_at"),
        Index("ix_campaigns_platform_campaign_id", "platform_campaign_id"),
        CheckConstraint(
            "budget_amount > 0",
            name="ck_campaigns_positive_budget",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_campaigns_valid_dates",
        ),
    )

    # Relationships
    ad_copies = relationship("AdCopy", back_populates="campaign", cascade="all, delete-orphan")
    versions = relationship("CampaignVersion", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Campaign {self.name} ({self.status}) [{self.id}]>"

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition to new status is valid."""
        return new_status in CAMPAIGN_STATUS_TRANSITIONS.get(self.status, [])

    @property
    def is_editable(self) -> bool:
        """Check if campaign can be edited."""
        return self.status in ("draft", "rejected")

    @property
    def is_live(self) -> bool:
        """Check if campaign is live on the platform."""
        return self.status in ("active", "paused") and self.platform_campaign_id is not None

    @property
    def needs_approval(self) -> bool:
        """Check if campaign is waiting for approval."""
        return self.status == "pending_review"


class AdCopy(Base):
    """
    Ad copy content for a campaign.

    Stores headlines, descriptions, and other creative elements.
    Supports multiple variations for A/B testing.
    """

    __tablename__ = "ad_copies"

    # Primary key
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

    # Ad copy content
    headline_1: Mapped[str] = mapped_column(String(30), nullable=False)  # Google limit: 30 chars
    headline_2: Mapped[Optional[str]] = mapped_column(String(30))
    headline_3: Mapped[Optional[str]] = mapped_column(String(30))

    description_1: Mapped[str] = mapped_column(String(90), nullable=False)  # Google limit: 90 chars
    description_2: Mapped[Optional[str]] = mapped_column(String(90))

    # Display URL paths
    path_1: Mapped[Optional[str]] = mapped_column(String(15))  # Google limit: 15 chars
    path_2: Mapped[Optional[str]] = mapped_column(String(15))

    # Final URL (landing page)
    final_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    # Call to action
    call_to_action: Mapped[Optional[str]] = mapped_column(String(50))

    # AI generation tracking
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_generation_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    # Variation tracking
    variation_name: Mapped[Optional[str]] = mapped_column(String(50))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Platform-specific creative fields (images, videos, etc.)
    creative_assets: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example:
    # {
    #     "images": ["asset_id_1", "asset_id_2"],
    #     "videos": ["video_id_1"],
    #     "logos": ["logo_id_1"],
    # }

    # Platform sync
    platform_ad_id: Mapped[Optional[str]] = mapped_column(String(100))

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

    # Indexes
    __table_args__ = (
        Index("ix_ad_copies_campaign_id", "campaign_id"),
    )

    # Relationships
    campaign = relationship("Campaign", back_populates="ad_copies")

    def __repr__(self) -> str:
        return f"<AdCopy {self.headline_1[:20]}... ({self.id})>"


class CampaignVersion(Base):
    """
    Version history for campaigns.

    Tracks changes over time for audit and rollback purposes.
    """

    __tablename__ = "campaign_versions"

    # Primary key
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

    # Version number
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of campaign state at this version
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Contains: name, objective, budget_type, budget_amount, targeting, platform_settings, ad_copies

    # Change tracking
    change_type: Mapped[str] = mapped_column(
        Enum("created", "updated", "status_change", name="change_type"),
        nullable=False,
    )
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    changed_fields: Mapped[Optional[list]] = mapped_column(JSONB)

    # Who made the change
    changed_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("ix_campaign_versions_campaign_id", "campaign_id"),
        Index("ix_campaign_versions_version", "campaign_id", "version"),
        UniqueConstraint("campaign_id", "version", name="uq_campaign_version"),
    )

    # Relationships
    campaign = relationship("Campaign", back_populates="versions")

    def __repr__(self) -> str:
        return f"<CampaignVersion campaign={self.campaign_id} v{self.version}>"


class CampaignApproval(Base):
    """
    Approval workflow tracking for campaigns.

    Records approval requests, decisions, and comments.
    """

    __tablename__ = "campaign_approvals"

    # Primary key
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

    # Approval request
    requested_by_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Decision
    decision: Mapped[Optional[str]] = mapped_column(
        Enum("pending", "approved", "rejected", name="approval_decision"),
        default="pending",
    )
    decided_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Comments
    request_comment: Mapped[Optional[str]] = mapped_column(Text)
    decision_comment: Mapped[Optional[str]] = mapped_column(Text)

    # Campaign version at time of request
    campaign_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_campaign_approvals_campaign_id", "campaign_id"),
        Index("ix_campaign_approvals_decision", "decision"),
        Index("ix_campaign_approvals_requested_at", "requested_at"),
    )

    def __repr__(self) -> str:
        return f"<CampaignApproval campaign={self.campaign_id} {self.decision}>"

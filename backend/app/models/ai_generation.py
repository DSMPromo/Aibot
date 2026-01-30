"""
AI Generation models for tracking AI usage and costs.

Tracks:
- Individual AI generations with token usage and cost
- Organization-level usage aggregates
- Usage limits per subscription tier
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIGeneration(Base):
    """
    Record of an individual AI generation.

    Tracks all AI generations for usage billing and analytics.
    """

    __tablename__ = "ai_generations"

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

    # User who triggered the generation
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Generation type
    generation_type: Mapped[str] = mapped_column(
        Enum(
            "ad_copy",
            "headline",
            "description",
            "cta",
            "targeting_suggestion",
            "other",
            name="ai_generation_type",
        ),
        nullable=False,
    )

    # Model and provider info
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(
        Enum("openai", "anthropic", "other", name="ai_provider"),
        nullable=False,
    )
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)

    # Token usage
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0"),
    )

    # Generation metadata
    generation_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64))  # For caching

    # Input/output (optional, for debugging/improvement)
    input_summary: Mapped[Optional[str]] = mapped_column(Text)  # Truncated input
    output_summary: Mapped[Optional[str]] = mapped_column(Text)  # Truncated output

    # Status
    status: Mapped[str] = mapped_column(
        Enum("success", "error", "rate_limited", name="ai_generation_status"),
        default="success",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Context (what the generation was for)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )
    context: Mapped[Optional[dict]] = mapped_column(JSONB)  # Additional context

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("ix_ai_generations_org_id", "org_id"),
        Index("ix_ai_generations_user_id", "user_id"),
        Index("ix_ai_generations_created_at", "created_at"),
        Index("ix_ai_generations_type", "generation_type"),
        Index("ix_ai_generations_org_created", "org_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AIGeneration {self.generation_type} {self.status} ({self.id})>"


class AIUsageQuota(Base):
    """
    AI usage quota tracking per organization.

    Tracks monthly usage against plan limits.
    """

    __tablename__ = "ai_usage_quotas"

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

    # Period (year-month)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Plan tier at time of quota
    plan_tier: Mapped[str] = mapped_column(
        Enum("free", "pro", "enterprise", name="plan_tier"),
        default="free",
    )

    # Limits
    generation_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    token_limit: Mapped[Optional[int]] = mapped_column(Integer)  # Optional token limit

    # Current usage
    generations_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
    )

    # Warning flags
    warning_sent_80: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_sent_100: Mapped[bool] = mapped_column(Boolean, default=False)
    limit_reached_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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

    # Unique constraint on org + period
    __table_args__ = (
        UniqueConstraint(
            "org_id", "period_year", "period_month",
            name="uq_ai_usage_quota_org_period"
        ),
        Index("ix_ai_usage_quotas_org_id", "org_id"),
        Index("ix_ai_usage_quotas_period", "period_year", "period_month"),
    )

    def __repr__(self) -> str:
        return f"<AIUsageQuota {self.org_id} {self.period_year}-{self.period_month}>"

    @property
    def usage_percentage(self) -> float:
        """Get current usage as percentage of limit."""
        if self.generation_limit <= 0:
            return 0.0
        return (self.generations_used / self.generation_limit) * 100

    @property
    def is_limit_reached(self) -> bool:
        """Check if limit has been reached."""
        return self.generations_used >= self.generation_limit

    @property
    def remaining_generations(self) -> int:
        """Get remaining generations."""
        return max(0, self.generation_limit - self.generations_used)

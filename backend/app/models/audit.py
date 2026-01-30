"""
Audit Log model.

Implements comprehensive audit logging for security and compliance.
Tracks all significant user and system actions.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """
    Audit log entry.

    Records all significant actions for security auditing and compliance.
    Retained for 90 days hot, 2 years cold (per DATA-003).
    """

    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Context
    org_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action details
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    # Change tracking
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    changes: Mapped[Optional[dict]] = mapped_column(JSONB)  # Diff of old/new

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Additional metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Impersonation tracking
    impersonator_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamp (partitioning key)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        # Composite index for common query pattern
        Index("ix_audit_logs_org_action_created", "org_id", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id} at {self.created_at}>"


# Audit action constants for type safety
class AuditActions:
    """Constants for audit log actions."""

    # User actions
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_MFA_ENABLED = "user.mfa_enabled"
    USER_MFA_DISABLED = "user.mfa_disabled"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_PASSWORD_RESET = "user.password_reset"

    # Organization actions
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    ORG_DELETED = "org.deleted"
    ORG_USER_INVITED = "org.user_invited"
    ORG_USER_REMOVED = "org.user_removed"

    # Campaign actions
    CAMPAIGN_CREATED = "campaign.created"
    CAMPAIGN_UPDATED = "campaign.updated"
    CAMPAIGN_DELETED = "campaign.deleted"
    CAMPAIGN_LAUNCHED = "campaign.launched"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_APPROVED = "campaign.approved"
    CAMPAIGN_REJECTED = "campaign.rejected"

    # Ad account actions
    AD_ACCOUNT_CONNECTED = "ad_account.connected"
    AD_ACCOUNT_DISCONNECTED = "ad_account.disconnected"
    AD_ACCOUNT_SYNC_FAILED = "ad_account.sync_failed"

    # Automation rule actions
    RULE_CREATED = "rule.created"
    RULE_UPDATED = "rule.updated"
    RULE_DELETED = "rule.deleted"
    RULE_TRIGGERED = "rule.triggered"
    RULE_ACTION_EXECUTED = "rule.action_executed"

    # Billing actions
    BILLING_SUBSCRIPTION_CREATED = "billing.subscription_created"
    BILLING_SUBSCRIPTION_UPDATED = "billing.subscription_updated"
    BILLING_PAYMENT_FAILED = "billing.payment_failed"

    # AI actions
    AI_GENERATION_REQUESTED = "ai.generation_requested"
    AI_LIMIT_REACHED = "ai.limit_reached"

    # Admin actions
    ADMIN_IMPERSONATION_STARTED = "admin.impersonation_started"
    ADMIN_IMPERSONATION_ENDED = "admin.impersonation_ended"
    ADMIN_TENANT_SUSPENDED = "admin.tenant_suspended"
    ADMIN_TENANT_UNSUSPENDED = "admin.tenant_unsuspended"

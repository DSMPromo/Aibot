"""
User and Organization models.

Implements database schema for:
- Organizations (multi-tenancy)
- Users with RBAC
- Sessions for session management
- Invitations for user onboarding
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Organization(Base):
    """
    Organization/Tenant model.

    Each organization is an isolated tenant with its own:
    - Users with roles
    - Ad accounts
    - Campaigns
    - Billing subscription
    """

    __tablename__ = "organizations"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Organization details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Subscription
    plan_tier: Mapped[str] = mapped_column(
        Enum("free", "starter", "pro", "agency", "enterprise", name="plan_tier"),
        default="free",
        nullable=False,
    )

    # Stripe integration
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Usage tracking
    ai_generations_used: Mapped[int] = mapped_column(Integer, default=0)
    ai_generations_limit: Mapped[int] = mapped_column(Integer, default=50)

    # Settings (JSONB for flexibility)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text)

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
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation", back_populates="organization", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_organizations_slug", "slug"),
        Index("ix_organizations_stripe_customer", "stripe_customer_id"),
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.id})>"


class User(Base):
    """
    User model.

    Users belong to an organization and have a role (admin, manager, user).
    Implements MFA with TOTP and recovery codes.
    """

    __tablename__ = "users"

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

    # User details
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Authentication
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(100))
    email_verification_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Password reset
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(100))
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Role (RBAC)
    role: Mapped[str] = mapped_column(
        Enum("admin", "manager", "user", name="user_role"),
        default="user",
        nullable=False,
    )

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[Optional[bytes]] = mapped_column()  # Encrypted TOTP secret
    mfa_recovery_codes: Mapped[Optional[list]] = mapped_column(JSONB)  # Hashed recovery codes

    # Google SSO
    google_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Activity
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45))

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="users"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_user_org_email"),
        Index("ix_users_email", "email"),
        Index("ix_users_org_id", "org_id"),
        Index("ix_users_google_id", "google_id"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.id})>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        """Check if user has manager or admin role."""
        return self.role in ("admin", "manager")


class Session(Base):
    """
    User session model.

    Tracks active sessions for session management feature.
    Stores refresh token JTI for revocation.
    """

    __tablename__ = "sessions"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Session details
    refresh_token_jti: Mapped[str] = mapped_column(String(100), unique=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_refresh_token_jti", "refresh_token_jti"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} for user {self.user_id}>"


class Invitation(Base):
    """
    User invitation model.

    Tracks pending invitations to organizations.
    """

    __tablename__ = "invitations"

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

    # Invitation details
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "manager", "user", name="user_role"),
        default="user",
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Who sent the invitation
    invited_by_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="invitations"
    )

    # Indexes
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_invitation_org_email"),
        Index("ix_invitations_token", "token"),
        Index("ix_invitations_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Invitation {self.email} to org {self.org_id}>"

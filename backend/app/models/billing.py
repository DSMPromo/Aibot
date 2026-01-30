"""
Billing models for Stripe integration.

Implements database schema for:
- Subscriptions (linked to Stripe)
- Invoices and payment history
- Plan tiers and limits
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Plan tier limits configuration
PLAN_LIMITS = {
    "free": {
        "ai_generations": 50,
        "ad_accounts": 1,
        "campaigns": 5,
        "team_members": 1,
        "api_requests_per_day": 100,
        "report_exports": 5,
        "automation_rules": 2,
    },
    "starter": {
        "ai_generations": 200,
        "ad_accounts": 3,
        "campaigns": 25,
        "team_members": 3,
        "api_requests_per_day": 1000,
        "report_exports": 50,
        "automation_rules": 10,
    },
    "pro": {
        "ai_generations": 1000,
        "ad_accounts": 10,
        "campaigns": 100,
        "team_members": 10,
        "api_requests_per_day": 10000,
        "report_exports": -1,  # Unlimited
        "automation_rules": 50,
    },
    "agency": {
        "ai_generations": 5000,
        "ad_accounts": 50,
        "campaigns": 500,
        "team_members": 25,
        "api_requests_per_day": 50000,
        "report_exports": -1,
        "automation_rules": 200,
    },
    "enterprise": {
        "ai_generations": -1,  # Unlimited
        "ad_accounts": -1,
        "campaigns": -1,
        "team_members": -1,
        "api_requests_per_day": -1,
        "report_exports": -1,
        "automation_rules": -1,
    },
}


class Subscription(Base):
    """
    Subscription model linked to Stripe.

    Tracks the organization's subscription status, plan, and billing cycle.
    """

    __tablename__ = "subscriptions"

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
        unique=True,
    )

    # Stripe IDs
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(100))
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Plan details
    plan_tier: Mapped[str] = mapped_column(
        Enum("free", "starter", "pro", "agency", "enterprise", name="subscription_plan_tier"),
        default="free",
        nullable=False,
    )

    # Subscription status
    status: Mapped[str] = mapped_column(
        Enum(
            "active",
            "past_due",
            "canceled",
            "incomplete",
            "incomplete_expired",
            "trialing",
            "unpaid",
            "paused",
            name="subscription_status",
        ),
        default="active",
        nullable=False,
    )

    # Billing cycle
    billing_cycle: Mapped[str] = mapped_column(
        Enum("monthly", "yearly", name="billing_cycle"),
        default="monthly",
        nullable=False,
    )

    # Pricing (in cents)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")

    # Dates
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancel_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Cancellation
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)

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
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_subscriptions_org_id", "org_id"),
        Index("ix_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
        Index("ix_subscriptions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.plan_tier} for org {self.org_id}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is in an active state."""
        return self.status in ("active", "trialing")

    @property
    def is_canceled(self) -> bool:
        """Check if subscription is canceled."""
        return self.status == "canceled" or self.cancel_at_period_end

    def get_limit(self, limit_name: str) -> int:
        """Get a specific limit for the current plan tier."""
        limits = PLAN_LIMITS.get(self.plan_tier, PLAN_LIMITS["free"])
        return limits.get(limit_name, 0)


class Invoice(Base):
    """
    Invoice model linked to Stripe.

    Tracks all invoices for billing history.
    """

    __tablename__ = "invoices"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign keys
    subscription_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Stripe IDs
    stripe_invoice_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(100))
    stripe_charge_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Invoice details
    invoice_number: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "open",
            "paid",
            "void",
            "uncollectible",
            name="invoice_status",
        ),
        default="draft",
        nullable=False,
    )

    # Amounts (in cents)
    amount_due: Mapped[int] = mapped_column(Integer, default=0)
    amount_paid: Mapped[int] = mapped_column(Integer, default=0)
    amount_remaining: Mapped[int] = mapped_column(Integer, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text)

    # URLs
    hosted_invoice_url: Mapped[Optional[str]] = mapped_column(Text)
    invoice_pdf: Mapped[Optional[str]] = mapped_column(Text)

    # Dates
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Line items stored as JSON
    line_items: Mapped[list] = mapped_column(JSONB, default=list)

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
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="invoices")

    # Indexes
    __table_args__ = (
        Index("ix_invoices_subscription_id", "subscription_id"),
        Index("ix_invoices_org_id", "org_id"),
        Index("ix_invoices_stripe_invoice_id", "stripe_invoice_id"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.stripe_invoice_id} - {self.status}>"


class PaymentMethod(Base):
    """
    Payment method model linked to Stripe.

    Tracks saved payment methods for customers.
    """

    __tablename__ = "payment_methods"

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

    # Stripe IDs
    stripe_payment_method_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    # Payment method type
    type: Mapped[str] = mapped_column(
        Enum("card", "bank_account", "sepa_debit", name="payment_method_type"),
        default="card",
        nullable=False,
    )

    # Card details (for display only - sensitive data stored in Stripe)
    card_brand: Mapped[Optional[str]] = mapped_column(String(20))
    card_last4: Mapped[Optional[str]] = mapped_column(String(4))
    card_exp_month: Mapped[Optional[int]] = mapped_column(Integer)
    card_exp_year: Mapped[Optional[int]] = mapped_column(Integer)

    # Bank account details (for display only)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100))
    bank_last4: Mapped[Optional[str]] = mapped_column(String(4))

    # Default payment method flag
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

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
        Index("ix_payment_methods_org_id", "org_id"),
        Index("ix_payment_methods_stripe_id", "stripe_payment_method_id"),
    )

    def __repr__(self) -> str:
        if self.type == "card":
            return f"<PaymentMethod {self.card_brand} *{self.card_last4}>"
        return f"<PaymentMethod {self.type}>"


class UsageRecord(Base):
    """
    Usage record for usage-based billing tracking.

    Tracks API calls, AI generations, and other metered usage.
    """

    __tablename__ = "usage_records"

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

    # Usage type
    usage_type: Mapped[str] = mapped_column(
        Enum(
            "ai_generation",
            "api_request",
            "report_export",
            "data_sync",
            name="usage_type",
        ),
        nullable=False,
    )

    # Quantity
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # Period (for aggregation)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Stripe usage record ID (if reported to Stripe)
    stripe_usage_record_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Metadata
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("ix_usage_records_org_id", "org_id"),
        Index("ix_usage_records_type", "usage_type"),
        Index("ix_usage_records_period", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return f"<UsageRecord {self.usage_type}: {self.quantity}>"

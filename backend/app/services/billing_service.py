"""
Billing service for Stripe integration.

Provides functions for:
- Customer creation and management
- Subscription lifecycle
- Payment method management
- Invoice retrieval
- Usage tracking and limits
"""

from datetime import datetime, timezone
from typing import Optional

import stripe
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import (
    Invoice,
    PaymentMethod,
    Subscription,
    UsageRecord,
    PLAN_LIMITS,
)
from app.models.user import Organization

logger = structlog.get_logger()

# Initialize Stripe with API key
stripe.api_key = settings.stripe_secret_key


# =============================================================================
# Plan Configuration
# =============================================================================

# Stripe Price IDs mapped to plan tiers (configure in Stripe Dashboard)
STRIPE_PRICE_IDS = {
    "starter_monthly": "price_starter_monthly",
    "starter_yearly": "price_starter_yearly",
    "pro_monthly": "price_pro_monthly",
    "pro_yearly": "price_pro_yearly",
    "agency_monthly": "price_agency_monthly",
    "agency_yearly": "price_agency_yearly",
    "enterprise_monthly": "price_enterprise_monthly",
    "enterprise_yearly": "price_enterprise_yearly",
}

PRICE_TO_TIER = {
    "price_starter_monthly": "starter",
    "price_starter_yearly": "starter",
    "price_pro_monthly": "pro",
    "price_pro_yearly": "pro",
    "price_agency_monthly": "agency",
    "price_agency_yearly": "agency",
    "price_enterprise_monthly": "enterprise",
    "price_enterprise_yearly": "enterprise",
}


# =============================================================================
# Customer Management
# =============================================================================


async def create_stripe_customer(
    db: AsyncSession,
    org_id: str,
    email: str,
    name: str,
    metadata: Optional[dict] = None,
) -> str:
    """
    Create a Stripe customer for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        email: Billing email
        name: Organization name
        metadata: Additional metadata

    Returns:
        Stripe customer ID
    """
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={
                "org_id": org_id,
                **(metadata or {}),
            },
        )

        # Update organization with Stripe customer ID
        await db.execute(
            update(Organization)
            .where(Organization.id == org_id)
            .values(stripe_customer_id=customer.id)
        )

        logger.info(
            "stripe_customer_created",
            org_id=org_id,
            customer_id=customer.id,
        )

        return customer.id

    except stripe.StripeError as e:
        logger.error("stripe_customer_creation_failed", org_id=org_id, error=str(e))
        raise


async def get_or_create_stripe_customer(
    db: AsyncSession,
    org_id: str,
    email: str,
    name: str,
) -> str:
    """
    Get existing or create new Stripe customer.

    Args:
        db: Database session
        org_id: Organization ID
        email: Billing email
        name: Organization name

    Returns:
        Stripe customer ID
    """
    # Check if org already has a Stripe customer
    result = await db.execute(
        select(Organization.stripe_customer_id).where(Organization.id == org_id)
    )
    customer_id = result.scalar_one_or_none()

    if customer_id:
        return customer_id

    return await create_stripe_customer(db, org_id, email, name)


async def update_stripe_customer(
    customer_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Update Stripe customer details."""
    try:
        update_data = {}
        if email:
            update_data["email"] = email
        if name:
            update_data["name"] = name
        if metadata:
            update_data["metadata"] = metadata

        if update_data:
            stripe.Customer.modify(customer_id, **update_data)

    except stripe.StripeError as e:
        logger.error("stripe_customer_update_failed", customer_id=customer_id, error=str(e))
        raise


# =============================================================================
# Subscription Management
# =============================================================================


async def create_checkout_session(
    db: AsyncSession,
    org_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout session for subscription.

    Args:
        db: Database session
        org_id: Organization ID
        price_id: Stripe Price ID
        success_url: URL to redirect on success
        cancel_url: URL to redirect on cancel
        customer_email: Customer email for new customers

    Returns:
        Checkout session URL
    """
    # Get or create customer
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise ValueError(f"Organization not found: {org_id}")

    try:
        session_params = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"org_id": org_id},
            "subscription_data": {
                "metadata": {"org_id": org_id},
            },
            "allow_promotion_codes": True,
            "billing_address_collection": "required",
            "tax_id_collection": {"enabled": True},
        }

        if org.stripe_customer_id:
            session_params["customer"] = org.stripe_customer_id
        elif customer_email:
            session_params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        logger.info(
            "checkout_session_created",
            org_id=org_id,
            session_id=session.id,
            price_id=price_id,
        )

        return session.url

    except stripe.StripeError as e:
        logger.error("checkout_session_failed", org_id=org_id, error=str(e))
        raise


async def create_billing_portal_session(
    db: AsyncSession,
    org_id: str,
    return_url: str,
) -> str:
    """
    Create a Stripe Billing Portal session.

    Allows customers to manage their subscription, payment methods, and invoices.

    Args:
        db: Database session
        org_id: Organization ID
        return_url: URL to return to after portal session

    Returns:
        Billing portal session URL
    """
    result = await db.execute(
        select(Organization.stripe_customer_id).where(Organization.id == org_id)
    )
    customer_id = result.scalar_one_or_none()

    if not customer_id:
        raise ValueError("Organization does not have a Stripe customer")

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return session.url

    except stripe.StripeError as e:
        logger.error("billing_portal_failed", org_id=org_id, error=str(e))
        raise


async def get_subscription(db: AsyncSession, org_id: str) -> Optional[Subscription]:
    """Get subscription for an organization."""
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == org_id)
    )
    return result.scalar_one_or_none()


async def create_or_update_subscription_from_stripe(
    db: AsyncSession,
    stripe_subscription: stripe.Subscription,
) -> Subscription:
    """
    Create or update local subscription from Stripe subscription object.

    Called from webhook handlers.
    """
    org_id = stripe_subscription.metadata.get("org_id")
    if not org_id:
        # Try to find org by customer ID
        result = await db.execute(
            select(Organization.id).where(
                Organization.stripe_customer_id == stripe_subscription.customer
            )
        )
        org_id = result.scalar_one_or_none()

    if not org_id:
        raise ValueError("Could not determine organization for subscription")

    # Determine plan tier from price
    price_id = stripe_subscription["items"]["data"][0]["price"]["id"]
    plan_tier = PRICE_TO_TIER.get(price_id, "free")

    # Check for existing subscription
    result = await db.execute(
        select(Subscription).where(Subscription.org_id == org_id)
    )
    subscription = result.scalar_one_or_none()

    subscription_data = {
        "stripe_subscription_id": stripe_subscription.id,
        "stripe_price_id": price_id,
        "stripe_product_id": stripe_subscription["items"]["data"][0]["price"]["product"],
        "plan_tier": plan_tier,
        "status": stripe_subscription.status,
        "billing_cycle": "yearly" if "year" in price_id else "monthly",
        "amount": stripe_subscription["items"]["data"][0]["price"]["unit_amount"] or 0,
        "currency": stripe_subscription.currency,
        "current_period_start": datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=timezone.utc
        ),
        "current_period_end": datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=timezone.utc
        ),
        "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
        "canceled_at": (
            datetime.fromtimestamp(stripe_subscription.canceled_at, tz=timezone.utc)
            if stripe_subscription.canceled_at
            else None
        ),
        "updated_at": datetime.now(timezone.utc),
    }

    if stripe_subscription.trial_start:
        subscription_data["trial_start"] = datetime.fromtimestamp(
            stripe_subscription.trial_start, tz=timezone.utc
        )
    if stripe_subscription.trial_end:
        subscription_data["trial_end"] = datetime.fromtimestamp(
            stripe_subscription.trial_end, tz=timezone.utc
        )

    if subscription:
        # Update existing
        for key, value in subscription_data.items():
            setattr(subscription, key, value)
    else:
        # Create new
        subscription = Subscription(org_id=org_id, **subscription_data)
        db.add(subscription)

    # Update organization plan tier
    await db.execute(
        update(Organization)
        .where(Organization.id == org_id)
        .values(
            plan_tier=plan_tier,
            stripe_subscription_id=stripe_subscription.id,
            ai_generations_limit=PLAN_LIMITS[plan_tier]["ai_generations"],
        )
    )

    logger.info(
        "subscription_synced",
        org_id=org_id,
        subscription_id=stripe_subscription.id,
        plan_tier=plan_tier,
        status=stripe_subscription.status,
    )

    return subscription


async def cancel_subscription(
    db: AsyncSession,
    org_id: str,
    at_period_end: bool = True,
    reason: Optional[str] = None,
) -> Subscription:
    """
    Cancel an organization's subscription.

    Args:
        db: Database session
        org_id: Organization ID
        at_period_end: If True, cancel at end of billing period
        reason: Cancellation reason

    Returns:
        Updated subscription
    """
    subscription = await get_subscription(db, org_id)
    if not subscription or not subscription.stripe_subscription_id:
        raise ValueError("No active subscription found")

    try:
        if at_period_end:
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        else:
            stripe_sub = stripe.Subscription.delete(subscription.stripe_subscription_id)

        # Update local subscription
        subscription.cancel_at_period_end = at_period_end
        subscription.canceled_at = datetime.now(timezone.utc)
        subscription.cancellation_reason = reason
        if not at_period_end:
            subscription.status = "canceled"

        logger.info(
            "subscription_canceled",
            org_id=org_id,
            at_period_end=at_period_end,
        )

        return subscription

    except stripe.StripeError as e:
        logger.error("subscription_cancel_failed", org_id=org_id, error=str(e))
        raise


async def reactivate_subscription(db: AsyncSession, org_id: str) -> Subscription:
    """
    Reactivate a canceled subscription (if still in period).

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        Updated subscription
    """
    subscription = await get_subscription(db, org_id)
    if not subscription or not subscription.stripe_subscription_id:
        raise ValueError("No subscription found")

    if not subscription.cancel_at_period_end:
        raise ValueError("Subscription is not scheduled for cancellation")

    try:
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.cancellation_reason = None

        logger.info("subscription_reactivated", org_id=org_id)

        return subscription

    except stripe.StripeError as e:
        logger.error("subscription_reactivation_failed", org_id=org_id, error=str(e))
        raise


# =============================================================================
# Invoice Management
# =============================================================================


async def sync_invoice_from_stripe(
    db: AsyncSession,
    stripe_invoice: stripe.Invoice,
) -> Invoice:
    """
    Create or update local invoice from Stripe invoice object.

    Called from webhook handlers.
    """
    # Find organization by customer
    result = await db.execute(
        select(Organization.id).where(
            Organization.stripe_customer_id == stripe_invoice.customer
        )
    )
    org_id = result.scalar_one_or_none()

    if not org_id:
        raise ValueError("Could not find organization for invoice")

    # Find subscription
    result = await db.execute(
        select(Subscription.id).where(Subscription.org_id == org_id)
    )
    subscription_id = result.scalar_one_or_none()

    if not subscription_id:
        raise ValueError("Could not find subscription for invoice")

    # Check for existing invoice
    result = await db.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice.id)
    )
    invoice = result.scalar_one_or_none()

    invoice_data = {
        "stripe_invoice_id": stripe_invoice.id,
        "stripe_payment_intent_id": stripe_invoice.payment_intent,
        "invoice_number": stripe_invoice.number,
        "status": stripe_invoice.status,
        "amount_due": stripe_invoice.amount_due,
        "amount_paid": stripe_invoice.amount_paid,
        "amount_remaining": stripe_invoice.amount_remaining,
        "subtotal": stripe_invoice.subtotal,
        "tax": stripe_invoice.tax or 0,
        "total": stripe_invoice.total,
        "currency": stripe_invoice.currency,
        "description": stripe_invoice.description,
        "hosted_invoice_url": stripe_invoice.hosted_invoice_url,
        "invoice_pdf": stripe_invoice.invoice_pdf,
        "updated_at": datetime.now(timezone.utc),
    }

    if stripe_invoice.period_start:
        invoice_data["period_start"] = datetime.fromtimestamp(
            stripe_invoice.period_start, tz=timezone.utc
        )
    if stripe_invoice.period_end:
        invoice_data["period_end"] = datetime.fromtimestamp(
            stripe_invoice.period_end, tz=timezone.utc
        )
    if stripe_invoice.due_date:
        invoice_data["due_date"] = datetime.fromtimestamp(
            stripe_invoice.due_date, tz=timezone.utc
        )
    if stripe_invoice.status == "paid" and stripe_invoice.status_transitions:
        if stripe_invoice.status_transitions.paid_at:
            invoice_data["paid_at"] = datetime.fromtimestamp(
                stripe_invoice.status_transitions.paid_at, tz=timezone.utc
            )

    # Extract line items
    line_items = []
    for item in stripe_invoice.lines.data:
        line_items.append({
            "description": item.description,
            "amount": item.amount,
            "quantity": item.quantity,
        })
    invoice_data["line_items"] = line_items

    if invoice:
        for key, value in invoice_data.items():
            setattr(invoice, key, value)
    else:
        invoice = Invoice(
            subscription_id=subscription_id,
            org_id=org_id,
            **invoice_data,
        )
        db.add(invoice)

    logger.info(
        "invoice_synced",
        org_id=org_id,
        invoice_id=stripe_invoice.id,
        status=stripe_invoice.status,
    )

    return invoice


async def get_invoices(
    db: AsyncSession,
    org_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Invoice], int]:
    """Get invoices for an organization."""
    # Count total
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.org_id == org_id)
    )
    total = count_result.scalar() or 0

    # Get invoices
    result = await db.execute(
        select(Invoice)
        .where(Invoice.org_id == org_id)
        .order_by(Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    invoices = list(result.scalars().all())

    return invoices, total


# =============================================================================
# Payment Method Management
# =============================================================================


async def sync_payment_method(
    db: AsyncSession,
    stripe_pm: stripe.PaymentMethod,
    org_id: str,
    is_default: bool = False,
) -> PaymentMethod:
    """Sync a payment method from Stripe."""
    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.stripe_payment_method_id == stripe_pm.id
        )
    )
    payment_method = result.scalar_one_or_none()

    pm_data = {
        "type": stripe_pm.type,
        "is_default": is_default,
        "is_active": True,
        "updated_at": datetime.now(timezone.utc),
    }

    if stripe_pm.type == "card":
        pm_data.update({
            "card_brand": stripe_pm.card.brand,
            "card_last4": stripe_pm.card.last4,
            "card_exp_month": stripe_pm.card.exp_month,
            "card_exp_year": stripe_pm.card.exp_year,
        })

    if payment_method:
        for key, value in pm_data.items():
            setattr(payment_method, key, value)
    else:
        payment_method = PaymentMethod(
            org_id=org_id,
            stripe_payment_method_id=stripe_pm.id,
            **pm_data,
        )
        db.add(payment_method)

    return payment_method


async def get_payment_methods(
    db: AsyncSession,
    org_id: str,
) -> list[PaymentMethod]:
    """Get payment methods for an organization."""
    result = await db.execute(
        select(PaymentMethod)
        .where(
            PaymentMethod.org_id == org_id,
            PaymentMethod.is_active == True,
        )
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_payment_method(
    db: AsyncSession,
    org_id: str,
    payment_method_id: str,
) -> None:
    """Delete a payment method."""
    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.org_id == org_id,
        )
    )
    payment_method = result.scalar_one_or_none()

    if not payment_method:
        raise ValueError("Payment method not found")

    if payment_method.is_default:
        raise ValueError("Cannot delete default payment method")

    try:
        stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)
        payment_method.is_active = False

    except stripe.StripeError as e:
        logger.error("payment_method_delete_failed", error=str(e))
        raise


# =============================================================================
# Usage & Limits
# =============================================================================


async def check_limit(
    db: AsyncSession,
    org_id: str,
    limit_name: str,
    current_usage: int,
) -> tuple[bool, int]:
    """
    Check if organization is within a limit.

    Args:
        db: Database session
        org_id: Organization ID
        limit_name: Name of the limit to check
        current_usage: Current usage count

    Returns:
        Tuple of (is_within_limit, remaining)
    """
    subscription = await get_subscription(db, org_id)

    if subscription:
        limit = subscription.get_limit(limit_name)
    else:
        # Use free tier limits
        limit = PLAN_LIMITS["free"].get(limit_name, 0)

    # -1 means unlimited
    if limit == -1:
        return True, -1

    remaining = limit - current_usage
    is_within = remaining > 0

    return is_within, remaining


async def record_usage(
    db: AsyncSession,
    org_id: str,
    usage_type: str,
    quantity: int = 1,
    metadata: Optional[dict] = None,
) -> UsageRecord:
    """
    Record usage for billing tracking.

    Args:
        db: Database session
        org_id: Organization ID
        usage_type: Type of usage
        quantity: Usage quantity
        metadata: Additional metadata

    Returns:
        Created usage record
    """
    now = datetime.now(timezone.utc)
    # Period is the current month
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        period_end = period_start.replace(year=now.year + 1, month=1)
    else:
        period_end = period_start.replace(month=now.month + 1)

    usage_record = UsageRecord(
        org_id=org_id,
        usage_type=usage_type,
        quantity=quantity,
        period_start=period_start,
        period_end=period_end,
        metadata=metadata or {},
    )
    db.add(usage_record)

    return usage_record


async def get_usage_summary(
    db: AsyncSession,
    org_id: str,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> dict[str, int]:
    """
    Get usage summary for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        period_start: Start of period (default: start of current month)
        period_end: End of period (default: now)

    Returns:
        Dict mapping usage type to total quantity
    """
    from sqlalchemy import func

    now = datetime.now(timezone.utc)
    if not period_start:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not period_end:
        period_end = now

    result = await db.execute(
        select(
            UsageRecord.usage_type,
            func.sum(UsageRecord.quantity).label("total"),
        )
        .where(
            UsageRecord.org_id == org_id,
            UsageRecord.created_at >= period_start,
            UsageRecord.created_at <= period_end,
        )
        .group_by(UsageRecord.usage_type)
    )

    return {row.usage_type: row.total for row in result.all()}

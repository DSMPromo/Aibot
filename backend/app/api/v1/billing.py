"""
Billing API endpoints.

Provides endpoints for:
- Subscription management
- Checkout and billing portal
- Invoice history
- Payment methods
- Usage tracking
- Stripe webhook handling
"""

from datetime import datetime, timezone
from typing import Optional

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.billing import PLAN_LIMITS
from app.services.billing_service import (
    create_checkout_session,
    create_billing_portal_session,
    get_subscription,
    cancel_subscription,
    reactivate_subscription,
    get_invoices,
    get_payment_methods,
    delete_payment_method,
    check_limit,
    get_usage_summary,
    create_or_update_subscription_from_stripe,
    sync_invoice_from_stripe,
    sync_payment_method,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""

    price_id: str = Field(..., description="Stripe Price ID")
    success_url: str = Field(..., description="Redirect URL on success")
    cancel_url: str = Field(..., description="Redirect URL on cancel")


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    checkout_url: str


class BillingPortalRequest(BaseModel):
    """Request to create a billing portal session."""

    return_url: str = Field(..., description="URL to return to after portal")


class BillingPortalResponse(BaseModel):
    """Billing portal session response."""

    portal_url: str


class SubscriptionResponse(BaseModel):
    """Subscription details response."""

    id: str
    plan_tier: str
    status: str
    billing_cycle: str
    amount: int
    currency: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    trial_end: Optional[datetime]
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]


class PlanLimitsResponse(BaseModel):
    """Plan limits for current subscription."""

    plan_tier: str
    limits: dict


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""

    at_period_end: bool = Field(default=True, description="Cancel at end of period")
    reason: Optional[str] = Field(default=None, description="Cancellation reason")


class InvoiceResponse(BaseModel):
    """Invoice details response."""

    id: str
    invoice_number: Optional[str]
    status: str
    amount_due: int
    amount_paid: int
    total: int
    currency: str
    description: Optional[str]
    hosted_invoice_url: Optional[str]
    invoice_pdf: Optional[str]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    created_at: datetime


class InvoiceListResponse(BaseModel):
    """List of invoices response."""

    invoices: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class PaymentMethodResponse(BaseModel):
    """Payment method details response."""

    id: str
    type: str
    card_brand: Optional[str]
    card_last4: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    is_default: bool


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""

    period_start: datetime
    period_end: datetime
    usage: dict
    limits: dict


# =============================================================================
# Subscription Endpoints
# =============================================================================


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current subscription for the organization.

    Returns subscription details including plan, status, and billing cycle.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    subscription = await get_subscription(db, org_id)

    if not subscription:
        # Return free tier info
        return SubscriptionResponse(
            id="free",
            plan_tier="free",
            status="active",
            billing_cycle="monthly",
            amount=0,
            currency="usd",
            current_period_start=None,
            current_period_end=None,
            trial_end=None,
            cancel_at_period_end=False,
            canceled_at=None,
        )

    return SubscriptionResponse(
        id=subscription.id,
        plan_tier=subscription.plan_tier,
        status=subscription.status,
        billing_cycle=subscription.billing_cycle,
        amount=subscription.amount,
        currency=subscription.currency,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        canceled_at=subscription.canceled_at,
    )


@router.get("/plans", response_model=dict)
async def get_available_plans():
    """
    Get available subscription plans and their limits.

    Returns all plan tiers with their features and limits.
    """
    return {
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "description": "Get started with basic features",
                "price_monthly": 0,
                "price_yearly": 0,
                "limits": PLAN_LIMITS["free"],
            },
            {
                "id": "starter",
                "name": "Starter",
                "description": "For small businesses getting started",
                "price_monthly": 2900,  # $29.00
                "price_yearly": 29000,  # $290.00
                "price_id_monthly": "price_starter_monthly",
                "price_id_yearly": "price_starter_yearly",
                "limits": PLAN_LIMITS["starter"],
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "For growing businesses",
                "price_monthly": 7900,  # $79.00
                "price_yearly": 79000,  # $790.00
                "price_id_monthly": "price_pro_monthly",
                "price_id_yearly": "price_pro_yearly",
                "limits": PLAN_LIMITS["pro"],
            },
            {
                "id": "agency",
                "name": "Agency",
                "description": "For agencies managing multiple clients",
                "price_monthly": 19900,  # $199.00
                "price_yearly": 199000,  # $1990.00
                "price_id_monthly": "price_agency_monthly",
                "price_id_yearly": "price_agency_yearly",
                "limits": PLAN_LIMITS["agency"],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "description": "Custom solutions for large organizations",
                "price_monthly": None,  # Contact sales
                "price_yearly": None,
                "limits": PLAN_LIMITS["enterprise"],
            },
        ]
    }


@router.get("/limits", response_model=PlanLimitsResponse)
async def get_plan_limits(
    db: AsyncSession = Depends(get_db),
):
    """
    Get current plan limits for the organization.

    Returns limits based on the current subscription tier.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    subscription = await get_subscription(db, org_id)

    if subscription:
        plan_tier = subscription.plan_tier
    else:
        plan_tier = "free"

    return PlanLimitsResponse(
        plan_tier=plan_tier,
        limits=PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["free"]),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription.

    Returns a URL to redirect the user to Stripe Checkout.
    """
    # TODO: Get org_id and email from authenticated user
    org_id = "placeholder-org-id"
    email = "user@example.com"

    try:
        checkout_url = await create_checkout_session(
            db=db,
            org_id=org_id,
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=email,
        )

        return CheckoutResponse(checkout_url=checkout_url)

    except Exception as e:
        logger.error("checkout_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/portal", response_model=BillingPortalResponse)
async def create_portal_session(
    request: BillingPortalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Billing Portal session.

    Returns a URL to redirect the user to manage their subscription.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        portal_url = await create_billing_portal_session(
            db=db,
            org_id=org_id,
            return_url=request.return_url,
        )

        return BillingPortalResponse(portal_url=portal_url)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("portal_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session",
        )


@router.post("/cancel")
async def cancel_current_subscription(
    request: CancelSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel the current subscription.

    By default, cancels at the end of the current billing period.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        subscription = await cancel_subscription(
            db=db,
            org_id=org_id,
            at_period_end=request.at_period_end,
            reason=request.reason,
        )

        return {
            "message": "Subscription canceled",
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": subscription.current_period_end,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/reactivate")
async def reactivate_current_subscription(
    db: AsyncSession = Depends(get_db),
):
    """
    Reactivate a canceled subscription.

    Only works if the subscription is scheduled to cancel at period end.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        subscription = await reactivate_subscription(db=db, org_id=org_id)

        return {
            "message": "Subscription reactivated",
            "status": subscription.status,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# Invoice Endpoints
# =============================================================================


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get billing history (invoices).

    Returns a paginated list of invoices.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    invoices, total = await get_invoices(db, org_id, limit=page_size, offset=offset)

    return InvoiceListResponse(
        invoices=[
            InvoiceResponse(
                id=inv.id,
                invoice_number=inv.invoice_number,
                status=inv.status,
                amount_due=inv.amount_due,
                amount_paid=inv.amount_paid,
                total=inv.total,
                currency=inv.currency,
                description=inv.description,
                hosted_invoice_url=inv.hosted_invoice_url,
                invoice_pdf=inv.invoice_pdf,
                period_start=inv.period_start,
                period_end=inv.period_end,
                created_at=inv.created_at,
            )
            for inv in invoices
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Payment Method Endpoints
# =============================================================================


@router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods(
    db: AsyncSession = Depends(get_db),
):
    """
    Get saved payment methods.

    Returns all active payment methods for the organization.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    payment_methods = await get_payment_methods(db, org_id)

    return [
        PaymentMethodResponse(
            id=pm.id,
            type=pm.type,
            card_brand=pm.card_brand,
            card_last4=pm.card_last4,
            card_exp_month=pm.card_exp_month,
            card_exp_year=pm.card_exp_year,
            is_default=pm.is_default,
        )
        for pm in payment_methods
    ]


@router.delete("/payment-methods/{payment_method_id}")
async def remove_payment_method(
    payment_method_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a saved payment method.

    Cannot remove the default payment method.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        await delete_payment_method(db, org_id, payment_method_id)
        return {"message": "Payment method removed"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# Usage Endpoints
# =============================================================================


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    db: AsyncSession = Depends(get_db),
):
    """
    Get current usage summary.

    Returns usage counts and remaining limits for the current billing period.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    usage = await get_usage_summary(db, org_id, period_start=period_start)

    subscription = await get_subscription(db, org_id)
    plan_tier = subscription.plan_tier if subscription else "free"
    limits = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["free"])

    return UsageSummaryResponse(
        period_start=period_start,
        period_end=now,
        usage=usage,
        limits=limits,
    )


@router.get("/usage/check/{limit_name}")
async def check_usage_limit(
    limit_name: str,
    current_usage: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a specific limit has been reached.

    Returns whether the organization is within the limit and remaining count.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    is_within, remaining = await check_limit(db, org_id, limit_name, current_usage)

    return {
        "limit_name": limit_name,
        "is_within_limit": is_within,
        "remaining": remaining,
        "current_usage": current_usage,
    }


# =============================================================================
# Stripe Webhook Handler
# =============================================================================


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    Processes subscription and invoice events to keep local data in sync.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    logger.info("stripe_webhook_received", event_type=event.type)

    try:
        # Handle subscription events
        if event.type == "customer.subscription.created":
            await create_or_update_subscription_from_stripe(db, event.data.object)

        elif event.type == "customer.subscription.updated":
            await create_or_update_subscription_from_stripe(db, event.data.object)

        elif event.type == "customer.subscription.deleted":
            await create_or_update_subscription_from_stripe(db, event.data.object)

        # Handle invoice events
        elif event.type == "invoice.created":
            await sync_invoice_from_stripe(db, event.data.object)

        elif event.type == "invoice.paid":
            await sync_invoice_from_stripe(db, event.data.object)

        elif event.type == "invoice.payment_failed":
            await sync_invoice_from_stripe(db, event.data.object)

        elif event.type == "invoice.finalized":
            await sync_invoice_from_stripe(db, event.data.object)

        # Handle payment method events
        elif event.type == "payment_method.attached":
            pm = event.data.object
            # Find org by customer
            from sqlalchemy import select
            from app.models.user import Organization

            result = await db.execute(
                select(Organization.id).where(
                    Organization.stripe_customer_id == pm.customer
                )
            )
            org_id = result.scalar_one_or_none()
            if org_id:
                await sync_payment_method(db, pm, org_id)

        elif event.type == "checkout.session.completed":
            session = event.data.object
            if session.mode == "subscription":
                # Subscription will be handled by subscription.created event
                logger.info(
                    "checkout_completed",
                    session_id=session.id,
                    subscription_id=session.subscription,
                )

    except Exception as e:
        logger.error(
            "webhook_processing_failed",
            event_type=event.type,
            error=str(e),
        )
        # Don't fail the webhook - Stripe will retry
        # Log for manual investigation

    return {"status": "received"}

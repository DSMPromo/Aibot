"""
AI Usage Service

Manages AI generation usage tracking and quota enforcement.

Features:
- Track AI generations per organization
- Enforce monthly usage limits by plan tier
- Warn at 80% usage, hard stop at 100%
- Usage statistics and cost tracking
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_generation import AIGeneration, AIUsageQuota
from app.services.ai_service import GenerationResult

logger = structlog.get_logger()


# Plan tier limits (generations per month)
PLAN_LIMITS = {
    "free": settings.ai_free_tier_limit,
    "pro": settings.ai_pro_tier_limit,
    "enterprise": settings.ai_enterprise_tier_limit,
}


class UsageStatus:
    """Status of an organization's AI usage."""

    def __init__(
        self,
        generations_used: int,
        generation_limit: int,
        tokens_used: int,
        estimated_cost: Decimal,
        plan_tier: str,
    ):
        self.generations_used = generations_used
        self.generation_limit = generation_limit
        self.tokens_used = tokens_used
        self.estimated_cost = estimated_cost
        self.plan_tier = plan_tier

    @property
    def remaining_generations(self) -> int:
        return max(0, self.generation_limit - self.generations_used)

    @property
    def usage_percentage(self) -> float:
        if self.generation_limit <= 0:
            return 0.0
        return (self.generations_used / self.generation_limit) * 100

    @property
    def is_limit_reached(self) -> bool:
        return self.generations_used >= self.generation_limit

    @property
    def should_warn(self) -> bool:
        """Should show warning (at or above 80%)."""
        return self.usage_percentage >= 80

    def to_dict(self) -> dict:
        return {
            "generations_used": self.generations_used,
            "generation_limit": self.generation_limit,
            "remaining_generations": self.remaining_generations,
            "usage_percentage": round(self.usage_percentage, 1),
            "tokens_used": self.tokens_used,
            "estimated_cost_usd": float(self.estimated_cost),
            "plan_tier": self.plan_tier,
            "is_limit_reached": self.is_limit_reached,
            "should_warn": self.should_warn,
        }


async def get_or_create_quota(
    db: AsyncSession,
    org_id: str,
    plan_tier: str = "free",
) -> AIUsageQuota:
    """
    Get or create the current month's usage quota for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        plan_tier: Plan tier for new quotas

    Returns:
        AIUsageQuota for current month
    """
    now = datetime.now(timezone.utc)

    # Try to find existing quota for this month
    result = await db.execute(
        select(AIUsageQuota).where(
            AIUsageQuota.org_id == org_id,
            AIUsageQuota.period_year == now.year,
            AIUsageQuota.period_month == now.month,
        )
    )
    quota = result.scalar_one_or_none()

    if not quota:
        # Create new quota for this month
        quota = AIUsageQuota(
            org_id=org_id,
            period_year=now.year,
            period_month=now.month,
            plan_tier=plan_tier,
            generation_limit=PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["free"]),
        )
        db.add(quota)
        await db.commit()
        await db.refresh(quota)

        logger.info(
            "ai_quota_created",
            org_id=org_id,
            period=f"{now.year}-{now.month}",
            limit=quota.generation_limit,
        )

    return quota


async def get_usage_status(
    db: AsyncSession,
    org_id: str,
    plan_tier: str = "free",
) -> UsageStatus:
    """
    Get current usage status for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        plan_tier: Current plan tier

    Returns:
        UsageStatus with current usage info
    """
    quota = await get_or_create_quota(db, org_id, plan_tier)

    return UsageStatus(
        generations_used=quota.generations_used,
        generation_limit=quota.generation_limit,
        tokens_used=quota.tokens_used,
        estimated_cost=quota.estimated_cost_usd,
        plan_tier=quota.plan_tier,
    )


async def check_usage_limit(
    db: AsyncSession,
    org_id: str,
    plan_tier: str = "free",
) -> tuple[bool, UsageStatus]:
    """
    Check if an organization can make more AI generations.

    Args:
        db: Database session
        org_id: Organization ID
        plan_tier: Current plan tier

    Returns:
        Tuple of (can_generate, usage_status)
    """
    status = await get_usage_status(db, org_id, plan_tier)
    return not status.is_limit_reached, status


async def record_generation(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    generation_type: str,
    result: GenerationResult,
    campaign_id: Optional[str] = None,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    context: Optional[dict] = None,
) -> AIGeneration:
    """
    Record an AI generation and update usage quota.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User who triggered the generation
        generation_type: Type of generation (ad_copy, headline, etc.)
        result: GenerationResult from AI service
        campaign_id: Associated campaign ID
        input_summary: Summary of input (for debugging)
        output_summary: Summary of output (for debugging)
        context: Additional context

    Returns:
        Created AIGeneration record
    """
    # Create generation record
    generation = AIGeneration(
        org_id=org_id,
        user_id=user_id,
        generation_type=generation_type,
        model=result.model,
        provider=result.provider,
        fallback_used=result.fallback_used,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=Decimal(str(result.estimated_cost)),
        generation_time_ms=result.generation_time_ms,
        input_summary=input_summary[:500] if input_summary else None,
        output_summary=output_summary[:500] if output_summary else None,
        campaign_id=campaign_id,
        context=context,
        status="success",
    )

    db.add(generation)

    # Update quota
    quota = await get_or_create_quota(db, org_id)
    quota.generations_used += 1
    quota.tokens_used += result.total_tokens
    quota.estimated_cost_usd += Decimal(str(result.estimated_cost))

    # Check if limit reached
    if quota.is_limit_reached and not quota.limit_reached_at:
        quota.limit_reached_at = datetime.now(timezone.utc)
        logger.warning(
            "ai_usage_limit_reached",
            org_id=org_id,
            generations_used=quota.generations_used,
            limit=quota.generation_limit,
        )

    await db.commit()
    await db.refresh(generation)

    logger.info(
        "ai_generation_recorded",
        org_id=org_id,
        generation_id=generation.id,
        type=generation_type,
        tokens=result.total_tokens,
        cost=float(result.estimated_cost),
    )

    return generation


async def record_generation_error(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    generation_type: str,
    error_message: str,
    model: str = "unknown",
    provider: str = "unknown",
    campaign_id: Optional[str] = None,
) -> AIGeneration:
    """
    Record a failed AI generation.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User who triggered the generation
        generation_type: Type of generation
        error_message: Error message
        model: Model that was used
        provider: Provider that was used
        campaign_id: Associated campaign ID

    Returns:
        Created AIGeneration record (with error status)
    """
    generation = AIGeneration(
        org_id=org_id,
        user_id=user_id,
        generation_type=generation_type,
        model=model,
        provider=provider,
        status="error",
        error_message=error_message,
        campaign_id=campaign_id,
    )

    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    logger.warning(
        "ai_generation_error_recorded",
        org_id=org_id,
        generation_id=generation.id,
        type=generation_type,
        error=error_message,
    )

    return generation


async def get_usage_history(
    db: AsyncSession,
    org_id: str,
    limit: int = 50,
) -> list[AIGeneration]:
    """
    Get recent AI generations for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        limit: Max number of records

    Returns:
        List of recent AIGeneration records
    """
    result = await db.execute(
        select(AIGeneration)
        .where(AIGeneration.org_id == org_id)
        .order_by(AIGeneration.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_usage_stats(
    db: AsyncSession,
    org_id: str,
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
) -> dict:
    """
    Get usage statistics for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        period_year: Year to get stats for (defaults to current)
        period_month: Month to get stats for (defaults to current)

    Returns:
        Dictionary with usage statistics
    """
    now = datetime.now(timezone.utc)
    year = period_year or now.year
    month = period_month or now.month

    # Get quota for the period
    result = await db.execute(
        select(AIUsageQuota).where(
            AIUsageQuota.org_id == org_id,
            AIUsageQuota.period_year == year,
            AIUsageQuota.period_month == month,
        )
    )
    quota = result.scalar_one_or_none()

    if not quota:
        return {
            "period": f"{year}-{month:02d}",
            "generations_used": 0,
            "generation_limit": PLAN_LIMITS.get("free", 50),
            "tokens_used": 0,
            "estimated_cost_usd": 0.0,
            "by_type": {},
            "by_model": {},
        }

    # Get breakdown by type
    type_result = await db.execute(
        select(
            AIGeneration.generation_type,
            func.count(AIGeneration.id).label("count"),
            func.sum(AIGeneration.total_tokens).label("tokens"),
        )
        .where(
            AIGeneration.org_id == org_id,
            func.extract("year", AIGeneration.created_at) == year,
            func.extract("month", AIGeneration.created_at) == month,
            AIGeneration.status == "success",
        )
        .group_by(AIGeneration.generation_type)
    )
    by_type = {row.generation_type: {"count": row.count, "tokens": row.tokens or 0} for row in type_result}

    # Get breakdown by model
    model_result = await db.execute(
        select(
            AIGeneration.model,
            func.count(AIGeneration.id).label("count"),
            func.sum(AIGeneration.estimated_cost_usd).label("cost"),
        )
        .where(
            AIGeneration.org_id == org_id,
            func.extract("year", AIGeneration.created_at) == year,
            func.extract("month", AIGeneration.created_at) == month,
            AIGeneration.status == "success",
        )
        .group_by(AIGeneration.model)
    )
    by_model = {row.model: {"count": row.count, "cost": float(row.cost or 0)} for row in model_result}

    return {
        "period": f"{year}-{month:02d}",
        "generations_used": quota.generations_used,
        "generation_limit": quota.generation_limit,
        "remaining_generations": quota.remaining_generations,
        "usage_percentage": round(quota.usage_percentage, 1),
        "tokens_used": quota.tokens_used,
        "estimated_cost_usd": float(quota.estimated_cost_usd),
        "plan_tier": quota.plan_tier,
        "limit_reached": quota.is_limit_reached,
        "limit_reached_at": quota.limit_reached_at.isoformat() if quota.limit_reached_at else None,
        "by_type": by_type,
        "by_model": by_model,
    }

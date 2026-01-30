"""
AI Generation API endpoints.

Implements:
- Ad copy generation (AI-001 to AI-012)
- Usage tracking and limits (AI-020 to AI-027)
- Human-in-the-loop enforcement (AI-013 to AI-019)
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.security import limiter
from app.services import (
    AIServiceError,
    AIRateLimitError,
    get_usage_status,
    get_usage_stats,
    generate_headlines,
    generate_descriptions,
    generate_ctas,
    generate_full_ad_copy,
    PLATFORM_LIMITS,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class HeadlineGenerationRequest(BaseModel):
    """Request to generate headline variations."""
    product: str = Field(min_length=10, max_length=500, description="Product/service description")
    audience: str = Field(min_length=5, max_length=300, description="Target audience")
    benefits: str = Field(min_length=10, max_length=500, description="Key benefits")
    objective: str = Field(pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")
    platform: str = Field(default="google", pattern="^(google|meta|tiktok)$")
    num_variations: int = Field(default=5, ge=3, le=10)
    additional_context: Optional[str] = Field(default="", max_length=500)
    campaign_id: Optional[str] = None


class DescriptionGenerationRequest(BaseModel):
    """Request to generate description variations."""
    product: str = Field(min_length=10, max_length=500)
    audience: str = Field(min_length=5, max_length=300)
    benefits: str = Field(min_length=10, max_length=500)
    headline: str = Field(min_length=5, max_length=100, description="The headline to complement")
    platform: str = Field(default="google", pattern="^(google|meta|tiktok)$")
    num_variations: int = Field(default=3, ge=2, le=5)
    additional_context: Optional[str] = Field(default="", max_length=500)
    campaign_id: Optional[str] = None


class CTAGenerationRequest(BaseModel):
    """Request to generate CTA suggestions."""
    product: str = Field(min_length=10, max_length=500)
    objective: str = Field(pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")
    headline: str = Field(min_length=5, max_length=100)
    num_suggestions: int = Field(default=5, ge=3, le=8)
    additional_context: Optional[str] = Field(default="", max_length=500)
    campaign_id: Optional[str] = None


class FullAdCopyGenerationRequest(BaseModel):
    """Request to generate complete ad copy variations."""
    product: str = Field(min_length=10, max_length=500)
    audience: str = Field(min_length=5, max_length=300)
    benefits: str = Field(min_length=10, max_length=500)
    objective: str = Field(pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")
    url: str = Field(min_length=10, max_length=2048, description="Landing page URL")
    platform: str = Field(default="google", pattern="^(google|meta|tiktok)$")
    num_variations: int = Field(default=3, ge=2, le=5)
    additional_context: Optional[str] = Field(default="", max_length=500)
    campaign_id: Optional[str] = None


class UsageLimitsResponse(BaseModel):
    """Response with current usage limits."""
    generations_used: int
    generation_limit: int
    remaining_generations: int
    usage_percentage: float
    tokens_used: int
    estimated_cost_usd: float
    plan_tier: str
    is_limit_reached: bool
    should_warn: bool


class GenerationMetadata(BaseModel):
    """Metadata about a generation."""
    model: str
    provider: str
    tokens_used: int
    estimated_cost: float
    generation_time_ms: int
    fallback_used: bool


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/limits", response_model=UsageLimitsResponse)
async def get_usage_limits(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current AI usage limits and status.

    Returns usage statistics including:
    - Current generation count vs limit
    - Whether warning threshold (80%) is reached
    - Whether hard limit is reached
    """
    # TODO: Get current user's org_id and plan_tier
    org_id = "00000000-0000-0000-0000-000000000001"
    plan_tier = "free"

    status = await get_usage_status(db, org_id, plan_tier)

    return UsageLimitsResponse(
        generations_used=status.generations_used,
        generation_limit=status.generation_limit,
        remaining_generations=status.remaining_generations,
        usage_percentage=round(status.usage_percentage, 1),
        tokens_used=status.tokens_used,
        estimated_cost_usd=float(status.estimated_cost),
        plan_tier=status.plan_tier,
        is_limit_reached=status.is_limit_reached,
        should_warn=status.should_warn,
    )


@router.get("/usage")
async def get_usage_statistics(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed AI usage statistics.

    Returns breakdown by generation type and model.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    stats = await get_usage_stats(db, org_id, year, month)

    return stats


@router.get("/platform-limits")
async def get_platform_character_limits():
    """
    Get character limits for each ad platform.

    Useful for client-side validation before generation.
    """
    return {
        "platforms": PLATFORM_LIMITS,
    }


@router.post("/generate-headlines")
@limiter.limit("10/minute")
async def generate_headline_variations(
    request: Request,
    data: HeadlineGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate headline variations for an ad.

    Returns multiple headline options with different angles.
    All outputs are labeled as AI-assisted.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    try:
        response, result = await generate_headlines(
            db=db,
            org_id=org_id,
            user_id=user_id,
            product=data.product,
            audience=data.audience,
            benefits=data.benefits,
            objective=data.objective,
            platform=data.platform,
            num_variations=data.num_variations,
            additional_context=data.additional_context or "",
            campaign_id=data.campaign_id,
        )

        return {
            "variations": [v.model_dump() for v in response.variations],
            "ai_assisted": True,
            "metadata": GenerationMetadata(
                model=result.model,
                provider=result.provider,
                tokens_used=result.total_tokens,
                estimated_cost=result.estimated_cost,
                generation_time_ms=result.generation_time_ms,
                fallback_used=result.fallback_used,
            ).model_dump(),
            "platform_limits": PLATFORM_LIMITS.get(data.platform, PLATFORM_LIMITS["google"]),
        }

    except ValueError as e:
        # Usage limit error
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except AIRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI provider rate limit exceeded. Please try again in {e.retry_after} seconds.",
        )
    except AIServiceError as e:
        logger.error("headline_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again.",
        )


@router.post("/generate-descriptions")
@limiter.limit("10/minute")
async def generate_description_variations(
    request: Request,
    data: DescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate description variations for an ad.

    Returns descriptions that complement the provided headline.
    All outputs are labeled as AI-assisted.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    try:
        response, result = await generate_descriptions(
            db=db,
            org_id=org_id,
            user_id=user_id,
            product=data.product,
            audience=data.audience,
            benefits=data.benefits,
            headline=data.headline,
            platform=data.platform,
            num_variations=data.num_variations,
            additional_context=data.additional_context or "",
            campaign_id=data.campaign_id,
        )

        return {
            "variations": [v.model_dump() for v in response.variations],
            "ai_assisted": True,
            "metadata": GenerationMetadata(
                model=result.model,
                provider=result.provider,
                tokens_used=result.total_tokens,
                estimated_cost=result.estimated_cost,
                generation_time_ms=result.generation_time_ms,
                fallback_used=result.fallback_used,
            ).model_dump(),
            "platform_limits": PLATFORM_LIMITS.get(data.platform, PLATFORM_LIMITS["google"]),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except AIRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI provider rate limit exceeded. Please try again in {e.retry_after} seconds.",
        )
    except AIServiceError as e:
        logger.error("description_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again.",
        )


@router.post("/generate-ctas")
@limiter.limit("10/minute")
async def generate_cta_suggestions(
    request: Request,
    data: CTAGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate CTA (call-to-action) suggestions.

    Returns various CTA options appropriate for the objective.
    All outputs are labeled as AI-assisted.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    try:
        response, result = await generate_ctas(
            db=db,
            org_id=org_id,
            user_id=user_id,
            product=data.product,
            objective=data.objective,
            headline=data.headline,
            num_suggestions=data.num_suggestions,
            additional_context=data.additional_context or "",
            campaign_id=data.campaign_id,
        )

        return {
            "suggestions": [s.model_dump() for s in response.suggestions],
            "ai_assisted": True,
            "metadata": GenerationMetadata(
                model=result.model,
                provider=result.provider,
                tokens_used=result.total_tokens,
                estimated_cost=result.estimated_cost,
                generation_time_ms=result.generation_time_ms,
                fallback_used=result.fallback_used,
            ).model_dump(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except AIRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI provider rate limit exceeded. Please try again in {e.retry_after} seconds.",
        )
    except AIServiceError as e:
        logger.error("cta_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again.",
        )


@router.post("/generate-ad-copy")
@limiter.limit("5/minute")
async def generate_full_ad_copy_variations(
    request: Request,
    data: FullAdCopyGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate complete ad copy variations.

    Returns full ad copies with headlines, descriptions, and CTAs.
    Each variation is optimized for A/B testing.
    All outputs are labeled as AI-assisted.

    Note: This is a more expensive operation that generates complete ad copies.
    Rate limited to 5 per minute.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    try:
        response, result = await generate_full_ad_copy(
            db=db,
            org_id=org_id,
            user_id=user_id,
            product=data.product,
            audience=data.audience,
            benefits=data.benefits,
            objective=data.objective,
            url=data.url,
            platform=data.platform,
            num_variations=data.num_variations,
            additional_context=data.additional_context or "",
            campaign_id=data.campaign_id,
        )

        return {
            "variations": [v.model_dump() for v in response.variations],
            "ai_assisted": True,
            "metadata": GenerationMetadata(
                model=result.model,
                provider=result.provider,
                tokens_used=result.total_tokens,
                estimated_cost=result.estimated_cost,
                generation_time_ms=result.generation_time_ms,
                fallback_used=result.fallback_used,
            ).model_dump(),
            "platform_limits": PLATFORM_LIMITS.get(data.platform, PLATFORM_LIMITS["google"]),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except AIRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI provider rate limit exceeded. Please try again in {e.retry_after} seconds.",
        )
    except AIServiceError as e:
        logger.error("ad_copy_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again.",
        )

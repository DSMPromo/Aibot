"""
Ad Copy Generation Service

AI-powered ad copy generation with platform-specific formatting.

Features:
- Generate headlines (multiple variations)
- Generate descriptions
- Generate CTAs
- Enforce character limits per platform
- Label all outputs as AI-assisted
"""

from typing import Optional

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import ai_service, GenerationResult
from app.services.ai_usage_service import (
    check_usage_limit,
    record_generation,
    record_generation_error,
)

logger = structlog.get_logger()


# =============================================================================
# Platform Character Limits
# =============================================================================

PLATFORM_LIMITS = {
    "google": {
        "headline": 30,
        "description": 90,
        "path": 15,
        "cta_max": 25,
    },
    "meta": {
        "headline": 40,
        "description": 125,
        "primary_text": 500,
        "cta_max": 30,
    },
    "tiktok": {
        "headline": 100,
        "description": 100,
        "cta_max": 20,
    },
}


# =============================================================================
# Pydantic Models for Structured Outputs
# =============================================================================

class HeadlineVariation(BaseModel):
    """A single headline variation."""
    headline: str = Field(description="The headline text")
    character_count: int = Field(description="Number of characters")
    focus: str = Field(description="What this headline focuses on (e.g., 'benefit', 'urgency', 'value')")


class HeadlineGenerationResponse(BaseModel):
    """Response from headline generation."""
    variations: list[HeadlineVariation] = Field(
        description="List of headline variations",
        min_length=3,
        max_length=10,
    )
    ai_assisted: bool = Field(default=True, description="Indicates content is AI-generated")


class DescriptionVariation(BaseModel):
    """A single description variation."""
    description: str = Field(description="The description text")
    character_count: int = Field(description="Number of characters")
    style: str = Field(description="Style of this description (e.g., 'informative', 'persuasive', 'emotional')")


class DescriptionGenerationResponse(BaseModel):
    """Response from description generation."""
    variations: list[DescriptionVariation] = Field(
        description="List of description variations",
        min_length=2,
        max_length=5,
    )
    ai_assisted: bool = Field(default=True, description="Indicates content is AI-generated")


class CTASuggestion(BaseModel):
    """A CTA suggestion."""
    cta: str = Field(description="The call-to-action text")
    type: str = Field(description="Type of CTA (e.g., 'action', 'learn', 'shop', 'signup')")


class CTAGenerationResponse(BaseModel):
    """Response from CTA generation."""
    suggestions: list[CTASuggestion] = Field(
        description="List of CTA suggestions",
        min_length=3,
        max_length=8,
    )
    ai_assisted: bool = Field(default=True, description="Indicates content is AI-generated")


class FullAdCopyVariation(BaseModel):
    """A complete ad copy variation with all elements."""
    headline_1: str = Field(description="Primary headline")
    headline_2: Optional[str] = Field(default=None, description="Secondary headline")
    headline_3: Optional[str] = Field(default=None, description="Tertiary headline")
    description_1: str = Field(description="Primary description")
    description_2: Optional[str] = Field(default=None, description="Secondary description")
    cta: str = Field(description="Call to action")
    variation_name: str = Field(description="Name for this variation (e.g., 'Benefit-focused', 'Urgency')")


class FullAdCopyGenerationResponse(BaseModel):
    """Response from full ad copy generation."""
    variations: list[FullAdCopyVariation] = Field(
        description="List of complete ad copy variations",
        min_length=2,
        max_length=5,
    )
    ai_assisted: bool = Field(default=True, description="Indicates content is AI-generated")


# =============================================================================
# Prompt Templates
# =============================================================================

HEADLINE_SYSTEM_PROMPT = """You are an expert advertising copywriter specializing in digital ads.
Your task is to generate compelling headlines that drive clicks and conversions.

Guidelines:
- Be concise and impactful
- Use action words when appropriate
- Highlight benefits and unique value propositions
- Create urgency without being pushy
- Make each variation distinct with a different angle

Platform: {platform}
Character limit: {char_limit} characters per headline
"""

HEADLINE_USER_PROMPT = """Generate {num_variations} headline variations for the following ad:

Product/Service: {product}
Target Audience: {audience}
Key Benefits: {benefits}
Objective: {objective}
{additional_context}

Each headline must be under {char_limit} characters. Provide diverse angles including benefit-focused, urgency, and value propositions."""

DESCRIPTION_SYSTEM_PROMPT = """You are an expert advertising copywriter specializing in digital ads.
Your task is to generate compelling descriptions that expand on the headline and drive action.

Guidelines:
- Support and expand on the headline's message
- Include a clear value proposition
- Use persuasive language without being overly salesy
- Include relevant keywords naturally
- End with a subtle call to action

Platform: {platform}
Character limit: {char_limit} characters per description
"""

DESCRIPTION_USER_PROMPT = """Generate {num_variations} description variations for the following ad:

Product/Service: {product}
Target Audience: {audience}
Key Benefits: {benefits}
Headline Being Used: {headline}
{additional_context}

Each description must be under {char_limit} characters. Provide diverse styles including informative, persuasive, and emotional approaches."""

CTA_SYSTEM_PROMPT = """You are an expert advertising copywriter specializing in call-to-actions.
Your task is to generate compelling CTAs that drive clicks and conversions.

Guidelines:
- Be action-oriented
- Create urgency without being pushy
- Match the tone of the ad
- Keep it short and clear
"""

CTA_USER_PROMPT = """Generate {num_suggestions} CTA suggestions for the following ad:

Product/Service: {product}
Objective: {objective}
Headline: {headline}
{additional_context}

Include a mix of action-oriented, learning-focused, and shop/signup CTAs as appropriate."""

FULL_AD_COPY_SYSTEM_PROMPT = """You are an expert advertising copywriter specializing in {platform} ads.
Your task is to generate complete ad copy variations that work together cohesively.

Platform requirements:
- Headline character limit: {headline_limit}
- Description character limit: {description_limit}

Guidelines:
- Create cohesive ad copy where headlines and descriptions work together
- Each variation should take a different angle or approach
- Include a clear call to action
- Make each variation distinct and testable for A/B testing
"""

FULL_AD_COPY_USER_PROMPT = """Generate {num_variations} complete ad copy variations for:

Product/Service: {product}
Target Audience: {audience}
Key Benefits: {benefits}
Objective: {objective}
Landing Page URL: {url}
{additional_context}

Create distinct variations suitable for A/B testing. Each should have a unique angle such as:
- Benefit-focused
- Problem-solution
- Social proof/trust
- Urgency/scarcity
- Emotional appeal"""


# =============================================================================
# Generation Functions
# =============================================================================

async def generate_headlines(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    product: str,
    audience: str,
    benefits: str,
    objective: str,
    platform: str = "google",
    num_variations: int = 5,
    additional_context: str = "",
    campaign_id: Optional[str] = None,
) -> tuple[HeadlineGenerationResponse, GenerationResult]:
    """
    Generate headline variations for an ad.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID
        product: Product/service description
        audience: Target audience
        benefits: Key benefits
        objective: Campaign objective
        platform: Ad platform (google, meta, tiktok)
        num_variations: Number of variations to generate
        additional_context: Additional context for generation
        campaign_id: Optional associated campaign

    Returns:
        Tuple of (HeadlineGenerationResponse, GenerationResult)
    """
    # Check usage limit
    can_generate, usage_status = await check_usage_limit(db, org_id)
    if not can_generate:
        raise ValueError(f"AI generation limit reached. Used {usage_status.generations_used}/{usage_status.generation_limit} this month.")

    char_limit = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["google"])["headline"]

    system_prompt = HEADLINE_SYSTEM_PROMPT.format(
        platform=platform.title(),
        char_limit=char_limit,
    )

    user_prompt = HEADLINE_USER_PROMPT.format(
        num_variations=num_variations,
        product=product,
        audience=audience,
        benefits=benefits,
        objective=objective,
        char_limit=char_limit,
        additional_context=f"Additional context: {additional_context}" if additional_context else "",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response, result = await ai_service.generate_structured(
            messages=messages,
            response_model=HeadlineGenerationResponse,
            temperature=0.8,  # Higher creativity for headlines
        )

        # Record the generation
        await record_generation(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="headline",
            result=result,
            campaign_id=campaign_id,
            input_summary=f"Product: {product[:100]}",
            output_summary=f"Generated {len(response.variations)} headline variations",
        )

        return response, result

    except Exception as e:
        await record_generation_error(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="headline",
            error_message=str(e),
            campaign_id=campaign_id,
        )
        raise


async def generate_descriptions(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    product: str,
    audience: str,
    benefits: str,
    headline: str,
    platform: str = "google",
    num_variations: int = 3,
    additional_context: str = "",
    campaign_id: Optional[str] = None,
) -> tuple[DescriptionGenerationResponse, GenerationResult]:
    """
    Generate description variations for an ad.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID
        product: Product/service description
        audience: Target audience
        benefits: Key benefits
        headline: The headline being used
        platform: Ad platform
        num_variations: Number of variations
        additional_context: Additional context
        campaign_id: Optional associated campaign

    Returns:
        Tuple of (DescriptionGenerationResponse, GenerationResult)
    """
    can_generate, usage_status = await check_usage_limit(db, org_id)
    if not can_generate:
        raise ValueError(f"AI generation limit reached. Used {usage_status.generations_used}/{usage_status.generation_limit} this month.")

    char_limit = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["google"])["description"]

    system_prompt = DESCRIPTION_SYSTEM_PROMPT.format(
        platform=platform.title(),
        char_limit=char_limit,
    )

    user_prompt = DESCRIPTION_USER_PROMPT.format(
        num_variations=num_variations,
        product=product,
        audience=audience,
        benefits=benefits,
        headline=headline,
        char_limit=char_limit,
        additional_context=f"Additional context: {additional_context}" if additional_context else "",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response, result = await ai_service.generate_structured(
            messages=messages,
            response_model=DescriptionGenerationResponse,
            temperature=0.7,
        )

        await record_generation(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="description",
            result=result,
            campaign_id=campaign_id,
            input_summary=f"Product: {product[:100]}, Headline: {headline[:50]}",
            output_summary=f"Generated {len(response.variations)} description variations",
        )

        return response, result

    except Exception as e:
        await record_generation_error(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="description",
            error_message=str(e),
            campaign_id=campaign_id,
        )
        raise


async def generate_ctas(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    product: str,
    objective: str,
    headline: str,
    num_suggestions: int = 5,
    additional_context: str = "",
    campaign_id: Optional[str] = None,
) -> tuple[CTAGenerationResponse, GenerationResult]:
    """
    Generate CTA suggestions for an ad.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID
        product: Product/service description
        objective: Campaign objective
        headline: The headline being used
        num_suggestions: Number of suggestions
        additional_context: Additional context
        campaign_id: Optional associated campaign

    Returns:
        Tuple of (CTAGenerationResponse, GenerationResult)
    """
    can_generate, usage_status = await check_usage_limit(db, org_id)
    if not can_generate:
        raise ValueError(f"AI generation limit reached. Used {usage_status.generations_used}/{usage_status.generation_limit} this month.")

    user_prompt = CTA_USER_PROMPT.format(
        num_suggestions=num_suggestions,
        product=product,
        objective=objective,
        headline=headline,
        additional_context=f"Additional context: {additional_context}" if additional_context else "",
    )

    messages = [
        {"role": "system", "content": CTA_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response, result = await ai_service.generate_structured(
            messages=messages,
            response_model=CTAGenerationResponse,
            temperature=0.6,
        )

        await record_generation(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="cta",
            result=result,
            campaign_id=campaign_id,
            input_summary=f"Product: {product[:100]}",
            output_summary=f"Generated {len(response.suggestions)} CTA suggestions",
        )

        return response, result

    except Exception as e:
        await record_generation_error(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="cta",
            error_message=str(e),
            campaign_id=campaign_id,
        )
        raise


async def generate_full_ad_copy(
    db: AsyncSession,
    org_id: str,
    user_id: Optional[str],
    product: str,
    audience: str,
    benefits: str,
    objective: str,
    url: str,
    platform: str = "google",
    num_variations: int = 3,
    additional_context: str = "",
    campaign_id: Optional[str] = None,
) -> tuple[FullAdCopyGenerationResponse, GenerationResult]:
    """
    Generate complete ad copy variations with headlines, descriptions, and CTAs.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID
        product: Product/service description
        audience: Target audience
        benefits: Key benefits
        objective: Campaign objective
        url: Landing page URL
        platform: Ad platform
        num_variations: Number of complete variations
        additional_context: Additional context
        campaign_id: Optional associated campaign

    Returns:
        Tuple of (FullAdCopyGenerationResponse, GenerationResult)
    """
    can_generate, usage_status = await check_usage_limit(db, org_id)
    if not can_generate:
        raise ValueError(f"AI generation limit reached. Used {usage_status.generations_used}/{usage_status.generation_limit} this month.")

    limits = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["google"])

    system_prompt = FULL_AD_COPY_SYSTEM_PROMPT.format(
        platform=platform.title(),
        headline_limit=limits["headline"],
        description_limit=limits["description"],
    )

    user_prompt = FULL_AD_COPY_USER_PROMPT.format(
        num_variations=num_variations,
        product=product,
        audience=audience,
        benefits=benefits,
        objective=objective,
        url=url,
        additional_context=f"Additional context: {additional_context}" if additional_context else "",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response, result = await ai_service.generate_structured(
            messages=messages,
            response_model=FullAdCopyGenerationResponse,
            temperature=0.8,
            max_tokens=2048,  # Full ad copy needs more tokens
        )

        await record_generation(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="ad_copy",
            result=result,
            campaign_id=campaign_id,
            input_summary=f"Product: {product[:100]}, Platform: {platform}",
            output_summary=f"Generated {len(response.variations)} full ad copy variations",
        )

        return response, result

    except Exception as e:
        await record_generation_error(
            db=db,
            org_id=org_id,
            user_id=user_id,
            generation_type="ad_copy",
            error_message=str(e),
            campaign_id=campaign_id,
        )
        raise

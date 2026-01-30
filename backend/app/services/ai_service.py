"""
AI Service

Provides AI-powered functionality using litellm with multi-provider support.
Includes fallback from OpenAI to Anthropic for reliability.

Features:
- Multi-provider LLM access (OpenAI, Anthropic)
- Automatic fallback on provider failure
- Structured outputs using instructor
- Usage and cost tracking
- Retry logic with exponential backoff
"""

import os
from datetime import datetime, timezone
from typing import Any, Optional, Type, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel

from app.config import settings

logger = structlog.get_logger()

# Type variable for structured outputs
T = TypeVar("T", bound=BaseModel)

# Configure litellm
litellm.set_verbose = settings.debug
litellm.drop_params = True  # Drop unsupported params gracefully

# Set API keys in environment for litellm
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.anthropic_api_key:
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key


class AIServiceError(Exception):
    """Base exception for AI service errors."""

    def __init__(self, message: str, provider: Optional[str] = None, details: dict = None):
        self.message = message
        self.provider = provider
        self.details = details or {}
        super().__init__(message)


class AIRateLimitError(AIServiceError):
    """Rate limit exceeded error."""

    def __init__(self, message: str, provider: str, retry_after: Optional[int] = None):
        super().__init__(message, provider, {"retry_after": retry_after})
        self.retry_after = retry_after


class AIUsageLimitError(AIServiceError):
    """Organization usage limit exceeded."""
    pass


class AIProviderError(AIServiceError):
    """Provider-specific error."""
    pass


class GenerationResult(BaseModel):
    """Result of an AI generation."""

    content: Any  # The generated content (can be structured)
    model: str  # Model used for generation
    provider: str  # Provider used (openai, anthropic)
    prompt_tokens: int  # Tokens in the prompt
    completion_tokens: int  # Tokens in the completion
    total_tokens: int  # Total tokens used
    estimated_cost: float  # Estimated cost in USD
    generation_time_ms: int  # Time taken for generation
    fallback_used: bool = False  # Whether fallback was used


# Pricing per 1M tokens (approximate, update as needed)
MODEL_PRICING = {
    # OpenAI models
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Anthropic models
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Estimate the cost of a generation.

    Args:
        model: Model used
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model, {"input": 1.00, "output": 2.00})
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def get_provider_from_model(model: str) -> str:
    """Determine provider from model name."""
    if model.startswith("gpt-") or model.startswith("o1"):
        return "openai"
    elif model.startswith("claude-"):
        return "anthropic"
    return "unknown"


class AIService:
    """
    AI Service for generating content using LLMs.

    Provides structured output generation with automatic fallback
    and usage tracking.
    """

    def __init__(self):
        self.default_model = settings.ai_default_model
        self.fallback_model = settings.ai_fallback_model
        self.max_tokens = settings.ai_max_tokens
        self.temperature = settings.ai_temperature
        self.timeout = settings.ai_timeout_seconds
        self.max_retries = settings.ai_max_retries

        # Create instructor client for structured outputs
        self._setup_instructor()

    def _setup_instructor(self):
        """Set up instructor for structured outputs."""
        # instructor patches litellm for structured outputs
        self.client = instructor.from_litellm(litellm.completion)

    async def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_fallback: bool = True,
    ) -> GenerationResult:
        """
        Generate a completion using the AI model.

        Args:
            messages: List of message dicts (role, content)
            model: Model to use (defaults to configured default)
            max_tokens: Max tokens for response
            temperature: Temperature for randomness
            use_fallback: Whether to try fallback on failure

        Returns:
            GenerationResult with content and metadata
        """
        model = model or self.default_model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        start_time = datetime.now(timezone.utc)
        fallback_used = False

        try:
            response = await self._call_llm(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            if use_fallback and self.fallback_model and model != self.fallback_model:
                logger.warning(
                    "ai_primary_failed_using_fallback",
                    primary_model=model,
                    fallback_model=self.fallback_model,
                    error=str(e),
                )
                try:
                    response = await self._call_llm(
                        messages=messages,
                        model=self.fallback_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    fallback_used = True
                    model = self.fallback_model
                except Exception as fallback_error:
                    logger.error(
                        "ai_fallback_also_failed",
                        error=str(fallback_error),
                    )
                    raise AIProviderError(
                        message="Both primary and fallback AI providers failed",
                        provider="both",
                        details={
                            "primary_error": str(e),
                            "fallback_error": str(fallback_error),
                        },
                    )
            else:
                raise self._handle_error(e, model)

        end_time = datetime.now(timezone.utc)
        generation_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Extract usage info
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        content = response.choices[0].message.content

        return GenerationResult(
            content=content,
            model=model,
            provider=get_provider_from_model(model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimate_cost(model, prompt_tokens, completion_tokens),
            generation_time_ms=generation_time_ms,
            fallback_used=fallback_used,
        )

    async def generate_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_fallback: bool = True,
    ) -> tuple[T, GenerationResult]:
        """
        Generate a structured output using the AI model.

        Uses instructor to ensure the response matches the Pydantic model.

        Args:
            messages: List of message dicts (role, content)
            response_model: Pydantic model for the response
            model: Model to use
            max_tokens: Max tokens for response
            temperature: Temperature for randomness
            use_fallback: Whether to try fallback on failure

        Returns:
            Tuple of (structured response, GenerationResult metadata)
        """
        model = model or self.default_model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        start_time = datetime.now(timezone.utc)
        fallback_used = False

        try:
            response, completion = await self._call_instructor(
                messages=messages,
                response_model=response_model,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            if use_fallback and self.fallback_model and model != self.fallback_model:
                logger.warning(
                    "ai_primary_failed_using_fallback",
                    primary_model=model,
                    fallback_model=self.fallback_model,
                    error=str(e),
                )
                try:
                    response, completion = await self._call_instructor(
                        messages=messages,
                        response_model=response_model,
                        model=self.fallback_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    fallback_used = True
                    model = self.fallback_model
                except Exception as fallback_error:
                    logger.error(
                        "ai_fallback_also_failed",
                        error=str(fallback_error),
                    )
                    raise AIProviderError(
                        message="Both primary and fallback AI providers failed",
                        provider="both",
                        details={
                            "primary_error": str(e),
                            "fallback_error": str(fallback_error),
                        },
                    )
            else:
                raise self._handle_error(e, model)

        end_time = datetime.now(timezone.utc)
        generation_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Extract usage info
        usage = completion.usage if hasattr(completion, "usage") else None
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        result = GenerationResult(
            content=response.model_dump(),
            model=model,
            provider=get_provider_from_model(model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimate_cost(model, prompt_tokens, completion_tokens),
            generation_time_ms=generation_time_ms,
            fallback_used=fallback_used,
        )

        return response, result

    async def _call_llm(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
    ):
        """Make a direct LLM call using litellm."""
        return await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self.timeout,
        )

    async def _call_instructor(
        self,
        messages: list[dict],
        response_model: Type[T],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[T, Any]:
        """Make a structured LLM call using instructor."""
        # instructor's from_litellm returns a sync client, so we use it directly
        # For async, we need to use litellm.acompletion with instructor patching
        import instructor
        from litellm import acompletion

        # Create async instructor client
        client = instructor.from_litellm(acompletion)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self.timeout,
        )

        # instructor returns the parsed model directly
        # We need to get the raw completion for usage info
        # In newer versions, we can access _raw_response
        raw_response = getattr(response, "_raw_response", None)

        return response, raw_response

    def _handle_error(self, error: Exception, model: str) -> AIServiceError:
        """Convert provider errors to AIServiceError."""
        provider = get_provider_from_model(model)
        error_str = str(error).lower()

        if "rate limit" in error_str or "rate_limit" in error_str:
            return AIRateLimitError(
                message="AI rate limit exceeded",
                provider=provider,
                retry_after=60,
            )

        if "authentication" in error_str or "api key" in error_str:
            return AIProviderError(
                message="AI authentication failed",
                provider=provider,
                details={"error": str(error)},
            )

        return AIProviderError(
            message=f"AI provider error: {str(error)}",
            provider=provider,
            details={"error": str(error)},
        )


# Global AI service instance
ai_service = AIService()

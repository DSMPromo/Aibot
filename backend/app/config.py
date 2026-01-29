"""
Application configuration using Pydantic Settings.

All configuration is loaded from environment variables with sensible defaults
for development. In production, set all required variables.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Environment
    # =========================================================================
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Enable debug mode")

    # =========================================================================
    # Security (REQUIRED)
    # =========================================================================
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT signing",
        min_length=32,
    )
    encryption_key: str = Field(
        default="change-me-in-production",
        description="Fernet key for token encryption",
    )

    # =========================================================================
    # JWT Configuration
    # =========================================================================
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=15, description="Access token expiry in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token expiry in days"
    )

    # =========================================================================
    # Database
    # =========================================================================
    database_url: str = Field(
        default="postgresql+asyncpg://aimarketing:aimarketing_dev@localhost:5432/aimarketing",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(default=5, description="Connection pool size")
    database_max_overflow: int = Field(default=10, description="Max pool overflow")
    database_pool_timeout: int = Field(
        default=30, description="Pool connection timeout"
    )

    # =========================================================================
    # Redis
    # =========================================================================
    redis_url: str = Field(
        default="redis://:redis_dev@localhost:6379/0",
        description="Redis connection URL",
    )

    # =========================================================================
    # Application
    # =========================================================================
    app_name: str = Field(default="AI Marketing Platform", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Allowed host headers",
    )
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def split_string_to_list(cls, v):
        """Split comma-separated string to list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_auth: str = Field(
        default="5/minute", description="Auth endpoint rate limit"
    )
    rate_limit_api: str = Field(
        default="60/minute", description="General API rate limit"
    )
    rate_limit_ai: str = Field(
        default="10/minute", description="AI endpoint rate limit"
    )

    # =========================================================================
    # Email (Resend)
    # =========================================================================
    resend_api_key: Optional[str] = Field(default=None, description="Resend API key")
    email_from: str = Field(
        default="noreply@localhost", description="Default from email"
    )

    # =========================================================================
    # Google Ads API
    # =========================================================================
    google_ads_client_id: Optional[str] = Field(default=None)
    google_ads_client_secret: Optional[str] = Field(default=None)
    google_ads_developer_token: Optional[str] = Field(default=None)
    google_ads_redirect_uri: str = Field(
        default="http://localhost/api/v1/auth/google-ads/callback"
    )

    # =========================================================================
    # Meta (Facebook) Ads API
    # =========================================================================
    meta_app_id: Optional[str] = Field(default=None)
    meta_app_secret: Optional[str] = Field(default=None)
    meta_redirect_uri: str = Field(
        default="http://localhost/api/v1/auth/meta/callback"
    )

    # =========================================================================
    # TikTok Ads API
    # =========================================================================
    tiktok_app_id: Optional[str] = Field(default=None)
    tiktok_app_secret: Optional[str] = Field(default=None)
    tiktok_redirect_uri: str = Field(
        default="http://localhost/api/v1/auth/tiktok/callback"
    )

    # =========================================================================
    # AI Providers
    # =========================================================================
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API key"
    )
    ai_default_model: str = Field(
        default="gpt-4o-mini", description="Default AI model"
    )

    # =========================================================================
    # Google SSO
    # =========================================================================
    google_sso_client_id: Optional[str] = Field(default=None)
    google_sso_client_secret: Optional[str] = Field(default=None)
    google_sso_redirect_uri: str = Field(
        default="http://localhost/api/v1/auth/google/callback"
    )

    # =========================================================================
    # Stripe
    # =========================================================================
    stripe_secret_key: Optional[str] = Field(default=None)
    stripe_publishable_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)

    # =========================================================================
    # Sentry
    # =========================================================================
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")

    # =========================================================================
    # Properties
    # =========================================================================
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

"""
OAuth 2.0 Infrastructure for Ad Platform Connections.

Implements secure OAuth flows for:
- Google Ads API
- Meta (Facebook) Marketing API
- TikTok Marketing API

Security features:
- CSRF protection via state parameter
- Token encryption at rest (Fernet)
- Secure token refresh
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

import structlog
from authlib.integrations.httpx_client import AsyncOAuth2Client
from pydantic import BaseModel

from app.config import settings
from app.core.security import decrypt_token, encrypt_token

logger = structlog.get_logger()


# =============================================================================
# OAuth State Management
# =============================================================================

class OAuthState(BaseModel):
    """OAuth state for CSRF protection."""
    state: str
    platform: str
    user_id: str
    org_id: str
    redirect_uri: str
    created_at: datetime
    expires_at: datetime


# In-memory state storage for development
# In production, use Redis with TTL
_oauth_states: dict[str, OAuthState] = {}


def generate_oauth_state(
    platform: str,
    user_id: str,
    org_id: str,
    redirect_uri: str,
    ttl_minutes: int = 10,
) -> str:
    """
    Generate a secure OAuth state parameter.

    Args:
        platform: Ad platform (google, meta, tiktok)
        user_id: User initiating the connection
        org_id: Organization to connect account to
        redirect_uri: Where to redirect after auth
        ttl_minutes: State validity period

    Returns:
        Secure state token
    """
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    oauth_state = OAuthState(
        state=state,
        platform=platform,
        user_id=user_id,
        org_id=org_id,
        redirect_uri=redirect_uri,
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )

    _oauth_states[state] = oauth_state

    logger.info(
        "oauth_state_generated",
        platform=platform,
        user_id=user_id,
        expires_in_minutes=ttl_minutes,
    )

    return state


def validate_oauth_state(state: str) -> Optional[OAuthState]:
    """
    Validate and consume an OAuth state.

    Args:
        state: State token from callback

    Returns:
        OAuthState if valid, None otherwise
    """
    oauth_state = _oauth_states.pop(state, None)

    if not oauth_state:
        logger.warning("oauth_state_not_found", state=state[:10] + "...")
        return None

    if datetime.now(timezone.utc) > oauth_state.expires_at:
        logger.warning("oauth_state_expired", state=state[:10] + "...")
        return None

    return oauth_state


def cleanup_expired_states() -> int:
    """
    Remove expired OAuth states.

    Returns:
        Number of states removed
    """
    now = datetime.now(timezone.utc)
    expired = [
        state
        for state, data in _oauth_states.items()
        if data.expires_at < now
    ]

    for state in expired:
        del _oauth_states[state]

    if expired:
        logger.info("oauth_states_cleaned", count=len(expired))

    return len(expired)


# =============================================================================
# OAuth Provider Configurations
# =============================================================================

class OAuthProviderConfig(BaseModel):
    """OAuth provider configuration."""
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    redirect_uri: str


def get_google_ads_config() -> OAuthProviderConfig:
    """Get Google Ads OAuth configuration."""
    return OAuthProviderConfig(
        client_id=settings.google_ads_client_id or "",
        client_secret=settings.google_ads_client_secret or "",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/adwords"],
        redirect_uri=settings.google_ads_redirect_uri,
    )


def get_meta_config() -> OAuthProviderConfig:
    """Get Meta (Facebook) OAuth configuration."""
    return OAuthProviderConfig(
        client_id=settings.meta_app_id or "",
        client_secret=settings.meta_app_secret or "",
        authorize_url="https://www.facebook.com/v18.0/dialog/oauth",
        token_url="https://graph.facebook.com/v18.0/oauth/access_token",
        scopes=[
            "ads_management",
            "ads_read",
            "business_management",
            "pages_read_engagement",
        ],
        redirect_uri=settings.meta_redirect_uri,
    )


def get_tiktok_config() -> OAuthProviderConfig:
    """Get TikTok OAuth configuration."""
    return OAuthProviderConfig(
        client_id=settings.tiktok_app_id or "",
        client_secret=settings.tiktok_app_secret or "",
        authorize_url="https://business-api.tiktok.com/portal/auth",
        token_url="https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
        scopes=["user.info.basic", "ads.read", "ads.write"],
        redirect_uri=settings.tiktok_redirect_uri,
    )


def get_provider_config(platform: str) -> OAuthProviderConfig:
    """Get OAuth configuration for a platform."""
    configs = {
        "google": get_google_ads_config,
        "meta": get_meta_config,
        "tiktok": get_tiktok_config,
    }

    if platform not in configs:
        raise ValueError(f"Unknown platform: {platform}")

    return configs[platform]()


# =============================================================================
# OAuth Client Factory
# =============================================================================

class OAuthClientFactory:
    """Factory for creating OAuth clients."""

    @staticmethod
    def create_client(platform: str) -> AsyncOAuth2Client:
        """
        Create an OAuth client for a platform.

        Args:
            platform: Ad platform name

        Returns:
            Configured AsyncOAuth2Client
        """
        config = get_provider_config(platform)

        return AsyncOAuth2Client(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            scope=" ".join(config.scopes),
        )

    @staticmethod
    def get_authorization_url(
        platform: str,
        user_id: str,
        org_id: str,
    ) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL.

        Args:
            platform: Ad platform
            user_id: User ID
            org_id: Organization ID

        Returns:
            Tuple of (authorization_url, state)
        """
        config = get_provider_config(platform)
        state = generate_oauth_state(
            platform=platform,
            user_id=user_id,
            org_id=org_id,
            redirect_uri=config.redirect_uri,
        )

        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
            "access_type": "offline",  # For refresh tokens
            "prompt": "consent",  # Always show consent to get refresh token
        }

        # Platform-specific adjustments
        if platform == "tiktok":
            params["app_id"] = config.client_id
            del params["client_id"]

        auth_url = f"{config.authorize_url}?{urlencode(params)}"

        logger.info(
            "oauth_authorization_url_generated",
            platform=platform,
            user_id=user_id,
        )

        return auth_url, state


# =============================================================================
# Token Management
# =============================================================================

class TokenData(BaseModel):
    """OAuth token data."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: list[str] = []


async def exchange_code_for_tokens(
    platform: str,
    code: str,
    state: str,
) -> Optional[TokenData]:
    """
    Exchange authorization code for access tokens.

    Args:
        platform: Ad platform
        code: Authorization code from callback
        state: State parameter for validation

    Returns:
        TokenData if successful, None otherwise
    """
    # Validate state
    oauth_state = validate_oauth_state(state)
    if not oauth_state:
        return None

    if oauth_state.platform != platform:
        logger.error(
            "oauth_platform_mismatch",
            expected=oauth_state.platform,
            received=platform,
        )
        return None

    config = get_provider_config(platform)
    client = OAuthClientFactory.create_client(platform)

    try:
        # Exchange code for tokens
        token = await client.fetch_token(
            config.token_url,
            code=code,
            grant_type="authorization_code",
        )

        # Calculate expiry
        expires_at = None
        if "expires_in" in token:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token["expires_in"]
            )
        elif "expires_at" in token:
            expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)

        token_data = TokenData(
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            token_type=token.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=token.get("scope", "").split() if token.get("scope") else [],
        )

        logger.info(
            "oauth_tokens_exchanged",
            platform=platform,
            user_id=oauth_state.user_id,
            has_refresh_token=bool(token_data.refresh_token),
        )

        return token_data

    except Exception as e:
        logger.error(
            "oauth_token_exchange_failed",
            platform=platform,
            error=str(e),
        )
        return None

    finally:
        await client.aclose()


async def refresh_access_token(
    platform: str,
    refresh_token: str,
) -> Optional[TokenData]:
    """
    Refresh an access token.

    Args:
        platform: Ad platform
        refresh_token: Refresh token (decrypted)

    Returns:
        New TokenData if successful, None otherwise
    """
    config = get_provider_config(platform)
    client = OAuthClientFactory.create_client(platform)

    try:
        token = await client.refresh_token(
            config.token_url,
            refresh_token=refresh_token,
        )

        expires_at = None
        if "expires_in" in token:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token["expires_in"]
            )

        token_data = TokenData(
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token", refresh_token),
            token_type=token.get("token_type", "Bearer"),
            expires_at=expires_at,
        )

        logger.info(
            "oauth_token_refreshed",
            platform=platform,
        )

        return token_data

    except Exception as e:
        logger.error(
            "oauth_token_refresh_failed",
            platform=platform,
            error=str(e),
        )
        return None

    finally:
        await client.aclose()


# =============================================================================
# Token Encryption Helpers
# =============================================================================

def encrypt_tokens(token_data: TokenData) -> Tuple[bytes, Optional[bytes]]:
    """
    Encrypt tokens for storage.

    Args:
        token_data: Token data to encrypt

    Returns:
        Tuple of (encrypted_access_token, encrypted_refresh_token)
    """
    access_encrypted = encrypt_token(token_data.access_token)
    refresh_encrypted = None
    if token_data.refresh_token:
        refresh_encrypted = encrypt_token(token_data.refresh_token)

    return access_encrypted, refresh_encrypted


def decrypt_tokens(
    access_encrypted: bytes,
    refresh_encrypted: Optional[bytes] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Decrypt tokens from storage.

    Args:
        access_encrypted: Encrypted access token
        refresh_encrypted: Encrypted refresh token

    Returns:
        Tuple of (access_token, refresh_token)
    """
    access_token = decrypt_token(access_encrypted)
    refresh_token = None
    if refresh_encrypted:
        refresh_token = decrypt_token(refresh_encrypted)

    return access_token, refresh_token

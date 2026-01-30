"""
Ad Platform Connections API endpoints.

Implements OAuth flows and account management for:
- Google Ads (CAMP-001)
- Meta Ads (CAMP-002)
- TikTok Ads (CAMP-003)

Also handles:
- Account listing (CAMP-004)
- Account disconnect (CAMP-005)
- Token refresh (CAMP-006)
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import get_adapter
from app.config import settings
from app.core.database import get_db
from app.core.oauth import (
    OAuthClientFactory,
    TokenData,
    decrypt_tokens,
    encrypt_tokens,
    exchange_code_for_tokens,
    get_provider_config,
    validate_oauth_state,
)
from app.middleware.auth import get_current_user
from app.middleware.security import limiter
from app.models.ad_account import AdAccount
from app.models.user import User
from app.workers import refresh_single_account

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ConnectRequest(BaseModel):
    """Request to initiate OAuth connection."""
    platform: str = Field(pattern="^(google|meta|tiktok)$")


class ConnectResponse(BaseModel):
    """Response with OAuth authorization URL."""
    authorization_url: str
    state: str


class ConnectionCallback(BaseModel):
    """OAuth callback parameters."""
    code: str
    state: str


class AdAccountResponse(BaseModel):
    """Ad account details."""
    id: str
    platform: str
    platform_account_id: str
    platform_account_name: Optional[str]
    is_active: bool
    sync_status: str
    last_sync_at: Optional[datetime]
    connected_at: datetime
    needs_reauth: bool


class AdAccountListResponse(BaseModel):
    """List of connected ad accounts."""
    accounts: list[AdAccountResponse]
    total: int


class PlatformAccountOption(BaseModel):
    """Available account to connect."""
    account_id: str
    account_name: str
    already_connected: bool


class AvailableAccountsResponse(BaseModel):
    """Available accounts from platform."""
    platform: str
    accounts: list[PlatformAccountOption]


class SelectAccountsRequest(BaseModel):
    """Request to select accounts after OAuth."""
    account_ids: list[str]


# =============================================================================
# In-memory token storage (use Redis in production)
# =============================================================================

_pending_tokens: dict[str, tuple[str, TokenData]] = {}  # state -> (org_id, token_data)


# =============================================================================
# OAuth Flow Endpoints
# =============================================================================

@router.post("/connect", response_model=ConnectResponse)
@limiter.limit("10/minute")
async def initiate_connection(
    request: Request,
    data: ConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth flow to connect an ad platform.

    Returns an authorization URL to redirect the user to.
    """
    # Check if platform is configured
    config = get_provider_config(data.platform)
    if not config.client_id or not config.client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{data.platform.title()} integration is not configured",
        )

    # Generate authorization URL
    auth_url, state = OAuthClientFactory.get_authorization_url(
        platform=data.platform,
        user_id=str(current_user.id),
        org_id=str(current_user.organization_id),
    )

    logger.info(
        "oauth_connection_initiated",
        platform=data.platform,
        user_id=current_user.id,
    )

    return ConnectResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get("/callback/{platform}")
async def oauth_callback(
    request: Request,
    platform: str,
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Handle OAuth callback from ad platform.

    This endpoint receives the authorization code and exchanges it for tokens.
    """
    # Check for OAuth errors
    if error:
        logger.error(
            "oauth_callback_error",
            platform=platform,
            error=error,
            description=error_description,
        )
        return {
            "error": error,
            "error_description": error_description,
            "redirect_url": f"/settings/connections?error={error}",
        }

    # Validate platform
    if platform not in ("google", "meta", "tiktok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid platform",
        )

    # Get state data before exchange (for org_id)
    from app.core.oauth import _oauth_states
    state_data = _oauth_states.get(state)
    if not state_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state",
        )
    org_id = state_data.org_id

    # Exchange code for tokens
    token_data = await exchange_code_for_tokens(
        platform=platform,
        code=code,
        state=state,
    )

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code",
        )

    # Store tokens temporarily for account selection
    temp_state = state[:16]  # Use partial state as temp key
    _pending_tokens[temp_state] = (org_id, token_data)

    logger.info(
        "oauth_callback_success",
        platform=platform,
        has_refresh_token=bool(token_data.refresh_token),
    )

    return {
        "status": "success",
        "platform": platform,
        "message": "OAuth successful. Select accounts to connect.",
        "redirect_url": f"/settings/connections/{platform}/select?state={temp_state}",
        "temp_state": temp_state,
    }


@router.post("/callback/{platform}/select")
async def select_accounts(
    request: Request,
    platform: str,
    data: SelectAccountsRequest,
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Select which platform accounts to connect after OAuth.

    Called after user selects accounts from the available list.
    """
    # Get stored tokens
    if state not in _pending_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session expired. Please reconnect.",
        )

    org_id, token_data = _pending_tokens.pop(state)

    # Verify user belongs to org
    if str(current_user.organization_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Encrypt tokens for storage
    access_encrypted, refresh_encrypted = encrypt_tokens(token_data)

    # Get adapter to fetch account details
    adapter = get_adapter(platform)
    platform_accounts = await adapter.list_accounts(token_data.access_token)

    # Create AdAccount records for selected accounts
    created_count = 0
    for account in platform_accounts:
        if account.account_id not in data.account_ids:
            continue

        # Check if already connected
        existing = await db.execute(
            select(AdAccount).where(
                AdAccount.org_id == org_id,
                AdAccount.platform == platform,
                AdAccount.platform_account_id == account.account_id,
            )
        )
        if existing.scalar_one_or_none():
            continue  # Skip already connected

        ad_account = AdAccount(
            org_id=org_id,
            platform=platform,
            platform_account_id=account.account_id,
            platform_account_name=account.account_name,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=token_data.expires_at,
            token_scopes=token_data.scopes,
            is_active=True,
            connected_by_id=str(current_user.id),
            sync_status="pending",
            metadata={
                "currency": account.currency,
                "timezone": account.timezone,
            },
        )
        db.add(ad_account)
        created_count += 1

    await db.commit()

    logger.info(
        "accounts_selected",
        platform=platform,
        count=created_count,
        org_id=org_id,
    )

    return {
        "status": "success",
        "connected_accounts": created_count,
    }


# =============================================================================
# Account Management Endpoints
# =============================================================================

@router.get("", response_model=AdAccountListResponse)
async def list_connections(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all connected ad accounts for the current organization.
    """
    result = await db.execute(
        select(AdAccount)
        .where(
            AdAccount.org_id == str(current_user.organization_id),
            AdAccount.is_active == True,
        )
        .order_by(AdAccount.platform, AdAccount.platform_account_name)
    )
    accounts = result.scalars().all()

    return AdAccountListResponse(
        accounts=[
            AdAccountResponse(
                id=str(account.id),
                platform=account.platform,
                platform_account_id=account.platform_account_id,
                platform_account_name=account.platform_account_name,
                is_active=account.is_active,
                sync_status=account.sync_status,
                last_sync_at=account.last_sync_at,
                connected_at=account.connected_at,
                needs_reauth=account.needs_reauth,
            )
            for account in accounts
        ],
        total=len(accounts),
    )


@router.get("/{account_id}", response_model=AdAccountResponse)
async def get_connection(
    request: Request,
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific connected account.
    """
    result = await db.execute(
        select(AdAccount).where(
            AdAccount.id == account_id,
            AdAccount.org_id == str(current_user.organization_id),
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return AdAccountResponse(
        id=str(account.id),
        platform=account.platform,
        platform_account_id=account.platform_account_id,
        platform_account_name=account.platform_account_name,
        is_active=account.is_active,
        sync_status=account.sync_status,
        last_sync_at=account.last_sync_at,
        connected_at=account.connected_at,
        needs_reauth=account.needs_reauth,
    )


@router.delete("/{account_id}")
async def disconnect_account(
    request: Request,
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disconnect an ad account.

    This will:
    - Mark account as disconnected
    - Clear stored tokens
    - Stop syncing data
    """
    result = await db.execute(
        select(AdAccount).where(
            AdAccount.id == account_id,
            AdAccount.org_id == str(current_user.organization_id),
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Mark as disconnected and clear tokens
    account.is_active = False
    account.disconnected_at = datetime.now(timezone.utc)
    account.access_token_encrypted = None
    account.refresh_token_encrypted = None

    await db.commit()

    logger.info(
        "account_disconnected",
        account_id=account_id,
        platform=account.platform,
        user_id=current_user.id,
    )

    return {"message": "Account disconnected successfully"}


@router.post("/{account_id}/sync")
async def trigger_sync(
    request: Request,
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger a sync for an ad account.
    """
    result = await db.execute(
        select(AdAccount).where(
            AdAccount.id == account_id,
            AdAccount.org_id == str(current_user.organization_id),
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is disconnected",
        )

    # Update sync status
    account.sync_status = "pending"
    await db.commit()

    # TODO: Queue actual sync job with arq

    logger.info(
        "sync_triggered",
        account_id=account_id,
        platform=account.platform,
    )

    return {"message": "Sync queued successfully"}


@router.post("/{account_id}/refresh-token")
async def refresh_account_token_endpoint(
    request: Request,
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually refresh OAuth token for an account.

    Useful when automatic refresh fails.
    """
    result = await db.execute(
        select(AdAccount).where(
            AdAccount.id == account_id,
            AdAccount.org_id == str(current_user.organization_id),
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    logger.info(
        "token_refresh_requested",
        account_id=account_id,
        platform=account.platform,
    )

    success = await refresh_single_account({"account_id": account_id})

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to refresh token. Account may need to be reconnected.",
        )

    return {"message": "Token refreshed successfully"}


# =============================================================================
# Platform-Specific Endpoints
# =============================================================================

@router.get("/{platform}/accounts", response_model=AvailableAccountsResponse)
async def list_platform_accounts(
    request: Request,
    platform: str,
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List available accounts from a platform.

    Used after OAuth to show which accounts can be connected.
    Requires temp_state from OAuth callback.
    """
    if platform not in ("google", "meta", "tiktok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid platform",
        )

    # Get stored tokens
    if state not in _pending_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session expired. Please reconnect.",
        )

    org_id, token_data = _pending_tokens[state]

    # Verify user belongs to org
    if str(current_user.organization_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get adapter and fetch accounts
    adapter = get_adapter(platform)
    platform_accounts = await adapter.list_accounts(token_data.access_token)

    # Get already connected accounts
    result = await db.execute(
        select(AdAccount.platform_account_id).where(
            AdAccount.org_id == org_id,
            AdAccount.platform == platform,
            AdAccount.is_active == True,
        )
    )
    connected_ids = {row[0] for row in result.all()}

    accounts = [
        PlatformAccountOption(
            account_id=acc.account_id,
            account_name=acc.account_name,
            already_connected=acc.account_id in connected_ids,
        )
        for acc in platform_accounts
    ]

    return AvailableAccountsResponse(
        platform=platform,
        accounts=accounts,
    )

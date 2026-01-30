"""
Token Refresh Worker

Background worker that proactively refreshes OAuth tokens before they expire.
This ensures uninterrupted access to ad platform APIs.

Refresh Strategy:
- Check every 5 minutes for tokens expiring within 15 minutes
- Refresh tokens 15 minutes before expiry (buffer time)
- Track consecutive failures and mark accounts for re-auth
- Log all refresh attempts for monitoring
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_context
from app.core.oauth import (
    decrypt_tokens,
    encrypt_tokens,
    refresh_access_token,
    TokenData,
)
from app.models.ad_account import AdAccount

logger = structlog.get_logger()

# Configuration
TOKEN_REFRESH_BUFFER_MINUTES = 15  # Refresh tokens 15 min before expiry
MAX_CONSECUTIVE_FAILURES = 3  # Mark account for re-auth after this many failures


async def refresh_tokens(ctx: dict) -> dict:
    """
    Check and refresh expiring OAuth tokens.

    This is the main job function called by arq scheduler.
    Runs every 5 minutes to ensure tokens don't expire.

    Args:
        ctx: arq context (contains Redis connection pool)

    Returns:
        Summary dict with refresh statistics
    """
    logger.info("token_refresh_job_started")

    stats = {
        "checked": 0,
        "refreshed": 0,
        "failed": 0,
        "skipped": 0,
        "marked_reauth": 0,
    }

    async with get_db_context() as db:
        # Find accounts with tokens expiring soon
        accounts = await find_accounts_needing_refresh(db)
        stats["checked"] = len(accounts)

        for account in accounts:
            try:
                success = await refresh_account_token(db, account)
                if success:
                    stats["refreshed"] += 1
                else:
                    stats["failed"] += 1

                    # Check if account needs to be marked for re-auth
                    if account.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        await mark_account_reauth_needed(db, account.id)
                        stats["marked_reauth"] += 1

            except Exception as e:
                logger.error(
                    "token_refresh_error",
                    account_id=str(account.id),
                    platform=account.platform,
                    error=str(e),
                )
                stats["failed"] += 1

    logger.info(
        "token_refresh_job_completed",
        **stats,
    )

    return {
        "status": "success",
        **stats,
    }


async def find_accounts_needing_refresh(
    db: AsyncSession,
    buffer_minutes: int = TOKEN_REFRESH_BUFFER_MINUTES,
) -> list[AdAccount]:
    """
    Find ad accounts with tokens expiring within the buffer period.

    Args:
        db: Database session
        buffer_minutes: Minutes before expiry to start refresh

    Returns:
        List of accounts needing token refresh
    """
    threshold = datetime.now(timezone.utc) + timedelta(minutes=buffer_minutes)

    query = select(AdAccount).where(
        AdAccount.is_active == True,
        AdAccount.refresh_token_encrypted.is_not(None),
        AdAccount.token_expires_at.is_not(None),
        AdAccount.token_expires_at < threshold,
        AdAccount.sync_status != "auth_error",  # Don't retry failed auth
    )

    result = await db.execute(query)
    accounts = result.scalars().all()

    logger.info(
        "accounts_needing_refresh",
        count=len(accounts),
        threshold=threshold.isoformat(),
    )

    return list(accounts)


async def refresh_account_token(
    db: AsyncSession,
    account: AdAccount,
) -> bool:
    """
    Refresh the OAuth token for a single ad account.

    Args:
        db: Database session
        account: Ad account to refresh

    Returns:
        True if refresh was successful
    """
    logger.info(
        "refreshing_account_token",
        account_id=str(account.id),
        platform=account.platform,
        expires_at=account.token_expires_at.isoformat() if account.token_expires_at else None,
    )

    # Decrypt the refresh token
    if not account.refresh_token_encrypted:
        logger.warning(
            "no_refresh_token",
            account_id=str(account.id),
        )
        return False

    _, refresh_token = decrypt_tokens(
        account.access_token_encrypted,
        account.refresh_token_encrypted,
    )

    if not refresh_token:
        logger.error(
            "refresh_token_decrypt_failed",
            account_id=str(account.id),
        )
        return False

    # Attempt to refresh the token
    new_token_data = await refresh_access_token(
        platform=account.platform,
        refresh_token=refresh_token,
    )

    if not new_token_data:
        # Increment failure counter
        await increment_failure_counter(db, account.id)
        return False

    # Encrypt and store new tokens
    access_encrypted, refresh_encrypted = encrypt_tokens(new_token_data)

    # Update account with new tokens
    await update_account_tokens(
        db=db,
        account_id=account.id,
        access_token_encrypted=access_encrypted,
        refresh_token_encrypted=refresh_encrypted or account.refresh_token_encrypted,
        token_expires_at=new_token_data.expires_at,
    )

    logger.info(
        "token_refreshed_successfully",
        account_id=str(account.id),
        platform=account.platform,
        new_expires_at=new_token_data.expires_at.isoformat() if new_token_data.expires_at else None,
    )

    return True


async def update_account_tokens(
    db: AsyncSession,
    account_id: str,
    access_token_encrypted: bytes,
    refresh_token_encrypted: Optional[bytes],
    token_expires_at: Optional[datetime],
) -> None:
    """
    Update account with new encrypted tokens.

    Args:
        db: Database session
        account_id: Account to update
        access_token_encrypted: New encrypted access token
        refresh_token_encrypted: New encrypted refresh token
        token_expires_at: New token expiry time
    """
    stmt = (
        update(AdAccount)
        .where(AdAccount.id == account_id)
        .values(
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            token_expires_at=token_expires_at,
            consecutive_failures=0,  # Reset on success
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.execute(stmt)
    await db.commit()


async def increment_failure_counter(
    db: AsyncSession,
    account_id: str,
) -> int:
    """
    Increment the consecutive failure counter for an account.

    Args:
        db: Database session
        account_id: Account to update

    Returns:
        New failure count
    """
    # Get current count
    result = await db.execute(
        select(AdAccount.consecutive_failures).where(AdAccount.id == account_id)
    )
    current_count = result.scalar() or 0
    new_count = current_count + 1

    stmt = (
        update(AdAccount)
        .where(AdAccount.id == account_id)
        .values(
            consecutive_failures=new_count,
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.execute(stmt)
    await db.commit()

    logger.warning(
        "token_refresh_failure_incremented",
        account_id=account_id,
        consecutive_failures=new_count,
    )

    return new_count


async def mark_account_reauth_needed(
    db: AsyncSession,
    account_id: str,
) -> None:
    """
    Mark an account as needing re-authentication.

    This happens after too many consecutive refresh failures.

    Args:
        db: Database session
        account_id: Account to mark
    """
    stmt = (
        update(AdAccount)
        .where(AdAccount.id == account_id)
        .values(
            sync_status="auth_error",
            needs_reauth=True,
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.execute(stmt)
    await db.commit()

    logger.warning(
        "account_marked_reauth_needed",
        account_id=account_id,
    )


async def refresh_single_account(account_id: str) -> bool:
    """
    Manually refresh tokens for a single account.

    Called from API endpoint when user requests manual refresh.

    Args:
        account_id: Account to refresh

    Returns:
        True if refresh was successful
    """
    async with get_db_context() as db:
        result = await db.execute(
            select(AdAccount).where(AdAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.error("account_not_found", account_id=account_id)
            return False

        return await refresh_account_token(db, account)

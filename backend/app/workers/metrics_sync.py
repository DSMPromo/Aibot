"""
Metrics Sync Worker

Background worker that synchronizes metrics from ad platforms.

Responsibilities:
- Sync campaign metrics from Google Ads (and other platforms)
- Store metrics in TimescaleDB hypertable
- Track sync status per ad account
- Handle errors gracefully with retry logic

Sync Strategy:
- Run every 15 minutes via cron
- Fetch metrics from last sync time to now
- Upsert metrics to avoid duplicates
- Track sync progress for incremental updates
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterError, AuthenticationError, RateLimitError
from app.adapters.google_ads import GoogleAdsAdapter
from app.core.database import get_db_context
from app.core.oauth import decrypt_tokens
from app.models.ad_account import AdAccount
from app.models.campaign import Campaign
from app.models.metrics import CampaignMetrics, MetricsSyncStatus

logger = structlog.get_logger()

# Configuration
SYNC_BATCH_SIZE = 100  # Max campaigns to sync per batch
DEFAULT_LOOKBACK_DAYS = 7  # Default days to look back for first sync
MAX_CONSECUTIVE_ERRORS = 5  # Max errors before disabling sync


def get_adapter_for_platform(platform: str):
    """
    Get the appropriate adapter for a platform.

    Args:
        platform: Platform name (google, meta, tiktok)

    Returns:
        Platform adapter instance
    """
    if platform == "google":
        return GoogleAdsAdapter()
    # TODO: Add meta and tiktok adapters when implemented
    raise ValueError(f"Unsupported platform: {platform}")


async def get_decrypted_tokens(ad_account: AdAccount) -> tuple[Optional[str], Optional[str]]:
    """
    Get decrypted tokens for an ad account.

    Args:
        ad_account: Ad account to get tokens for

    Returns:
        Tuple of (access_token, refresh_token)
    """
    if not ad_account.access_token_encrypted:
        return None, None

    return decrypt_tokens(
        ad_account.access_token_encrypted,
        ad_account.refresh_token_encrypted,
    )


# =============================================================================
# Main Sync Functions
# =============================================================================

async def sync_all_metrics(ctx: dict) -> dict:
    """
    Sync metrics for all active ad accounts.

    This is the main job function called by arq scheduler.
    Runs every 15 minutes to fetch latest metrics.

    Args:
        ctx: arq context (contains Redis connection pool)

    Returns:
        Summary dict with sync statistics
    """
    logger.info("metrics_sync_job_started")

    stats = {
        "accounts_checked": 0,
        "accounts_synced": 0,
        "accounts_failed": 0,
        "campaigns_synced": 0,
        "metrics_stored": 0,
    }

    async with get_db_context() as db:
        # Find all active ad accounts with sync enabled
        ad_accounts = await find_active_accounts(db)
        stats["accounts_checked"] = len(ad_accounts)

        for ad_account in ad_accounts:
            try:
                result = await sync_account_metrics(db, ad_account)
                stats["accounts_synced"] += 1
                stats["campaigns_synced"] += result.get("campaigns_synced", 0)
                stats["metrics_stored"] += result.get("metrics_stored", 0)
            except Exception as e:
                logger.error(
                    "account_metrics_sync_error",
                    ad_account_id=str(ad_account.id),
                    platform=ad_account.platform,
                    error=str(e),
                )
                stats["accounts_failed"] += 1

                # Update sync status with error
                await update_sync_status_error(db, ad_account.id, str(e))

    logger.info("metrics_sync_job_completed", **stats)

    return {
        "status": "success",
        **stats,
    }


async def find_active_accounts(db: AsyncSession) -> list[AdAccount]:
    """
    Find active ad accounts that should be synced.

    Args:
        db: Database session

    Returns:
        List of active ad accounts
    """
    query = (
        select(AdAccount)
        .where(
            AdAccount.is_active == True,
            AdAccount.sync_status != "auth_error",
        )
    )

    result = await db.execute(query)
    accounts = result.scalars().all()

    logger.info("active_accounts_found", count=len(accounts))

    return list(accounts)


async def sync_account_metrics(db: AsyncSession, ad_account: AdAccount) -> dict:
    """
    Sync metrics for a single ad account.

    Args:
        db: Database session
        ad_account: Ad account to sync

    Returns:
        Result dict with sync statistics
    """
    logger.info(
        "syncing_account_metrics",
        ad_account_id=str(ad_account.id),
        platform=ad_account.platform,
    )

    result = {
        "campaigns_synced": 0,
        "metrics_stored": 0,
    }

    # Get or create sync status
    sync_status = await get_or_create_sync_status(db, ad_account.id)

    # Check if sync is enabled
    if not sync_status.sync_enabled:
        logger.info("sync_disabled", ad_account_id=str(ad_account.id))
        return result

    # Get access token
    access_token, _ = await get_decrypted_tokens(ad_account)
    if not access_token:
        logger.error("no_access_token", ad_account_id=str(ad_account.id))
        await update_sync_status_error(db, ad_account.id, "No access token available")
        return result

    # Get adapter
    try:
        adapter = get_adapter_for_platform(ad_account.platform)
    except ValueError as e:
        logger.error("unsupported_platform", platform=ad_account.platform)
        await update_sync_status_error(db, ad_account.id, str(e))
        return result

    # Determine date range to sync
    end_date = date.today()
    if sync_status.latest_data_date:
        # Sync from last sync date
        start_date = sync_status.latest_data_date.date()
    else:
        # First sync - look back DEFAULT_LOOKBACK_DAYS
        start_date = end_date - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    # Get campaigns for this account
    campaigns = await get_account_campaigns(db, ad_account.id)

    if not campaigns:
        logger.info("no_campaigns", ad_account_id=str(ad_account.id))
        await update_sync_status_success(db, ad_account.id, end_date)
        return result

    try:
        # Sync metrics for each campaign
        for campaign in campaigns:
            if not campaign.platform_campaign_id:
                continue

            try:
                metrics = await adapter.get_campaign_metrics(
                    access_token=access_token,
                    account_id=ad_account.platform_account_id,
                    campaign_id=campaign.platform_campaign_id,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Store metrics
                stored_count = await store_campaign_metrics(
                    db=db,
                    campaign_id=campaign.id,
                    metrics=metrics,
                )

                result["campaigns_synced"] += 1
                result["metrics_stored"] += stored_count

            except AdapterError as e:
                logger.warning(
                    "campaign_metrics_sync_error",
                    campaign_id=str(campaign.id),
                    error=str(e),
                )

        # Update sync status
        await update_sync_status_success(db, ad_account.id, end_date)

        logger.info(
            "account_metrics_synced",
            ad_account_id=str(ad_account.id),
            campaigns_synced=result["campaigns_synced"],
            metrics_stored=result["metrics_stored"],
        )

    except AuthenticationError as e:
        logger.error("auth_error", ad_account_id=str(ad_account.id), error=str(e))
        await update_sync_status_error(db, ad_account.id, "Authentication failed")
        # Mark account as needing reauth
        await db.execute(
            update(AdAccount)
            .where(AdAccount.id == ad_account.id)
            .values(sync_status="auth_error", needs_reauth=True)
        )
        await db.commit()

    except RateLimitError as e:
        logger.warning("rate_limit", ad_account_id=str(ad_account.id), retry_after=e.retry_after)
        await update_sync_status_error(db, ad_account.id, "Rate limit exceeded")

    return result


async def get_account_campaigns(db: AsyncSession, ad_account_id: str) -> list[Campaign]:
    """
    Get campaigns for an ad account.

    Args:
        db: Database session
        ad_account_id: Ad account ID

    Returns:
        List of campaigns
    """
    query = (
        select(Campaign)
        .where(
            Campaign.ad_account_id == ad_account_id,
            Campaign.status.in_(["active", "paused"]),
            Campaign.platform_campaign_id.isnot(None),
        )
        .limit(SYNC_BATCH_SIZE)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def store_campaign_metrics(
    db: AsyncSession,
    campaign_id: str,
    metrics: list,
) -> int:
    """
    Store campaign metrics in the database.

    Uses upsert to handle duplicates gracefully.

    Args:
        db: Database session
        campaign_id: Campaign ID
        metrics: List of metrics from adapter

    Returns:
        Number of metrics stored
    """
    if not metrics:
        return 0

    stored_count = 0

    for metric in metrics:
        # Calculate derived metrics
        derived = CampaignMetrics.calculate_derived_metrics(
            impressions=metric.impressions,
            clicks=metric.clicks,
            spend=Decimal(str(metric.spend)),
            conversions=metric.conversions,
            conversion_value=Decimal(str(metric.conversion_value)),
        )

        # Create timestamp from date (end of day for daily metrics)
        timestamp = datetime.combine(
            metric.date,
            datetime.max.time(),
            tzinfo=timezone.utc,
        )

        # Prepare upsert statement
        stmt = insert(CampaignMetrics).values(
            campaign_id=campaign_id,
            timestamp=timestamp,
            granularity="raw",
            impressions=metric.impressions,
            clicks=metric.clicks,
            ctr=derived["ctr"],
            spend=Decimal(str(metric.spend)),
            avg_cpc=derived["avg_cpc"],
            avg_cpm=derived["avg_cpm"],
            conversions=metric.conversions,
            conversion_value=Decimal(str(metric.conversion_value)),
            cpa=derived["cpa"],
            roas=derived["roas"],
            view_conversions=getattr(metric, "view_conversions", 0),
            synced_at=datetime.now(timezone.utc),
        )

        # On conflict, update the values
        stmt = stmt.on_conflict_do_update(
            constraint="uq_campaign_metrics_unique",
            set_={
                "impressions": stmt.excluded.impressions,
                "clicks": stmt.excluded.clicks,
                "ctr": stmt.excluded.ctr,
                "spend": stmt.excluded.spend,
                "avg_cpc": stmt.excluded.avg_cpc,
                "avg_cpm": stmt.excluded.avg_cpm,
                "conversions": stmt.excluded.conversions,
                "conversion_value": stmt.excluded.conversion_value,
                "cpa": stmt.excluded.cpa,
                "roas": stmt.excluded.roas,
                "view_conversions": stmt.excluded.view_conversions,
                "synced_at": stmt.excluded.synced_at,
            },
        )

        await db.execute(stmt)
        stored_count += 1

    await db.commit()

    return stored_count


# =============================================================================
# Sync Status Management
# =============================================================================

async def get_or_create_sync_status(
    db: AsyncSession,
    ad_account_id: str,
) -> MetricsSyncStatus:
    """
    Get or create sync status for an ad account.

    Args:
        db: Database session
        ad_account_id: Ad account ID

    Returns:
        MetricsSyncStatus record
    """
    query = select(MetricsSyncStatus).where(
        MetricsSyncStatus.ad_account_id == ad_account_id
    )
    result = await db.execute(query)
    sync_status = result.scalar_one_or_none()

    if not sync_status:
        sync_status = MetricsSyncStatus(
            ad_account_id=ad_account_id,
            sync_enabled=True,
            sync_interval_minutes=15,
        )
        db.add(sync_status)
        await db.commit()
        await db.refresh(sync_status)

    return sync_status


async def update_sync_status_success(
    db: AsyncSession,
    ad_account_id: str,
    latest_date: date,
) -> None:
    """
    Update sync status after successful sync.

    Args:
        db: Database session
        ad_account_id: Ad account ID
        latest_date: Latest date synced
    """
    now = datetime.now(timezone.utc)
    latest_datetime = datetime.combine(latest_date, datetime.max.time(), tzinfo=timezone.utc)

    stmt = (
        update(MetricsSyncStatus)
        .where(MetricsSyncStatus.ad_account_id == ad_account_id)
        .values(
            last_sync_at=now,
            last_sync_status="success",
            latest_data_date=latest_datetime,
            last_error=None,
            consecutive_errors=0,
            updated_at=now,
        )
    )

    await db.execute(stmt)
    await db.commit()


async def update_sync_status_error(
    db: AsyncSession,
    ad_account_id: str,
    error_message: str,
) -> None:
    """
    Update sync status after error.

    Args:
        db: Database session
        ad_account_id: Ad account ID
        error_message: Error description
    """
    now = datetime.now(timezone.utc)

    # Get current consecutive errors
    query = select(MetricsSyncStatus).where(
        MetricsSyncStatus.ad_account_id == ad_account_id
    )
    result = await db.execute(query)
    sync_status = result.scalar_one_or_none()

    consecutive_errors = (sync_status.consecutive_errors if sync_status else 0) + 1
    sync_enabled = consecutive_errors < MAX_CONSECUTIVE_ERRORS

    if sync_status:
        stmt = (
            update(MetricsSyncStatus)
            .where(MetricsSyncStatus.ad_account_id == ad_account_id)
            .values(
                last_sync_at=now,
                last_sync_status="error",
                last_error=error_message,
                consecutive_errors=consecutive_errors,
                sync_enabled=sync_enabled,
                updated_at=now,
            )
        )
        await db.execute(stmt)
    else:
        sync_status = MetricsSyncStatus(
            ad_account_id=ad_account_id,
            last_sync_at=now,
            last_sync_status="error",
            last_error=error_message,
            consecutive_errors=consecutive_errors,
            sync_enabled=sync_enabled,
        )
        db.add(sync_status)

    await db.commit()

    if not sync_enabled:
        logger.warning(
            "sync_disabled_due_to_errors",
            ad_account_id=ad_account_id,
            consecutive_errors=consecutive_errors,
        )


# =============================================================================
# Manual Sync Functions
# =============================================================================

async def sync_single_account_metrics(ad_account_id: str) -> dict:
    """
    Manually sync metrics for a single ad account.

    Called from API endpoint for on-demand sync.

    Args:
        ad_account_id: Ad account to sync

    Returns:
        Sync result dict
    """
    async with get_db_context() as db:
        # Get ad account
        query = select(AdAccount).where(AdAccount.id == ad_account_id)
        result = await db.execute(query)
        ad_account = result.scalar_one_or_none()

        if not ad_account:
            return {"status": "error", "message": "Ad account not found"}

        if not ad_account.is_active:
            return {"status": "error", "message": "Ad account is not active"}

        # Run sync
        sync_result = await sync_account_metrics(db, ad_account)

        return {
            "status": "success",
            **sync_result,
        }


async def sync_campaign_metrics_range(
    campaign_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Sync metrics for a specific campaign and date range.

    Called from API endpoint for backfilling data.

    Args:
        campaign_id: Campaign to sync
        start_date: Start of date range
        end_date: End of date range

    Returns:
        Sync result dict
    """
    async with get_db_context() as db:
        # Get campaign with ad account
        query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            return {"status": "error", "message": "Campaign not found"}

        if not campaign.platform_campaign_id:
            return {"status": "error", "message": "Campaign not synced to platform"}

        # Get ad account
        query = select(AdAccount).where(AdAccount.id == campaign.ad_account_id)
        result = await db.execute(query)
        ad_account = result.scalar_one_or_none()

        if not ad_account or not ad_account.is_active:
            return {"status": "error", "message": "Ad account not available"}

        # Get access token
        access_token, _ = await get_decrypted_tokens(ad_account)
        if not access_token:
            return {"status": "error", "message": "No access token available"}

        # Get adapter
        try:
            adapter = get_adapter_for_platform(ad_account.platform)
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        # Fetch and store metrics
        try:
            metrics = await adapter.get_campaign_metrics(
                access_token=access_token,
                account_id=ad_account.platform_account_id,
                campaign_id=campaign.platform_campaign_id,
                start_date=start_date,
                end_date=end_date,
            )

            stored_count = await store_campaign_metrics(
                db=db,
                campaign_id=campaign.id,
                metrics=metrics,
            )

            return {
                "status": "success",
                "metrics_stored": stored_count,
                "date_range": f"{start_date} to {end_date}",
            }

        except AdapterError as e:
            return {"status": "error", "message": str(e)}

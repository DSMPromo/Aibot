"""
Campaign Sync Worker

Background worker that synchronizes campaigns with ad platforms.

Responsibilities:
- Push approved campaigns to platforms (Google Ads, Meta, TikTok)
- Sync campaign status changes from platforms
- Update local campaign status based on platform status
- Handle sync errors gracefully with retry logic

Sync Strategy:
- On approval: Push campaign to platform, get platform_campaign_id
- After push: Set campaign status to 'active'
- Periodic sync: Check platform status for live campaigns
- On pause/resume: Update platform status accordingly
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.base import (
    AdapterError,
    AuthenticationError,
    CampaignCreateRequest,
    CampaignObjective,
    CampaignStatus as PlatformCampaignStatus,
    CampaignUpdateRequest,
    RateLimitError,
)
from app.adapters.google_ads import GoogleAdsAdapter
from app.core.database import get_db_context
from app.core.oauth import decrypt_tokens
from app.models.ad_account import AdAccount
from app.models.campaign import Campaign

logger = structlog.get_logger()

# Configuration
MAX_SYNC_RETRIES = 3
SYNC_BATCH_SIZE = 50  # Max campaigns to sync in one batch


# Objective mapping from our schema to adapter schema
OBJECTIVE_MAP = {
    "awareness": CampaignObjective.AWARENESS,
    "traffic": CampaignObjective.TRAFFIC,
    "engagement": CampaignObjective.ENGAGEMENT,
    "leads": CampaignObjective.LEADS,
    "sales": CampaignObjective.SALES,
    "app_promotion": CampaignObjective.APP_PROMOTION,
}


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


async def get_access_token(db: AsyncSession, ad_account: AdAccount) -> Optional[str]:
    """
    Get the decrypted access token for an ad account.

    Args:
        db: Database session
        ad_account: Ad account to get token for

    Returns:
        Decrypted access token or None
    """
    if not ad_account.access_token_encrypted:
        return None

    access_token, _ = decrypt_tokens(
        ad_account.access_token_encrypted,
        ad_account.refresh_token_encrypted,
    )

    return access_token


# =============================================================================
# Campaign Push (Approved -> Active)
# =============================================================================

async def sync_approved_campaigns(ctx: dict) -> dict:
    """
    Push approved campaigns to their respective platforms.

    This is the main job function called by arq scheduler.
    Finds campaigns in 'approved' status and pushes them to platforms.

    Args:
        ctx: arq context (contains Redis connection pool)

    Returns:
        Summary dict with sync statistics
    """
    logger.info("campaign_push_job_started")

    stats = {
        "checked": 0,
        "pushed": 0,
        "failed": 0,
        "skipped": 0,
    }

    async with get_db_context() as db:
        # Find approved campaigns that haven't been pushed yet
        campaigns = await find_approved_campaigns(db)
        stats["checked"] = len(campaigns)

        for campaign in campaigns:
            try:
                success = await push_campaign_to_platform(db, campaign)
                if success:
                    stats["pushed"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(
                    "campaign_push_error",
                    campaign_id=str(campaign.id),
                    platform=campaign.platform,
                    error=str(e),
                )
                stats["failed"] += 1

                # Record sync error on campaign
                await update_campaign_sync_error(db, campaign.id, str(e))

    logger.info("campaign_push_job_completed", **stats)

    return {
        "status": "success",
        **stats,
    }


async def find_approved_campaigns(db: AsyncSession) -> list[Campaign]:
    """
    Find campaigns in approved status that need to be pushed.

    Args:
        db: Database session

    Returns:
        List of campaigns to push
    """
    query = (
        select(Campaign)
        .where(
            Campaign.status == "approved",
            Campaign.platform_campaign_id.is_(None),  # Not yet pushed
        )
        .options(selectinload(Campaign.ad_copies))
        .limit(SYNC_BATCH_SIZE)
    )

    result = await db.execute(query)
    campaigns = result.scalars().all()

    logger.info("approved_campaigns_found", count=len(campaigns))

    return list(campaigns)


async def push_campaign_to_platform(db: AsyncSession, campaign: Campaign) -> bool:
    """
    Push a single campaign to its ad platform.

    Args:
        db: Database session
        campaign: Campaign to push

    Returns:
        True if push was successful
    """
    logger.info(
        "pushing_campaign_to_platform",
        campaign_id=str(campaign.id),
        platform=campaign.platform,
        name=campaign.name,
    )

    # Get the ad account
    result = await db.execute(
        select(AdAccount).where(AdAccount.id == campaign.ad_account_id)
    )
    ad_account = result.scalar_one_or_none()

    if not ad_account:
        logger.error("ad_account_not_found", ad_account_id=campaign.ad_account_id)
        return False

    if not ad_account.is_active:
        logger.warning("ad_account_not_active", ad_account_id=str(ad_account.id))
        return False

    # Get access token
    access_token = await get_access_token(db, ad_account)
    if not access_token:
        logger.error("no_access_token", ad_account_id=str(ad_account.id))
        await update_campaign_sync_error(db, campaign.id, "No access token available")
        return False

    # Get the adapter
    try:
        adapter = get_adapter_for_platform(campaign.platform)
    except ValueError as e:
        logger.error("unsupported_platform", platform=campaign.platform, error=str(e))
        await update_campaign_sync_error(db, campaign.id, str(e))
        return False

    # Build the create request
    create_request = CampaignCreateRequest(
        name=campaign.name,
        objective=OBJECTIVE_MAP.get(campaign.objective, CampaignObjective.AWARENESS),
        budget_amount=float(campaign.budget_amount),
        budget_type=campaign.budget_type,
        start_date=campaign.start_date,
        end_date=campaign.end_date if not campaign.is_ongoing else None,
        targeting=campaign.targeting or {},
    )

    # Add ad copy if available
    if campaign.ad_copies:
        primary_copy = next(
            (c for c in campaign.ad_copies if c.is_primary),
            campaign.ad_copies[0] if campaign.ad_copies else None,
        )
        if primary_copy:
            create_request.ad_copy = {
                "headline_1": primary_copy.headline_1,
                "headline_2": primary_copy.headline_2,
                "headline_3": primary_copy.headline_3,
                "description_1": primary_copy.description_1,
                "description_2": primary_copy.description_2,
                "final_url": primary_copy.final_url,
            }

    try:
        # Create campaign on platform
        platform_campaign_id = await adapter.create_campaign(
            access_token=access_token,
            account_id=ad_account.platform_account_id,
            request=create_request,
        )

        # Update campaign with platform ID and set to active
        await update_campaign_after_push(
            db=db,
            campaign_id=campaign.id,
            platform_campaign_id=platform_campaign_id,
        )

        logger.info(
            "campaign_pushed_successfully",
            campaign_id=str(campaign.id),
            platform_campaign_id=platform_campaign_id,
        )

        return True

    except AuthenticationError as e:
        logger.error("auth_error_pushing_campaign", error=str(e))
        await update_campaign_sync_error(db, campaign.id, f"Authentication error: {e.message}")
        return False

    except RateLimitError as e:
        logger.warning("rate_limit_pushing_campaign", retry_after=e.retry_after)
        await update_campaign_sync_error(db, campaign.id, "Rate limit exceeded, will retry")
        return False

    except AdapterError as e:
        logger.error("adapter_error_pushing_campaign", error=str(e))
        await update_campaign_sync_error(db, campaign.id, f"Platform error: {e.message}")
        return False


async def update_campaign_after_push(
    db: AsyncSession,
    campaign_id: str,
    platform_campaign_id: str,
) -> None:
    """
    Update campaign after successful push to platform.

    Args:
        db: Database session
        campaign_id: Campaign to update
        platform_campaign_id: ID from platform
    """
    stmt = (
        update(Campaign)
        .where(Campaign.id == campaign_id)
        .values(
            platform_campaign_id=platform_campaign_id,
            platform_status="paused",  # Google creates campaigns as paused
            status="active",
            sync_error=None,
            last_synced_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.execute(stmt)
    await db.commit()


async def update_campaign_sync_error(
    db: AsyncSession,
    campaign_id: str,
    error_message: str,
) -> None:
    """
    Update campaign with sync error.

    Args:
        db: Database session
        campaign_id: Campaign to update
        error_message: Error description
    """
    stmt = (
        update(Campaign)
        .where(Campaign.id == campaign_id)
        .values(
            sync_error=error_message,
            last_synced_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    await db.execute(stmt)
    await db.commit()


# =============================================================================
# Campaign Status Sync (Platform -> Local)
# =============================================================================

async def sync_campaign_statuses(ctx: dict) -> dict:
    """
    Sync campaign statuses from platforms to local database.

    This is the main job function for status sync.
    Checks platform status for active/paused campaigns.

    Args:
        ctx: arq context

    Returns:
        Summary dict with sync statistics
    """
    logger.info("campaign_status_sync_job_started")

    stats = {
        "checked": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
    }

    async with get_db_context() as db:
        # Find live campaigns that have platform IDs
        campaigns = await find_live_campaigns(db)
        stats["checked"] = len(campaigns)

        # Group by ad account for efficiency
        campaigns_by_account: dict[str, list[Campaign]] = {}
        for campaign in campaigns:
            if campaign.ad_account_id not in campaigns_by_account:
                campaigns_by_account[campaign.ad_account_id] = []
            campaigns_by_account[campaign.ad_account_id].append(campaign)

        # Sync each account's campaigns
        for ad_account_id, account_campaigns in campaigns_by_account.items():
            try:
                result = await sync_account_campaigns(db, ad_account_id, account_campaigns)
                stats["updated"] += result["updated"]
                stats["unchanged"] += result["unchanged"]
                stats["failed"] += result["failed"]
            except Exception as e:
                logger.error(
                    "account_campaign_sync_error",
                    ad_account_id=ad_account_id,
                    error=str(e),
                )
                stats["failed"] += len(account_campaigns)

    logger.info("campaign_status_sync_job_completed", **stats)

    return {
        "status": "success",
        **stats,
    }


async def find_live_campaigns(db: AsyncSession) -> list[Campaign]:
    """
    Find campaigns that are live on platforms.

    Args:
        db: Database session

    Returns:
        List of live campaigns
    """
    query = (
        select(Campaign)
        .where(
            Campaign.status.in_(["active", "paused"]),
            Campaign.platform_campaign_id.is_not(None),
        )
        .limit(SYNC_BATCH_SIZE)
    )

    result = await db.execute(query)
    campaigns = result.scalars().all()

    logger.info("live_campaigns_found", count=len(campaigns))

    return list(campaigns)


async def sync_account_campaigns(
    db: AsyncSession,
    ad_account_id: str,
    campaigns: list[Campaign],
) -> dict:
    """
    Sync campaign statuses for a single ad account.

    Args:
        db: Database session
        ad_account_id: Ad account to sync
        campaigns: Campaigns belonging to this account

    Returns:
        Result dict with counts
    """
    result = {"updated": 0, "unchanged": 0, "failed": 0}

    # Get the ad account
    query = select(AdAccount).where(AdAccount.id == ad_account_id)
    db_result = await db.execute(query)
    ad_account = db_result.scalar_one_or_none()

    if not ad_account or not ad_account.is_active:
        logger.warning("ad_account_not_available", ad_account_id=ad_account_id)
        result["failed"] = len(campaigns)
        return result

    # Get access token
    access_token = await get_access_token(db, ad_account)
    if not access_token:
        logger.error("no_access_token", ad_account_id=str(ad_account.id))
        result["failed"] = len(campaigns)
        return result

    # Get adapter
    try:
        adapter = get_adapter_for_platform(ad_account.platform)
    except ValueError:
        logger.error("unsupported_platform", platform=ad_account.platform)
        result["failed"] = len(campaigns)
        return result

    # Sync each campaign
    for campaign in campaigns:
        try:
            campaign_info = await adapter.get_campaign(
                access_token=access_token,
                account_id=ad_account.platform_account_id,
                campaign_id=campaign.platform_campaign_id,
            )

            # Map platform status to our status
            new_platform_status = campaign_info.status.value
            status_changed = campaign.platform_status != new_platform_status

            if status_changed:
                await update_campaign_platform_status(
                    db=db,
                    campaign_id=campaign.id,
                    platform_status=new_platform_status,
                )
                result["updated"] += 1

                logger.info(
                    "campaign_status_updated",
                    campaign_id=str(campaign.id),
                    old_status=campaign.platform_status,
                    new_status=new_platform_status,
                )
            else:
                result["unchanged"] += 1

        except AdapterError as e:
            logger.error(
                "campaign_sync_error",
                campaign_id=str(campaign.id),
                error=str(e),
            )
            result["failed"] += 1

    return result


async def update_campaign_platform_status(
    db: AsyncSession,
    campaign_id: str,
    platform_status: str,
) -> None:
    """
    Update campaign platform status.

    Args:
        db: Database session
        campaign_id: Campaign to update
        platform_status: New platform status
    """
    # Map platform status to our internal status
    internal_status = None
    if platform_status == "enabled":
        internal_status = "active"
    elif platform_status == "paused":
        internal_status = "paused"
    elif platform_status == "removed":
        internal_status = "archived"

    values = {
        "platform_status": platform_status,
        "last_synced_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    if internal_status:
        values["status"] = internal_status

    stmt = update(Campaign).where(Campaign.id == campaign_id).values(**values)

    await db.execute(stmt)
    await db.commit()


# =============================================================================
# Campaign Actions (Local -> Platform)
# =============================================================================

async def pause_campaign_on_platform(campaign_id: str) -> bool:
    """
    Pause a campaign on its platform.

    Called when campaign is paused locally.

    Args:
        campaign_id: Campaign to pause

    Returns:
        True if successful
    """
    async with get_db_context() as db:
        # Get campaign with ad account
        query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign or not campaign.platform_campaign_id:
            logger.warning("campaign_not_live", campaign_id=campaign_id)
            return False

        # Get ad account
        query = select(AdAccount).where(AdAccount.id == campaign.ad_account_id)
        result = await db.execute(query)
        ad_account = result.scalar_one_or_none()

        if not ad_account or not ad_account.is_active:
            return False

        # Get access token
        access_token = await get_access_token(db, ad_account)
        if not access_token:
            return False

        # Get adapter and pause
        try:
            adapter = get_adapter_for_platform(campaign.platform)
            success = await adapter.pause_campaign(
                access_token=access_token,
                account_id=ad_account.platform_account_id,
                campaign_id=campaign.platform_campaign_id,
            )

            if success:
                await update_campaign_platform_status(db, campaign_id, "paused")
                logger.info("campaign_paused_on_platform", campaign_id=campaign_id)

            return success

        except AdapterError as e:
            logger.error("pause_campaign_error", campaign_id=campaign_id, error=str(e))
            await update_campaign_sync_error(db, campaign_id, f"Pause failed: {e.message}")
            return False


async def resume_campaign_on_platform(campaign_id: str) -> bool:
    """
    Resume a paused campaign on its platform.

    Called when campaign is resumed locally.

    Args:
        campaign_id: Campaign to resume

    Returns:
        True if successful
    """
    async with get_db_context() as db:
        # Get campaign with ad account
        query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign or not campaign.platform_campaign_id:
            logger.warning("campaign_not_live", campaign_id=campaign_id)
            return False

        # Get ad account
        query = select(AdAccount).where(AdAccount.id == campaign.ad_account_id)
        result = await db.execute(query)
        ad_account = result.scalar_one_or_none()

        if not ad_account or not ad_account.is_active:
            return False

        # Get access token
        access_token = await get_access_token(db, ad_account)
        if not access_token:
            return False

        # Get adapter and resume
        try:
            adapter = get_adapter_for_platform(campaign.platform)
            success = await adapter.resume_campaign(
                access_token=access_token,
                account_id=ad_account.platform_account_id,
                campaign_id=campaign.platform_campaign_id,
            )

            if success:
                await update_campaign_platform_status(db, campaign_id, "enabled")
                logger.info("campaign_resumed_on_platform", campaign_id=campaign_id)

            return success

        except AdapterError as e:
            logger.error("resume_campaign_error", campaign_id=campaign_id, error=str(e))
            await update_campaign_sync_error(db, campaign_id, f"Resume failed: {e.message}")
            return False


# =============================================================================
# Manual Sync Functions
# =============================================================================

async def sync_single_campaign(campaign_id: str) -> bool:
    """
    Manually sync a single campaign's status from platform.

    Called from API endpoint for on-demand sync.

    Args:
        campaign_id: Campaign to sync

    Returns:
        True if sync was successful
    """
    async with get_db_context() as db:
        # Get campaign
        query = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            logger.error("campaign_not_found", campaign_id=campaign_id)
            return False

        if not campaign.platform_campaign_id:
            logger.warning("campaign_not_on_platform", campaign_id=campaign_id)
            return False

        # Run sync for this campaign
        sync_result = await sync_account_campaigns(
            db=db,
            ad_account_id=campaign.ad_account_id,
            campaigns=[campaign],
        )

        return sync_result["failed"] == 0


async def push_single_campaign(campaign_id: str) -> bool:
    """
    Manually push a single approved campaign to platform.

    Called from API endpoint for on-demand push.

    Args:
        campaign_id: Campaign to push

    Returns:
        True if push was successful
    """
    async with get_db_context() as db:
        # Get campaign
        query = (
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(selectinload(Campaign.ad_copies))
        )
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            logger.error("campaign_not_found", campaign_id=campaign_id)
            return False

        if campaign.status != "approved":
            logger.warning(
                "campaign_not_approved",
                campaign_id=campaign_id,
                status=campaign.status,
            )
            return False

        return await push_campaign_to_platform(db, campaign)

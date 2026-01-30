"""
Campaign Management API endpoints.

Implements:
- Campaign CRUD (CAMP-007 to CAMP-011)
- Status workflow (draft -> pending_review -> approved -> active)
- Manager approval (CAMP-016, CAMP-017)
- Pause/resume operations
- Bulk operations
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.security import limiter
from app.models.campaign import (
    Campaign,
    AdCopy,
    CampaignVersion,
    CampaignApproval,
    CAMPAIGN_STATUS_TRANSITIONS,
)
from app.workers.campaign_sync import (
    pause_campaign_on_platform,
    resume_campaign_on_platform,
    push_single_campaign,
    sync_single_campaign,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class AdCopyCreate(BaseModel):
    """Ad copy creation schema."""
    headline_1: str = Field(max_length=30)
    headline_2: Optional[str] = Field(default=None, max_length=30)
    headline_3: Optional[str] = Field(default=None, max_length=30)
    description_1: str = Field(max_length=90)
    description_2: Optional[str] = Field(default=None, max_length=90)
    path_1: Optional[str] = Field(default=None, max_length=15)
    path_2: Optional[str] = Field(default=None, max_length=15)
    final_url: str = Field(max_length=2048)
    call_to_action: Optional[str] = Field(default=None, max_length=50)
    variation_name: Optional[str] = Field(default=None, max_length=50)
    is_primary: bool = False


class AdCopyResponse(BaseModel):
    """Ad copy response schema."""
    id: str
    headline_1: str
    headline_2: Optional[str]
    headline_3: Optional[str]
    description_1: str
    description_2: Optional[str]
    path_1: Optional[str]
    path_2: Optional[str]
    final_url: str
    call_to_action: Optional[str]
    variation_name: Optional[str]
    is_primary: bool
    is_ai_generated: bool
    platform_ad_id: Optional[str]

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    """Campaign creation schema."""
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    ad_account_id: str
    objective: str = Field(pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")

    # Budget
    budget_type: str = Field(default="daily", pattern="^(daily|lifetime)$")
    budget_amount: Decimal = Field(gt=0)
    budget_currency: str = Field(default="USD", max_length=3)

    # Schedule
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_ongoing: bool = False

    # Targeting (optional, can be added later)
    targeting: Optional[dict] = None

    # Platform-specific settings
    platform_settings: Optional[dict] = None

    # Ad copies (at least one required for submission)
    ad_copies: list[AdCopyCreate] = []

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v, info):
        if v and info.data.get("start_date") and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class CampaignUpdate(BaseModel):
    """Campaign update schema."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    objective: Optional[str] = Field(default=None, pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")

    # Budget
    budget_type: Optional[str] = Field(default=None, pattern="^(daily|lifetime)$")
    budget_amount: Optional[Decimal] = Field(default=None, gt=0)

    # Schedule
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_ongoing: Optional[bool] = None

    # Targeting
    targeting: Optional[dict] = None

    # Platform-specific settings
    platform_settings: Optional[dict] = None


class CampaignResponse(BaseModel):
    """Campaign response schema."""
    id: str
    name: str
    description: Optional[str]
    platform: str
    objective: str
    status: str
    status_reason: Optional[str]

    budget_type: str
    budget_amount: float
    budget_currency: str

    start_date: Optional[date]
    end_date: Optional[date]
    is_ongoing: bool

    targeting: Optional[dict]
    platform_settings: Optional[dict]

    platform_campaign_id: Optional[str]
    platform_status: Optional[str]
    last_synced_at: Optional[datetime]

    ad_account_id: str
    org_id: str
    version: int

    created_by_id: Optional[str]
    approved_by_id: Optional[str]
    approved_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime

    ad_copies: list[AdCopyResponse] = []

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Campaign list response."""
    campaigns: list[CampaignResponse]
    total: int
    page: int
    page_size: int


class StatusChangeRequest(BaseModel):
    """Request to change campaign status."""
    comment: Optional[str] = None


class BulkActionRequest(BaseModel):
    """Request for bulk campaign actions."""
    campaign_ids: list[str]
    action: str = Field(pattern="^(pause|resume|archive)$")


class BulkActionResponse(BaseModel):
    """Response for bulk actions."""
    success_count: int
    failure_count: int
    failures: list[dict] = []


# =============================================================================
# Helper Functions
# =============================================================================

async def get_campaign_or_404(
    db: AsyncSession,
    campaign_id: str,
    org_id: str,
) -> Campaign:
    """Get campaign by ID or raise 404."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.org_id == org_id,
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return campaign


async def create_campaign_version(
    db: AsyncSession,
    campaign: Campaign,
    change_type: str,
    changed_by_id: Optional[str],
    changed_fields: Optional[list] = None,
    change_summary: Optional[str] = None,
) -> CampaignVersion:
    """Create a version snapshot of the campaign."""
    # Build snapshot
    snapshot = {
        "name": campaign.name,
        "description": campaign.description,
        "objective": campaign.objective,
        "budget_type": campaign.budget_type,
        "budget_amount": str(campaign.budget_amount),
        "budget_currency": campaign.budget_currency,
        "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
        "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
        "targeting": campaign.targeting,
        "platform_settings": campaign.platform_settings,
        "status": campaign.status,
    }

    version = CampaignVersion(
        campaign_id=campaign.id,
        version=campaign.version,
        snapshot=snapshot,
        change_type=change_type,
        change_summary=change_summary,
        changed_fields=changed_fields,
        changed_by_id=changed_by_id,
    )

    db.add(version)
    return version


# =============================================================================
# Campaign CRUD Endpoints
# =============================================================================

@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_campaign(
    request: Request,
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new campaign.

    Creates campaign in draft status. Must be submitted for approval before launch.
    """
    # TODO: Get current user and org from auth
    user_id = "00000000-0000-0000-0000-000000000002"
    org_id = "00000000-0000-0000-0000-000000000001"

    # TODO: Verify ad_account belongs to org
    # TODO: Get platform from ad_account

    campaign = Campaign(
        id=str(uuid4()),
        org_id=org_id,
        ad_account_id=data.ad_account_id,
        name=data.name,
        description=data.description,
        platform="google",  # TODO: Get from ad_account
        objective=data.objective,
        status="draft",
        budget_type=data.budget_type,
        budget_amount=data.budget_amount,
        budget_currency=data.budget_currency,
        start_date=data.start_date,
        end_date=data.end_date,
        is_ongoing=data.is_ongoing,
        targeting=data.targeting,
        platform_settings=data.platform_settings,
        created_by_id=user_id,
        version=1,
    )

    db.add(campaign)

    # Create ad copies
    for ad_copy_data in data.ad_copies:
        ad_copy = AdCopy(
            id=str(uuid4()),
            campaign_id=campaign.id,
            headline_1=ad_copy_data.headline_1,
            headline_2=ad_copy_data.headline_2,
            headline_3=ad_copy_data.headline_3,
            description_1=ad_copy_data.description_1,
            description_2=ad_copy_data.description_2,
            path_1=ad_copy_data.path_1,
            path_2=ad_copy_data.path_2,
            final_url=ad_copy_data.final_url,
            call_to_action=ad_copy_data.call_to_action,
            variation_name=ad_copy_data.variation_name,
            is_primary=ad_copy_data.is_primary,
        )
        db.add(ad_copy)

    # Create initial version
    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="created",
        changed_by_id=user_id,
        change_summary="Campaign created",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_created",
        campaign_id=campaign.id,
        name=campaign.name,
        user_id=user_id,
    )

    # Fetch with ad copies for response
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign.id)
    )
    campaign = result.scalar_one()

    return campaign


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    request: Request,
    status_filter: Optional[str] = Query(None, pattern="^(draft|pending_review|approved|rejected|active|paused|archived)$"),
    platform_filter: Optional[str] = Query(None, pattern="^(google|meta|tiktok)$"),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List campaigns for the current organization.

    Supports filtering by status, platform, and search term.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    # Build query
    query = select(Campaign).where(Campaign.org_id == org_id)

    if status_filter:
        query = query.where(Campaign.status == status_filter)
    if platform_filter:
        query = query.where(Campaign.platform == platform_filter)
    if search:
        query = query.where(Campaign.name.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    query = query.order_by(Campaign.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get campaign details by ID.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    request: Request,
    campaign_id: str,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a campaign.

    Only campaigns in draft or rejected status can be edited.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign in {campaign.status} status cannot be edited",
        )

    # Track changed fields
    changed_fields = []

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None and getattr(campaign, field) != value:
            setattr(campaign, field, value)
            changed_fields.append(field)

    if changed_fields:
        campaign.version += 1
        campaign.updated_by_id = user_id

        # Create version record
        await create_campaign_version(
            db=db,
            campaign=campaign,
            change_type="updated",
            changed_by_id=user_id,
            changed_fields=changed_fields,
            change_summary=f"Updated: {', '.join(changed_fields)}",
        )

        await db.commit()
        await db.refresh(campaign)

        logger.info(
            "campaign_updated",
            campaign_id=campaign_id,
            changed_fields=changed_fields,
            user_id=user_id,
        )

    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete (archive) a campaign.

    Campaigns that are live on platforms will be paused before archiving.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    # If live, pause on platform first
    if campaign.is_live:
        # TODO: Call adapter to pause on platform
        pass

    campaign.status = "archived"
    campaign.updated_by_id = user_id

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary="Campaign archived",
    )

    await db.commit()

    logger.info(
        "campaign_archived",
        campaign_id=campaign_id,
        user_id=user_id,
    )


# =============================================================================
# Ad Copy Endpoints
# =============================================================================

@router.post("/{campaign_id}/ad-copies", response_model=AdCopyResponse, status_code=status.HTTP_201_CREATED)
async def add_ad_copy(
    request: Request,
    campaign_id: str,
    data: AdCopyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add an ad copy variation to a campaign.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add ad copy to non-editable campaign",
        )

    ad_copy = AdCopy(
        id=str(uuid4()),
        campaign_id=campaign_id,
        headline_1=data.headline_1,
        headline_2=data.headline_2,
        headline_3=data.headline_3,
        description_1=data.description_1,
        description_2=data.description_2,
        path_1=data.path_1,
        path_2=data.path_2,
        final_url=data.final_url,
        call_to_action=data.call_to_action,
        variation_name=data.variation_name,
        is_primary=data.is_primary,
    )

    db.add(ad_copy)
    await db.commit()
    await db.refresh(ad_copy)

    logger.info(
        "ad_copy_added",
        campaign_id=campaign_id,
        ad_copy_id=ad_copy.id,
    )

    return ad_copy


@router.delete("/{campaign_id}/ad-copies/{ad_copy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad_copy(
    request: Request,
    campaign_id: str,
    ad_copy_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an ad copy from a campaign.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete ad copy from non-editable campaign",
        )

    # Find ad copy
    result = await db.execute(
        select(AdCopy).where(
            AdCopy.id == ad_copy_id,
            AdCopy.campaign_id == campaign_id,
        )
    )
    ad_copy = result.scalar_one_or_none()

    if not ad_copy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ad copy not found",
        )

    await db.delete(ad_copy)
    await db.commit()

    logger.info(
        "ad_copy_deleted",
        campaign_id=campaign_id,
        ad_copy_id=ad_copy_id,
    )


# =============================================================================
# Status Workflow Endpoints
# =============================================================================

@router.post("/{campaign_id}/submit", response_model=CampaignResponse)
async def submit_for_approval(
    request: Request,
    campaign_id: str,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a campaign for manager approval.

    Transitions from draft to pending_review.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.can_transition_to("pending_review"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit campaign in {campaign.status} status",
        )

    # Validate campaign has required fields
    if not campaign.ad_copies:
        # Reload with ad copies
        result = await db.execute(
            select(AdCopy).where(AdCopy.campaign_id == campaign_id)
        )
        ad_copies = result.scalars().all()
        if not ad_copies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must have at least one ad copy before submission",
            )

    campaign.status = "pending_review"
    campaign.updated_by_id = user_id

    # Create approval request
    approval = CampaignApproval(
        id=str(uuid4()),
        campaign_id=campaign_id,
        requested_by_id=user_id,
        request_comment=data.comment,
        campaign_version=campaign.version,
    )
    db.add(approval)

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary="Submitted for approval",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_submitted",
        campaign_id=campaign_id,
        user_id=user_id,
    )

    return campaign


@router.post("/{campaign_id}/approve", response_model=CampaignResponse)
async def approve_campaign(
    request: Request,
    campaign_id: str,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a campaign for launch.

    Transitions from pending_review to approved. Requires manager role.
    """
    # TODO: Get current user's org_id and user_id
    # TODO: Verify user has manager or admin role
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.can_transition_to("approved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve campaign in {campaign.status} status",
        )

    campaign.status = "approved"
    campaign.approved_by_id = user_id
    campaign.approved_at = datetime.now(timezone.utc)
    campaign.updated_by_id = user_id

    # Update approval record
    result = await db.execute(
        select(CampaignApproval).where(
            CampaignApproval.campaign_id == campaign_id,
            CampaignApproval.decision == "pending",
        ).order_by(CampaignApproval.requested_at.desc())
    )
    approval = result.scalar_one_or_none()

    if approval:
        approval.decision = "approved"
        approval.decided_by_id = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_comment = data.comment

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary="Approved",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_approved",
        campaign_id=campaign_id,
        approved_by=user_id,
    )

    # TODO: Trigger platform sync to create campaign on ad platform

    return campaign


@router.post("/{campaign_id}/reject", response_model=CampaignResponse)
async def reject_campaign(
    request: Request,
    campaign_id: str,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a campaign.

    Transitions from pending_review to rejected. Requires manager role.
    """
    # TODO: Get current user's org_id and user_id
    # TODO: Verify user has manager or admin role
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.can_transition_to("rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject campaign in {campaign.status} status",
        )

    if not data.comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required",
        )

    campaign.status = "rejected"
    campaign.status_reason = data.comment
    campaign.updated_by_id = user_id

    # Update approval record
    result = await db.execute(
        select(CampaignApproval).where(
            CampaignApproval.campaign_id == campaign_id,
            CampaignApproval.decision == "pending",
        ).order_by(CampaignApproval.requested_at.desc())
    )
    approval = result.scalar_one_or_none()

    if approval:
        approval.decision = "rejected"
        approval.decided_by_id = user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.decision_comment = data.comment

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary=f"Rejected: {data.comment}",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_rejected",
        campaign_id=campaign_id,
        rejected_by=user_id,
        reason=data.comment,
    )

    return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Pause an active campaign.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.can_transition_to("paused"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause campaign in {campaign.status} status",
        )

    # Pause on platform if live
    if campaign.is_live:
        platform_success = await pause_campaign_on_platform(campaign_id)
        if not platform_success:
            logger.warning(
                "platform_pause_failed",
                campaign_id=campaign_id,
                platform=campaign.platform,
            )
            # Continue with local status change even if platform fails
            # The sync worker will retry later

    campaign.status = "paused"
    campaign.updated_by_id = user_id

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary="Paused",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_paused",
        campaign_id=campaign_id,
        user_id=user_id,
    )

    return campaign


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Resume a paused campaign.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.can_transition_to("active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume campaign in {campaign.status} status",
        )

    # Resume on platform if live
    if campaign.platform_campaign_id:
        platform_success = await resume_campaign_on_platform(campaign_id)
        if not platform_success:
            logger.warning(
                "platform_resume_failed",
                campaign_id=campaign_id,
                platform=campaign.platform,
            )
            # Continue with local status change even if platform fails
            # The sync worker will retry later

    campaign.status = "active"
    campaign.updated_by_id = user_id

    await create_campaign_version(
        db=db,
        campaign=campaign,
        change_type="status_change",
        changed_by_id=user_id,
        change_summary="Resumed",
    )

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        "campaign_resumed",
        campaign_id=campaign_id,
        user_id=user_id,
    )

    return campaign


# =============================================================================
# Bulk Operations Endpoints
# =============================================================================

@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_action(
    request: Request,
    data: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Perform bulk actions on multiple campaigns.

    Supported actions: pause, resume, archive
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    success_count = 0
    failures = []

    for campaign_id in data.campaign_ids:
        try:
            campaign = await get_campaign_or_404(db, campaign_id, org_id)

            target_status = {
                "pause": "paused",
                "resume": "active",
                "archive": "archived",
            }[data.action]

            if not campaign.can_transition_to(target_status):
                failures.append({
                    "campaign_id": campaign_id,
                    "error": f"Cannot {data.action} campaign in {campaign.status} status",
                })
                continue

            # Sync with platform for live campaigns
            if campaign.is_live or campaign.platform_campaign_id:
                if data.action == "pause":
                    platform_success = await pause_campaign_on_platform(campaign_id)
                    if not platform_success:
                        logger.warning(
                            "bulk_platform_pause_failed",
                            campaign_id=campaign_id,
                        )
                elif data.action == "resume":
                    platform_success = await resume_campaign_on_platform(campaign_id)
                    if not platform_success:
                        logger.warning(
                            "bulk_platform_resume_failed",
                            campaign_id=campaign_id,
                        )

            campaign.status = target_status
            campaign.updated_by_id = user_id

            await create_campaign_version(
                db=db,
                campaign=campaign,
                change_type="status_change",
                changed_by_id=user_id,
                change_summary=f"Bulk action: {data.action}",
            )

            success_count += 1

        except HTTPException as e:
            failures.append({
                "campaign_id": campaign_id,
                "error": e.detail,
            })

    await db.commit()

    logger.info(
        "bulk_action_completed",
        action=data.action,
        success_count=success_count,
        failure_count=len(failures),
        user_id=user_id,
    )

    return BulkActionResponse(
        success_count=success_count,
        failure_count=len(failures),
        failures=failures,
    )


@router.post("/{campaign_id}/duplicate", response_model=CampaignResponse)
async def duplicate_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Duplicate an existing campaign.

    Creates a copy in draft status.
    """
    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    original = await get_campaign_or_404(db, campaign_id, org_id)

    # Create copy
    new_campaign = Campaign(
        id=str(uuid4()),
        org_id=org_id,
        ad_account_id=original.ad_account_id,
        name=f"{original.name} (Copy)",
        description=original.description,
        platform=original.platform,
        objective=original.objective,
        status="draft",
        budget_type=original.budget_type,
        budget_amount=original.budget_amount,
        budget_currency=original.budget_currency,
        start_date=None,  # Reset dates
        end_date=None,
        is_ongoing=original.is_ongoing,
        targeting=original.targeting,
        platform_settings=original.platform_settings,
        created_by_id=user_id,
        version=1,
    )

    db.add(new_campaign)

    # Copy ad copies
    result = await db.execute(
        select(AdCopy).where(AdCopy.campaign_id == campaign_id)
    )
    ad_copies = result.scalars().all()

    for original_copy in ad_copies:
        new_copy = AdCopy(
            id=str(uuid4()),
            campaign_id=new_campaign.id,
            headline_1=original_copy.headline_1,
            headline_2=original_copy.headline_2,
            headline_3=original_copy.headline_3,
            description_1=original_copy.description_1,
            description_2=original_copy.description_2,
            path_1=original_copy.path_1,
            path_2=original_copy.path_2,
            final_url=original_copy.final_url,
            call_to_action=original_copy.call_to_action,
            variation_name=original_copy.variation_name,
            is_primary=original_copy.is_primary,
        )
        db.add(new_copy)

    # Create version
    await create_campaign_version(
        db=db,
        campaign=new_campaign,
        change_type="created",
        changed_by_id=user_id,
        change_summary=f"Duplicated from {original.name}",
    )

    await db.commit()
    await db.refresh(new_campaign)

    logger.info(
        "campaign_duplicated",
        original_id=campaign_id,
        new_id=new_campaign.id,
        user_id=user_id,
    )

    return new_campaign


# =============================================================================
# Approval Queue Endpoints
# =============================================================================

@router.get("/pending-approvals", response_model=CampaignListResponse)
async def list_pending_approvals(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List campaigns pending approval.

    For managers to review and approve/reject campaigns.
    """
    # TODO: Get current user's org_id
    # TODO: Verify user has manager or admin role
    org_id = "00000000-0000-0000-0000-000000000001"

    query = select(Campaign).where(
        Campaign.org_id == org_id,
        Campaign.status == "pending_review",
    )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    query = query.order_by(Campaign.updated_at.asc())  # Oldest first
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Platform Sync Endpoints
# =============================================================================

@router.post("/{campaign_id}/sync", response_model=CampaignResponse)
async def sync_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually sync a campaign's status from the platform.

    Fetches the current status from the ad platform and updates the local record.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if not campaign.platform_campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign is not yet published to a platform",
        )

    success = await sync_single_campaign(campaign_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync campaign from platform",
        )

    # Refresh and return updated campaign
    await db.refresh(campaign)

    logger.info(
        "campaign_synced",
        campaign_id=campaign_id,
    )

    return campaign


@router.post("/{campaign_id}/push", response_model=CampaignResponse)
async def push_campaign(
    request: Request,
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually push an approved campaign to the platform.

    Triggers immediate creation of the campaign on the ad platform.
    """
    # TODO: Get current user's org_id
    org_id = "00000000-0000-0000-0000-000000000001"

    campaign = await get_campaign_or_404(db, campaign_id, org_id)

    if campaign.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only approved campaigns can be pushed. Current status: {campaign.status}",
        )

    if campaign.platform_campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign has already been pushed to the platform",
        )

    success = await push_single_campaign(campaign_id)

    if not success:
        # Refresh to get any error message
        await db.refresh(campaign)
        error_msg = campaign.sync_error or "Failed to push campaign to platform"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    # Refresh and return updated campaign
    await db.refresh(campaign)

    logger.info(
        "campaign_pushed",
        campaign_id=campaign_id,
        platform_campaign_id=campaign.platform_campaign_id,
    )

    return campaign


# =============================================================================
# CSV Import Endpoints
# =============================================================================

class CSVImportResponse(BaseModel):
    """Response for CSV import."""
    created_count: int
    error_count: int
    errors: list[dict] = []
    campaign_ids: list[str] = []


@router.post("/import-csv", response_model=CSVImportResponse)
async def import_campaigns_csv(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Import campaigns from CSV data.

    Expects CSV with columns:
    - name (required): Campaign name
    - ad_account_id (required): Ad account ID
    - objective (required): awareness|traffic|engagement|leads|sales|app_promotion
    - budget_type: daily|lifetime (default: daily)
    - budget_amount (required): Budget amount (number)
    - budget_currency: Currency code (default: USD)
    - start_date: Start date (YYYY-MM-DD)
    - end_date: End date (YYYY-MM-DD)
    - is_ongoing: true|false (default: false)
    - description: Campaign description

    Creates all campaigns in draft status.
    """
    import csv
    import io

    # TODO: Get current user's org_id and user_id
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    # Read body as text
    body = await request.body()
    csv_text = body.decode("utf-8")

    created_count = 0
    errors = []
    campaign_ids = []

    try:
        reader = csv.DictReader(io.StringIO(csv_text))

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 = header)
            try:
                # Validate required fields
                if not row.get("name"):
                    errors.append({"row": row_num, "error": "Missing required field: name"})
                    continue
                if not row.get("ad_account_id"):
                    errors.append({"row": row_num, "error": "Missing required field: ad_account_id"})
                    continue
                if not row.get("objective"):
                    errors.append({"row": row_num, "error": "Missing required field: objective"})
                    continue
                if not row.get("budget_amount"):
                    errors.append({"row": row_num, "error": "Missing required field: budget_amount"})
                    continue

                # Validate objective
                valid_objectives = ["awareness", "traffic", "engagement", "leads", "sales", "app_promotion"]
                if row["objective"] not in valid_objectives:
                    errors.append({"row": row_num, "error": f"Invalid objective: {row['objective']}"})
                    continue

                # Parse budget
                try:
                    budget_amount = Decimal(row["budget_amount"])
                    if budget_amount <= 0:
                        raise ValueError("Budget must be positive")
                except (ValueError, TypeError):
                    errors.append({"row": row_num, "error": f"Invalid budget_amount: {row['budget_amount']}"})
                    continue

                # Parse dates
                start_date = None
                end_date = None
                if row.get("start_date"):
                    try:
                        start_date = date.fromisoformat(row["start_date"])
                    except ValueError:
                        errors.append({"row": row_num, "error": f"Invalid start_date format: {row['start_date']}"})
                        continue
                if row.get("end_date"):
                    try:
                        end_date = date.fromisoformat(row["end_date"])
                    except ValueError:
                        errors.append({"row": row_num, "error": f"Invalid end_date format: {row['end_date']}"})
                        continue

                # Parse is_ongoing
                is_ongoing = row.get("is_ongoing", "").lower() in ("true", "1", "yes")

                # Create campaign
                campaign = Campaign(
                    id=str(uuid4()),
                    org_id=org_id,
                    ad_account_id=row["ad_account_id"],
                    name=row["name"],
                    description=row.get("description"),
                    platform="google",  # TODO: Get from ad_account
                    objective=row["objective"],
                    status="draft",
                    budget_type=row.get("budget_type", "daily"),
                    budget_amount=budget_amount,
                    budget_currency=row.get("budget_currency", "USD"),
                    start_date=start_date,
                    end_date=end_date,
                    is_ongoing=is_ongoing,
                    created_by_id=user_id,
                    version=1,
                )

                db.add(campaign)

                # Create initial version
                await create_campaign_version(
                    db=db,
                    campaign=campaign,
                    change_type="created",
                    changed_by_id=user_id,
                    change_summary="Imported from CSV",
                )

                campaign_ids.append(campaign.id)
                created_count += 1

            except Exception as e:
                errors.append({"row": row_num, "error": str(e)})

        await db.commit()

    except csv.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid CSV format: {str(e)}",
        )

    logger.info(
        "csv_import_completed",
        created_count=created_count,
        error_count=len(errors),
        user_id=user_id,
    )

    return CSVImportResponse(
        created_count=created_count,
        error_count=len(errors),
        errors=errors,
        campaign_ids=campaign_ids,
    )


# =============================================================================
# Cross-Platform Campaign Creation
# =============================================================================

class MultiPlatformCampaignCreate(BaseModel):
    """Request to create campaign across multiple platforms."""
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    objective: str = Field(pattern="^(awareness|traffic|engagement|leads|sales|app_promotion)$")

    budget_type: str = Field(default="daily", pattern="^(daily|lifetime)$")
    budget_amount: Decimal = Field(gt=0, description="Budget per platform")

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_ongoing: bool = False

    targeting: Optional[dict] = None
    ad_copies: list[AdCopyCreate] = []

    # Platform to ad_account_id mapping
    platform_accounts: dict[str, str] = Field(
        description="Map of platform (google/meta/tiktok) to ad_account_id"
    )

    add_utm_tracking: bool = Field(
        default=True,
        description="Automatically add UTM parameters to URLs"
    )


class MultiPlatformCampaignResponse(BaseModel):
    """Response for multi-platform campaign creation."""
    campaigns: dict[str, CampaignResponse]
    created_count: int
    platforms: list[str]


@router.post("/multi-platform", response_model=MultiPlatformCampaignResponse)
async def create_multi_platform_campaign_endpoint(
    request: Request,
    data: MultiPlatformCampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a campaign across multiple ad platforms.

    Creates separate Campaign records for each specified platform
    with consistent settings and optional UTM tracking.
    """
    # TODO: Get from auth
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"

    from app.services.cross_platform_service import create_multi_platform_campaign

    # Convert ad copies to dict format
    ad_copies_data = [copy.model_dump() for copy in data.ad_copies] if data.ad_copies else None

    created_campaigns = await create_multi_platform_campaign(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=data.name,
        objective=data.objective,
        budget_amount=data.budget_amount,
        budget_type=data.budget_type,
        platform_account_ids=data.platform_accounts,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        is_ongoing=data.is_ongoing,
        targeting=data.targeting,
        ad_copies=ad_copies_data,
        add_utm_tracking=data.add_utm_tracking,
    )

    # Refresh campaigns to get ad_copies relationship
    for platform, campaign in created_campaigns.items():
        await db.refresh(campaign)

    return MultiPlatformCampaignResponse(
        campaigns={
            platform: CampaignResponse.model_validate(campaign)
            for platform, campaign in created_campaigns.items()
        },
        created_count=len(created_campaigns),
        platforms=list(created_campaigns.keys()),
    )

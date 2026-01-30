"""
Webhooks API endpoints.

Provides endpoints for:
- Webhook endpoint management
- Delivery history and logs
- Testing webhooks
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.webhook import WEBHOOK_EVENT_TYPES
from app.services.webhook_service import (
    create_webhook_endpoint,
    get_webhook_endpoint,
    list_webhook_endpoints,
    update_webhook_endpoint,
    delete_webhook_endpoint,
    regenerate_webhook_secret,
    get_delivery_history,
    get_delivery,
    resend_delivery,
    test_webhook_endpoint,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class WebhookEndpointCreate(BaseModel):
    """Create webhook endpoint request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    url: HttpUrl = Field(..., description="Webhook URL")
    events: list[str] = Field(..., min_items=1, description="Event types to subscribe to")
    headers: Optional[dict] = Field(default=None, description="Custom headers")


class WebhookEndpointUpdate(BaseModel):
    """Update webhook endpoint request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[list[str]] = Field(default=None, min_items=1)
    headers: Optional[dict] = None
    is_enabled: Optional[bool] = None


class WebhookEndpointResponse(BaseModel):
    """Webhook endpoint response."""

    id: str
    name: str
    description: Optional[str]
    url: str
    events: list[str]
    headers: dict
    is_enabled: bool
    is_verified: bool
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: Optional[str]
    last_delivery_status: Optional[str]
    created_at: str
    updated_at: str


class WebhookEndpointWithSecret(WebhookEndpointResponse):
    """Webhook endpoint response with secret (only shown on create)."""

    secret: str


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response."""

    id: str
    endpoint_id: str
    event_type: str
    event_id: str
    payload: dict
    status: str
    response_status_code: Optional[int]
    response_body: Optional[str]
    response_time_ms: Optional[int]
    error_message: Optional[str]
    attempt_count: int
    next_retry_at: Optional[str]
    created_at: str
    delivered_at: Optional[str]


class WebhookDeliveryListResponse(BaseModel):
    """List of webhook deliveries."""

    deliveries: list[WebhookDeliveryResponse]
    total: int


class WebhookEndpointListResponse(BaseModel):
    """List of webhook endpoints."""

    endpoints: list[WebhookEndpointResponse]
    total: int


class EventTypesResponse(BaseModel):
    """Available event types."""

    event_types: dict[str, str]


# =============================================================================
# Endpoint Management
# =============================================================================


@router.get("/event-types", response_model=EventTypesResponse)
async def get_event_types():
    """
    Get available webhook event types.

    Returns all event types that can be subscribed to.
    """
    return EventTypesResponse(event_types=WEBHOOK_EVENT_TYPES)


@router.get("", response_model=WebhookEndpointListResponse)
async def list_endpoints(
    is_enabled: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List webhook endpoints for the organization.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    endpoints, total = await list_webhook_endpoints(
        db=db,
        org_id=org_id,
        is_enabled=is_enabled,
        limit=page_size,
        offset=offset,
    )

    return WebhookEndpointListResponse(
        endpoints=[
            WebhookEndpointResponse(
                id=e.id,
                name=e.name,
                description=e.description,
                url=e.url,
                events=e.events,
                headers=e.headers,
                is_enabled=e.is_enabled,
                is_verified=e.is_verified,
                total_deliveries=e.total_deliveries,
                successful_deliveries=e.successful_deliveries,
                failed_deliveries=e.failed_deliveries,
                last_delivery_at=e.last_delivery_at.isoformat() if e.last_delivery_at else None,
                last_delivery_status=e.last_delivery_status,
                created_at=e.created_at.isoformat(),
                updated_at=e.updated_at.isoformat(),
            )
            for e in endpoints
        ],
        total=total,
    )


@router.post("", response_model=WebhookEndpointWithSecret, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    request: WebhookEndpointCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new webhook endpoint.

    Returns the endpoint with its secret (secret is only shown once).
    """
    # TODO: Get org_id and user_id from authenticated user
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    try:
        endpoint = await create_webhook_endpoint(
            db=db,
            org_id=org_id,
            name=request.name,
            url=str(request.url),
            events=request.events,
            description=request.description,
            headers=request.headers,
            created_by_id=user_id,
        )

        return WebhookEndpointWithSecret(
            id=endpoint.id,
            name=endpoint.name,
            description=endpoint.description,
            url=endpoint.url,
            events=endpoint.events,
            headers=endpoint.headers,
            is_enabled=endpoint.is_enabled,
            is_verified=endpoint.is_verified,
            total_deliveries=endpoint.total_deliveries,
            successful_deliveries=endpoint.successful_deliveries,
            failed_deliveries=endpoint.failed_deliveries,
            last_delivery_at=None,
            last_delivery_status=None,
            created_at=endpoint.created_at.isoformat(),
            updated_at=endpoint.updated_at.isoformat(),
            secret=endpoint.secret,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_endpoint(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a webhook endpoint by ID.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    endpoint = await get_webhook_endpoint(db, endpoint_id, org_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )

    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        description=endpoint.description,
        url=endpoint.url,
        events=endpoint.events,
        headers=endpoint.headers,
        is_enabled=endpoint.is_enabled,
        is_verified=endpoint.is_verified,
        total_deliveries=endpoint.total_deliveries,
        successful_deliveries=endpoint.successful_deliveries,
        failed_deliveries=endpoint.failed_deliveries,
        last_delivery_at=endpoint.last_delivery_at.isoformat() if endpoint.last_delivery_at else None,
        last_delivery_status=endpoint.last_delivery_status,
        created_at=endpoint.created_at.isoformat(),
        updated_at=endpoint.updated_at.isoformat(),
    )


@router.patch("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_endpoint(
    endpoint_id: str,
    request: WebhookEndpointUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a webhook endpoint.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        endpoint = await update_webhook_endpoint(
            db=db,
            endpoint_id=endpoint_id,
            org_id=org_id,
            name=request.name,
            description=request.description,
            url=str(request.url) if request.url else None,
            events=request.events,
            headers=request.headers,
            is_enabled=request.is_enabled,
        )

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook endpoint not found",
            )

        return WebhookEndpointResponse(
            id=endpoint.id,
            name=endpoint.name,
            description=endpoint.description,
            url=endpoint.url,
            events=endpoint.events,
            headers=endpoint.headers,
            is_enabled=endpoint.is_enabled,
            is_verified=endpoint.is_verified,
            total_deliveries=endpoint.total_deliveries,
            successful_deliveries=endpoint.successful_deliveries,
            failed_deliveries=endpoint.failed_deliveries,
            last_delivery_at=endpoint.last_delivery_at.isoformat() if endpoint.last_delivery_at else None,
            last_delivery_status=endpoint.last_delivery_status,
            created_at=endpoint.created_at.isoformat(),
            updated_at=endpoint.updated_at.isoformat(),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a webhook endpoint.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    deleted = await delete_webhook_endpoint(db, endpoint_id, org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )


@router.post("/{endpoint_id}/regenerate-secret")
async def regenerate_secret(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate the webhook secret.

    The new secret will be returned and must be updated in your system.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    secret = await regenerate_webhook_secret(db, endpoint_id, org_id)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )

    return {"secret": secret}


@router.post("/{endpoint_id}/test", response_model=WebhookDeliveryResponse)
async def test_endpoint(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a test event to a webhook endpoint.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    try:
        delivery = await test_webhook_endpoint(db, endpoint_id, org_id)

        return WebhookDeliveryResponse(
            id=delivery.id,
            endpoint_id=delivery.endpoint_id,
            event_type=delivery.event_type,
            event_id=delivery.event_id,
            payload=delivery.payload,
            status=delivery.status,
            response_status_code=delivery.response_status_code,
            response_body=delivery.response_body,
            response_time_ms=delivery.response_time_ms,
            error_message=delivery.error_message,
            attempt_count=delivery.attempt_count,
            next_retry_at=delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            created_at=delivery.created_at.isoformat(),
            delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# Delivery History
# =============================================================================


@router.get("/{endpoint_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_deliveries(
    endpoint_id: str,
    event_type: Optional[str] = Query(default=None),
    delivery_status: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get delivery history for a webhook endpoint.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    deliveries, total = await get_delivery_history(
        db=db,
        org_id=org_id,
        endpoint_id=endpoint_id,
        event_type=event_type,
        status=delivery_status,
        limit=page_size,
        offset=offset,
    )

    return WebhookDeliveryListResponse(
        deliveries=[
            WebhookDeliveryResponse(
                id=d.id,
                endpoint_id=d.endpoint_id,
                event_type=d.event_type,
                event_id=d.event_id,
                payload=d.payload,
                status=d.status,
                response_status_code=d.response_status_code,
                response_body=d.response_body,
                response_time_ms=d.response_time_ms,
                error_message=d.error_message,
                attempt_count=d.attempt_count,
                next_retry_at=d.next_retry_at.isoformat() if d.next_retry_at else None,
                created_at=d.created_at.isoformat(),
                delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
            )
            for d in deliveries
        ],
        total=total,
    )


@router.get("/deliveries/{delivery_id}", response_model=WebhookDeliveryResponse)
async def get_delivery_detail(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific delivery.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    delivery = await get_delivery(db, delivery_id, org_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    return WebhookDeliveryResponse(
        id=delivery.id,
        endpoint_id=delivery.endpoint_id,
        event_type=delivery.event_type,
        event_id=delivery.event_id,
        payload=delivery.payload,
        status=delivery.status,
        response_status_code=delivery.response_status_code,
        response_body=delivery.response_body,
        response_time_ms=delivery.response_time_ms,
        error_message=delivery.error_message,
        attempt_count=delivery.attempt_count,
        next_retry_at=delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
        created_at=delivery.created_at.isoformat(),
        delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None,
    )


@router.post("/deliveries/{delivery_id}/resend", response_model=WebhookDeliveryResponse)
async def resend_delivery_endpoint(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually resend a delivery.
    """
    # TODO: Get org_id from authenticated user
    org_id = "placeholder-org-id"

    delivery = await resend_delivery(db, delivery_id, org_id)
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found or endpoint disabled",
        )

    return WebhookDeliveryResponse(
        id=delivery.id,
        endpoint_id=delivery.endpoint_id,
        event_type=delivery.event_type,
        event_id=delivery.event_id,
        payload=delivery.payload,
        status=delivery.status,
        response_status_code=delivery.response_status_code,
        response_body=delivery.response_body,
        response_time_ms=delivery.response_time_ms,
        error_message=delivery.error_message,
        attempt_count=delivery.attempt_count,
        next_retry_at=delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
        created_at=delivery.created_at.isoformat(),
        delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None,
    )

"""
Webhook service for outbound event delivery.

Provides functions for:
- Creating and managing webhook endpoints
- Delivering events with HMAC signatures
- Retry logic with exponential backoff
- Delivery logging and monitoring
"""

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import httpx
import structlog
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEndpoint, WebhookDelivery, WEBHOOK_EVENT_TYPES

logger = structlog.get_logger()


# Retry schedule (seconds after previous attempt)
RETRY_SCHEDULE = [60, 300, 900, 3600, 7200]  # 1m, 5m, 15m, 1h, 2h


# =============================================================================
# Endpoint Management
# =============================================================================


def generate_webhook_secret() -> str:
    """Generate a secure webhook secret."""
    return secrets.token_hex(32)


async def create_webhook_endpoint(
    db: AsyncSession,
    org_id: str,
    name: str,
    url: str,
    events: list[str],
    description: Optional[str] = None,
    headers: Optional[dict] = None,
    created_by_id: Optional[str] = None,
) -> WebhookEndpoint:
    """
    Create a new webhook endpoint.

    Args:
        db: Database session
        org_id: Organization ID
        name: Endpoint name
        url: Webhook URL
        events: List of event types to subscribe to
        description: Optional description
        headers: Optional custom headers
        created_by_id: User who created the endpoint

    Returns:
        Created endpoint
    """
    # Validate events
    invalid_events = [e for e in events if e not in WEBHOOK_EVENT_TYPES]
    if invalid_events:
        raise ValueError(f"Invalid event types: {invalid_events}")

    endpoint = WebhookEndpoint(
        org_id=org_id,
        name=name,
        description=description,
        url=url,
        secret=generate_webhook_secret(),
        events=events,
        headers=headers or {},
        created_by_id=created_by_id,
    )
    db.add(endpoint)

    logger.info(
        "webhook_endpoint_created",
        org_id=org_id,
        endpoint_id=endpoint.id,
        name=name,
        events=events,
    )

    return endpoint


async def get_webhook_endpoint(
    db: AsyncSession,
    endpoint_id: str,
    org_id: Optional[str] = None,
) -> Optional[WebhookEndpoint]:
    """Get a webhook endpoint by ID."""
    query = select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
    if org_id:
        query = query.where(WebhookEndpoint.org_id == org_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_webhook_endpoints(
    db: AsyncSession,
    org_id: str,
    is_enabled: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[WebhookEndpoint], int]:
    """List webhook endpoints for an organization."""
    query = select(WebhookEndpoint).where(WebhookEndpoint.org_id == org_id)

    if is_enabled is not None:
        query = query.where(WebhookEndpoint.is_enabled == is_enabled)

    # Count
    count_result = await db.execute(
        select(func.count(WebhookEndpoint.id)).where(WebhookEndpoint.org_id == org_id)
    )
    total = count_result.scalar() or 0

    # Get endpoints
    result = await db.execute(
        query.order_by(WebhookEndpoint.created_at.desc()).offset(offset).limit(limit)
    )
    endpoints = list(result.scalars().all())

    return endpoints, total


async def update_webhook_endpoint(
    db: AsyncSession,
    endpoint_id: str,
    org_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    url: Optional[str] = None,
    events: Optional[list[str]] = None,
    headers: Optional[dict] = None,
    is_enabled: Optional[bool] = None,
) -> Optional[WebhookEndpoint]:
    """Update a webhook endpoint."""
    endpoint = await get_webhook_endpoint(db, endpoint_id, org_id)
    if not endpoint:
        return None

    if name is not None:
        endpoint.name = name
    if description is not None:
        endpoint.description = description
    if url is not None:
        endpoint.url = url
    if events is not None:
        invalid_events = [e for e in events if e not in WEBHOOK_EVENT_TYPES]
        if invalid_events:
            raise ValueError(f"Invalid event types: {invalid_events}")
        endpoint.events = events
    if headers is not None:
        endpoint.headers = headers
    if is_enabled is not None:
        endpoint.is_enabled = is_enabled

    return endpoint


async def delete_webhook_endpoint(
    db: AsyncSession,
    endpoint_id: str,
    org_id: str,
) -> bool:
    """Delete a webhook endpoint."""
    result = await db.execute(
        delete(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    return result.rowcount > 0


async def regenerate_webhook_secret(
    db: AsyncSession,
    endpoint_id: str,
    org_id: str,
) -> Optional[str]:
    """Regenerate the webhook secret for an endpoint."""
    endpoint = await get_webhook_endpoint(db, endpoint_id, org_id)
    if not endpoint:
        return None

    endpoint.secret = generate_webhook_secret()
    return endpoint.secret


# =============================================================================
# Event Delivery
# =============================================================================


def sign_payload(payload: dict, secret: str, timestamp: int) -> str:
    """
    Create HMAC signature for webhook payload.

    Signature format: v1=<hmac-sha256>
    Signed string: <timestamp>.<payload_json>
    """
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signed_string = f"{timestamp}.{payload_json}"

    signature = hmac.new(
        secret.encode("utf-8"),
        signed_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"v1={signature}"


async def deliver_webhook(
    db: AsyncSession,
    endpoint: WebhookEndpoint,
    event_type: str,
    event_data: dict,
    event_id: Optional[str] = None,
) -> WebhookDelivery:
    """
    Deliver a webhook event to an endpoint.

    Args:
        db: Database session
        endpoint: Webhook endpoint to deliver to
        event_type: Type of event
        event_data: Event payload data
        event_id: Optional event ID (generated if not provided)

    Returns:
        Delivery record
    """
    event_id = event_id or str(uuid4())
    timestamp = int(datetime.now(timezone.utc).timestamp())

    # Build payload
    payload = {
        "id": event_id,
        "type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": event_data,
    }

    # Create signature
    signature = sign_payload(payload, endpoint.secret, timestamp)

    # Create delivery record
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        org_id=endpoint.org_id,
        event_type=event_type,
        event_id=event_id,
        payload=payload,
        status="pending",
    )
    db.add(delivery)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AIMarketing-Webhook/1.0",
        "X-Webhook-ID": event_id,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Signature": signature,
        **endpoint.headers,
    }

    # Attempt delivery
    start_time = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint.url,
                json=payload,
                headers=headers,
                timeout=30.0,
            )

        response_time = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        delivery.response_status_code = response.status_code
        delivery.response_body = response.text[:10000] if response.text else None
        delivery.response_headers = dict(response.headers)
        delivery.response_time_ms = response_time

        if 200 <= response.status_code < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            endpoint.successful_deliveries += 1
        else:
            delivery.status = "failed"
            delivery.error_message = f"HTTP {response.status_code}"
            endpoint.failed_deliveries += 1
            _schedule_retry(delivery)

    except httpx.TimeoutException:
        delivery.status = "failed"
        delivery.error_message = "Request timeout"
        endpoint.failed_deliveries += 1
        _schedule_retry(delivery)

    except httpx.RequestError as e:
        delivery.status = "failed"
        delivery.error_message = str(e)
        endpoint.failed_deliveries += 1
        _schedule_retry(delivery)

    except Exception as e:
        delivery.status = "failed"
        delivery.error_message = f"Unexpected error: {str(e)}"
        endpoint.failed_deliveries += 1
        _schedule_retry(delivery)

    # Update endpoint stats
    endpoint.total_deliveries += 1
    endpoint.last_delivery_at = datetime.now(timezone.utc)
    endpoint.last_delivery_status = delivery.status

    logger.info(
        "webhook_delivered",
        endpoint_id=endpoint.id,
        event_type=event_type,
        event_id=event_id,
        status=delivery.status,
        response_code=delivery.response_status_code,
    )

    return delivery


def _schedule_retry(delivery: WebhookDelivery) -> None:
    """Schedule a retry for a failed delivery."""
    if delivery.attempt_count >= delivery.max_attempts:
        delivery.status = "failed"
        return

    retry_index = min(delivery.attempt_count - 1, len(RETRY_SCHEDULE) - 1)
    retry_delay = RETRY_SCHEDULE[retry_index]

    delivery.status = "retrying"
    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)


async def retry_webhook_delivery(
    db: AsyncSession,
    delivery: WebhookDelivery,
) -> WebhookDelivery:
    """
    Retry a failed webhook delivery.

    Args:
        db: Database session
        delivery: Delivery to retry

    Returns:
        Updated delivery record
    """
    endpoint = await get_webhook_endpoint(db, delivery.endpoint_id)
    if not endpoint or not endpoint.is_enabled:
        delivery.status = "failed"
        delivery.error_message = "Endpoint disabled or not found"
        return delivery

    delivery.attempt_count += 1
    delivery.next_retry_at = None

    # Re-sign and deliver
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signature = sign_payload(delivery.payload, endpoint.secret, timestamp)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AIMarketing-Webhook/1.0",
        "X-Webhook-ID": delivery.event_id,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Signature": signature,
        "X-Webhook-Retry": str(delivery.attempt_count),
        **endpoint.headers,
    }

    start_time = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint.url,
                json=delivery.payload,
                headers=headers,
                timeout=30.0,
            )

        response_time = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        delivery.response_status_code = response.status_code
        delivery.response_body = response.text[:10000] if response.text else None
        delivery.response_headers = dict(response.headers)
        delivery.response_time_ms = response_time

        if 200 <= response.status_code < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            endpoint.successful_deliveries += 1
        else:
            delivery.error_message = f"HTTP {response.status_code}"
            endpoint.failed_deliveries += 1
            _schedule_retry(delivery)

    except Exception as e:
        delivery.error_message = str(e)
        endpoint.failed_deliveries += 1
        _schedule_retry(delivery)

    logger.info(
        "webhook_retry_attempted",
        endpoint_id=endpoint.id,
        delivery_id=delivery.id,
        attempt=delivery.attempt_count,
        status=delivery.status,
    )

    return delivery


async def get_pending_retries(
    db: AsyncSession,
    limit: int = 100,
) -> list[WebhookDelivery]:
    """Get deliveries that are ready for retry."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status == "retrying",
            WebhookDelivery.next_retry_at <= now,
        )
        .order_by(WebhookDelivery.next_retry_at)
        .limit(limit)
    )
    return list(result.scalars().all())


# =============================================================================
# Broadcasting Events
# =============================================================================


async def broadcast_event(
    db: AsyncSession,
    org_id: str,
    event_type: str,
    event_data: dict,
) -> list[WebhookDelivery]:
    """
    Broadcast an event to all subscribed webhooks.

    Args:
        db: Database session
        org_id: Organization ID
        event_type: Type of event
        event_data: Event payload data

    Returns:
        List of delivery records
    """
    # Find all enabled endpoints subscribed to this event
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.org_id == org_id,
            WebhookEndpoint.is_enabled == True,
        )
    )
    endpoints = result.scalars().all()

    # Filter to those subscribed to this event type
    subscribed = [e for e in endpoints if event_type in e.events]

    if not subscribed:
        return []

    # Deliver to each endpoint
    event_id = str(uuid4())  # Same event ID for all deliveries
    deliveries = []

    for endpoint in subscribed:
        delivery = await deliver_webhook(
            db=db,
            endpoint=endpoint,
            event_type=event_type,
            event_data=event_data,
            event_id=event_id,
        )
        deliveries.append(delivery)

    return deliveries


# =============================================================================
# Delivery History
# =============================================================================


async def get_delivery_history(
    db: AsyncSession,
    org_id: str,
    endpoint_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WebhookDelivery], int]:
    """Get webhook delivery history."""
    query = select(WebhookDelivery).where(WebhookDelivery.org_id == org_id)

    if endpoint_id:
        query = query.where(WebhookDelivery.endpoint_id == endpoint_id)
    if event_type:
        query = query.where(WebhookDelivery.event_type == event_type)
    if status:
        query = query.where(WebhookDelivery.status == status)

    # Count
    count_query = select(func.count(WebhookDelivery.id)).where(
        WebhookDelivery.org_id == org_id
    )
    if endpoint_id:
        count_query = count_query.where(WebhookDelivery.endpoint_id == endpoint_id)
    if event_type:
        count_query = count_query.where(WebhookDelivery.event_type == event_type)
    if status:
        count_query = count_query.where(WebhookDelivery.status == status)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get deliveries
    result = await db.execute(
        query.order_by(WebhookDelivery.created_at.desc()).offset(offset).limit(limit)
    )
    deliveries = list(result.scalars().all())

    return deliveries, total


async def get_delivery(
    db: AsyncSession,
    delivery_id: str,
    org_id: str,
) -> Optional[WebhookDelivery]:
    """Get a specific delivery by ID."""
    result = await db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.org_id == org_id,
        )
    )
    return result.scalar_one_or_none()


async def resend_delivery(
    db: AsyncSession,
    delivery_id: str,
    org_id: str,
) -> Optional[WebhookDelivery]:
    """
    Manually resend a delivery.

    Creates a new delivery attempt for the same event.
    """
    original = await get_delivery(db, delivery_id, org_id)
    if not original:
        return None

    endpoint = await get_webhook_endpoint(db, original.endpoint_id, org_id)
    if not endpoint or not endpoint.is_enabled:
        return None

    return await deliver_webhook(
        db=db,
        endpoint=endpoint,
        event_type=original.event_type,
        event_data=original.payload["data"],
        event_id=original.event_id,
    )


# =============================================================================
# Testing
# =============================================================================


async def test_webhook_endpoint(
    db: AsyncSession,
    endpoint_id: str,
    org_id: str,
) -> WebhookDelivery:
    """
    Send a test event to a webhook endpoint.

    Args:
        db: Database session
        endpoint_id: Endpoint ID
        org_id: Organization ID

    Returns:
        Delivery record
    """
    endpoint = await get_webhook_endpoint(db, endpoint_id, org_id)
    if not endpoint:
        raise ValueError("Endpoint not found")

    test_data = {
        "message": "This is a test webhook event",
        "endpoint_id": endpoint_id,
        "org_id": org_id,
    }

    return await deliver_webhook(
        db=db,
        endpoint=endpoint,
        event_type="test",
        event_data=test_data,
    )

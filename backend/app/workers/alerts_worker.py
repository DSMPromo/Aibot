"""
Alerts Worker

Background jobs for checking and triggering alerts.
Runs periodically to evaluate all enabled alerts.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.user import Organization
from app.services.alerts_service import check_and_trigger_alerts

logger = structlog.get_logger()


async def check_all_alerts(ctx: dict) -> dict:
    """
    Check all alerts across all organizations.

    This job runs periodically (e.g., every 15 minutes) to evaluate
    all enabled alerts and trigger notifications for any that exceed
    their thresholds.

    Args:
        ctx: Worker context

    Returns:
        dict with status and counts
    """
    logger.info("Starting alert check job")
    start_time = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        # Get all organizations
        org_query = select(Organization.id)
        org_result = await db.execute(org_query)
        org_ids = [str(org_id) for org_id in org_result.scalars().all()]

        total_triggered = 0
        orgs_checked = 0

        for org_id in org_ids:
            try:
                triggered = await check_and_trigger_alerts(db, org_id)
                total_triggered += len(triggered)
                orgs_checked += 1

                if triggered:
                    logger.info(
                        "Alerts triggered for organization",
                        org_id=org_id,
                        triggered_count=len(triggered),
                    )

            except Exception as e:
                logger.error(
                    "Failed to check alerts for organization",
                    org_id=org_id,
                    error=str(e),
                )

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    logger.info(
        "Alert check job completed",
        orgs_checked=orgs_checked,
        total_triggered=total_triggered,
        duration_seconds=duration,
    )

    return {
        "status": "completed",
        "orgs_checked": orgs_checked,
        "total_triggered": total_triggered,
        "duration_seconds": duration,
    }

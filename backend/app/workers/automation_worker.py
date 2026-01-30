"""
Automation Worker

Background jobs for rule evaluation and action execution.
Runs every 5 minutes to evaluate all active automation rules.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.automation import AutomationRule
from app.models.campaign import Campaign
from app.models.user import Organization
from app.services.automation_service import (
    evaluate_rule,
    execute_rule_actions,
    expire_pending_actions,
)

logger = structlog.get_logger()


async def evaluate_automation_rules(ctx: dict) -> dict:
    """
    Evaluate all active automation rules.

    This job runs every 5 minutes to:
    1. Find all active rules
    2. Check if rules are due for evaluation (respecting cooldown)
    3. Evaluate conditions against current metrics
    4. Execute actions for triggered rules
    5. Expire pending actions that have timed out

    Args:
        ctx: Worker context

    Returns:
        dict with status and counts
    """
    logger.info("Starting automation rules evaluation")
    start_time = datetime.now(timezone.utc)

    rules_evaluated = 0
    rules_triggered = 0
    errors = 0

    async with async_session_maker() as db:
        # First, expire any pending actions
        expired_count = await expire_pending_actions(db)
        if expired_count > 0:
            logger.info(f"Expired {expired_count} pending actions")

        # Get all active rules
        rules_query = select(AutomationRule).where(
            AutomationRule.status == "active"
        )

        rules_result = await db.execute(rules_query)
        rules = rules_result.scalars().all()

        for rule in rules:
            try:
                # Check cooldown
                if rule.last_triggered_at:
                    cooldown_end = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
                    if datetime.now(timezone.utc) < cooldown_end:
                        continue

                # Check max executions per day
                if rule.max_executions_per_day:
                    # Count today's executions
                    today_start = datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    from app.models.automation import RuleExecution
                    exec_count_query = select(RuleExecution).where(
                        RuleExecution.rule_id == rule.id,
                        RuleExecution.executed_at >= today_start,
                    )
                    exec_result = await db.execute(exec_count_query)
                    today_executions = len(exec_result.scalars().all())

                    if today_executions >= rule.max_executions_per_day:
                        continue

                # Check schedule (if configured)
                if rule.schedule:
                    if not is_within_schedule(rule.schedule):
                        continue

                # Evaluate the rule
                if rule.scope_type == "campaign" and rule.campaign_id:
                    # Evaluate for specific campaign
                    evaluation = await evaluate_rule(db, rule, rule.campaign_id)
                    rules_evaluated += 1

                    if evaluation.triggered:
                        await execute_rule_actions(db, rule, evaluation, rule.campaign_id)
                        rules_triggered += 1
                        logger.info(
                            "Rule triggered",
                            rule_id=rule.id,
                            rule_name=rule.name,
                            campaign_id=rule.campaign_id,
                            reason=evaluation.trigger_reason,
                        )

                elif rule.scope_type == "org":
                    # Evaluate for all campaigns in org
                    campaigns_query = select(Campaign).where(
                        Campaign.org_id == rule.org_id,
                        Campaign.status.in_(["active", "paused"]),
                    )
                    campaigns_result = await db.execute(campaigns_query)
                    campaigns = campaigns_result.scalars().all()

                    for campaign in campaigns:
                        # Filter by platform if specified
                        if rule.platform and campaign.platform != rule.platform:
                            continue

                        evaluation = await evaluate_rule(db, rule, campaign.id)
                        rules_evaluated += 1

                        if evaluation.triggered:
                            await execute_rule_actions(db, rule, evaluation, campaign.id)
                            rules_triggered += 1
                            logger.info(
                                "Rule triggered",
                                rule_id=rule.id,
                                rule_name=rule.name,
                                campaign_id=campaign.id,
                                reason=evaluation.trigger_reason,
                            )

                # Update last evaluated time
                rule.last_evaluated_at = datetime.now(timezone.utc)
                await db.commit()

            except Exception as e:
                errors += 1
                logger.error(
                    "Error evaluating rule",
                    rule_id=rule.id,
                    error=str(e),
                )

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    logger.info(
        "Automation rules evaluation completed",
        rules_evaluated=rules_evaluated,
        rules_triggered=rules_triggered,
        errors=errors,
        expired_actions=expired_count,
        duration_seconds=duration,
    )

    return {
        "status": "completed",
        "rules_evaluated": rules_evaluated,
        "rules_triggered": rules_triggered,
        "errors": errors,
        "expired_actions": expired_count,
        "duration_seconds": duration,
    }


def is_within_schedule(schedule: dict) -> bool:
    """
    Check if current time is within the rule's schedule.

    Args:
        schedule: Schedule configuration

    Returns:
        True if within schedule, False otherwise
    """
    import pytz
    from datetime import time

    now = datetime.now(timezone.utc)

    schedule_type = schedule.get("type")
    tz_name = schedule.get("timezone", "UTC")

    try:
        tz = pytz.timezone(tz_name)
        local_now = now.astimezone(tz)
    except:
        local_now = now

    if schedule_type == "time_range":
        # Check if current time is within start_time and end_time
        start_str = schedule.get("start_time", "00:00")
        end_str = schedule.get("end_time", "23:59")

        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()

        current_time = local_now.time()

        # Handle overnight schedules (e.g., 22:00 to 06:00)
        if start_time <= end_time:
            if not (start_time <= current_time <= end_time):
                return False
        else:
            if not (current_time >= start_time or current_time <= end_time):
                return False

        # Check days of week if specified
        days_of_week = schedule.get("days_of_week")
        if days_of_week:
            # Python: Monday=0, Sunday=6
            if local_now.weekday() not in days_of_week:
                return False

    elif schedule_type == "days_of_week":
        days_of_week = schedule.get("days_of_week", [])
        if local_now.weekday() not in days_of_week:
            return False

    elif schedule_type == "specific_dates":
        dates = schedule.get("dates", [])
        current_date = local_now.strftime("%Y-%m-%d")
        if current_date not in dates:
            return False

    return True


async def run_single_rule(ctx: dict, rule_id: str) -> dict:
    """
    Manually run a single rule.

    Used for testing or manual execution.

    Args:
        ctx: Worker context
        rule_id: Rule ID to execute

    Returns:
        dict with execution results
    """
    logger.info("Manually running rule", rule_id=rule_id)

    async with async_session_maker() as db:
        rule_query = select(AutomationRule).where(AutomationRule.id == rule_id)
        rule_result = await db.execute(rule_query)
        rule = rule_result.scalar_one_or_none()

        if not rule:
            return {"status": "error", "message": "Rule not found"}

        if rule.scope_type == "campaign" and rule.campaign_id:
            evaluation = await evaluate_rule(db, rule, rule.campaign_id)

            if evaluation.triggered:
                execution = await execute_rule_actions(db, rule, evaluation, rule.campaign_id)
                return {
                    "status": "triggered",
                    "execution_id": execution.id,
                    "trigger_reason": evaluation.trigger_reason,
                }
            else:
                return {
                    "status": "not_triggered",
                    "condition_results": [
                        {
                            "metric": cr.metric,
                            "current_value": cr.current_value,
                            "threshold": cr.threshold,
                            "passed": cr.passed,
                        }
                        for cr in evaluation.condition_results
                    ],
                }
        else:
            # For org-wide rules, evaluate and show summary
            campaigns_query = select(Campaign).where(
                Campaign.org_id == rule.org_id,
                Campaign.status.in_(["active", "paused"]),
            )
            campaigns_result = await db.execute(campaigns_query)
            campaigns = campaigns_result.scalars().all()

            triggered_count = 0
            results = []

            for campaign in campaigns:
                if rule.platform and campaign.platform != rule.platform:
                    continue

                evaluation = await evaluate_rule(db, rule, campaign.id)

                if evaluation.triggered:
                    execution = await execute_rule_actions(db, rule, evaluation, campaign.id)
                    triggered_count += 1
                    results.append({
                        "campaign_id": campaign.id,
                        "campaign_name": campaign.name,
                        "triggered": True,
                        "execution_id": execution.id,
                    })
                else:
                    results.append({
                        "campaign_id": campaign.id,
                        "campaign_name": campaign.name,
                        "triggered": False,
                    })

            return {
                "status": "completed",
                "campaigns_checked": len(campaigns),
                "triggered_count": triggered_count,
                "results": results,
            }

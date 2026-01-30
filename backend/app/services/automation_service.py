"""
Automation Service

Provides core automation rule functionality:
- Rule evaluation against metrics
- Action execution
- Pending action management
- Rule lifecycle management
"""

from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional, Any
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import (
    AutomationRule,
    RuleExecution,
    PendingAction,
    RuleTemplate,
    CONDITION_TYPES,
    ACTION_TYPES,
    OPERATOR_LABELS,
)
from app.models.metrics import CampaignMetrics, Notification
from app.models.campaign import Campaign

logger = structlog.get_logger()


@dataclass
class ConditionResult:
    """Result of evaluating a single condition."""
    metric: str
    operator: str
    threshold: float
    current_value: float
    passed: bool
    lookback_days: int


@dataclass
class EvaluationResult:
    """Result of evaluating a rule."""
    rule_id: str
    triggered: bool
    condition_results: list[ConditionResult] = field(default_factory=list)
    trigger_reason: str = ""
    metrics_snapshot: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of executing an action."""
    action_type: str
    status: str  # success, failed, pending_approval
    details: str
    error: Optional[str] = None


# =============================================================================
# Rule CRUD Operations
# =============================================================================

async def get_rules(
    db: AsyncSession,
    org_id: str,
    status: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AutomationRule], int]:
    """Get automation rules for an organization."""
    conditions = [AutomationRule.org_id == org_id]

    if status:
        conditions.append(AutomationRule.status == status)
    if campaign_id:
        conditions.append(AutomationRule.campaign_id == campaign_id)

    count_query = select(func.count(AutomationRule.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = (
        select(AutomationRule)
        .where(and_(*conditions))
        .order_by(AutomationRule.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    rules = list(result.scalars().all())

    return rules, total


async def get_rule(
    db: AsyncSession,
    rule_id: str,
    org_id: str,
) -> Optional[AutomationRule]:
    """Get a specific rule."""
    query = select(AutomationRule).where(
        AutomationRule.id == rule_id,
        AutomationRule.org_id == org_id,
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_rule(
    db: AsyncSession,
    org_id: str,
    name: str,
    conditions: dict,
    actions: list,
    description: Optional[str] = None,
    scope_type: str = "org",
    campaign_id: Optional[str] = None,
    platform: Optional[str] = None,
    condition_logic: str = "and",
    requires_approval: bool = False,
    approval_timeout_hours: int = 24,
    cooldown_minutes: int = 60,
    schedule: Optional[dict] = None,
    template_id: Optional[str] = None,
    created_by_id: Optional[str] = None,
) -> AutomationRule:
    """Create a new automation rule."""
    rule = AutomationRule(
        org_id=org_id,
        name=name,
        description=description,
        conditions=conditions,
        actions=actions,
        scope_type=scope_type,
        campaign_id=campaign_id,
        platform=platform,
        condition_logic=condition_logic,
        requires_approval=requires_approval,
        approval_timeout_hours=approval_timeout_hours,
        cooldown_minutes=cooldown_minutes,
        schedule=schedule,
        template_id=template_id,
        created_by_id=created_by_id,
        status="draft",
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return rule


async def update_rule(
    db: AsyncSession,
    rule: AutomationRule,
    **kwargs,
) -> AutomationRule:
    """Update an automation rule."""
    for field, value in kwargs.items():
        if hasattr(rule, field) and field not in ("id", "org_id", "created_at"):
            setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)

    return rule


async def delete_rule(
    db: AsyncSession,
    rule: AutomationRule,
) -> None:
    """Delete an automation rule."""
    await db.delete(rule)
    await db.commit()


# =============================================================================
# Rule Evaluation
# =============================================================================

async def get_metric_value(
    db: AsyncSession,
    org_id: str,
    campaign_id: Optional[str],
    metric: str,
    lookback_days: int,
) -> tuple[float, dict]:
    """
    Get the current value of a metric.

    Returns tuple of (metric_value, metrics_snapshot)
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Build campaign filter
    if campaign_id:
        campaign_filter = CampaignMetrics.campaign_id == campaign_id
    else:
        # Get all campaigns for this org
        campaign_query = select(Campaign.id).where(Campaign.org_id == org_id)
        campaign_result = await db.execute(campaign_query)
        campaign_ids = [str(c) for c in campaign_result.scalars().all()]

        if not campaign_ids:
            return 0.0, {}

        campaign_filter = CampaignMetrics.campaign_id.in_(campaign_ids)

    # Get metrics
    metrics_query = select(CampaignMetrics).where(
        campaign_filter,
        CampaignMetrics.timestamp >= start_datetime,
        CampaignMetrics.timestamp <= end_datetime,
        CampaignMetrics.granularity == "raw",
    )

    metrics_result = await db.execute(metrics_query)
    metrics_rows = metrics_result.scalars().all()

    if not metrics_rows:
        return 0.0, {}

    # Calculate aggregates
    total_impressions = sum(r.impressions or 0 for r in metrics_rows)
    total_clicks = sum(r.clicks or 0 for r in metrics_rows)
    total_spend = sum(Decimal(str(r.spend or 0)) for r in metrics_rows)
    total_conversions = sum(r.conversions or 0 for r in metrics_rows)
    total_conversion_value = sum(Decimal(str(r.conversion_value or 0)) for r in metrics_rows)

    # Build snapshot
    snapshot = {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "spend": float(total_spend),
        "conversions": total_conversions,
        "conversion_value": float(total_conversion_value),
        "lookback_days": lookback_days,
    }

    # Calculate the requested metric
    if metric == "cpa":
        value = float(total_spend / total_conversions) if total_conversions > 0 else 0
        snapshot["cpa"] = value
    elif metric == "roas":
        value = float(total_conversion_value / total_spend) if total_spend > 0 else 0
        snapshot["roas"] = value
    elif metric == "ctr":
        value = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        snapshot["ctr"] = value
    elif metric == "cpc":
        value = float(total_spend / total_clicks) if total_clicks > 0 else 0
        snapshot["cpc"] = value
    elif metric == "spend":
        value = float(total_spend)
    elif metric == "impressions":
        value = float(total_impressions)
    elif metric == "clicks":
        value = float(total_clicks)
    elif metric == "conversions":
        value = float(total_conversions)
    else:
        value = 0

    return value, snapshot


def evaluate_condition(
    current_value: float,
    operator: str,
    threshold: float,
) -> bool:
    """Evaluate a single condition."""
    if operator == "gt":
        return current_value > threshold
    elif operator == "lt":
        return current_value < threshold
    elif operator == "gte":
        return current_value >= threshold
    elif operator == "lte":
        return current_value <= threshold
    elif operator == "eq":
        return current_value == threshold
    elif operator == "neq":
        return current_value != threshold
    else:
        return False


async def evaluate_rule(
    db: AsyncSession,
    rule: AutomationRule,
    campaign_id: Optional[str] = None,
) -> EvaluationResult:
    """
    Evaluate a rule's conditions against current metrics.

    Args:
        db: Database session
        rule: The rule to evaluate
        campaign_id: Optional specific campaign to check

    Returns:
        EvaluationResult with condition results and trigger status
    """
    result = EvaluationResult(
        rule_id=rule.id,
        triggered=False,
        condition_results=[],
        metrics_snapshot={},
    )

    # Use rule's campaign_id if scope is campaign, otherwise use provided
    target_campaign_id = rule.campaign_id if rule.scope_type == "campaign" else campaign_id

    # Get conditions from rule
    conditions_config = rule.conditions
    condition_list = conditions_config.get("conditions", [])

    if not condition_list:
        return result

    condition_results = []
    all_snapshots = {}

    for cond in condition_list:
        metric = cond.get("metric")
        operator = cond.get("operator")
        threshold = float(cond.get("value", 0))
        lookback_days = int(cond.get("lookback_days", 7))

        # Get current metric value
        current_value, snapshot = await get_metric_value(
            db=db,
            org_id=rule.org_id,
            campaign_id=target_campaign_id,
            metric=metric,
            lookback_days=lookback_days,
        )

        all_snapshots.update(snapshot)

        # Evaluate condition
        passed = evaluate_condition(current_value, operator, threshold)

        condition_results.append(ConditionResult(
            metric=metric,
            operator=operator,
            threshold=threshold,
            current_value=current_value,
            passed=passed,
            lookback_days=lookback_days,
        ))

    # Apply logic (AND/OR)
    if rule.condition_logic == "and":
        triggered = all(cr.passed for cr in condition_results)
    else:  # or
        triggered = any(cr.passed for cr in condition_results)

    # Build trigger reason
    if triggered:
        reasons = []
        for cr in condition_results:
            if cr.passed:
                op_label = OPERATOR_LABELS.get(cr.operator, cr.operator)
                reasons.append(
                    f"{cr.metric.upper()} ({cr.current_value:.2f}) is {op_label} {cr.threshold:.2f}"
                )
        trigger_reason = "; ".join(reasons)
    else:
        trigger_reason = ""

    result.triggered = triggered
    result.condition_results = condition_results
    result.trigger_reason = trigger_reason
    result.metrics_snapshot = all_snapshots

    return result


# =============================================================================
# Action Execution
# =============================================================================

async def execute_action(
    db: AsyncSession,
    rule: AutomationRule,
    action: dict,
    campaign_id: Optional[str],
    trigger_reason: str,
) -> ActionResult:
    """
    Execute a single action.

    Args:
        db: Database session
        rule: The rule triggering this action
        action: Action configuration
        campaign_id: Campaign to act on
        trigger_reason: Why the action was triggered

    Returns:
        ActionResult with status and details
    """
    action_type = action.get("type")
    params = action.get("params", {})

    try:
        if action_type == "pause_campaign":
            if not campaign_id:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="No campaign specified",
                    error="Campaign ID required for pause action",
                )

            # Get campaign and update status
            campaign_query = select(Campaign).where(Campaign.id == campaign_id)
            campaign_result = await db.execute(campaign_query)
            campaign = campaign_result.scalar_one_or_none()

            if not campaign:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="Campaign not found",
                    error=f"Campaign {campaign_id} not found",
                )

            if campaign.status == "paused":
                return ActionResult(
                    action_type=action_type,
                    status="success",
                    details="Campaign already paused",
                )

            campaign.status = "paused"
            # TODO: Also pause on ad platform via adapter

            return ActionResult(
                action_type=action_type,
                status="success",
                details=f"Campaign '{campaign.name}' paused",
            )

        elif action_type == "resume_campaign":
            if not campaign_id:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="No campaign specified",
                    error="Campaign ID required for resume action",
                )

            campaign_query = select(Campaign).where(Campaign.id == campaign_id)
            campaign_result = await db.execute(campaign_query)
            campaign = campaign_result.scalar_one_or_none()

            if not campaign:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="Campaign not found",
                    error=f"Campaign {campaign_id} not found",
                )

            if campaign.status == "active":
                return ActionResult(
                    action_type=action_type,
                    status="success",
                    details="Campaign already active",
                )

            campaign.status = "active"
            # TODO: Also resume on ad platform via adapter

            return ActionResult(
                action_type=action_type,
                status="success",
                details=f"Campaign '{campaign.name}' resumed",
            )

        elif action_type == "notify":
            channels = params.get("channels", ["in_app"])
            notifications_sent = 0

            if "in_app" in channels:
                # Create in-app notification
                notification = Notification(
                    user_id=rule.created_by_id or "00000000-0000-0000-0000-000000000002",
                    org_id=rule.org_id,
                    title=f"Automation: {rule.name}",
                    message=trigger_reason,
                    notification_type="automation",
                    related_entity_type="automation_rule",
                    related_entity_id=rule.id,
                    data={
                        "rule_id": rule.id,
                        "campaign_id": campaign_id,
                    },
                )
                db.add(notification)
                notifications_sent += 1

            # TODO: Implement email and other channels

            return ActionResult(
                action_type=action_type,
                status="success",
                details=f"Notification sent to {notifications_sent} recipients",
            )

        elif action_type == "adjust_budget":
            change_percent = float(params.get("change_percent", 0))

            if not campaign_id:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="No campaign specified",
                    error="Campaign ID required for budget adjustment",
                )

            campaign_query = select(Campaign).where(Campaign.id == campaign_id)
            campaign_result = await db.execute(campaign_query)
            campaign = campaign_result.scalar_one_or_none()

            if not campaign:
                return ActionResult(
                    action_type=action_type,
                    status="failed",
                    details="Campaign not found",
                )

            # Calculate new budget
            current_budget = float(campaign.budget_amount or 0)
            new_budget = current_budget * (1 + change_percent / 100)
            new_budget = max(0, new_budget)  # Don't go negative

            campaign.budget_amount = Decimal(str(round(new_budget, 2)))
            # TODO: Also update on ad platform via adapter

            return ActionResult(
                action_type=action_type,
                status="success",
                details=f"Budget adjusted from ${current_budget:.2f} to ${new_budget:.2f} ({change_percent:+.0f}%)",
            )

        else:
            return ActionResult(
                action_type=action_type,
                status="failed",
                details=f"Unknown action type: {action_type}",
                error="Unsupported action type",
            )

    except Exception as e:
        logger.error("Action execution failed", action_type=action_type, error=str(e))
        return ActionResult(
            action_type=action_type,
            status="failed",
            details="Action execution failed",
            error=str(e),
        )


async def execute_rule_actions(
    db: AsyncSession,
    rule: AutomationRule,
    evaluation: EvaluationResult,
    campaign_id: Optional[str] = None,
) -> RuleExecution:
    """
    Execute all actions for a triggered rule.

    Args:
        db: Database session
        rule: The triggered rule
        evaluation: Evaluation result
        campaign_id: Campaign that triggered the rule

    Returns:
        RuleExecution record
    """
    target_campaign_id = rule.campaign_id if rule.scope_type == "campaign" else campaign_id

    # Check if requires approval
    if rule.requires_approval:
        # Create pending actions instead of executing immediately
        expires_at = datetime.now(timezone.utc) + timedelta(hours=rule.approval_timeout_hours)

        for action in rule.actions:
            pending = PendingAction(
                rule_id=rule.id,
                org_id=rule.org_id,
                campaign_id=target_campaign_id,
                action_type=action.get("type"),
                action_params=action.get("params", {}),
                trigger_reason=evaluation.trigger_reason,
                condition_results={
                    "conditions": [
                        {
                            "metric": cr.metric,
                            "operator": cr.operator,
                            "threshold": cr.threshold,
                            "current_value": cr.current_value,
                            "passed": cr.passed,
                        }
                        for cr in evaluation.condition_results
                    ],
                    "overall_passed": evaluation.triggered,
                },
                metrics_snapshot=evaluation.metrics_snapshot,
                expires_at=expires_at,
            )
            db.add(pending)

        # Create execution record with pending status
        execution = RuleExecution(
            rule_id=rule.id,
            org_id=rule.org_id,
            campaign_id=target_campaign_id,
            trigger_reason=evaluation.trigger_reason,
            condition_results={
                "conditions": [
                    {
                        "metric": cr.metric,
                        "operator": cr.operator,
                        "threshold": cr.threshold,
                        "current_value": cr.current_value,
                        "passed": cr.passed,
                    }
                    for cr in evaluation.condition_results
                ],
                "overall_passed": evaluation.triggered,
            },
            actions_executed=[
                {"type": a.get("type"), "status": "pending_approval"}
                for a in rule.actions
            ],
            status="pending_approval",
            metrics_snapshot=evaluation.metrics_snapshot,
        )
    else:
        # Execute actions immediately
        action_results = []
        all_success = True

        for action in rule.actions:
            result = await execute_action(
                db=db,
                rule=rule,
                action=action,
                campaign_id=target_campaign_id,
                trigger_reason=evaluation.trigger_reason,
            )
            action_results.append({
                "type": result.action_type,
                "status": result.status,
                "details": result.details,
                "error": result.error,
            })
            if result.status == "failed":
                all_success = False

        # Create execution record
        execution = RuleExecution(
            rule_id=rule.id,
            org_id=rule.org_id,
            campaign_id=target_campaign_id,
            trigger_reason=evaluation.trigger_reason,
            condition_results={
                "conditions": [
                    {
                        "metric": cr.metric,
                        "operator": cr.operator,
                        "threshold": cr.threshold,
                        "current_value": cr.current_value,
                        "passed": cr.passed,
                    }
                    for cr in evaluation.condition_results
                ],
                "overall_passed": evaluation.triggered,
            },
            actions_executed=action_results,
            status="completed" if all_success else "partial",
            metrics_snapshot=evaluation.metrics_snapshot,
        )

    db.add(execution)

    # Update rule tracking
    rule.last_triggered_at = datetime.now(timezone.utc)
    rule.execution_count += 1

    # If one-time rule, disable it
    if rule.is_one_time:
        rule.status = "paused"

    await db.commit()
    await db.refresh(execution)

    return execution


# =============================================================================
# Pending Action Management
# =============================================================================

async def get_pending_actions(
    db: AsyncSession,
    org_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PendingAction], int]:
    """Get pending actions for an organization."""
    conditions = [PendingAction.org_id == org_id]

    if status:
        conditions.append(PendingAction.status == status)
    else:
        conditions.append(PendingAction.status == "pending")

    count_query = select(func.count(PendingAction.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = (
        select(PendingAction)
        .where(and_(*conditions))
        .order_by(PendingAction.expires_at.asc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    actions = list(result.scalars().all())

    return actions, total


async def approve_pending_action(
    db: AsyncSession,
    pending_action: PendingAction,
    user_id: str,
    note: Optional[str] = None,
) -> ActionResult:
    """Approve and execute a pending action."""
    if pending_action.status != "pending":
        return ActionResult(
            action_type=pending_action.action_type,
            status="failed",
            details="Action is not pending",
            error=f"Action status is {pending_action.status}",
        )

    # Get the rule
    rule_query = select(AutomationRule).where(AutomationRule.id == pending_action.rule_id)
    rule_result = await db.execute(rule_query)
    rule = rule_result.scalar_one_or_none()

    if not rule:
        return ActionResult(
            action_type=pending_action.action_type,
            status="failed",
            details="Rule not found",
            error="Associated rule has been deleted",
        )

    # Execute the action
    action = {
        "type": pending_action.action_type,
        "params": pending_action.action_params,
    }

    result = await execute_action(
        db=db,
        rule=rule,
        action=action,
        campaign_id=pending_action.campaign_id,
        trigger_reason=pending_action.trigger_reason,
    )

    # Update pending action
    pending_action.status = "executed" if result.status == "success" else "failed"
    pending_action.resolved_at = datetime.now(timezone.utc)
    pending_action.resolved_by_id = user_id
    pending_action.resolution_note = note
    pending_action.execution_result = {
        "status": result.status,
        "details": result.details,
        "error": result.error,
    }

    await db.commit()

    return result


async def reject_pending_action(
    db: AsyncSession,
    pending_action: PendingAction,
    user_id: str,
    note: Optional[str] = None,
) -> None:
    """Reject a pending action."""
    if pending_action.status != "pending":
        return

    pending_action.status = "rejected"
    pending_action.resolved_at = datetime.now(timezone.utc)
    pending_action.resolved_by_id = user_id
    pending_action.resolution_note = note

    await db.commit()


async def expire_pending_actions(db: AsyncSession) -> int:
    """Expire pending actions that have passed their timeout."""
    now = datetime.now(timezone.utc)

    # Find expired pending actions
    query = select(PendingAction).where(
        PendingAction.status == "pending",
        PendingAction.expires_at <= now,
    )

    result = await db.execute(query)
    expired_actions = result.scalars().all()

    count = 0
    for action in expired_actions:
        # Get the rule to check auto_approve setting
        rule_query = select(AutomationRule).where(AutomationRule.id == action.rule_id)
        rule_result = await db.execute(rule_query)
        rule = rule_result.scalar_one_or_none()

        if rule and rule.auto_approve_after_timeout:
            # Auto-approve and execute
            await approve_pending_action(db, action, "system", "Auto-approved after timeout")
        else:
            action.status = "expired"
            action.resolved_at = now

        count += 1

    await db.commit()
    return count


# =============================================================================
# Rule Execution History
# =============================================================================

async def get_rule_executions(
    db: AsyncSession,
    org_id: str,
    rule_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RuleExecution], int]:
    """Get rule execution history."""
    conditions = [RuleExecution.org_id == org_id]

    if rule_id:
        conditions.append(RuleExecution.rule_id == rule_id)
    if campaign_id:
        conditions.append(RuleExecution.campaign_id == campaign_id)

    count_query = select(func.count(RuleExecution.id)).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = (
        select(RuleExecution)
        .where(and_(*conditions))
        .order_by(RuleExecution.executed_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    executions = list(result.scalars().all())

    return executions, total


# =============================================================================
# Templates
# =============================================================================

async def get_rule_templates(
    db: AsyncSession,
    category: Optional[str] = None,
) -> list[RuleTemplate]:
    """Get available rule templates."""
    conditions = [RuleTemplate.is_active == True]

    if category:
        conditions.append(RuleTemplate.category == category)

    query = (
        select(RuleTemplate)
        .where(and_(*conditions))
        .order_by(RuleTemplate.sort_order, RuleTemplate.name)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def create_rule_from_template(
    db: AsyncSession,
    org_id: str,
    template_id: str,
    name: str,
    parameter_values: dict,
    campaign_id: Optional[str] = None,
    created_by_id: Optional[str] = None,
) -> Optional[AutomationRule]:
    """Create a rule from a template with customized parameters."""
    template_query = select(RuleTemplate).where(RuleTemplate.id == template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template:
        return None

    # Apply parameter values to conditions template
    conditions_str = str(template.conditions_template)
    for param in template.parameters:
        param_name = param.get("name")
        value = parameter_values.get(param_name, param.get("default"))
        conditions_str = conditions_str.replace(f"{{{{{{param_name}}}}}}".format(param_name=param_name), str(value))

    # Parse back to dict (simple replacement approach)
    import json
    try:
        conditions = json.loads(conditions_str.replace("'", '"'))
    except:
        conditions = template.conditions_template

    # Same for actions
    actions_str = str(template.actions_template)
    for param in template.parameters:
        param_name = param.get("name")
        value = parameter_values.get(param_name, param.get("default"))
        actions_str = actions_str.replace(f"{{{{{{param_name}}}}}}".format(param_name=param_name), str(value))

    try:
        actions = json.loads(actions_str.replace("'", '"'))
    except:
        actions = template.actions_template

    rule = await create_rule(
        db=db,
        org_id=org_id,
        name=name,
        conditions=conditions,
        actions=actions,
        scope_type="campaign" if campaign_id else "org",
        campaign_id=campaign_id,
        requires_approval=template.default_requires_approval,
        cooldown_minutes=template.default_cooldown_minutes,
        template_id=template_id,
        created_by_id=created_by_id,
    )

    return rule

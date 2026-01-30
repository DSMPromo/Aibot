"""
Automation API endpoints.

Provides endpoints for managing automation rules:
- CRUD operations for rules
- Rule templates
- Pending actions management
- Execution history
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.automation import (
    AutomationRule,
    CONDITION_TYPES,
    ACTION_TYPES,
    OPERATOR_LABELS,
)
from app.services.automation_service import (
    get_rules,
    get_rule,
    create_rule,
    update_rule,
    delete_rule,
    evaluate_rule,
    execute_rule_actions,
    get_pending_actions,
    approve_pending_action,
    reject_pending_action,
    get_rule_executions,
    get_rule_templates,
    create_rule_from_template,
)

logger = structlog.get_logger()

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ConditionSchema(BaseModel):
    """Single condition configuration."""
    metric: str = Field(..., pattern="^(cpa|roas|ctr|cpc|spend|impressions|clicks|conversions)$")
    operator: str = Field(..., pattern="^(gt|lt|gte|lte|eq|neq)$")
    value: float
    lookback_days: int = Field(default=7, ge=1, le=90)


class ConditionsSchema(BaseModel):
    """Conditions configuration."""
    operator: str = Field(default="and", pattern="^(and|or)$")
    conditions: list[ConditionSchema]


class ActionSchema(BaseModel):
    """Single action configuration."""
    type: str = Field(..., pattern="^(pause_campaign|resume_campaign|notify|adjust_budget|create_alert)$")
    params: dict = Field(default_factory=dict)


class ScheduleSchema(BaseModel):
    """Schedule configuration."""
    type: str = Field(..., pattern="^(time_range|days_of_week|specific_dates)$")
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: str = Field(default="UTC")
    days_of_week: Optional[list[int]] = None
    dates: Optional[list[str]] = None


class RuleCreate(BaseModel):
    """Request to create a rule."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    conditions: ConditionsSchema
    actions: list[ActionSchema]
    scope_type: str = Field(default="org", pattern="^(org|campaign|platform)$")
    campaign_id: Optional[str] = None
    platform: Optional[str] = Field(None, pattern="^(google|meta|tiktok)$")
    requires_approval: bool = False
    approval_timeout_hours: int = Field(default=24, ge=1, le=168)
    cooldown_minutes: int = Field(default=60, ge=5, le=10080)
    max_executions_per_day: Optional[int] = Field(None, ge=1)
    is_one_time: bool = False
    schedule: Optional[ScheduleSchema] = None


class RuleUpdate(BaseModel):
    """Request to update a rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    conditions: Optional[ConditionsSchema] = None
    actions: Optional[list[ActionSchema]] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|paused)$")
    requires_approval: Optional[bool] = None
    approval_timeout_hours: Optional[int] = Field(None, ge=1, le=168)
    cooldown_minutes: Optional[int] = Field(None, ge=5, le=10080)
    max_executions_per_day: Optional[int] = None
    schedule: Optional[ScheduleSchema] = None


class RuleResponse(BaseModel):
    """Response for a rule."""
    id: str
    name: str
    description: Optional[str]
    status: str
    scope_type: str
    campaign_id: Optional[str]
    platform: Optional[str]
    conditions: dict
    condition_logic: str
    actions: list
    requires_approval: bool
    approval_timeout_hours: int
    cooldown_minutes: int
    max_executions_per_day: Optional[int]
    is_one_time: bool
    schedule: Optional[dict]
    template_id: Optional[str]
    last_evaluated_at: Optional[str]
    last_triggered_at: Optional[str]
    execution_count: int
    created_at: str


class RuleListResponse(BaseModel):
    """Response for list of rules."""
    rules: list[RuleResponse]
    total: int


class ExecutionResponse(BaseModel):
    """Response for a rule execution."""
    id: str
    rule_id: str
    campaign_id: Optional[str]
    executed_at: str
    trigger_reason: str
    condition_results: dict
    actions_executed: list
    status: str
    error_message: Optional[str]
    metrics_snapshot: Optional[dict]


class ExecutionListResponse(BaseModel):
    """Response for list of executions."""
    executions: list[ExecutionResponse]
    total: int


class PendingActionResponse(BaseModel):
    """Response for a pending action."""
    id: str
    rule_id: str
    rule_name: str
    campaign_id: Optional[str]
    action_type: str
    action_params: dict
    trigger_reason: str
    status: str
    created_at: str
    expires_at: str
    resolved_at: Optional[str]
    resolved_by_id: Optional[str]


class PendingActionListResponse(BaseModel):
    """Response for list of pending actions."""
    actions: list[PendingActionResponse]
    total: int


class TemplateResponse(BaseModel):
    """Response for a rule template."""
    id: str
    name: str
    description: str
    category: str
    conditions_template: dict
    actions_template: list
    default_requires_approval: bool
    default_cooldown_minutes: int
    parameters: list
    applicable_platforms: list


class TemplateListResponse(BaseModel):
    """Response for list of templates."""
    templates: list[TemplateResponse]


class CreateFromTemplateRequest(BaseModel):
    """Request to create a rule from template."""
    name: str = Field(..., min_length=1, max_length=100)
    parameter_values: dict
    campaign_id: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Response for rule evaluation."""
    rule_id: str
    triggered: bool
    trigger_reason: str
    condition_results: list[dict]
    metrics_snapshot: dict


class ApprovalRequest(BaseModel):
    """Request to approve/reject an action."""
    note: Optional[str] = None


# =============================================================================
# Metadata Endpoints
# =============================================================================

@router.get("/metadata/conditions")
async def get_condition_types():
    """Get available condition types and operators."""
    return {
        "condition_types": CONDITION_TYPES,
        "operators": OPERATOR_LABELS,
    }


@router.get("/metadata/actions")
async def get_action_types():
    """Get available action types."""
    return {
        "action_types": ACTION_TYPES,
    }


# =============================================================================
# Rule CRUD Endpoints
# =============================================================================

@router.get("/rules", response_model=RuleListResponse)
async def list_rules(
    status: Optional[str] = Query(None, pattern="^(draft|active|paused)$"),
    campaign_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List automation rules."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    rules, total = await get_rules(
        db=db,
        org_id=org_id,
        status=status,
        campaign_id=campaign_id,
        limit=page_size,
        offset=offset,
    )

    return RuleListResponse(
        rules=[
            RuleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                status=r.status,
                scope_type=r.scope_type,
                campaign_id=r.campaign_id,
                platform=r.platform,
                conditions=r.conditions,
                condition_logic=r.condition_logic,
                actions=r.actions,
                requires_approval=r.requires_approval,
                approval_timeout_hours=r.approval_timeout_hours,
                cooldown_minutes=r.cooldown_minutes,
                max_executions_per_day=r.max_executions_per_day,
                is_one_time=r.is_one_time,
                schedule=r.schedule,
                template_id=r.template_id,
                last_evaluated_at=r.last_evaluated_at.isoformat() if r.last_evaluated_at else None,
                last_triggered_at=r.last_triggered_at.isoformat() if r.last_triggered_at else None,
                execution_count=r.execution_count,
                created_at=r.created_at.isoformat(),
            )
            for r in rules
        ],
        total=total,
    )


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_rule(
    request: RuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new automation rule."""
    # TODO: Get current user's org_id and user_id from auth
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    # Validate scope
    if request.scope_type == "campaign" and not request.campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campaign_id is required when scope_type is 'campaign'",
        )

    rule = await create_rule(
        db=db,
        org_id=org_id,
        name=request.name,
        description=request.description,
        conditions=request.conditions.model_dump(),
        actions=[a.model_dump() for a in request.actions],
        scope_type=request.scope_type,
        campaign_id=request.campaign_id,
        platform=request.platform,
        condition_logic=request.conditions.operator,
        requires_approval=request.requires_approval,
        approval_timeout_hours=request.approval_timeout_hours,
        cooldown_minutes=request.cooldown_minutes,
        schedule=request.schedule.model_dump() if request.schedule else None,
        created_by_id=user_id,
    )

    # Set additional fields
    if request.max_executions_per_day:
        rule.max_executions_per_day = request.max_executions_per_day
    if request.is_one_time:
        rule.is_one_time = request.is_one_time
    await db.commit()
    await db.refresh(rule)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=None,
        last_triggered_at=None,
        execution_count=0,
        created_at=rule.created_at.isoformat(),
    )


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_single_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific rule."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        execution_count=rule.execution_count,
        created_at=rule.created_at.isoformat(),
    )


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_existing_rule(
    rule_id: str,
    request: RuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a rule."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    update_data = request.model_dump(exclude_unset=True)

    # Handle nested objects
    if "conditions" in update_data:
        update_data["conditions"] = request.conditions.model_dump()
        update_data["condition_logic"] = request.conditions.operator
    if "actions" in update_data:
        update_data["actions"] = [a.model_dump() for a in request.actions]
    if "schedule" in update_data and request.schedule:
        update_data["schedule"] = request.schedule.model_dump()

    rule = await update_rule(db, rule, **update_data)

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        execution_count=rule.execution_count,
        created_at=rule.created_at.isoformat(),
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a rule."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    await delete_rule(db, rule)


@router.post("/rules/{rule_id}/activate", response_model=RuleResponse)
async def activate_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Activate a rule."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule = await update_rule(db, rule, status="active")

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        execution_count=rule.execution_count,
        created_at=rule.created_at.isoformat(),
    )


@router.post("/rules/{rule_id}/pause", response_model=RuleResponse)
async def pause_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Pause a rule."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    rule = await update_rule(db, rule, status="paused")

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        execution_count=rule.execution_count,
        created_at=rule.created_at.isoformat(),
    )


@router.post("/rules/{rule_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_single_rule(
    rule_id: str,
    campaign_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a rule without executing actions."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    evaluation = await evaluate_rule(db, rule, campaign_id)

    return EvaluationResponse(
        rule_id=evaluation.rule_id,
        triggered=evaluation.triggered,
        trigger_reason=evaluation.trigger_reason,
        condition_results=[
            {
                "metric": cr.metric,
                "operator": cr.operator,
                "threshold": cr.threshold,
                "current_value": cr.current_value,
                "passed": cr.passed,
                "lookback_days": cr.lookback_days,
            }
            for cr in evaluation.condition_results
        ],
        metrics_snapshot=evaluation.metrics_snapshot,
    )


@router.post("/rules/{rule_id}/run", response_model=ExecutionResponse)
async def run_rule_now(
    rule_id: str,
    campaign_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Manually run a rule (evaluate and execute if triggered)."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    rule = await get_rule(db, rule_id, org_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    evaluation = await evaluate_rule(db, rule, campaign_id)

    if not evaluation.triggered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule conditions not met",
        )

    execution = await execute_rule_actions(db, rule, evaluation, campaign_id)

    return ExecutionResponse(
        id=execution.id,
        rule_id=execution.rule_id,
        campaign_id=execution.campaign_id,
        executed_at=execution.executed_at.isoformat(),
        trigger_reason=execution.trigger_reason,
        condition_results=execution.condition_results,
        actions_executed=execution.actions_executed,
        status=execution.status,
        error_message=execution.error_message,
        metrics_snapshot=execution.metrics_snapshot,
    )


# =============================================================================
# Execution History Endpoints
# =============================================================================

@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    rule_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List rule executions."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    executions, total = await get_rule_executions(
        db=db,
        org_id=org_id,
        rule_id=rule_id,
        campaign_id=campaign_id,
        limit=page_size,
        offset=offset,
    )

    return ExecutionListResponse(
        executions=[
            ExecutionResponse(
                id=e.id,
                rule_id=e.rule_id,
                campaign_id=e.campaign_id,
                executed_at=e.executed_at.isoformat(),
                trigger_reason=e.trigger_reason,
                condition_results=e.condition_results,
                actions_executed=e.actions_executed,
                status=e.status,
                error_message=e.error_message,
                metrics_snapshot=e.metrics_snapshot,
            )
            for e in executions
        ],
        total=total,
    )


# =============================================================================
# Pending Actions Endpoints
# =============================================================================

@router.get("/pending-actions", response_model=PendingActionListResponse)
async def list_pending_actions(
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected|expired|executed)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List pending actions."""
    # TODO: Get current user's org_id from auth
    org_id = "placeholder-org-id"

    offset = (page - 1) * page_size
    actions, total = await get_pending_actions(
        db=db,
        org_id=org_id,
        status=status,
        limit=page_size,
        offset=offset,
    )

    return PendingActionListResponse(
        actions=[
            PendingActionResponse(
                id=a.id,
                rule_id=a.rule_id,
                rule_name=a.rule.name if a.rule else "Unknown",
                campaign_id=a.campaign_id,
                action_type=a.action_type,
                action_params=a.action_params,
                trigger_reason=a.trigger_reason,
                status=a.status,
                created_at=a.created_at.isoformat(),
                expires_at=a.expires_at.isoformat(),
                resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
                resolved_by_id=a.resolved_by_id,
            )
            for a in actions
        ],
        total=total,
    )


@router.post("/pending-actions/{action_id}/approve")
async def approve_action(
    action_id: str,
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending action."""
    # TODO: Get current user's org_id and user_id from auth
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    from sqlalchemy import select
    from app.models.automation import PendingAction

    query = select(PendingAction).where(
        PendingAction.id == action_id,
        PendingAction.org_id == org_id,
    )
    result = await db.execute(query)
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending action not found",
        )

    result = await approve_pending_action(db, action, user_id, request.note)

    return {
        "status": result.status,
        "details": result.details,
        "error": result.error,
    }


@router.post("/pending-actions/{action_id}/reject")
async def reject_action(
    action_id: str,
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending action."""
    # TODO: Get current user's org_id and user_id from auth
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    from sqlalchemy import select
    from app.models.automation import PendingAction

    query = select(PendingAction).where(
        PendingAction.id == action_id,
        PendingAction.org_id == org_id,
    )
    result = await db.execute(query)
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending action not found",
        )

    await reject_pending_action(db, action, user_id, request.note)

    return {"status": "rejected"}


# =============================================================================
# Templates Endpoints
# =============================================================================

@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, pattern="^(budget|performance|schedule|alerts)$"),
    db: AsyncSession = Depends(get_db),
):
    """List available rule templates."""
    templates = await get_rule_templates(db, category)

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category,
                conditions_template=t.conditions_template,
                actions_template=t.actions_template,
                default_requires_approval=t.default_requires_approval,
                default_cooldown_minutes=t.default_cooldown_minutes,
                parameters=t.parameters,
                applicable_platforms=t.applicable_platforms,
            )
            for t in templates
        ],
    )


@router.post("/templates/{template_id}/create-rule", response_model=RuleResponse)
async def create_rule_from_template_endpoint(
    template_id: str,
    request: CreateFromTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a rule from a template."""
    # TODO: Get current user's org_id and user_id from auth
    org_id = "placeholder-org-id"
    user_id = "placeholder-user-id"

    rule = await create_rule_from_template(
        db=db,
        org_id=org_id,
        template_id=template_id,
        name=request.name,
        parameter_values=request.parameter_values,
        campaign_id=request.campaign_id,
        created_by_id=user_id,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return RuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        scope_type=rule.scope_type,
        campaign_id=rule.campaign_id,
        platform=rule.platform,
        conditions=rule.conditions,
        condition_logic=rule.condition_logic,
        actions=rule.actions,
        requires_approval=rule.requires_approval,
        approval_timeout_hours=rule.approval_timeout_hours,
        cooldown_minutes=rule.cooldown_minutes,
        max_executions_per_day=rule.max_executions_per_day,
        is_one_time=rule.is_one_time,
        schedule=rule.schedule,
        template_id=rule.template_id,
        last_evaluated_at=None,
        last_triggered_at=None,
        execution_count=0,
        created_at=rule.created_at.isoformat(),
    )

"""
Automation Rules Models

Provides data models for rule-based automation:
- AutomationRule: Rule definition with conditions and actions
- RuleExecution: Execution history and logging
- PendingAction: Actions awaiting human approval
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AutomationRule(Base):
    """
    Automation rule definition.

    Rules consist of conditions that trigger actions when met.
    Conditions are evaluated periodically against campaign metrics.
    """

    __tablename__ = "automation_rules"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Organization reference
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Rule metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )  # draft, active, paused

    # Scope - can be org-wide or specific campaigns
    scope_type: Mapped[str] = mapped_column(
        String(20),
        default="org",
        nullable=False,
    )  # org, campaign, platform
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
    )
    platform: Mapped[Optional[str]] = mapped_column(String(20))  # google, meta, tiktok

    # Conditions (when to trigger)
    # Uses JSONB for flexibility
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example:
    # {
    #     "operator": "and",  # and, or
    #     "conditions": [
    #         {"metric": "cpa", "operator": "gt", "value": 50.0, "lookback_days": 7},
    #         {"metric": "spend", "operator": "gt", "value": 100.0, "lookback_days": 1},
    #     ]
    # }

    # Condition type shortcuts
    condition_logic: Mapped[str] = mapped_column(
        String(10),
        default="and",
        nullable=False,
    )  # and, or

    # Actions (what to do when triggered)
    actions: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Example:
    # [
    #     {"type": "pause_campaign", "params": {}},
    #     {"type": "notify", "params": {"channels": ["email", "in_app"]}},
    #     {"type": "adjust_budget", "params": {"change_percent": -20}},
    # ]

    # Approval settings
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    auto_approve_after_timeout: Mapped[bool] = mapped_column(Boolean, default=False)

    # Execution settings
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    max_executions_per_day: Mapped[Optional[int]] = mapped_column(Integer)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False)

    # Schedule (optional time-based conditions)
    schedule: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example:
    # {
    #     "type": "time_range",  # time_range, days_of_week, specific_dates
    #     "start_time": "09:00",
    #     "end_time": "18:00",
    #     "timezone": "America/New_York",
    #     "days_of_week": [1, 2, 3, 4, 5],  # Monday-Friday
    # }

    # Template reference (if created from template)
    template_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Execution tracking
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    execution_count: Mapped[int] = mapped_column(Integer, default=0)

    # Created by
    created_by_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    executions: Mapped[list["RuleExecution"]] = relationship(
        "RuleExecution",
        back_populates="rule",
        cascade="all, delete-orphan",
    )
    pending_actions: Mapped[list["PendingAction"]] = relationship(
        "PendingAction",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_automation_rules_org_id", "org_id"),
        Index("ix_automation_rules_status", "status"),
        Index("ix_automation_rules_campaign_id", "campaign_id"),
        Index("ix_automation_rules_template_id", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<AutomationRule {self.name} ({self.status})>"


class RuleExecution(Base):
    """
    Record of a rule execution.

    Logs when rules are evaluated and what actions were taken.
    """

    __tablename__ = "rule_executions"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Rule reference
    rule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization reference (denormalized)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign that triggered (if applicable)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )

    # Execution timestamp
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Trigger details
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Example: "CPA ($65.00) exceeded threshold ($50.00)"

    # Condition evaluation results
    condition_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example:
    # {
    #     "conditions": [
    #         {"metric": "cpa", "current_value": 65.0, "threshold": 50.0, "passed": true},
    #         {"metric": "spend", "current_value": 150.0, "threshold": 100.0, "passed": true},
    #     ],
    #     "overall_passed": true
    # }

    # Actions taken
    actions_executed: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Example:
    # [
    #     {"type": "pause_campaign", "status": "success", "details": "Campaign paused"},
    #     {"type": "notify", "status": "success", "details": "Notification sent to 2 users"},
    # ]

    # Execution status
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
        nullable=False,
    )  # completed, partial, failed, pending_approval

    # Error details (if failed)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Metrics at time of execution
    metrics_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Snapshot of relevant metrics when rule was triggered

    # Relationship
    rule: Mapped["AutomationRule"] = relationship(
        "AutomationRule",
        back_populates="executions",
    )

    __table_args__ = (
        Index("ix_rule_executions_rule_id", "rule_id"),
        Index("ix_rule_executions_org_id", "org_id"),
        Index("ix_rule_executions_campaign_id", "campaign_id"),
        Index("ix_rule_executions_executed_at", "executed_at"),
        Index("ix_rule_executions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RuleExecution rule={self.rule_id} status={self.status}>"


class PendingAction(Base):
    """
    Action awaiting human approval.

    When a rule requires approval, actions are queued here
    until approved, rejected, or timed out.
    """

    __tablename__ = "pending_actions"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Rule reference
    rule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Organization reference
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign reference (if applicable)
    campaign_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )

    # Action details
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_params: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Trigger context
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    condition_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, approved, rejected, expired, executed

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    # Execution result (if approved and executed)
    execution_result: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationship
    rule: Mapped["AutomationRule"] = relationship(
        "AutomationRule",
        back_populates="pending_actions",
    )

    __table_args__ = (
        Index("ix_pending_actions_rule_id", "rule_id"),
        Index("ix_pending_actions_org_id", "org_id"),
        Index("ix_pending_actions_status", "status"),
        Index("ix_pending_actions_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<PendingAction {self.action_type} ({self.status})>"


class RuleTemplate(Base):
    """
    Pre-built rule templates.

    Provides common automation patterns that users can quickly apply.
    """

    __tablename__ = "rule_templates"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )  # e.g., "pause_high_cpa", "alert_low_roas"

    # Template metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # Categories: budget, performance, schedule, alerts

    # Template configuration
    conditions_template: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actions_template: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Default settings
    default_requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    default_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Customizable parameters
    parameters: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Example:
    # [
    #     {"name": "cpa_threshold", "type": "number", "label": "CPA Threshold ($)", "default": 50},
    #     {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 7},
    # ]

    # Platforms this template applies to
    applicable_platforms: Mapped[list] = mapped_column(JSONB, default=list)
    # Empty list means all platforms

    # Visibility
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_rule_templates_category", "category"),
        Index("ix_rule_templates_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<RuleTemplate {self.id}: {self.name}>"


# Condition types enum for reference
CONDITION_TYPES = {
    "cpa": {
        "label": "Cost Per Acquisition (CPA)",
        "unit": "$",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "roas": {
        "label": "Return on Ad Spend (ROAS)",
        "unit": "x",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "ctr": {
        "label": "Click-Through Rate (CTR)",
        "unit": "%",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "spend": {
        "label": "Spend",
        "unit": "$",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "impressions": {
        "label": "Impressions",
        "unit": "",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "clicks": {
        "label": "Clicks",
        "unit": "",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "conversions": {
        "label": "Conversions",
        "unit": "",
        "operators": ["gt", "lt", "gte", "lte"],
    },
    "cpc": {
        "label": "Cost Per Click (CPC)",
        "unit": "$",
        "operators": ["gt", "lt", "gte", "lte"],
    },
}

# Action types enum for reference
ACTION_TYPES = {
    "pause_campaign": {
        "label": "Pause Campaign",
        "description": "Pause the campaign on the ad platform",
        "params": [],
    },
    "resume_campaign": {
        "label": "Resume Campaign",
        "description": "Resume a paused campaign",
        "params": [],
    },
    "notify": {
        "label": "Send Notification",
        "description": "Send notification to specified channels",
        "params": ["channels"],  # email, in_app, slack
    },
    "adjust_budget": {
        "label": "Adjust Budget",
        "description": "Increase or decrease campaign budget by percentage",
        "params": ["change_percent"],  # -20 = decrease by 20%, 20 = increase by 20%
    },
    "create_alert": {
        "label": "Create Alert",
        "description": "Create an alert entry in alert history",
        "params": ["severity"],  # info, warning, critical
    },
}

# Operator labels for UI
OPERATOR_LABELS = {
    "gt": "greater than",
    "lt": "less than",
    "gte": "greater than or equal to",
    "lte": "less than or equal to",
    "eq": "equal to",
    "neq": "not equal to",
}

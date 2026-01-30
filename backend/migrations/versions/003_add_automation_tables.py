"""Add automation tables

Revision ID: 003_add_automation_tables
Revises: 002_add_report_schedules
Create Date: 2024-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_automation_tables'
down_revision: Union[str, None] = '002_add_report_schedules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create automation tables."""

    # Create automation_rules table
    op.create_table(
        'automation_rules',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('scope_type', sa.String(20), server_default='org', nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('platform', sa.String(20), nullable=True),
        sa.Column('conditions', postgresql.JSONB(), nullable=False),
        sa.Column('condition_logic', sa.String(10), server_default='and', nullable=False),
        sa.Column('actions', postgresql.JSONB(), nullable=False),
        sa.Column('requires_approval', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('approval_timeout_hours', sa.Integer(), server_default='24', nullable=False),
        sa.Column('auto_approve_after_timeout', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('cooldown_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('max_executions_per_day', sa.Integer(), nullable=True),
        sa.Column('is_one_time', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('schedule', postgresql.JSONB(), nullable=True),
        sa.Column('template_id', sa.String(50), nullable=True),
        sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_automation_rules_org_id', 'automation_rules', ['org_id'])
    op.create_index('ix_automation_rules_status', 'automation_rules', ['status'])
    op.create_index('ix_automation_rules_campaign_id', 'automation_rules', ['campaign_id'])
    op.create_index('ix_automation_rules_template_id', 'automation_rules', ['template_id'])

    # Create rule_executions table
    op.create_table(
        'rule_executions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('condition_results', postgresql.JSONB(), nullable=False),
        sa.Column('actions_executed', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), server_default='completed', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metrics_snapshot', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_rule_executions_rule_id', 'rule_executions', ['rule_id'])
    op.create_index('ix_rule_executions_org_id', 'rule_executions', ['org_id'])
    op.create_index('ix_rule_executions_campaign_id', 'rule_executions', ['campaign_id'])
    op.create_index('ix_rule_executions_executed_at', 'rule_executions', ['executed_at'])
    op.create_index('ix_rule_executions_status', 'rule_executions', ['status'])

    # Create pending_actions table
    op.create_table(
        'pending_actions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('action_params', postgresql.JSONB(), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('condition_results', postgresql.JSONB(), nullable=False),
        sa.Column('metrics_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('execution_result', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ondelete='SET NULL'),
    )

    op.create_index('ix_pending_actions_rule_id', 'pending_actions', ['rule_id'])
    op.create_index('ix_pending_actions_org_id', 'pending_actions', ['org_id'])
    op.create_index('ix_pending_actions_status', 'pending_actions', ['status'])
    op.create_index('ix_pending_actions_expires_at', 'pending_actions', ['expires_at'])

    # Create rule_templates table
    op.create_table(
        'rule_templates',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('conditions_template', postgresql.JSONB(), nullable=False),
        sa.Column('actions_template', postgresql.JSONB(), nullable=False),
        sa.Column('default_requires_approval', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('default_cooldown_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('parameters', postgresql.JSONB(), nullable=False),
        sa.Column('applicable_platforms', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_rule_templates_category', 'rule_templates', ['category'])
    op.create_index('ix_rule_templates_is_active', 'rule_templates', ['is_active'])

    # Insert default rule templates
    op.execute("""
        INSERT INTO rule_templates (id, name, description, category, conditions_template, actions_template, default_requires_approval, default_cooldown_minutes, parameters, applicable_platforms, sort_order)
        VALUES
        (
            'pause_high_cpa',
            'Pause High CPA Campaigns',
            'Automatically pause campaigns when Cost Per Acquisition exceeds a threshold',
            'performance',
            '{"operator": "and", "conditions": [{"metric": "cpa", "operator": "gt", "value": "{{cpa_threshold}}", "lookback_days": "{{lookback_days}}"}]}',
            '[{"type": "pause_campaign", "params": {}}, {"type": "notify", "params": {"channels": ["in_app", "email"]}}]',
            true,
            60,
            '[{"name": "cpa_threshold", "type": "number", "label": "CPA Threshold ($)", "default": 50}, {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 7}]',
            '[]',
            1
        ),
        (
            'alert_low_roas',
            'Alert on Low ROAS',
            'Send notification when Return on Ad Spend drops below threshold',
            'performance',
            '{"operator": "and", "conditions": [{"metric": "roas", "operator": "lt", "value": "{{roas_threshold}}", "lookback_days": "{{lookback_days}}"}]}',
            '[{"type": "notify", "params": {"channels": ["in_app", "email"]}}]',
            false,
            120,
            '[{"name": "roas_threshold", "type": "number", "label": "ROAS Threshold", "default": 2.0}, {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 7}]',
            '[]',
            2
        ),
        (
            'pause_daily_budget',
            'Pause at Daily Budget',
            'Pause campaigns when daily spend reaches a threshold',
            'budget',
            '{"operator": "and", "conditions": [{"metric": "spend", "operator": "gte", "value": "{{budget_amount}}", "lookback_days": 1}]}',
            '[{"type": "pause_campaign", "params": {}}, {"type": "notify", "params": {"channels": ["in_app"]}}]',
            false,
            1440,
            '[{"name": "budget_amount", "type": "number", "label": "Daily Budget ($)", "default": 100}]',
            '[]',
            3
        ),
        (
            'reduce_budget_high_cpa',
            'Reduce Budget on High CPA',
            'Automatically reduce campaign budget by percentage when CPA is too high',
            'budget',
            '{"operator": "and", "conditions": [{"metric": "cpa", "operator": "gt", "value": "{{cpa_threshold}}", "lookback_days": "{{lookback_days}}"}]}',
            '[{"type": "adjust_budget", "params": {"change_percent": "{{budget_change}}"}}, {"type": "notify", "params": {"channels": ["in_app"]}}]',
            true,
            240,
            '[{"name": "cpa_threshold", "type": "number", "label": "CPA Threshold ($)", "default": 50}, {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 3}, {"name": "budget_change", "type": "number", "label": "Budget Change (%)", "default": -20}]',
            '[]',
            4
        ),
        (
            'alert_low_ctr',
            'Alert on Low CTR',
            'Send notification when Click-Through Rate is underperforming',
            'performance',
            '{"operator": "and", "conditions": [{"metric": "ctr", "operator": "lt", "value": "{{ctr_threshold}}", "lookback_days": "{{lookback_days}}"}, {"metric": "impressions", "operator": "gte", "value": "{{min_impressions}}", "lookback_days": "{{lookback_days}}"}]}',
            '[{"type": "notify", "params": {"channels": ["in_app"]}}]',
            false,
            360,
            '[{"name": "ctr_threshold", "type": "number", "label": "CTR Threshold (%)", "default": 1.0}, {"name": "min_impressions", "type": "number", "label": "Min Impressions", "default": 1000}, {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 7}]',
            '[]',
            5
        ),
        (
            'resume_recovered_campaign',
            'Resume Recovered Campaign',
            'Automatically resume paused campaigns when performance improves',
            'performance',
            '{"operator": "and", "conditions": [{"metric": "cpa", "operator": "lt", "value": "{{cpa_threshold}}", "lookback_days": "{{lookback_days}}"}, {"metric": "conversions", "operator": "gte", "value": "{{min_conversions}}", "lookback_days": "{{lookback_days}}"}]}',
            '[{"type": "resume_campaign", "params": {}}, {"type": "notify", "params": {"channels": ["in_app"]}}]',
            true,
            1440,
            '[{"name": "cpa_threshold", "type": "number", "label": "Max CPA Threshold ($)", "default": 40}, {"name": "min_conversions", "type": "number", "label": "Min Conversions", "default": 5}, {"name": "lookback_days", "type": "number", "label": "Lookback Days", "default": 3}]',
            '[]',
            6
        )
    """)


def downgrade() -> None:
    """Drop automation tables."""
    op.drop_table('rule_templates')
    op.drop_table('pending_actions')
    op.drop_table('rule_executions')
    op.drop_table('automation_rules')

"""Add report_schedules table

Revision ID: 002_add_report_schedules
Revises: 001_add_metrics_tables
Create Date: 2024-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_report_schedules'
down_revision: Union[str, None] = '001_add_metrics_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create report_schedules table."""
    op.create_table(
        'report_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('format', sa.String(10), server_default='pdf', nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('schedule_config', postgresql.JSONB(), nullable=False),
        sa.Column('report_config', postgresql.JSONB(), nullable=False),
        sa.Column('recipients', postgresql.JSONB(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(20), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_report_schedules_org_id', 'report_schedules', ['org_id'])
    op.create_index('ix_report_schedules_is_enabled', 'report_schedules', ['is_enabled'])
    op.create_index('ix_report_schedules_next_run_at', 'report_schedules', ['next_run_at'])


def downgrade() -> None:
    """Drop report_schedules table."""
    op.drop_index('ix_report_schedules_next_run_at', table_name='report_schedules')
    op.drop_index('ix_report_schedules_is_enabled', table_name='report_schedules')
    op.drop_index('ix_report_schedules_org_id', table_name='report_schedules')
    op.drop_table('report_schedules')

"""Add metrics tables with TimescaleDB hypertable

Revision ID: 001_metrics
Revises:
Create Date: 2026-01-29

Creates:
- campaign_metrics table (converted to hypertable)
- metrics_sync_status table
- alerts table
- alert_history table
- notifications table
- Continuous aggregates for hourly/daily/weekly rollups
- Data retention policies
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_metrics'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create TimescaleDB extension if not exists
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Create campaign_metrics table
    op.create_table(
        'campaign_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('granularity', sa.String(10), nullable=False, server_default='raw'),
        sa.Column('impressions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('clicks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ctr', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('spend', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('spend_currency', sa.String(3), server_default='USD'),
        sa.Column('avg_cpc', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('avg_cpm', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('conversions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conversion_value', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('cpa', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('roas', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('view_conversions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extra_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes
    op.create_index(
        'ix_campaign_metrics_campaign_timestamp',
        'campaign_metrics',
        ['campaign_id', 'timestamp']
    )
    op.create_index(
        'ix_campaign_metrics_granularity',
        'campaign_metrics',
        ['granularity']
    )
    op.create_index(
        'ix_campaign_metrics_timestamp',
        'campaign_metrics',
        ['timestamp']
    )

    # Create unique constraint for upserts
    op.create_unique_constraint(
        'uq_campaign_metrics_unique',
        'campaign_metrics',
        ['campaign_id', 'timestamp', 'granularity']
    )

    # Convert to TimescaleDB hypertable
    # Chunk interval of 1 day for optimal query performance
    op.execute("""
        SELECT create_hypertable(
            'campaign_metrics',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create continuous aggregate for hourly metrics
    op.execute("""
        CREATE MATERIALIZED VIEW campaign_metrics_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            campaign_id,
            time_bucket('1 hour', timestamp) AS bucket,
            'hourly' AS granularity,
            SUM(impressions) AS impressions,
            SUM(clicks) AS clicks,
            CASE WHEN SUM(impressions) > 0
                THEN (SUM(clicks)::numeric / SUM(impressions) * 100)
                ELSE 0
            END AS ctr,
            SUM(spend) AS spend,
            CASE WHEN SUM(clicks) > 0
                THEN (SUM(spend) / SUM(clicks))
                ELSE 0
            END AS avg_cpc,
            CASE WHEN SUM(impressions) > 0
                THEN (SUM(spend) / SUM(impressions) * 1000)
                ELSE 0
            END AS avg_cpm,
            SUM(conversions) AS conversions,
            SUM(conversion_value) AS conversion_value,
            CASE WHEN SUM(conversions) > 0
                THEN (SUM(spend) / SUM(conversions))
                ELSE 0
            END AS cpa,
            CASE WHEN SUM(spend) > 0
                THEN (SUM(conversion_value) / SUM(spend))
                ELSE 0
            END AS roas,
            SUM(view_conversions) AS view_conversions
        FROM campaign_metrics
        WHERE granularity = 'raw'
        GROUP BY campaign_id, bucket
        WITH NO DATA
    """)

    # Create continuous aggregate for daily metrics
    op.execute("""
        CREATE MATERIALIZED VIEW campaign_metrics_daily
        WITH (timescaledb.continuous) AS
        SELECT
            campaign_id,
            time_bucket('1 day', timestamp) AS bucket,
            'daily' AS granularity,
            SUM(impressions) AS impressions,
            SUM(clicks) AS clicks,
            CASE WHEN SUM(impressions) > 0
                THEN (SUM(clicks)::numeric / SUM(impressions) * 100)
                ELSE 0
            END AS ctr,
            SUM(spend) AS spend,
            CASE WHEN SUM(clicks) > 0
                THEN (SUM(spend) / SUM(clicks))
                ELSE 0
            END AS avg_cpc,
            CASE WHEN SUM(impressions) > 0
                THEN (SUM(spend) / SUM(impressions) * 1000)
                ELSE 0
            END AS avg_cpm,
            SUM(conversions) AS conversions,
            SUM(conversion_value) AS conversion_value,
            CASE WHEN SUM(conversions) > 0
                THEN (SUM(spend) / SUM(conversions))
                ELSE 0
            END AS cpa,
            CASE WHEN SUM(spend) > 0
                THEN (SUM(conversion_value) / SUM(spend))
                ELSE 0
            END AS roas,
            SUM(view_conversions) AS view_conversions
        FROM campaign_metrics
        WHERE granularity = 'raw'
        GROUP BY campaign_id, bucket
        WITH NO DATA
    """)

    # Add continuous aggregate policies to refresh automatically
    op.execute("""
        SELECT add_continuous_aggregate_policy('campaign_metrics_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('campaign_metrics_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day'
        )
    """)

    # Add data retention policy for raw data (90 days)
    op.execute("""
        SELECT add_retention_policy('campaign_metrics', INTERVAL '90 days')
    """)

    # Create metrics_sync_status table
    op.create_table(
        'metrics_sync_status',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('ad_account_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(20), server_default='pending'),
        sa.Column('earliest_data_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latest_data_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('consecutive_errors', sa.Integer(), server_default='0'),
        sa.Column('sync_enabled', sa.Boolean(), server_default='true'),
        sa.Column('sync_interval_minutes', sa.Integer(), server_default='15'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['ad_account_id'], ['ad_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ad_account_id'),
    )
    op.create_index('ix_metrics_sync_status_ad_account_id', 'metrics_sync_status', ['ad_account_id'])
    op.create_index('ix_metrics_sync_status_last_sync_at', 'metrics_sync_status', ['last_sync_at'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('scope_type', sa.String(20), server_default='org'),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('notification_channels', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('is_enabled', sa.Boolean(), server_default='true'),
        sa.Column('is_triggered', sa.Boolean(), server_default='false'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), server_default='60'),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alerts_org_id', 'alerts', ['org_id'])
    op.create_index('ix_alerts_campaign_id', 'alerts', ['campaign_id'])
    op.create_index('ix_alerts_alert_type', 'alerts', ['alert_type'])
    op.create_index('ix_alerts_is_enabled', 'alerts', ['is_enabled'])

    # Create alert_history table
    op.create_table(
        'alert_history',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metric_value', sa.Numeric(12, 4), nullable=True),
        sa.Column('threshold_value', sa.Numeric(12, 4), nullable=True),
        sa.Column('status', sa.String(20), server_default='triggered'),
        sa.Column('acknowledged_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('notifications_sent', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['acknowledged_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alert_history_alert_id', 'alert_history', ['alert_id'])
    op.create_index('ix_alert_history_org_id', 'alert_history', ['org_id'])
    op.create_index('ix_alert_history_campaign_id', 'alert_history', ['campaign_id'])
    op.create_index('ix_alert_history_triggered_at', 'alert_history', ['triggered_at'])
    op.create_index('ix_alert_history_status', 'alert_history', ['status'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_org_id', 'notifications', ['org_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])


def downgrade() -> None:
    # Remove continuous aggregate policies
    op.execute("SELECT remove_continuous_aggregate_policy('campaign_metrics_hourly', if_exists => true)")
    op.execute("SELECT remove_continuous_aggregate_policy('campaign_metrics_daily', if_exists => true)")

    # Remove retention policy
    op.execute("SELECT remove_retention_policy('campaign_metrics', if_exists => true)")

    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS campaign_metrics_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS campaign_metrics_hourly CASCADE")

    # Drop tables
    op.drop_table('notifications')
    op.drop_table('alert_history')
    op.drop_table('alerts')
    op.drop_table('metrics_sync_status')
    op.drop_table('campaign_metrics')

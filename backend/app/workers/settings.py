"""
arq Worker Settings

Configures background job workers for:
- Metrics sync from ad platforms
- Token refresh
- Automation rule evaluation
- Notification delivery
- Report generation
"""

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.workers.token_refresh import refresh_tokens
from app.workers.campaign_sync import (
    sync_approved_campaigns,
    sync_campaign_statuses,
)
from app.workers.metrics_sync import sync_all_metrics
from app.workers.alerts_worker import check_all_alerts
from app.workers.automation_worker import evaluate_automation_rules


# =============================================================================
# Job Functions (Placeholders for future implementation)
# =============================================================================


async def send_notification(
    ctx: dict,
    channel: str,
    recipient: str,
    message: dict,
) -> dict:
    """
    Send notification via specified channel.

    Channels: email, slack, whatsapp, signal
    """
    # TODO: Implement notification sending
    return {"status": "success", "channel": channel}


async def generate_report(
    ctx: dict,
    org_id: str,
    report_type: str,
    date_range: dict,
) -> dict:
    """
    Generate scheduled report.
    """
    # TODO: Implement report generation
    return {"status": "success", "report_type": report_type}


async def cleanup_dead_letters(ctx: dict) -> dict:
    """
    Clean up expired dead letter queue entries.

    Runs daily to remove entries older than 7 days.
    """
    # TODO: Implement cleanup
    return {"status": "success", "cleaned": 0}


async def send_daily_summaries(ctx: dict) -> dict:
    """
    Send daily performance summary notifications.

    Runs at 6 AM UTC for users who opted in.
    """
    # TODO: Implement daily summaries
    return {"status": "success", "sent": 0}


# =============================================================================
# Worker Configuration
# =============================================================================

class WorkerSettings:
    """arq worker settings."""

    # Available job functions
    functions = [
        sync_all_metrics,
        check_all_alerts,
        refresh_tokens,
        evaluate_automation_rules,
        send_notification,
        generate_report,
        cleanup_dead_letters,
        send_daily_summaries,
        sync_approved_campaigns,
        sync_campaign_statuses,
    ]

    # Scheduled jobs (cron)
    cron_jobs = [
        # Metrics sync every 15 minutes
        cron(sync_all_metrics, minute={0, 15, 30, 45}),

        # Alert checks every 15 minutes (after metrics sync)
        cron(check_all_alerts, minute={5, 20, 35, 50}),

        # Token refresh check every 5 minutes
        cron(refresh_tokens, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),

        # Automation rules every 5 minutes
        cron(evaluate_automation_rules, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),

        # Campaign sync: push approved campaigns every minute
        cron(sync_approved_campaigns, minute=set(range(60))),

        # Campaign sync: sync statuses every 10 minutes
        cron(sync_campaign_statuses, minute={0, 10, 20, 30, 40, 50}),

        # Daily summaries at 6 AM UTC
        cron(send_daily_summaries, hour=6, minute=0),

        # Dead letter cleanup at 2 AM UTC
        cron(cleanup_dead_letters, hour=2, minute=0),
    ]

    # Redis connection settings
    @staticmethod
    def redis_settings() -> RedisSettings:
        """Get Redis settings from environment."""
        # Parse redis URL
        # Format: redis://:password@host:port/db
        import urllib.parse

        url = urllib.parse.urlparse(settings.redis_url)

        return RedisSettings(
            host=url.hostname or "localhost",
            port=url.port or 6379,
            password=url.password,
            database=int(url.path.lstrip("/") or 0),
        )

    # Job settings
    max_jobs = 10  # Max concurrent jobs
    job_timeout = 300  # 5 minutes default timeout
    keep_result = 3600  # Keep results for 1 hour
    max_tries = 3  # Retry failed jobs up to 3 times
    retry_delay = 60  # Wait 60 seconds before retry

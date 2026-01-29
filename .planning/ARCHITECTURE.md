# System Architecture

> AI Marketing Automation Platform
> Version: 1.0
> Last Updated: 2026-01-29

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │   Web App    │    │  Admin UI    │    │   Webhooks   │                │
│   │   (React)    │    │  (Internal)  │    │  (Inbound)   │                │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│          │                   │                   │                         │
└──────────┼───────────────────┼───────────────────┼─────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EDGE / INGRESS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     Caddy (Reverse Proxy)                            │  │
│   │  - TLS termination (auto Let's Encrypt)                             │  │
│   │  - Rate limiting (first layer)                                       │  │
│   │  - Security headers                                                  │  │
│   │  - Static file serving (React build)                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    FastAPI Application                               │  │
│   │                    (Gunicorn + Uvicorn workers)                     │  │
│   ├─────────────────────────────────────────────────────────────────────┤  │
│   │                                                                     │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│   │  │    Auth     │  │  Campaigns  │  │  Analytics  │  │    AI     │ │  │
│   │  │   Module    │  │   Module    │  │   Module    │  │  Module   │ │  │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │  │
│   │                                                                     │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │  │
│   │  │  Automation │  │   Billing   │  │   Admin     │  │  Webhooks │ │  │
│   │  │   Module    │  │   Module    │  │   Module    │  │  Module   │ │  │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │  │
│   │                                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│   │    PostgreSQL    │  │      Redis       │  │   File Storage   │        │
│   │   + TimescaleDB  │  │                  │  │   (Local/S3)     │        │
│   ├──────────────────┤  ├──────────────────┤  ├──────────────────┤        │
│   │ - Users/Orgs     │  │ - Session cache  │  │ - Report exports │        │
│   │ - Campaigns      │  │ - Rate limiting  │  │ - Asset uploads  │        │
│   │ - Metrics (TS)   │  │ - Job queue      │  │ - Backups        │        │
│   │ - Audit logs     │  │ - Token cache    │  │                  │        │
│   │ - OAuth tokens   │  │ - Pub/sub        │  │                  │        │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKGROUND WORKERS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                        arq Worker Pool                                │ │
│   ├──────────────────────────────────────────────────────────────────────┤ │
│   │                                                                      │ │
│   │  Queue: default          Queue: ai            Queue: sync            │ │
│   │  ├── Email sending       ├── Ad copy gen      ├── Google metrics     │ │
│   │  ├── Webhook delivery    ├── Targeting        ├── Meta metrics       │ │
│   │  ├── Report generation   └── Summaries        ├── TikTok metrics     │ │
│   │  └── Notifications                            └── Token refresh      │ │
│   │                                                                      │ │
│   │  Scheduler (arq cron):                                               │ │
│   │  ├── Metrics sync (every 15 min)                                     │ │
│   │  ├── Token refresh check (every 5 min)                               │ │
│   │  ├── Rule evaluation (every 5 min)                                   │ │
│   │  ├── Daily reports (6 AM)                                            │ │
│   │  └── Dead letter cleanup (daily)                                     │ │
│   │                                                                      │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│   │ Google Ads  │  │  Meta Ads   │  │ TikTok Ads  │  │   Stripe    │      │
│   │    API      │  │    API      │  │    API      │  │    API      │      │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│   │   OpenAI    │  │  Anthropic  │  │   Resend    │  │   Slack     │      │
│   │    API      │  │    API      │  │   (Email)   │  │  Webhooks   │      │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐                                         │
│   │  WhatsApp   │  │   Signal    │                                         │
│   │ Business API│  │  (self-host)│                                         │
│   └─────────────┘  └─────────────┘                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Frontend (React)

```
frontend/
├── src/
│   ├── components/        # Shared UI components (shadcn/ui)
│   ├── features/          # Feature modules
│   │   ├── auth/          # Login, register, MFA
│   │   ├── campaigns/     # Campaign CRUD
│   │   ├── analytics/     # Dashboards, reports
│   │   ├── automation/    # Rules management
│   │   ├── settings/      # Account, billing, connections
│   │   └── admin/         # Internal admin UI
│   ├── hooks/             # Custom hooks
│   ├── lib/               # Utilities, API client
│   ├── stores/            # Zustand stores
│   └── types/             # TypeScript types
├── public/
└── package.json
```

**Key Libraries:**
- `@tanstack/react-query` - Server state
- `zustand` - Client state
- `react-hook-form` + `zod` - Forms
- `recharts` + `@tremor/react` - Charts
- `@tanstack/react-table` - Tables

---

### 2. Backend (FastAPI)

```
backend/
├── app/
│   ├── main.py            # FastAPI app entry
│   ├── config.py          # Settings (pydantic-settings)
│   ├── dependencies.py    # DI containers
│   │
│   ├── api/               # API routes
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   ├── campaigns.py
│   │   │   ├── analytics.py
│   │   │   ├── automation.py
│   │   │   ├── billing.py
│   │   │   ├── webhooks.py
│   │   │   └── admin.py
│   │   └── deps.py        # Route dependencies
│   │
│   ├── core/              # Core business logic
│   │   ├── security.py    # Auth, MFA, sessions
│   │   ├── rbac.py        # Permission checks
│   │   └── audit.py       # Audit logging
│   │
│   ├── models/            # SQLAlchemy models
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── campaign.py
│   │   ├── metrics.py
│   │   └── audit.py
│   │
│   ├── schemas/           # Pydantic schemas
│   │   ├── user.py
│   │   ├── campaign.py
│   │   └── ...
│   │
│   ├── services/          # Business services
│   │   ├── campaign_service.py
│   │   ├── ai_service.py
│   │   ├── analytics_service.py
│   │   └── notification_service.py
│   │
│   ├── adapters/          # External API adapters
│   │   ├── base.py        # Abstract adapter
│   │   ├── google_ads.py
│   │   ├── meta_ads.py
│   │   ├── tiktok_ads.py
│   │   └── ai_providers.py
│   │
│   ├── workers/           # Background jobs
│   │   ├── sync.py        # Metrics sync
│   │   ├── automation.py  # Rule evaluation
│   │   ├── notifications.py
│   │   └── reports.py
│   │
│   └── middleware/        # FastAPI middleware
│       ├── security.py    # Headers, rate limiting
│       ├── tenant.py      # Multi-tenant context
│       └── logging.py     # Request logging
│
├── migrations/            # Alembic migrations
├── tests/
├── requirements.txt
└── Dockerfile
```

---

### 3. Database Schema (Core Tables)

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan_tier VARCHAR(20) DEFAULT 'free',
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    ai_generations_used INT DEFAULT 0,
    ai_generations_limit INT DEFAULT 50,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',  -- 'admin', 'manager', 'user'
    mfa_secret VARCHAR(100),  -- Encrypted
    mfa_enabled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, email)
);

-- Connected Ad Accounts
CREATE TABLE ad_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,  -- 'google', 'meta', 'tiktok'
    platform_account_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    access_token_encrypted BYTEA,
    refresh_token_encrypted BYTEA,
    token_expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMPTZ,
    sync_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, platform, platform_account_id)
);

-- Campaigns (unified)
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'pending_review', 'active', 'paused', 'archived'
    platforms JSONB DEFAULT '[]',  -- ['google', 'meta', 'tiktok']
    budget_daily DECIMAL(12,2),
    budget_total DECIMAL(12,2),
    start_date DATE,
    end_date DATE,
    targeting JSONB DEFAULT '{}',
    ad_copy JSONB DEFAULT '{}',  -- Headlines, descriptions, CTAs
    platform_ids JSONB DEFAULT '{}',  -- {'google': 'xxx', 'meta': 'yyy'}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row-Level Security
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

-- Metrics (TimescaleDB hypertable)
CREATE TABLE campaign_metrics (
    id UUID DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    conversions BIGINT DEFAULT 0,
    conversion_value DECIMAL(12,2) DEFAULT 0,
    PRIMARY KEY (id, recorded_at)
);

SELECT create_hypertable('campaign_metrics', 'recorded_at');

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID,
    user_id UUID,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dead Letter Queue
CREATE TABLE dead_letter_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);
```

---

### 4. Ad Platform Adapter Pattern

```python
# adapters/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignMetrics

class AdPlatformAdapter(ABC):
    """Abstract base for all ad platform integrations."""

    @abstractmethod
    async def authenticate(self, auth_code: str) -> dict:
        """Exchange OAuth code for tokens."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token."""
        pass

    @abstractmethod
    async def list_accounts(self, access_token: str) -> List[dict]:
        """List accessible ad accounts."""
        pass

    @abstractmethod
    async def create_campaign(
        self,
        account_id: str,
        campaign: CampaignCreate,
        access_token: str
    ) -> str:
        """Create campaign, return platform campaign ID."""
        pass

    @abstractmethod
    async def update_campaign(
        self,
        account_id: str,
        campaign_id: str,
        updates: CampaignUpdate,
        access_token: str
    ) -> bool:
        """Update campaign."""
        pass

    @abstractmethod
    async def pause_campaign(
        self,
        account_id: str,
        campaign_id: str,
        access_token: str
    ) -> bool:
        """Pause campaign."""
        pass

    @abstractmethod
    async def get_metrics(
        self,
        account_id: str,
        campaign_id: str,
        start_date: date,
        end_date: date,
        access_token: str
    ) -> CampaignMetrics:
        """Fetch campaign metrics."""
        pass


# adapters/google_ads.py
from google.ads.googleads.client import GoogleAdsClient

class GoogleAdsAdapter(AdPlatformAdapter):
    def __init__(self, client_id: str, client_secret: str, developer_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.developer_token = developer_token

    async def create_campaign(self, account_id, campaign, access_token):
        # Google Ads specific implementation
        client = GoogleAdsClient.load_from_dict({
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": access_token,  # Actually refresh token
            "use_proto_plus": True
        })
        # ... implementation
```

---

### 5. AI Service Architecture

```python
# services/ai_service.py
from litellm import acompletion
from instructor import from_openai
from app.schemas.ad_copy import AdCopyRequest, AdCopyResponse

class AIService:
    def __init__(self, settings):
        self.primary_model = "gpt-4o"
        self.fallback_model = "claude-sonnet-4-20250514"
        self.budget_model = "gpt-4o-mini"

    async def generate_ad_copy(
        self,
        request: AdCopyRequest,
        org_id: str,
        user_tier: str
    ) -> AdCopyResponse:
        # Check usage limits
        usage = await self._get_usage(org_id)
        if usage.exceeded:
            raise AIUsageLimitExceeded()

        # Select model based on tier
        model = self._select_model(user_tier)

        # Generate with structured output
        try:
            result = await self._generate(model, request)
        except Exception:
            # Fallback
            result = await self._generate(self.fallback_model, request)

        # Track usage
        await self._track_usage(org_id, result.tokens_used)

        return result

    def _select_model(self, tier: str) -> str:
        if tier in ("free", "starter"):
            return self.budget_model
        return self.primary_model

    async def _generate(self, model: str, request: AdCopyRequest) -> AdCopyResponse:
        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": self._get_system_prompt(request.platform)},
                {"role": "user", "content": self._format_user_prompt(request)}
            ],
            response_format=AdCopyResponse,  # Structured output
        )
        return response
```

---

### 6. Background Job Architecture

```python
# workers/sync.py
from arq import cron
from app.adapters import get_adapter
from app.models import AdAccount, CampaignMetrics

async def sync_account_metrics(ctx, account_id: str):
    """Sync metrics for a single ad account."""
    account = await AdAccount.get(account_id)
    if not account or not account.is_active:
        return {"status": "skipped", "reason": "inactive"}

    adapter = get_adapter(account.platform)

    try:
        # Decrypt token
        access_token = decrypt(account.access_token_encrypted)

        # Fetch metrics
        campaigns = await adapter.list_campaigns(account.platform_account_id, access_token)

        for campaign in campaigns:
            metrics = await adapter.get_metrics(
                account.platform_account_id,
                campaign.id,
                date.today() - timedelta(days=1),
                date.today(),
                access_token
            )

            # Upsert metrics
            await CampaignMetrics.upsert(
                campaign_id=campaign.internal_id,
                platform=account.platform,
                recorded_at=datetime.utcnow(),
                **metrics.dict()
            )

        # Update sync status
        account.last_sync_at = datetime.utcnow()
        account.sync_status = "success"
        await account.save()

        return {"status": "success", "campaigns": len(campaigns)}

    except RateLimitError as e:
        # Retry with backoff
        raise Retry(defer=e.retry_after)

    except AuthenticationError:
        account.sync_status = "auth_error"
        await account.save()
        # Notify user
        await notify_connector_failure(account)
        return {"status": "auth_error"}

    except Exception as e:
        account.sync_status = "error"
        await account.save()
        raise  # Will be retried


class WorkerSettings:
    functions = [
        sync_account_metrics,
        evaluate_automation_rules,
        send_notification,
        generate_report,
    ]

    cron_jobs = [
        cron(sync_all_active_accounts, minute={0, 15, 30, 45}),  # Every 15 min
        cron(check_token_expiry, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),  # Every 5 min
        cron(evaluate_all_rules, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),  # Every 5 min
        cron(send_daily_summaries, hour=6, minute=0),  # 6 AM daily
        cron(cleanup_dead_letters, hour=2, minute=0),  # 2 AM daily
    ]

    redis_settings = RedisSettings(host='redis')
    max_jobs = 10
    job_timeout = 300  # 5 minutes
```

---

### 7. Security Middleware Stack

```python
# middleware/security.py
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import secure

def setup_security_middleware(app: FastAPI):
    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    # Secure headers
    secure_headers = secure.Secure(
        hsts=secure.StrictTransportSecurity().max_age(31536000).include_subdomains(),
        xfo=secure.XFrameOptions().deny(),
        csp=secure.ContentSecurityPolicy()
            .default_src("'self'")
            .script_src("'self'")
            .connect_src("'self'", "https://api.stripe.com"),
        referrer=secure.ReferrerPolicy().strict_origin_when_cross_origin(),
    )

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        response = await call_next(request)
        secure_headers.framework.fastapi(response)
        return response

    # Request logging
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
            ip=request.client.host,
        )
        return response
```

---

### 8. Deployment Architecture

```yaml
# docker-compose.yml
version: '3.8'

services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - ./frontend/dist:/srv/frontend
    depends_on:
      - api

  api:
    build: ./backend
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/aimarketing
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    depends_on:
      - postgres
      - redis
    deploy:
      resources:
        limits:
          memory: 1G

  worker:
    build: ./backend
    command: arq app.workers.WorkerSettings
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/aimarketing
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    deploy:
      resources:
        limits:
          memory: 512M

  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=aimarketing
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 256M

  # Observability
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    deploy:
      resources:
        limits:
          memory: 256M

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    deploy:
      resources:
        limits:
          memory: 256M

  loki:
    image: grafana/loki:latest
    volumes:
      - loki_data:/loki
    deploy:
      resources:
        limits:
          memory: 256M

volumes:
  caddy_data:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
  loki_data:
```

---

### 9. Scaling Strategy

#### Phase 1: Single VPS (0-1000 users)

```
VPS: 4 vCPU, 8GB RAM, 100GB SSD
├── Caddy
├── API (4 workers)
├── Worker (2 workers)
├── PostgreSQL
├── Redis
└── Observability stack
```

#### Phase 2: Separated Database (1000-5000 users)

```
VPS 1 (App): 4 vCPU, 8GB RAM
├── Caddy
├── API (4 workers)
├── Worker (4 workers)
└── Redis

Managed PostgreSQL (external)
├── Primary + Read replica
└── Automated backups
```

#### Phase 3: Horizontal Scale (5000+ users)

```
Load Balancer
├── VPS 1 (API)
├── VPS 2 (API)
└── VPS 3 (Workers)

Managed PostgreSQL
Managed Redis
Object Storage (S3-compatible)
```

---

## API Rate Limits

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Authentication | 5 | 1 minute |
| Campaign CRUD | 60 | 1 minute |
| Analytics queries | 100 | 1 minute |
| AI generation | 10 | 1 minute |
| Webhooks (inbound) | 100 | 1 minute |
| Admin API | 30 | 1 minute |

---

## Error Handling Strategy

| Error Type | Response | Retry | Log Level |
|------------|----------|-------|-----------|
| Validation error | 400 + details | No | Debug |
| Authentication | 401 | No | Info |
| Authorization | 403 | No | Warning |
| Not found | 404 | No | Debug |
| Rate limited | 429 + retry-after | Yes | Info |
| Platform API error | 502 + details | Yes | Warning |
| Internal error | 500 | No | Error |

---

## Monitoring Alerts

| Metric | Warning | Critical |
|--------|---------|----------|
| API p95 latency | > 1s | > 3s |
| Error rate | > 0.5% | > 2% |
| DB connections | > 70% | > 90% |
| Redis memory | > 70% | > 90% |
| Disk usage | > 80% | > 90% |
| Job queue depth | > 500 | > 2000 |
| Failed jobs (1h) | > 10 | > 50 |

---

*Architecture designed for solo developer operation with clear scaling path.*

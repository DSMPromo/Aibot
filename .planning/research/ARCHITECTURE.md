# Architecture Research: AI Marketing Automation Platform

## Executive Summary

This document analyzes architecture patterns for building an AI-powered marketing automation platform that integrates with Google Ads, Meta Ads, and TikTok Ads. Recommendations are tailored for a solo developer using React + FastAPI + PostgreSQL on self-hosted VPS.

---

## 1. Service Architecture

### Recommendation: Modular Monolith

For a solo developer, a **modular monolith** provides the best balance of simplicity and future scalability.

#### Why NOT Microservices
- Operational overhead (multiple deployments, service discovery, distributed tracing)
- Network latency between services
- Distributed transaction complexity
- Solo developer cannot maintain multiple codebases efficiently

#### Why NOT Pure Monolith
- Tight coupling makes future extraction difficult
- Ad platform integrations have different release cycles
- AI components may need independent scaling

#### Modular Monolith Structure
```
backend/
├── app/
│   ├── core/           # Shared utilities, config, security
│   ├── modules/
│   │   ├── auth/       # User auth + OAuth token management
│   │   ├── campaigns/  # Campaign CRUD, unified model
│   │   ├── platforms/  # Ad platform adapters
│   │   │   ├── google/
│   │   │   ├── meta/
│   │   │   └── tiktok/
│   │   ├── ai/         # LLM integration, prompt management
│   │   ├── analytics/  # Metrics aggregation, reporting
│   │   ├── automation/ # Rules engine, triggers
│   │   └── billing/    # Stripe integration
│   ├── workers/        # Background job definitions
│   └── api/            # FastAPI routes (thin layer)
```

#### Key Principle: Module Boundaries
Each module should:
- Have its own SQLAlchemy models (but shared database)
- Communicate via well-defined service classes (not direct imports)
- Be extractable to a microservice later if needed

---

## 2. Ad Platform API Integration Patterns

### Unified Adapter Pattern

Create a common interface that all ad platforms implement:

```python
# Abstract interface
class AdPlatformAdapter(ABC):
    @abstractmethod
    async def authenticate(self, oauth_code: str) -> TokenPair: pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> TokenPair: pass

    @abstractmethod
    async def create_campaign(self, campaign: UnifiedCampaign) -> PlatformCampaign: pass

    @abstractmethod
    async def get_metrics(self, campaign_id: str, date_range: DateRange) -> Metrics: pass

    @abstractmethod
    async def pause_campaign(self, campaign_id: str) -> bool: pass

    @abstractmethod
    async def update_budget(self, campaign_id: str, budget: Decimal) -> bool: pass

# Platform-specific implementations
class GoogleAdsAdapter(AdPlatformAdapter): ...
class MetaAdsAdapter(AdPlatformAdapter): ...
class TikTokAdsAdapter(AdPlatformAdapter): ...
```

### API Client Considerations

| Platform | SDK/Client | Rate Limits | Sandbox |
|----------|-----------|-------------|---------|
| Google Ads | `google-ads` Python SDK | 15,000 requests/day (standard) | Test accounts available |
| Meta | `facebook-business` SDK | Varies by endpoint | Test ad accounts |
| TikTok | REST API (no official Python SDK) | 600 requests/minute | Sandbox mode |

### Token Management Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Token Service                         │
├─────────────────────────────────────────────────────────┤
│  - Stores encrypted tokens in PostgreSQL                │
│  - Automatic refresh before expiration (buffer: 5 min)  │
│  - Retry logic with exponential backoff                 │
│  - Token revocation handling                            │
│  - Per-platform refresh schedules                       │
└─────────────────────────────────────────────────────────┘
```

Token storage schema:
```sql
CREATE TABLE oauth_tokens (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    platform VARCHAR(20) NOT NULL,  -- 'google', 'meta', 'tiktok'
    account_id VARCHAR(100) NOT NULL,
    access_token_encrypted BYTEA NOT NULL,
    refresh_token_encrypted BYTEA NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    scopes TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, platform, account_id)
);
```

### Error Handling Strategy

```python
class PlatformError(Exception):
    """Base for all platform errors"""

class RateLimitError(PlatformError):
    """Retry with exponential backoff"""
    retry_after: int

class AuthenticationError(PlatformError):
    """Token refresh needed or re-auth required"""

class ValidationError(PlatformError):
    """Platform rejected the request (bad data)"""

class TemporaryError(PlatformError):
    """Platform is down, retry later"""
```

---

## 3. Background Job Architecture

### Recommendation: Celery + Redis

For FastAPI with PostgreSQL, Celery with Redis as broker provides:
- Reliable task execution
- Scheduled tasks (Celery Beat)
- Task chaining and workflows
- Mature monitoring (Flower)

#### Alternative Considered: ARQ
- Simpler, async-native
- But: Less mature, fewer features for complex workflows

### Job Categories

```
┌────────────────────────────────────────────────────────────┐
│                      Job Types                              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  IMMEDIATE (user-triggered)                                │
│  ├── Campaign creation/update push                         │
│  ├── AI copy generation                                    │
│  └── OAuth token exchange                                  │
│                                                            │
│  SCHEDULED (periodic)                                      │
│  ├── Metrics sync (every 15 min)                          │
│  ├── Token refresh check (every 5 min)                    │
│  ├── Automation rule evaluation (every 5 min)             │
│  └── Daily report generation (configurable time)          │
│                                                            │
│  TRIGGERED (event-driven)                                  │
│  ├── Budget threshold alerts                               │
│  ├── Performance anomaly detection                         │
│  └── Webhook processing                                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Celery Configuration

```python
# celery_config.py
from celery import Celery
from celery.schedules import crontab

celery = Celery('aimarketing')

celery.conf.beat_schedule = {
    'sync-metrics-every-15-min': {
        'task': 'workers.analytics.sync_all_metrics',
        'schedule': crontab(minute='*/15'),
    },
    'check-token-refresh': {
        'task': 'workers.auth.refresh_expiring_tokens',
        'schedule': crontab(minute='*/5'),
    },
    'evaluate-automation-rules': {
        'task': 'workers.automation.evaluate_rules',
        'schedule': crontab(minute='*/5'),
    },
}

# Queue routing for priority
celery.conf.task_routes = {
    'workers.campaigns.*': {'queue': 'campaigns'},
    'workers.ai.*': {'queue': 'ai'},  # Separate queue for potentially slow LLM calls
    'workers.analytics.*': {'queue': 'analytics'},
}
```

### Job Idempotency

All jobs must be idempotent. Use idempotency keys:

```python
@celery.task(bind=True, max_retries=3)
def sync_campaign_metrics(self, campaign_id: str, idempotency_key: str):
    # Check if already processed
    if redis.get(f"idem:{idempotency_key}"):
        return {"status": "already_processed"}

    try:
        # Do the work
        result = _sync_metrics(campaign_id)
        # Mark as processed (TTL: 24 hours)
        redis.setex(f"idem:{idempotency_key}", 86400, "1")
        return result
    except RateLimitError as e:
        raise self.retry(countdown=e.retry_after)
```

---

## 4. Analytics Processing: Real-time vs Batch

### Hybrid Approach Recommended

```
┌─────────────────────────────────────────────────────────────────┐
│                    Analytics Architecture                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  NEAR REAL-TIME (15-minute sync)                               │
│  ├── Current spend                                              │
│  ├── Today's metrics (clicks, impressions)                     │
│  └── Active campaign status                                     │
│                                                                 │
│  BATCH (nightly)                                                │
│  ├── Historical aggregations                                    │
│  ├── Cross-platform comparisons                                 │
│  ├── Trend calculations                                         │
│  └── Report pre-generation                                      │
│                                                                 │
│  ON-DEMAND (user request)                                       │
│  ├── Custom date range queries                                  │
│  └── Export generation                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model for Analytics

```sql
-- Raw metrics (append-only, partitioned by date)
CREATE TABLE platform_metrics (
    id UUID PRIMARY KEY,
    campaign_id UUID REFERENCES campaigns(id),
    platform VARCHAR(20) NOT NULL,
    platform_campaign_id VARCHAR(100) NOT NULL,
    metric_date DATE NOT NULL,
    hour SMALLINT,  -- NULL for daily, 0-23 for hourly
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    conversions BIGINT DEFAULT 0,
    conversion_value DECIMAL(12,2) DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(campaign_id, platform, metric_date, hour)
) PARTITION BY RANGE (metric_date);

-- Aggregated metrics (materialized for fast queries)
CREATE MATERIALIZED VIEW campaign_daily_summary AS
SELECT
    campaign_id,
    metric_date,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks,
    SUM(spend) as total_spend,
    SUM(conversions) as total_conversions,
    SUM(conversion_value) as total_value,
    CASE WHEN SUM(clicks) > 0
         THEN SUM(spend) / SUM(clicks)
         ELSE NULL END as cpc,
    CASE WHEN SUM(conversions) > 0
         THEN SUM(spend) / SUM(conversions)
         ELSE NULL END as cpa,
    CASE WHEN SUM(spend) > 0
         THEN SUM(conversion_value) / SUM(spend)
         ELSE NULL END as roas
FROM platform_metrics
GROUP BY campaign_id, metric_date;

-- Refresh nightly
CREATE INDEX idx_campaign_daily_summary_date ON campaign_daily_summary(metric_date);
```

### Why NOT True Real-time

1. **API limitations**: Ad platforms update metrics with 1-4 hour delays
2. **Cost**: Real-time streaming adds infrastructure complexity
3. **Accuracy**: Conversions often attributed hours/days later
4. **Solo dev**: Cannot maintain streaming infrastructure

---

## 5. Multi-Tenant Data Architecture

### Recommendation: Shared Database, Row-Level Security

For a SaaS with multi-account support, use PostgreSQL Row-Level Security (RLS).

```
┌─────────────────────────────────────────────────────────┐
│                  Tenant Model                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Organization (tenant)                                  │
│  ├── Users (with roles)                                │
│  ├── Connected Ad Accounts                              │
│  ├── Campaigns                                          │
│  ├── Analytics Data                                     │
│  └── Billing (Stripe subscription)                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Schema Design

```sql
-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan_tier VARCHAR(20) DEFAULT 'starter',
    stripe_customer_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users belong to organizations
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',  -- 'owner', 'admin', 'member', 'client'
    UNIQUE(org_id, email)
);

-- Row-Level Security
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

CREATE POLICY campaigns_tenant_isolation ON campaigns
    USING (org_id = current_setting('app.current_org_id')::UUID);
```

### Request Context Pattern

```python
# middleware.py
from contextvars import ContextVar

current_org: ContextVar[str] = ContextVar('current_org')

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    # Extract org from JWT or session
    org_id = get_org_from_token(request)
    current_org.set(org_id)

    # Set PostgreSQL session variable for RLS
    async with db.connection() as conn:
        await conn.execute(f"SET app.current_org_id = '{org_id}'")

    return await call_next(request)
```

### Data Isolation Levels

| Data Type | Isolation Method |
|-----------|------------------|
| User data | RLS by org_id |
| OAuth tokens | RLS + encryption |
| Campaign data | RLS by org_id |
| Analytics | RLS by org_id |
| Audit logs | RLS by org_id |
| Billing | Per-org Stripe customer |

---

## 6. AI/LLM Integration Architecture

### Multi-Provider Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Service Layer                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   OpenAI     │    │   Claude     │    │   Fallback   │     │
│  │   GPT-4      │    │   (Anthropic)│    │   (GPT-3.5)  │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│          │                  │                    │              │
│          └──────────────────┼────────────────────┘              │
│                             │                                   │
│                    ┌────────┴────────┐                         │
│                    │  AI Router      │                         │
│                    │  - Task routing │                         │
│                    │  - Failover     │                         │
│                    │  - Cost control │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│              ┌──────────────┼──────────────┐                   │
│              │              │              │                    │
│         Ad Copy       Targeting      Budget                    │
│         Generation    Suggestions   Optimization               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Task-Based Model Selection

```python
class AIRouter:
    MODEL_ROUTING = {
        'ad_copy_generation': {
            'primary': 'claude-3-opus',      # Best creative writing
            'fallback': 'gpt-4',
            'budget': 'gpt-3.5-turbo',       # For low-tier plans
        },
        'targeting_analysis': {
            'primary': 'gpt-4',              # Strong analytical
            'fallback': 'claude-3-sonnet',
        },
        'quick_suggestions': {
            'primary': 'gpt-3.5-turbo',      # Fast, cheap
            'fallback': 'claude-3-haiku',
        },
    }

    async def generate(self, task: str, prompt: str, user_tier: str) -> str:
        model = self._select_model(task, user_tier)
        try:
            return await self._call_model(model, prompt)
        except (RateLimitError, TimeoutError):
            fallback = self.MODEL_ROUTING[task]['fallback']
            return await self._call_model(fallback, prompt)
```

### Prompt Management

```
prompts/
├── ad_copy/
│   ├── google_search.jinja2
│   ├── meta_feed.jinja2
│   ├── tiktok_video.jinja2
│   └── variations.jinja2
├── targeting/
│   ├── audience_expansion.jinja2
│   └── interest_mapping.jinja2
└── analysis/
    ├── performance_summary.jinja2
    └── optimization_recommendations.jinja2
```

### Prompt Template Example

```jinja2
{# prompts/ad_copy/google_search.jinja2 #}
You are an expert Google Ads copywriter. Generate {{num_variations}} headline variations.

PRODUCT: {{product_name}}
DESCRIPTION: {{product_description}}
TARGET AUDIENCE: {{target_audience}}
TONE: {{tone}}
KEY BENEFITS: {{benefits | join(', ')}}

CONSTRAINTS:
- Headlines: max 30 characters each
- Descriptions: max 90 characters each
- Include primary keyword: "{{primary_keyword}}"
- Avoid: {{prohibited_terms | join(', ')}}

Output JSON format:
{
  "headlines": ["...", "...", "..."],
  "descriptions": ["...", "..."]
}
```

### Cost Control Mechanisms

1. **Token budgets per organization/month**
2. **Caching repeated similar prompts** (Redis, 1-hour TTL)
3. **Batch processing** where possible (multiple variations in one call)
4. **Usage tracking** in database for billing/limits

---

## 7. OAuth Authentication Flow

### Ad Platform OAuth Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OAuth Flow Architecture                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User                  Your App                    Ad Platform     │
│     │                      │                            │           │
│     │ 1. Click "Connect"   │                            │           │
│     │─────────────────────>│                            │           │
│     │                      │                            │           │
│     │ 2. Redirect to auth  │                            │           │
│     │<─────────────────────│                            │           │
│     │                      │                            │           │
│     │ 3. Login & consent   │                            │           │
│     │──────────────────────────────────────────────────>│           │
│     │                      │                            │           │
│     │ 4. Redirect + code   │                            │           │
│     │<──────────────────────────────────────────────────│           │
│     │                      │                            │           │
│     │ 5. POST to callback  │                            │           │
│     │─────────────────────>│                            │           │
│     │                      │ 6. Exchange code           │           │
│     │                      │───────────────────────────>│           │
│     │                      │                            │           │
│     │                      │ 7. Tokens                  │           │
│     │                      │<───────────────────────────│           │
│     │                      │                            │           │
│     │ 8. Success           │                            │           │
│     │<─────────────────────│                            │           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Platform-Specific OAuth Details

| Platform | OAuth Version | Token Lifetime | Refresh |
|----------|--------------|----------------|---------|
| Google Ads | OAuth 2.0 | 1 hour | Yes (offline access) |
| Meta | OAuth 2.0 | 60 days | Exchange before expiry |
| TikTok | OAuth 2.0 | 24 hours | Yes |

### OAuth State Management

```python
# Prevent CSRF with encrypted state parameter
def generate_oauth_state(user_id: str, platform: str) -> str:
    payload = {
        'user_id': user_id,
        'platform': platform,
        'timestamp': time.time(),
        'nonce': secrets.token_urlsafe(16)
    }
    return encrypt(json.dumps(payload))

def verify_oauth_state(state: str, max_age: int = 600) -> dict:
    payload = json.loads(decrypt(state))
    if time.time() - payload['timestamp'] > max_age:
        raise ExpiredStateError()
    return payload
```

### OAuth Endpoints

```python
# routes/oauth.py

@router.get("/connect/{platform}")
async def initiate_oauth(platform: str, current_user: User):
    adapter = get_adapter(platform)
    state = generate_oauth_state(current_user.id, platform)

    auth_url = adapter.get_authorization_url(
        redirect_uri=f"{settings.BASE_URL}/oauth/callback/{platform}",
        state=state,
        scopes=adapter.required_scopes
    )
    return RedirectResponse(auth_url)

@router.get("/callback/{platform}")
async def oauth_callback(
    platform: str,
    code: str,
    state: str,
    error: Optional[str] = None
):
    if error:
        return RedirectResponse(f"/settings/connections?error={error}")

    payload = verify_oauth_state(state)
    adapter = get_adapter(platform)

    tokens = await adapter.exchange_code(
        code=code,
        redirect_uri=f"{settings.BASE_URL}/oauth/callback/{platform}"
    )

    # Get connected accounts
    accounts = await adapter.list_accessible_accounts(tokens.access_token)

    # Store tokens (encrypted)
    await token_service.store_tokens(
        user_id=payload['user_id'],
        platform=platform,
        tokens=tokens,
        accounts=accounts
    )

    return RedirectResponse("/settings/connections?success=true")
```

---

## 8. Complete System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        System Architecture                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   ┌─────────────┐                                                      │
│   │   React     │                                                      │
│   │   Frontend  │                                                      │
│   └──────┬──────┘                                                      │
│          │ HTTPS                                                       │
│          ▼                                                             │
│   ┌─────────────┐         ┌─────────────┐                             │
│   │   Nginx     │────────>│   FastAPI   │                             │
│   │   Reverse   │         │   App       │                             │
│   │   Proxy     │         └──────┬──────┘                             │
│   └─────────────┘                │                                     │
│                                  │                                     │
│          ┌───────────────────────┼───────────────────────┐            │
│          │                       │                       │             │
│          ▼                       ▼                       ▼             │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐     │
│   │  PostgreSQL │         │    Redis    │         │   Celery    │     │
│   │  Database   │         │   Cache +   │         │   Workers   │     │
│   │             │         │   Broker    │         │   + Beat    │     │
│   └─────────────┘         └─────────────┘         └─────────────┘     │
│                                                          │             │
│                                                          │             │
│   ┌──────────────────────────────────────────────────────┘             │
│   │                                                                    │
│   │   External Services                                                │
│   │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│   │   │ Google Ads  │ │  Meta Ads   │ │ TikTok Ads  │                 │
│   │   │    API      │ │    API      │ │    API      │                 │
│   │   └─────────────┘ └─────────────┘ └─────────────┘                 │
│   │                                                                    │
│   │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│   │   │   OpenAI    │ │  Anthropic  │ │   Stripe    │                 │
│   │   │    API      │ │    API      │ │    API      │                 │
│   │   └─────────────┘ └─────────────┘ └─────────────┘                 │
│   │                                                                    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Data Flow Patterns

### Campaign Creation Flow

```
User Input → Validation → AI Enhancement → Platform Adaptation → API Push → Status Update

1. User fills campaign form (React)
2. POST /api/campaigns (FastAPI validates)
3. Celery task: AI generates ad copy variations
4. Celery task: Transform to platform-specific formats
5. Celery task: Push to each connected platform
6. WebSocket: Real-time status updates to UI
7. Store platform IDs for future reference
```

### Metrics Sync Flow

```
Scheduler → Fetch → Transform → Store → Aggregate → Notify

1. Celery Beat triggers sync every 15 minutes
2. For each connected account:
   a. Check rate limits
   b. Fetch metrics from platform API
   c. Transform to unified format
   d. Upsert into platform_metrics table
3. Refresh materialized views (async)
4. Check automation rules against new data
5. Send alerts if thresholds breached
```

### Automation Rule Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Rule: "Pause ad if CPA > $50 for 3 consecutive days"          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Celery Beat: evaluate_rules task (every 5 min)             │
│  2. Query: SELECT campaigns with active rules                   │
│  3. For each rule:                                              │
│     a. Fetch relevant metrics                                   │
│     b. Evaluate condition (Python expression engine)            │
│     c. If triggered:                                            │
│        - Execute action via platform adapter                    │
│        - Log execution                                          │
│        - Notify user                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Recommended Build Order

### Phase 1: Foundation (Weeks 1-3)
```
[Must build first - everything depends on these]

1. Database schema + migrations (Alembic)
2. FastAPI project structure (modular monolith)
3. User authentication (JWT)
4. Basic React app shell + routing
5. Organization/tenant model

Dependencies: None
Deliverable: User can register, login, see empty dashboard
```

### Phase 2: OAuth + Platform Connections (Weeks 4-6)
```
[Required before any ad platform features]

1. OAuth flow implementation (start with Google Ads)
2. Token storage + encryption
3. Token refresh background job
4. Platform connection UI
5. Account listing from connected platforms

Dependencies: Phase 1
Deliverable: User can connect Google Ads account
```

### Phase 3: Campaign Foundation (Weeks 7-9)
```
[Core product functionality]

1. Unified campaign data model
2. Campaign CRUD API
3. Google Ads adapter (create/read campaigns)
4. Campaign creation UI
5. Campaign listing/detail views

Dependencies: Phase 2
Deliverable: User can create campaign that appears in Google Ads
```

### Phase 4: AI Integration (Weeks 10-11)
```
[Value differentiator]

1. AI service layer + router
2. Prompt templates for ad copy
3. Ad copy generation endpoint
4. Integration into campaign creation flow
5. Variation management UI

Dependencies: Phase 3
Deliverable: AI generates ad copy during campaign creation
```

### Phase 5: Analytics (Weeks 12-14)
```
[Essential for users to see value]

1. Metrics sync background jobs
2. Analytics data model
3. Materialized views for performance
4. Dashboard API endpoints
5. Analytics dashboard UI (charts, tables)

Dependencies: Phase 3
Deliverable: User sees campaign performance in unified dashboard
```

### Phase 6: Automation (Weeks 15-17)
```
[Power user feature]

1. Automation rules data model
2. Rule evaluation engine
3. Action execution (pause, budget change)
4. Rule management UI
5. Execution history/logs

Dependencies: Phase 5
Deliverable: Automated rules can pause underperforming campaigns
```

### Phase 7: Multi-Platform (Weeks 18-22)
```
[Market expansion]

1. Meta Ads adapter (OAuth + campaigns + metrics)
2. TikTok Ads adapter (OAuth + campaigns + metrics)
3. Cross-platform campaign creation
4. Unified analytics across platforms

Dependencies: Phase 3, 5
Deliverable: Full three-platform support
```

### Phase 8: Billing + Polish (Weeks 23-26)
```
[Monetization]

1. Stripe integration
2. Subscription plans + limits
3. Usage tracking
4. Billing UI
5. Onboarding flow improvements
6. Error handling + edge cases

Dependencies: All phases
Deliverable: Production-ready SaaS
```

---

## 11. Solo Developer Considerations

### Time Management
- **Prioritize ruthlessly**: Ship Google Ads first, validate, then add platforms
- **Timebox features**: 2-week sprints, ship incomplete rather than perfect
- **Automate early**: CI/CD, database backups, monitoring from day 1

### Technical Debt Strategy
- **Accept it initially**: Get to market fast
- **Document it**: Keep a TECH_DEBT.md file
- **Pay it down**: Dedicate 20% of time to refactoring after launch

### Monitoring Must-Haves
- **Error tracking**: Sentry (free tier)
- **Uptime monitoring**: UptimeRobot (free)
- **Log aggregation**: Simple file logs + logrotate (free)
- **Metrics**: PostgreSQL stats + pg_stat_statements

### Deployment Simplicity
```
Single VPS (4GB+ RAM):
├── Docker Compose
│   ├── nginx (reverse proxy)
│   ├── fastapi (gunicorn + uvicorn workers)
│   ├── celery-worker
│   ├── celery-beat
│   ├── redis
│   └── postgres (or managed DB)
```

### What to Skip (for now)
- Kubernetes (overkill for solo)
- Multiple environments beyond dev/prod
- Complex CI pipelines
- Microservices
- GraphQL (REST is sufficient)
- WebSocket (use polling initially)

### What NOT to Skip
- Automated database backups
- SSL certificates (Let's Encrypt)
- Rate limiting
- Input validation
- Token encryption
- Audit logging for OAuth actions

---

## 12. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ad platform API changes | High | Abstract behind adapters, monitor changelogs |
| Rate limiting | Medium | Implement backoff, queue management |
| Token expiration bugs | High | Comprehensive refresh logic, alerts |
| LLM cost overruns | Medium | Usage limits, caching, model routing |
| Single point of failure | High | Database backups, documented recovery |
| Scope creep | High | Strict MVP definition, say no often |

---

## Summary

For a solo developer building an AI marketing automation platform:

1. **Start with modular monolith** - easier to develop, deploy, debug
2. **Use adapter pattern** for ad platforms - clean separation, testable
3. **Celery + Redis** for background jobs - mature, well-documented
4. **Hybrid analytics** - near real-time sync, batch aggregation
5. **Row-level security** for multi-tenancy - PostgreSQL handles isolation
6. **Multi-provider AI** with routing - resilience and cost optimization
7. **Build incrementally** - Google Ads first, prove value, then expand

The recommended stack (React + FastAPI + PostgreSQL + Celery + Redis) is appropriate for this use case and can scale to thousands of users on a single well-configured VPS before requiring architectural changes.

---

*Research completed: 2026-01-29*
*Stack: React + FastAPI + PostgreSQL + Celery + Redis*
*Deployment: Self-hosted VPS with Docker Compose*

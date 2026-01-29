# Technology Stack Research: AI Marketing Automation Platform

> Research Date: 2026-01-29
> Target Stack: React + FastAPI + PostgreSQL (Self-hosted VPS)

---

## 0. Security Stack (DAY ONE - Implement First)

> **Security is the foundation. These libraries and patterns are non-negotiable.**

### Password Hashing

**Recommended:** `argon2-cffi`
- **Version:** `23.1.0+`
- **Rationale:** Argon2id is the winner of the Password Hashing Competition; more secure than bcrypt
- **Install:** `pip install argon2-cffi`

```python
from argon2 import PasswordHasher

ph = PasswordHasher()

# Hash password
hashed = ph.hash("user_password")

# Verify password
try:
    ph.verify(hashed, "user_password")
except argon2.exceptions.VerifyMismatchError:
    raise InvalidCredentials()
```

**Avoid:** bcrypt (older, less tunable), MD5/SHA (never for passwords)

---

### Rate Limiting

**Recommended:** `slowapi`
- **Version:** `0.1.9+`
- **Rationale:** FastAPI-native rate limiting with Redis backend
- **Install:** `pip install slowapi`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/auth/login")
@limiter.limit("5/minute")  # Brute force protection
async def login(request: Request):
    ...

@app.get("/api/campaigns")
@limiter.limit("100/minute")  # General API rate limit
async def get_campaigns():
    ...
```

---

### Secure Headers

**Recommended:** `secure`
- **Version:** `0.3.0+`
- **Rationale:** Easy secure headers middleware
- **Install:** `pip install secure`

```python
import secure

secure_headers = secure.Secure(
    hsts=secure.StrictTransportSecurity().max_age(31536000).include_subdomains(),
    xfo=secure.XFrameOptions().deny(),
    csp=secure.ContentSecurityPolicy()
        .default_src("'self'")
        .script_src("'self'", "'unsafe-inline'")  # Adjust for React
        .style_src("'self'", "'unsafe-inline'"),
    referrer=secure.ReferrerPolicy().strict_origin_when_cross_origin(),
    permissions=secure.PermissionsPolicy().geolocation("'none'").camera("'none'")
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    secure_headers.framework.fastapi(response)
    return response
```

---

### Input Validation

**Recommended:** `pydantic` (built into FastAPI)
- **Version:** `2.9.x`
- **Rationale:** Type validation, automatic sanitization, JSON schema generation

```python
from pydantic import BaseModel, EmailStr, constr, validator
import bleach

class CreateCampaignRequest(BaseModel):
    name: constr(min_length=1, max_length=100)
    budget: float
    email: EmailStr

    @validator('name')
    def sanitize_name(cls, v):
        return bleach.clean(v)  # XSS prevention
```

---

### Secrets Management

**Recommended:** `pydantic-settings` + environment variables
- **Version:** `2.5.x`
- **Rationale:** Type-safe settings from environment; never hardcode secrets

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    google_client_id: str
    google_client_secret: str
    openai_api_key: str
    encryption_key: str  # For Fernet

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Never:** Commit `.env` files, hardcode secrets, log sensitive values

---

### CSRF Protection

**Recommended:** `fastapi-csrf-protect`
- **Version:** `0.3.x`
- **Rationale:** SameSite cookies + CSRF tokens for state-changing operations

```python
from fastapi_csrf_protect import CsrfProtect

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings(secret_key=settings.secret_key)
```

---

### Security Logging

**Recommended:** `structlog` with security context
- **Version:** `24.x`

```python
import structlog

logger = structlog.get_logger()

# Log security events
logger.info("login_attempt", user_email=email, ip=request.client.host, success=True)
logger.warning("login_failed", user_email=email, ip=request.client.host, reason="invalid_password")
logger.critical("permission_denied", user_id=user.id, resource="campaign", action="delete")
```

---

### Security Dependencies Summary

```txt
# Security (add to requirements.txt)
argon2-cffi>=23.1.0      # Password hashing
slowapi>=0.1.9           # Rate limiting
secure>=0.3.0            # Security headers
bleach>=6.1.0            # HTML sanitization
fastapi-csrf-protect>=0.3.0  # CSRF protection
python-multipart>=0.0.9  # Secure file uploads
```

---

## 1. Ad Platform API Integrations (Python)

### Google Ads API

**Recommended:** `google-ads` (Official SDK)
- **Version:** `25.0.0+`
- **Rationale:** Official Google-maintained library with full API coverage, automatic token refresh, built-in retry logic
- **Key Features:** gRPC transport (faster), streaming for large reports, Search Ads 360 support
- **Install:** `pip install google-ads`

```python
# Example pattern
from google.ads.googleads.client import GoogleAdsClient
client = GoogleAdsClient.load_from_storage("google-ads.yaml")
```

**Avoid:**
- `googleads` (legacy SOAP-based, deprecated)
- Rolling your own REST client (OAuth complexity, rate limiting edge cases)

---

### Meta (Facebook/Instagram) Ads API

**Recommended:** `facebook-business` (Official SDK)
- **Version:** `20.0.0+`
- **Rationale:** Official Meta SDK, supports Marketing API v20+, async batch requests
- **Key Features:** Ad Insights API, Custom Audiences, Conversions API integration
- **Install:** `pip install facebook-business`

```python
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
FacebookAdsApi.init(app_id, app_secret, access_token)
```

**Avoid:**
- `facebook-sdk` (basic Graph API only, no marketing features)
- Direct REST calls without SDK (pagination handling is complex)

---

### TikTok Ads API

**Recommended:** Custom client with `httpx`
- **Version:** `httpx>=0.27.0`
- **Rationale:** No official Python SDK exists. TikTok Marketing API is REST-based with straightforward auth
- **Pattern:** Build thin wrapper around `httpx` with automatic token refresh

```python
import httpx

class TikTokAdsClient:
    BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

    async def get_campaigns(self, advertiser_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/campaign/get/",
                headers={"Access-Token": self.access_token},
                params={"advertiser_id": advertiser_id}
            )
            return response.json()
```

**Avoid:**
- `requests` for new projects (no native async, `httpx` is the modern standard)
- Unofficial TikTok SDKs (poorly maintained, break with API updates)

---

## 2. React UI Libraries

### Component Framework

**Recommended:** `shadcn/ui` + `Radix UI`
- **Version:** Latest (shadcn/ui is copy-paste, Radix `1.1.x`)
- **Rationale:**
  - Not a dependency - components copied into your codebase (full control)
  - Built on Radix primitives (accessibility, keyboard navigation)
  - Tailwind CSS styling (consistent with modern React patterns)
  - Highly customizable, no version lock-in
- **Install:** `npx shadcn-ui@latest init`

**Avoid:**
- `Material UI` / `@mui` - Heavy bundle size, opinionated design system hard to customize for marketing dashboards
- `Ant Design` - Large bundle, Chinese documentation issues, design system conflicts
- `Chakra UI` - Runtime CSS-in-JS (slower), less active development

---

### Data Visualization / Charts

**Recommended:** `Recharts` (primary) + `@tremor/react` (dashboard components)
- **Versions:** `recharts@2.12.x`, `@tremor/react@3.x`
- **Rationale:**
  - Recharts: Declarative, React-native, good performance, excellent for time-series (campaign metrics)
  - Tremor: Pre-built dashboard components (KPI cards, area charts, bar lists) - perfect for analytics dashboards
- **Install:** `npm install recharts @tremor/react`

```tsx
// Tremor example - KPI cards
import { Card, Metric, Text, AreaChart } from "@tremor/react";

<Card>
  <Text>Total Spend</Text>
  <Metric>$12,450</Metric>
  <AreaChart data={spendData} index="date" categories={["spend"]} />
</Card>
```

**Avoid:**
- `Chart.js` / `react-chartjs-2` - Canvas-based (less React-native), worse accessibility
- `D3.js` directly - Overkill for dashboards, steep learning curve
- `Victory` - Less maintained, smaller ecosystem
- `Apache ECharts` - Heavy, better for complex scientific visualization

---

### Data Tables

**Recommended:** `@tanstack/react-table` (TanStack Table v8)
- **Version:** `8.20.x`
- **Rationale:** Headless (bring your own UI), excellent for campaign lists with sorting/filtering/pagination, works perfectly with shadcn/ui
- **Install:** `npm install @tanstack/react-table`

**Avoid:**
- `ag-grid` - Expensive for commercial use, overkill for marketing dashboards
- `react-table` v7 - Deprecated, use TanStack Table v8
- `material-table` - Abandoned, MUI dependency

---

### State Management

**Recommended:** `@tanstack/react-query` (TanStack Query v5) + `zustand`
- **Versions:** `@tanstack/react-query@5.x`, `zustand@4.5.x`
- **Rationale:**
  - React Query: Server state (API data caching, background refetching, optimistic updates)
  - Zustand: Client state (UI state, user preferences) - minimal boilerplate
- **Install:** `npm install @tanstack/react-query zustand`

**Avoid:**
- `Redux` / `Redux Toolkit` - Overkill for this use case, too much boilerplate
- `MobX` - Magical reactivity harder to debug
- `Recoil` - Uncertain future (Meta deprioritizing)
- `SWR` - React Query has better DevTools and more features

---

## 3. AI/LLM Integration Patterns

### OpenAI Integration

**Recommended:** `openai` (Official SDK)
- **Version:** `1.50.x+`
- **Rationale:** Official SDK with streaming, function calling, async support, automatic retries
- **Install:** `pip install openai`

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def generate_ad_copy(product_description: str, platform: str):
    response = await client.chat.completions.create(
        model="gpt-4o",  # or gpt-4o-mini for cost efficiency
        messages=[
            {"role": "system", "content": f"Generate {platform} ad copy..."},
            {"role": "user", "content": product_description}
        ],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content
```

---

### Anthropic Integration

**Recommended:** `anthropic` (Official SDK)
- **Version:** `0.40.x+`
- **Rationale:** Official SDK, streaming support, tool use (function calling), async native
- **Install:** `pip install anthropic`

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def generate_ad_copy(prompt: str):
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
```

---

### Multi-Provider Pattern (Recommended Architecture)

**Recommended:** `litellm`
- **Version:** `1.50.x+`
- **Rationale:**
  - Unified interface for 100+ LLM providers
  - Automatic fallbacks (if OpenAI fails, try Anthropic)
  - Cost tracking, rate limiting, caching built-in
  - Same OpenAI-compatible interface
- **Install:** `pip install litellm`

```python
import litellm

# Unified interface - swap providers without code changes
response = await litellm.acompletion(
    model="gpt-4o",  # or "claude-sonnet-4-20250514", "gemini/gemini-pro"
    messages=[{"role": "user", "content": "Generate ad copy..."}],
    fallbacks=["claude-sonnet-4-20250514", "gpt-4o-mini"],  # Automatic failover
)
```

**Avoid:**
- Rolling your own abstraction layer - `litellm` handles edge cases
- `langchain` for simple completions - Massive overkill, adds complexity
- Vendor-specific SDKs only - No redundancy, single point of failure

---

### Structured Output (Ad Copy Generation)

**Recommended:** `instructor`
- **Version:** `1.4.x+`
- **Rationale:** Pydantic models for LLM outputs, automatic retries on validation failure, works with OpenAI/Anthropic
- **Install:** `pip install instructor`

```python
import instructor
from pydantic import BaseModel
from openai import AsyncOpenAI

class AdCopy(BaseModel):
    headlines: list[str]  # Max 3
    descriptions: list[str]  # Max 2
    call_to_action: str

client = instructor.from_openai(AsyncOpenAI())

ad = await client.chat.completions.create(
    model="gpt-4o",
    response_model=AdCopy,
    messages=[{"role": "user", "content": "Generate Google Ads copy for..."}]
)
# ad.headlines, ad.descriptions guaranteed to exist and be correct types
```

**Avoid:**
- Manual JSON parsing from LLM responses (fragile, no validation)
- `langchain` output parsers (complex, unnecessary abstraction)

---

## 4. Authentication & OAuth

### User Authentication (JWT Sessions)

**Recommended:** `fastapi-users`
- **Version:** `13.x`
- **Rationale:**
  - Complete auth system for FastAPI (registration, login, password reset, email verification)
  - JWT + cookie support, OAuth2 social login
  - SQLAlchemy/async compatible
- **Install:** `pip install 'fastapi-users[sqlalchemy]'`

**Alternative:** `authlib` + custom implementation
- **Version:** `1.3.x`
- **When:** If you need more control or `fastapi-users` is too opinionated

**Avoid:**
- Rolling your own JWT implementation (security pitfalls)
- `python-jose` alone (low-level, easy to misconfigure)
- `Flask-Login` patterns (not async, not FastAPI native)

---

### Google SSO (Sign in with Google)

**Recommended:** `authlib` + `httpx` (same as ad platform OAuth)
- **Rationale:** Google OAuth 2.0 with OpenID Connect for user identity
- Uses same library as ad platform connections (code reuse)

```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE_SSO_CLIENT_ID,
    client_secret=settings.GOOGLE_SSO_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@app.get("/auth/google")
async def google_login(request: Request):
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    # Create or link user account
    return await handle_sso_login(user_info['email'], user_info['name'], provider='google')
```

**Note:** Requires separate Google Cloud OAuth credentials (not same as Google Ads API)

---

### MFA (Multi-Factor Authentication)

**Recommended:** `pyotp` for TOTP
- **Version:** `2.9.x`
- **Rationale:** Standard TOTP (RFC 6238), works with Google Authenticator, Authy, 1Password
- **Install:** `pip install pyotp qrcode[pil]`

```python
import pyotp
import qrcode
from io import BytesIO

# Generate secret for user (store encrypted in DB)
def generate_mfa_secret() -> str:
    return pyotp.random_base32()

# Generate QR code for authenticator app setup
def generate_mfa_qr(user_email: str, secret: str) -> bytes:
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user_email,
        issuer_name="AI Marketing Platform"
    )
    qr = qrcode.make(provisioning_uri)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    return buffer.getvalue()

# Verify TOTP code
def verify_mfa_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # Allow 30-second drift
```

**Recovery codes:** Generate 10 single-use backup codes, store hashed

**Avoid:**
- SMS-based MFA (SIM swapping attacks, delivery issues)
- Email-based MFA (if email is compromised, MFA is useless)
- Rolling your own TOTP implementation

---

### Session Management

**Recommended:** Redis-backed sessions with `fastapi-users` or custom
- Store session metadata: device, IP, location, last active
- Allow users to view and revoke active sessions

```python
# Session model
class UserSession(Base):
    id: UUID
    user_id: UUID
    token_hash: str  # Hash of JWT, not the JWT itself
    device_info: str  # User-Agent parsed
    ip_address: str
    location: str  # GeoIP lookup
    created_at: datetime
    last_active_at: datetime
    is_active: bool

# Revoke session
async def revoke_session(session_id: UUID, user_id: UUID):
    session = await get_session(session_id)
    if session.user_id != user_id:
        raise PermissionError()
    session.is_active = False
    await invalidate_token_in_redis(session.token_hash)
```

---

### Audit Logging

**Recommended:** Structured audit events in PostgreSQL
- **Pattern:** Append-only audit table with JSON payload

```python
from enum import Enum

class AuditAction(str, Enum):
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    MFA_ENABLED = "user.mfa.enabled"
    CAMPAIGN_CREATED = "campaign.created"
    CAMPAIGN_UPDATED = "campaign.updated"
    CAMPAIGN_DELETED = "campaign.deleted"
    SETTINGS_CHANGED = "org.settings.changed"

class AuditLog(Base):
    id: UUID
    org_id: UUID
    user_id: UUID
    action: AuditAction
    resource_type: str  # "campaign", "user", "ad_account"
    resource_id: UUID
    changes: dict  # {"field": {"old": X, "new": Y}}
    ip_address: str
    user_agent: str
    created_at: datetime

# Usage
await create_audit_log(
    action=AuditAction.CAMPAIGN_UPDATED,
    resource_type="campaign",
    resource_id=campaign.id,
    changes={"budget": {"old": 100, "new": 150}}
)
```

**Retention:** Keep 90 days hot, archive to cold storage

---

### OAuth 2.0 for Ad Platforms

**Recommended:** `authlib`
- **Version:** `1.3.x`
- **Rationale:**
  - Industry-standard OAuth library
  - Supports OAuth 1.0a, 2.0, OpenID Connect
  - Async support with `httpx`
  - Token refresh handling
- **Install:** `pip install authlib httpx`

```python
from authlib.integrations.httpx_client import AsyncOAuth2Client

async def get_google_ads_oauth_client():
    client = AsyncOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_endpoint="https://oauth2.googleapis.com/token",
    )
    return client
```

**Avoid:**
- `requests-oauthlib` (no async support)
- `oauthlib` directly (low-level, authlib wraps it better)
- Platform-specific OAuth implementations (code duplication)

---

### Token Storage

**Recommended:** Encrypted in PostgreSQL with `cryptography`
- **Version:** `cryptography>=42.0.0`
- **Pattern:** Fernet symmetric encryption for refresh tokens at rest

```python
from cryptography.fernet import Fernet

# Encrypt before storing
cipher = Fernet(settings.ENCRYPTION_KEY)
encrypted_token = cipher.encrypt(refresh_token.encode())

# Decrypt when needed
decrypted_token = cipher.decrypt(encrypted_token).decode()
```

**Avoid:**
- Storing tokens in plain text (security risk)
- Redis for long-term token storage (not persistent by default)
- External secret managers for MVP (adds complexity)

---

## 5. Background Job Processing

### Primary Recommendation: `arq`
- **Version:** `0.26.x`
- **Rationale:**
  - Built on Redis + asyncio (matches FastAPI async patterns)
  - Lightweight, simple API
  - Cron scheduling, retries, result storage
  - Perfect for: campaign syncing, scheduled reports, bulk operations

```python
from arq import create_pool
from arq.connections import RedisSettings

async def sync_campaign_metrics(ctx, campaign_id: str):
    """Background job to sync metrics from ad platforms"""
    # ... sync logic

class WorkerSettings:
    functions = [sync_campaign_metrics]
    redis_settings = RedisSettings(host='localhost')
    cron_jobs = [
        cron(sync_all_campaigns, hour=0, minute=0)  # Daily sync
    ]
```

**Install:** `pip install arq`

---

### Alternative: `Celery`
- **Version:** `5.4.x`
- **When to use:** If you need advanced features (task chaining, canvas, priorities)
- **Rationale:** Battle-tested, extensive documentation, large community
- **Downside:** Heavier, sync-first design (can use `celery[gevent]` for async)

**Avoid:**
- `dramatiq` - Less maintained than arq/Celery
- `huey` - Simpler but fewer features
- `rq` (Redis Queue) - No native async, simpler than needed
- `APScheduler` alone - Good for scheduling but not for distributed job processing

---

### Job Types for Marketing Platform

| Job Type | Library | Frequency |
|----------|---------|-----------|
| Campaign metrics sync | arq | Every 15 min |
| Daily performance reports | arq cron | Daily 6 AM |
| Bulk ad creation | arq | On-demand |
| Budget alerts | arq | Every hour |
| Token refresh | arq | Before expiry |
| PDF report generation | arq | On-demand |

---

## 6. Real-time Analytics & Reporting

### Time-Series Storage (Campaign Metrics)

**Recommended:** `TimescaleDB` (PostgreSQL extension)
- **Version:** `2.14.x`
- **Rationale:**
  - PostgreSQL extension (no new database to manage)
  - Hypertables for time-series data (automatic partitioning)
  - Continuous aggregates (pre-computed rollups)
  - 10-100x faster queries for time-range analytics

```sql
-- Create hypertable for metrics
SELECT create_hypertable('campaign_metrics', 'recorded_at');

-- Continuous aggregate for daily rollups
CREATE MATERIALIZED VIEW daily_metrics
WITH (timescaledb.continuous) AS
SELECT
    campaign_id,
    time_bucket('1 day', recorded_at) AS day,
    SUM(impressions) as impressions,
    SUM(clicks) as clicks,
    SUM(spend) as spend
FROM campaign_metrics
GROUP BY campaign_id, day;
```

**Avoid:**
- Storing all metrics in regular PostgreSQL tables (slow aggregations at scale)
- InfluxDB / ClickHouse (separate system to manage, overkill for MVP)
- MongoDB time-series (different data model, harder joins with relational data)

---

### Real-time Updates (WebSocket)

**Recommended:** FastAPI native WebSocket + `broadcaster`
- **Version:** `broadcaster>=0.3.0`
- **Rationale:**
  - FastAPI has native WebSocket support
  - `broadcaster` adds pub/sub with Redis backend (multi-server support)

```python
from fastapi import WebSocket
from broadcaster import Broadcast

broadcast = Broadcast("redis://localhost:6379")

@app.websocket("/ws/campaigns/{campaign_id}")
async def campaign_updates(websocket: WebSocket, campaign_id: str):
    await websocket.accept()
    async with broadcast.subscribe(f"campaign:{campaign_id}") as subscriber:
        async for event in subscriber:
            await websocket.send_json(event.message)
```

**Frontend:**
```typescript
// React hook for real-time updates
const useCampaignUpdates = (campaignId: string) => {
  const queryClient = useQueryClient();

  useEffect(() => {
    const ws = new WebSocket(`wss://api.example.com/ws/campaigns/${campaignId}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      queryClient.setQueryData(['campaign', campaignId], data);
    };
    return () => ws.close();
  }, [campaignId]);
};
```

**Avoid:**
- Polling for real-time data (wasteful, poor UX)
- Socket.IO (JavaScript-focused, Python support is secondary)
- Server-Sent Events alone (one-way only, less flexible)

---

### Report Generation

**Recommended:** `weasyprint` (PDF) + `pandas` (CSV/Excel)
- **Versions:** `weasyprint>=60.0`, `pandas>=2.2.0`, `openpyxl>=3.1.0`
- **Rationale:**
  - WeasyPrint: HTML/CSS to PDF (use your existing React components as templates)
  - Pandas: Data manipulation, CSV/Excel export trivial

```python
from weasyprint import HTML
import pandas as pd

async def generate_pdf_report(campaign_data: dict) -> bytes:
    html = render_template("report.html", data=campaign_data)
    return HTML(string=html).write_pdf()

async def generate_excel_report(metrics: list[dict]) -> bytes:
    df = pd.DataFrame(metrics)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    return buffer.getvalue()
```

**Avoid:**
- `reportlab` (low-level, complex for styled reports)
- `fpdf2` (less CSS support than WeasyPrint)
- Client-side PDF generation (slow, limited styling)

---

## 7. Additional Recommendations

### API Framework Enhancements

| Library | Version | Purpose |
|---------|---------|---------|
| `pydantic` | `2.9.x` | Data validation (FastAPI core) |
| `pydantic-settings` | `2.5.x` | Environment/settings management |
| `uvicorn` | `0.30.x` | ASGI server |
| `gunicorn` | `22.x` | Process manager for production |
| `structlog` | `24.x` | Structured logging |
| `sentry-sdk` | `2.x` | Error tracking |

---

### Database & ORM

| Library | Version | Purpose |
|---------|---------|---------|
| `sqlalchemy` | `2.0.x` | ORM (async with `asyncpg`) |
| `asyncpg` | `0.29.x` | Async PostgreSQL driver |
| `alembic` | `1.13.x` | Database migrations |
| `sqlmodel` | `0.0.21` | Optional: Pydantic + SQLAlchemy hybrid |

---

### Testing

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | `8.x` | Test framework |
| `pytest-asyncio` | `0.23.x` | Async test support |
| `httpx` | `0.27.x` | Async test client for FastAPI |
| `factory-boy` | `3.3.x` | Test data factories |
| `pytest-cov` | `5.x` | Coverage reporting |

---

### DevOps / Self-Hosted VPS

| Tool | Purpose |
|------|---------|
| `Docker` + `docker-compose` | Containerization |
| `Caddy` or `Traefik` | Reverse proxy + automatic HTTPS |
| `PostgreSQL 16` | Database |
| `Redis 7` | Caching + job queue backend |
| `TimescaleDB` | Time-series extension |

---

## 8. Complete Stack Summary

### Backend (Python)
```txt
# requirements.txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
gunicorn>=22.0.0
pydantic>=2.9.0
pydantic-settings>=2.5.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
httpx>=0.27.0
authlib>=1.3.0
fastapi-users[sqlalchemy]>=13.0.0
cryptography>=42.0.0
arq>=0.26.0
redis>=5.0.0
google-ads>=25.0.0
facebook-business>=20.0.0
openai>=1.50.0
anthropic>=0.40.0
litellm>=1.50.0
instructor>=1.4.0
weasyprint>=60.0
pandas>=2.2.0
openpyxl>=3.1.0
structlog>=24.0.0
sentry-sdk[fastapi]>=2.0.0
resend>=2.0.0  # or sendgrid>=6.11.0
```

### Email Service (Transactional)

**Recommended:** `resend`
- **Version:** `2.0.0+`
- **Rationale:** Modern API, excellent DX, generous free tier (3,000 emails/month), React email templates
- **Install:** `pip install resend`

```python
import resend

resend.api_key = "re_123456789"

resend.Emails.send({
    "from": "noreply@yourdomain.com",
    "to": "user@example.com",
    "subject": "Campaign Alert: Budget threshold reached",
    "html": render_template("emails/budget_alert.html", data=alert_data)
})
```

**Alternative:** `sendgrid` - More features, higher volume, but more complex API

**Avoid:**
- SMTP directly (deliverability issues, no analytics)
- AWS SES without wrapper (low-level, complex setup)

---

### WhatsApp Business API

**Recommended:** Meta Cloud API (direct) or `twilio`
- **Rationale:** Official Meta API is free (pay per conversation), Twilio adds reliability layer
- **Use cases:** Campaign alerts, budget warnings, performance summaries

```python
import httpx

class WhatsAppNotifier:
    BASE_URL = "https://graph.facebook.com/v18.0"

    async def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        parameters: list[str]
    ):
        """Send pre-approved template message"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": phone_number,
                    "type": "template",
                    "template": {
                        "name": template_name,  # e.g., "campaign_alert"
                        "language": {"code": "en"},
                        "components": [{
                            "type": "body",
                            "parameters": [{"type": "text", "text": p} for p in parameters]
                        }]
                    }
                }
            )
            return response.json()
```

**Note:** WhatsApp requires pre-approved message templates for business-initiated messages.

---

### Signal Notifications

**Recommended:** `signal-cli` via REST wrapper or `signald`
- **Rationale:** No official API; use community tools
- **Pattern:** Self-hosted signal-cli-rest-api container

```python
import httpx

class SignalNotifier:
    def __init__(self, signal_api_url: str, sender_number: str):
        self.api_url = signal_api_url  # e.g., "http://signal-api:8080"
        self.sender = sender_number

    async def send_to_group(self, group_id: str, message: str):
        """Send message to Signal group"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v2/send",
                json={
                    "number": self.sender,
                    "recipients": [group_id],
                    "message": message
                }
            )
            return response.json()

# Usage
await signal.send_to_group(
    group_id="group.abc123...",
    message="⚠️ Campaign 'Summer Sale' exceeded budget threshold ($500/$450)"
)
```

**Infrastructure:** Deploy `signal-cli-rest-api` Docker container alongside your app.

**Avoid:**
- Unofficial bots that violate Signal ToS
- Storing Signal credentials insecurely

### Frontend (React/TypeScript)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "@tanstack/react-query": "^5.60.0",
    "@tanstack/react-table": "^8.20.0",
    "zustand": "^4.5.0",
    "recharts": "^2.12.0",
    "@tremor/react": "^3.18.0",
    "@radix-ui/react-*": "^1.1.0",
    "tailwindcss": "^3.4.0",
    "react-router-dom": "^6.26.0",
    "react-hook-form": "^7.53.0",
    "zod": "^3.23.0",
    "date-fns": "^3.6.0",
    "lucide-react": "^0.447.0"
  }
}
```

---

## 9. What NOT to Use (Summary)

| Category | Avoid | Reason |
|----------|-------|--------|
| Ad APIs | `googleads` (legacy) | SOAP-based, deprecated |
| Ad APIs | Manual REST clients | OAuth complexity, missing retry logic |
| UI Framework | Material UI, Ant Design | Heavy bundles, hard to customize |
| Charts | Chart.js, D3 directly | Less React-native, complexity |
| State | Redux, Recoil | Overkill, uncertain futures |
| LLM | LangChain (for simple calls) | Massive abstraction overhead |
| Auth | Rolling your own JWT | Security pitfalls |
| Jobs | APScheduler alone | Not distributed |
| Jobs | rq | No native async |
| Real-time | Polling | Wasteful, poor UX |
| Time-series | Regular PostgreSQL tables | Slow at scale |
| PDF | reportlab | Low-level complexity |

---

*Research compiled from current industry standards and production-proven patterns for AI-powered marketing platforms.*

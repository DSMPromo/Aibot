# AI Marketing Platform

AI-powered marketing automation platform for Google, Meta, and TikTok Ads. Manage campaigns across multiple platforms, generate ad copy with AI, monitor performance with real-time analytics, and automate optimization rules.

## Features

### Multi-Platform Campaign Management
- **Google Ads** - Search, Display, and Performance Max campaigns
- **Meta Ads** - Facebook and Instagram campaigns
- **TikTok Ads** - In-feed and TopView campaigns
- Unified dashboard for cross-platform management
- Campaign creation wizard with platform-specific targeting

### AI-Powered Ad Generation
- Generate headlines, descriptions, and CTAs using GPT-4 or Claude
- Platform-optimized copy that respects character limits
- A/B testing variations generated automatically
- Brand voice and tone customization

### Analytics & Reporting
- Real-time performance metrics (impressions, clicks, conversions, ROAS)
- Cross-platform comparison charts
- Scheduled report exports (PDF, CSV, Excel)
- Custom date range analysis

### Automation Rules
- Threshold-based alerts (budget, CPA, ROAS)
- Automated actions (pause, adjust bids, notify)
- Approval workflows for high-impact changes
- Pre-built rule templates

### Billing & Subscriptions
- Stripe-powered subscription management
- Usage-based billing with plan limits
- Self-service billing portal
- Invoice history and payment methods

### Notifications & Webhooks
- Multi-channel notifications (in-app, Slack, email)
- Outbound webhooks with HMAC signing
- Delivery tracking with automatic retries
- Event subscriptions for integrations

## Tech Stack

### Backend
- **FastAPI** - Async Python web framework
- **PostgreSQL** - Primary database with TimescaleDB for metrics
- **Redis** - Caching and job queue
- **SQLAlchemy 2.0** - Async ORM
- **ARQ** - Background task processing
- **Alembic** - Database migrations

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **Zustand** - State management
- **React Query** - Data fetching
- **Recharts** - Analytics charts

### Infrastructure
- **Docker** - Containerization
- **Caddy** - Reverse proxy with auto-TLS
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards and visualization
- **Loki** - Log aggregation
- **Sentry** - Error tracking

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone https://github.com/DSMPromo/Aibot.git
cd Aibot
```

2. Copy the environment file and configure:
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

3. Start all services:
```bash
docker-compose up -d
```

4. Access the application:
- **Frontend**: http://localhost
- **API Docs**: http://localhost/api/docs
- **Grafana**: http://localhost:3001

### Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) |
| `ENCRYPTION_KEY` | Fernet key for token encryption |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

### External Services

| Service | Variables |
|---------|-----------|
| **Stripe** | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` |
| **OpenAI** | `OPENAI_API_KEY` |
| **Anthropic** | `ANTHROPIC_API_KEY` |
| **Google Ads** | `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_DEVELOPER_TOKEN` |
| **Meta Ads** | `META_APP_ID`, `META_APP_SECRET` |
| **TikTok Ads** | `TIKTOK_APP_ID`, `TIKTOK_APP_SECRET` |
| **Resend** | `RESEND_API_KEY` |
| **Sentry** | `SENTRY_DSN` |

See `.env.example` for all available configuration options.

## API Documentation

When running in development mode, API documentation is available at:
- **Swagger UI**: `/api/docs`
- **ReDoc**: `/api/redoc`
- **OpenAPI JSON**: `/api/openapi.json`

## Health Checks

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic health check |
| `/health/ready` | Readiness (DB + Redis connectivity) |
| `/health/live` | Liveness probe |
| `/status` | Public status page data |
| `/metrics` | Prometheus metrics |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── adapters/        # Platform adapters (Google, Meta, TikTok)
│   │   ├── core/            # Database, auth, OAuth
│   │   ├── middleware/      # Security, rate limiting
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   └── workers/         # Background tasks
│   ├── migrations/          # Alembic migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # Shared UI components
│   │   ├── features/        # Feature modules
│   │   ├── lib/             # API client, utilities
│   │   └── stores/          # Zustand stores
│   └── package.json
├── infrastructure/
│   ├── Caddyfile            # Reverse proxy config
│   ├── prometheus.yml       # Metrics config
│   └── grafana/             # Dashboard provisioning
├── docker-compose.yml
├── DEPLOYMENT.md            # Production deployment guide
└── README.md
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions, including:
- Pre-deployment checklist
- Docker Compose commands
- Health check verification
- Rollback procedures

## License

MIT License - see [LICENSE](LICENSE) for details.

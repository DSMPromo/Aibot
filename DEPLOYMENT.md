# Production Deployment Checklist

## Pre-Deployment Verification

### Security
- [ ] Generate new SECRET_KEY: `openssl rand -hex 32`
- [ ] Generate new ENCRYPTION_KEY: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Set strong POSTGRES_PASSWORD and REDIS_PASSWORD
- [ ] Configure CORS_ORIGINS for production domains only
- [ ] Configure ALLOWED_HOSTS for production domains
- [ ] Verify Stripe webhook secret is configured
- [ ] Enable Sentry for error tracking (SENTRY_DSN)
- [ ] Review rate limiting settings for production traffic

### Database
- [ ] Run Alembic migrations: `alembic upgrade head`
- [ ] Verify TimescaleDB extension is enabled
- [ ] Create database backups schedule
- [ ] Configure connection pool sizes for expected load

### External Services
- [ ] Configure Google Ads API credentials
- [ ] Configure Meta Ads API credentials
- [ ] Configure TikTok Ads API credentials
- [ ] Configure OpenAI/Anthropic API keys
- [ ] Configure Stripe live mode keys
- [ ] Configure Resend API for production emails
- [ ] Configure Slack integration (if using)

### Infrastructure
- [ ] Configure TLS certificates (Caddy handles auto-TLS)
- [ ] Set up monitoring dashboards in Grafana
- [ ] Configure log retention in Loki
- [ ] Set up alerting rules in Prometheus

## Deployment Commands

```bash
# Build and deploy
docker-compose -f docker-compose.yml up -d --build

# Check service health
docker-compose ps
curl https://yourdomain.com/health
curl https://yourdomain.com/health/ready

# View logs
docker-compose logs -f api

# Run database migrations
docker-compose exec api alembic upgrade head

# Scale workers
docker-compose up -d --scale worker=3
```

## Health Check Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/health` | Basic health check | `{"status": "healthy"}` |
| `/health/ready` | Readiness (DB + Redis) | `{"status": "ready"}` |
| `/health/live` | Liveness probe | `{"status": "alive"}` |
| `/status` | Public status page data | Component statuses |
| `/metrics` | Prometheus metrics | Prometheus format |

## Rollback Procedure

```bash
# Stop services
docker-compose down

# Revert to previous image
docker-compose pull api:previous-tag
docker-compose up -d

# Rollback database if needed
docker-compose exec api alembic downgrade -1
```

## Post-Deployment Verification

- [ ] Verify all health checks pass
- [ ] Verify API endpoints respond correctly
- [ ] Verify webhook deliveries work
- [ ] Verify Stripe checkout flow
- [ ] Verify email notifications
- [ ] Check Grafana dashboards for metrics
- [ ] Verify Sentry is receiving errors (if any)

## Environment Variables Reference

### Required for Production

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key (32+ hex chars) |
| `ENCRYPTION_KEY` | Fernet encryption key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `STRIPE_SECRET_KEY` | Stripe secret API key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

### Recommended for Production

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry error tracking |
| `RESEND_API_KEY` | Email service API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

## Support

For issues, check:
1. Docker logs: `docker-compose logs api`
2. Grafana dashboards: http://localhost:3001
3. Prometheus metrics: http://localhost:9090

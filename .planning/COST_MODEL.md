# Cost Model

> AI Marketing Automation Platform
> Version: 1.0
> Last Updated: 2026-01-29

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Monthly infrastructure (MVP)** | $80-150 |
| **Variable cost per user** | $0.50-2.00 |
| **Break-even users (Starter plan)** | ~50 |
| **Target gross margin** | 70-80% |

---

## 1. Infrastructure Costs

### MVP Phase (Single VPS)

| Component | Provider | Spec | Monthly Cost |
|-----------|----------|------|--------------|
| **VPS** | Hetzner/DigitalOcean | 4 vCPU, 8GB RAM, 160GB SSD | $40-48 |
| **Backup storage** | Same provider | 100GB block storage | $5-10 |
| **Domain** | Cloudflare | Primary domain | $0 (after initial) |
| **SSL** | Let's Encrypt | Auto via Caddy | $0 |
| **Email (transactional)** | Resend | 3,000/month free | $0 |
| **Error tracking** | Sentry | Free tier (5K errors) | $0 |
| **Uptime monitoring** | UptimeRobot | Free tier | $0 |
| **Total MVP** | | | **$45-58/month** |

### Growth Phase (Separated DB)

| Component | Provider | Spec | Monthly Cost |
|-----------|----------|------|--------------|
| **App VPS** | Hetzner | 4 vCPU, 8GB RAM | $40 |
| **Managed PostgreSQL** | DigitalOcean/Supabase | 2GB RAM, 25GB storage | $25-50 |
| **Managed Redis** | Upstash | Pay-per-use | $10-20 |
| **Email** | Resend | 10K/month | $20 |
| **Sentry** | Paid tier | 50K errors | $26 |
| **Total Growth** | | | **$121-166/month** |

### Scale Phase (Multi-server)

| Component | Provider | Spec | Monthly Cost |
|-----------|----------|------|--------------|
| **App servers (2)** | Hetzner | 4 vCPU, 8GB each | $80 |
| **Worker server** | Hetzner | 2 vCPU, 4GB | $20 |
| **Load balancer** | Hetzner | LB | $10 |
| **Managed PostgreSQL** | | 4GB RAM, 100GB | $75-100 |
| **Managed Redis** | | Dedicated | $30 |
| **Object storage** | S3-compatible | 100GB | $5 |
| **CDN** | Cloudflare | Pro | $20 |
| **Email** | Resend | 100K/month | $100 |
| **Monitoring** | Grafana Cloud | Teams | $50 |
| **Total Scale** | | | **$390-515/month** |

---

## 2. External API Costs

### Ad Platform APIs

| Platform | API Cost | Notes |
|----------|----------|-------|
| **Google Ads API** | Free | Rate limits apply |
| **Meta Marketing API** | Free | Rate limits apply |
| **TikTok Marketing API** | Free | Rate limits apply |

### AI Provider Costs

| Provider | Model | Input (1M tokens) | Output (1M tokens) |
|----------|-------|-------------------|-------------------|
| **OpenAI** | GPT-4o | $2.50 | $10.00 |
| **OpenAI** | GPT-4o-mini | $0.15 | $0.60 |
| **Anthropic** | Claude Sonnet | $3.00 | $15.00 |
| **Anthropic** | Claude Haiku | $0.25 | $1.25 |

#### AI Cost Per Generation (Estimated)

| Generation Type | Tokens (avg) | Model | Cost |
|-----------------|--------------|-------|------|
| Ad copy (1 campaign) | 500 in / 800 out | GPT-4o-mini | $0.0006 |
| Ad copy (1 campaign) | 500 in / 800 out | GPT-4o | $0.009 |
| Targeting suggestion | 1000 in / 500 out | GPT-4o-mini | $0.0005 |
| Performance summary | 2000 in / 500 out | GPT-4o-mini | $0.0006 |

#### Monthly AI Cost by Plan

| Plan | Gen Limit | Model | Max AI Cost |
|------|-----------|-------|-------------|
| Free | 50 | GPT-4o-mini | $0.03 |
| Starter | 500 | GPT-4o-mini | $0.30 |
| Pro | 2,000 | GPT-4o (mix) | $5.00 |
| Agency | 10,000 | GPT-4o | $50.00 |

### Payment Processing (Stripe)

| Fee Type | Rate |
|----------|------|
| Transaction fee | 2.9% + $0.30 |
| Subscription billing | Included |
| Invoicing | Included |

### Other APIs

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| **Resend** | 10K emails | $20 |
| **Resend** | 50K emails | $50 |
| **Slack** | Webhooks | Free |
| **WhatsApp Business** | Per conversation | $0.005-0.08/msg |
| **Signal** | Self-hosted | $0 (infra only) |
| **Google Safe Browsing** | Free tier | $0 |

---

## 3. Pricing Strategy

### Proposed Plans

| Plan | Monthly Price | Annual Price | Target Users |
|------|---------------|--------------|--------------|
| **Free** | $0 | $0 | Hobbyists, trial |
| **Starter** | $49 | $470 (20% off) | SMB, 1-2 people |
| **Pro** | $149 | $1,430 (20% off) | Growing teams |
| **Agency** | $399 | $3,830 (20% off) | Agencies |
| **Enterprise** | Custom | Custom | Large orgs |

### Plan Limits

| Feature | Free | Starter | Pro | Agency |
|---------|------|---------|-----|--------|
| Ad accounts | 1 | 3 | 10 | Unlimited |
| Campaigns | 3 | 20 | 100 | Unlimited |
| AI generations/mo | 50 | 500 | 2,000 | 10,000 |
| Users | 1 | 3 | 10 | Unlimited |
| Metrics history | 30 days | 6 months | 1 year | 2 years |
| Automation rules | 3 | 10 | 50 | Unlimited |
| Report exports | PDF only | PDF, CSV | All | All |
| WhatsApp/Signal | No | No | Yes | Yes |
| Priority support | No | Email | Chat | Dedicated |
| API access | No | No | No | Yes |

---

## 4. Unit Economics

### Cost Per User (Monthly)

| Cost Type | Free | Starter | Pro | Agency |
|-----------|------|---------|-----|--------|
| Infrastructure (allocated) | $0.10 | $0.50 | $1.00 | $2.00 |
| AI (max usage) | $0.03 | $0.30 | $5.00 | $50.00 |
| Email (est. 20 emails/user) | $0.02 | $0.02 | $0.02 | $0.02 |
| Support (allocated) | $0 | $1.00 | $5.00 | $20.00 |
| **Total variable cost** | **$0.15** | **$1.82** | **$11.02** | **$72.02** |

### Gross Margin by Plan

| Plan | Price | Variable Cost | Gross Margin | Margin % |
|------|-------|---------------|--------------|----------|
| Free | $0 | $0.15 | -$0.15 | N/A |
| Starter | $49 | $1.82 | $47.18 | 96% |
| Pro | $149 | $11.02 | $137.98 | 93% |
| Agency | $399 | $72.02 | $326.98 | 82% |

**Note:** Gross margin is high because infrastructure is shared (not per-user allocated), and AI costs are capped.

### Break-Even Analysis

| Scenario | Monthly Fixed | Required MRR | Users Needed |
|----------|---------------|--------------|--------------|
| MVP (solo) | $60 | $60 | 2 Starter |
| Growth | $150 | $150 | 4 Starter |
| With salary ($5K) | $5,150 | $5,150 | 106 Starter or 35 Pro |

---

## 5. Revenue Projections

### Conservative Scenario (Year 1)

| Month | Free | Starter | Pro | Agency | MRR |
|-------|------|---------|-----|--------|-----|
| 1 | 50 | 5 | 0 | 0 | $245 |
| 3 | 150 | 20 | 3 | 0 | $1,427 |
| 6 | 300 | 50 | 10 | 2 | $4,738 |
| 9 | 500 | 80 | 20 | 5 | $8,875 |
| 12 | 800 | 120 | 35 | 10 | $15,055 |

**Year 1 total:** ~$75,000 ARR (conservative)

### Moderate Scenario (Year 1)

| Month | Free | Starter | Pro | Agency | MRR |
|-------|------|---------|-----|--------|-----|
| 6 | 500 | 100 | 20 | 5 | $9,875 |
| 12 | 1500 | 250 | 75 | 20 | $31,355 |

**Year 1 total:** ~$200,000 ARR (moderate)

---

## 6. Cost Optimization Strategies

### AI Costs

| Strategy | Impact | Implementation |
|----------|--------|----------------|
| Use GPT-4o-mini for low tiers | -80% AI cost | Day 1 |
| Cache common generations | -20% AI cost | Month 2 |
| Batch generation requests | -10% AI cost | Month 3 |
| Prompt optimization | -15% AI cost | Ongoing |

### Infrastructure

| Strategy | Impact | When |
|----------|--------|------|
| Reserved instances | -30% VPS cost | After 6 months |
| Database connection pooling | Better efficiency | Day 1 |
| CDN for static assets | Reduced bandwidth | Month 3 |
| Aggressive caching | Reduced DB load | Day 1 |

### Support

| Strategy | Impact | When |
|----------|--------|------|
| Self-service docs | -50% tickets | Day 1 |
| In-app help | -30% tickets | Month 2 |
| AI-assisted support | -20% time/ticket | Month 6 |

---

## 7. Risk Factors

### Cost Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AI API price increase | Medium | High | Multi-provider, caps |
| Unexpected usage spike | Medium | Medium | Hard caps, alerts |
| Ad platform API changes | Low | High | Abstraction layer |
| Stripe fee increase | Low | Low | Limited options |

### Revenue Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Low conversion (free→paid) | High | High | Focus on activation |
| High churn | Medium | High | Improve onboarding |
| Agency dependency | Medium | Medium | Diversify customer base |
| Pricing too low | Medium | Medium | Review quarterly |

---

## 8. Financial Guardrails

### Alerts

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| AI cost/user | > $5 | > $10 | Review usage, adjust limits |
| Infra cost/user | > $1 | > $2 | Optimize or scale |
| Support hours/user | > 0.5h | > 1h | Improve self-service |
| Churn rate | > 5%/mo | > 10%/mo | Retention campaign |

### Monthly Review

- [ ] Total costs vs budget
- [ ] Cost per user trend
- [ ] AI usage by tenant (top 10)
- [ ] Infrastructure utilization
- [ ] Support ticket volume

### Quarterly Review

- [ ] Unit economics by plan
- [ ] Pricing competitiveness
- [ ] Feature cost allocation
- [ ] Vendor contract optimization

---

## 9. Summary Tables

### Infrastructure Cost by Phase

| Phase | Users | Monthly Cost | Cost/User |
|-------|-------|--------------|-----------|
| MVP | 0-100 | $50 | $0.50+ |
| Growth | 100-1000 | $150 | $0.15-1.50 |
| Scale | 1000-5000 | $400 | $0.08-0.40 |

### Key Metrics to Track

| Metric | Target |
|--------|--------|
| Gross margin | > 75% |
| LTV:CAC ratio | > 3:1 |
| Payback period | < 6 months |
| Monthly churn | < 5% |
| NRR (net revenue retention) | > 100% |

---

## 10. First Year Budget

### Fixed Costs (Monthly)

| Category | Month 1-3 | Month 4-6 | Month 7-12 |
|----------|-----------|-----------|------------|
| Infrastructure | $50 | $100 | $200 |
| Tools (Sentry, etc.) | $0 | $50 | $100 |
| Legal (privacy, ToS) | $100 (one-time) | $0 | $0 |
| Domain | $15/year | - | - |
| **Total fixed** | **$65** | **$150** | **$300** |

### Variable Costs (at 100 paid users)

| Category | Monthly |
|----------|---------|
| AI (avg $2/user) | $200 |
| Email (20/user) | $20 |
| Payment processing (3%) | ~$150 |
| **Total variable** | **$370** |

### First Year Projection

| Quarter | Revenue | Costs | Net |
|---------|---------|-------|-----|
| Q1 | $2,500 | $1,000 | $1,500 |
| Q2 | $12,000 | $3,000 | $9,000 |
| Q3 | $25,000 | $6,000 | $19,000 |
| Q4 | $40,000 | $10,000 | $30,000 |
| **Year 1** | **$79,500** | **$20,000** | **$59,500** |

---

*Cost model based on 2026 pricing. Review and update quarterly.*

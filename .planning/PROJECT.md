# AI Marketing Automation Platform

## What This Is

A SaaS platform that enables businesses to create, launch, manage, and optimize paid advertising campaigns across Google Ads, Meta (Facebook/Instagram) Ads, and TikTok Ads from a unified dashboard. The platform uses AI to generate ad copy, recommend targeting, and optimize campaign performance automatically.

## Core Value

**One dashboard to rule all ad platforms** - Marketing teams stop context-switching between Google, Meta, and TikTok interfaces. They create campaigns once, AI generates the creative variations, and the system handles cross-platform optimization.

## Who It's For

- Marketing managers at small and medium businesses
- Digital agencies managing multiple client accounts
- Startups and e-commerce brands running paid acquisition
- Affiliate marketers scaling campaigns

## What Success Looks Like

A marketing manager logs in, connects their ad accounts once, describes their campaign goal in plain language, and the AI generates ad copy variations. They review, adjust if needed, set budget, and launch to all three platforms simultaneously. The dashboard shows unified performance metrics, and automation rules pause underperforming ads automatically.

## Technical Foundation

### Stack
- **Frontend:** React (TypeScript)
- **Backend:** Python + FastAPI
- **Database:** PostgreSQL
- **AI:** Multiple providers (OpenAI GPT-4, Anthropic Claude)
- **Hosting:** Self-hosted VPS
- **Auth:** OAuth 2.0 for ad platform connections, JWT for user sessions

### External Integrations
- Google Ads API (developer access secured)
- Meta Marketing API (business verification complete)
- TikTok Marketing API (developer access granted)
- Stripe for billing
- Multiple AI providers for text generation
- Email service (Resend/SendGrid) for notifications and reports
- Conversion pixel management (Meta Pixel, Google Tag, TikTok Pixel)

## Constraints

- **Timeline:** 3-6 months to full-featured launch
- **Team:** Solo developer with Claude assistance
- **Images:** Users upload their own (no AI image generation in v1)
- **Compliance:** Must adhere to each ad platform's API policies

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| React + FastAPI | Familiar stack, Python strong for AI/ML, React ecosystem robust | Pending |
| PostgreSQL | Relational fits campaign/analytics data, good for reporting queries | Pending |
| Multiple AI providers | Redundancy, best model for each task, avoid vendor lock-in | Pending |
| Self-hosted VPS | Cost control, full control over infrastructure | Pending |
| No AI images v1 | Reduces scope, focus on core value (campaign management + AI copy) | Pending |

## What's NOT in Scope (v1)

- AI-generated images/videos (users upload their own)
- LinkedIn, Twitter, Pinterest ad platforms
- White-label/reseller features
- Mobile native apps (web responsive only)
- Self-hosted LLMs (using cloud AI APIs)

## Requirements

### Validated

(None yet - ship to validate)

### Active

- [ ] User authentication and account management
- [ ] Connect Google Ads accounts via OAuth
- [ ] Connect Meta Ads accounts via OAuth
- [ ] Connect TikTok Ads accounts via OAuth
- [ ] Unified campaign creation UI
- [ ] AI-generated ad copy (headlines, descriptions, CTAs)
- [ ] AI targeting recommendations
- [ ] AI budget allocation suggestions
- [ ] Campaign launch to multiple platforms
- [ ] Real-time analytics dashboard
- [ ] Performance metrics (clicks, impressions, spend, conversions, CPA, ROAS)
- [ ] Automation rules (pause low performers, budget alerts)
- [ ] Multi-account/client management
- [ ] Role-based access (admin, operator, client)
- [ ] Subscription billing (Stripe)
- [ ] Pricing tiers (Starter, Professional, Enterprise)
- [ ] Affiliate program with referral tracking
- [ ] Exportable reports (PDF/CSV)
- [ ] Email notifications (campaign alerts, scheduled reports, system notifications)
- [ ] Conversion pixel setup wizard (guide users to install tracking pixels)
- [ ] Outbound webhooks (send events to user's systems)
- [ ] CSV/bulk import for campaigns

### Out of Scope

- AI image generation - focus on core value first
- Additional ad platforms - prove model with big three first
- Mobile apps - responsive web sufficient
- White-label - adds complexity, validate demand first

---
*Last updated: 2026-01-29 after initialization*

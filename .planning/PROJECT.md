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
- **Security:** Security-first development - all security requirements implemented from Day One

## Security (Day One Priority)

> Security is not a feature. It's the foundation.

### Non-Negotiables (Before First Deploy)
- [ ] TLS 1.3 on all connections
- [ ] Data encrypted at rest (AES-256)
- [ ] OAuth tokens encrypted before storage (Fernet)
- [ ] Secrets in environment variables only
- [ ] Input validation on all endpoints (Pydantic)
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding, CSP)
- [ ] Rate limiting (auth + public endpoints)
- [ ] Secure headers (HSTS, X-Frame-Options, CSP)
- [ ] Password hashing with Argon2id
- [ ] JWT short expiry (15 min access token)
- [ ] Firewall configured (minimal ports)
- [ ] Database not publicly accessible
- [ ] Automated encrypted backups
- [ ] Security event logging
- [ ] Privacy policy + Terms of Service
- [ ] GDPR: Cookie consent, account deletion

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
- [ ] Google SSO login (Sign in with Google Workspace)
- [ ] MFA (Multi-Factor Authentication via TOTP authenticator apps)
- [ ] Session management (view active sessions, force logout, session timeout)
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
- [ ] Role-based access control (RBAC):
  - [ ] Admin: Full system access, billing, user management
  - [ ] Manager: Team oversight, approve campaigns, view all reports
  - [ ] User: Create/edit own campaigns, view assigned accounts
- [ ] Audit logging (who did what, when, with before/after states)
- [ ] Subscription billing (Stripe)
- [ ] Pricing tiers (Starter, Professional, Enterprise)
- [ ] Affiliate program with referral tracking
- [ ] Exportable reports (PDF/CSV)
- [ ] Email notifications (campaign alerts, scheduled reports, system notifications)
- [ ] Conversion pixel setup wizard (guide users to install tracking pixels)
- [ ] Outbound webhooks (send events to user's systems)
- [ ] CSV/bulk import for campaigns
- [ ] WhatsApp Business notifications (campaign alerts, budget warnings)
- [ ] Signal group notifications (privacy-focused alternative)
- [ ] Google Analytics 4 integration (traffic, landing page metrics)
- [ ] UTM parameter auto-generation for campaign links
- [ ] Landing page performance tracking

### Out of Scope

- AI image generation - focus on core value first
- Additional ad platforms - prove model with big three first
- Mobile apps - responsive web sufficient
- White-label - adds complexity, validate demand first

## Related Documents

- **PLATFORM.md** - Platform-level decisions (data ownership, observability, admin tooling, exit paths)
- **REQUIREMENTS.md** - All requirements with REQ-IDs
- **research/STACK.md** - Technology recommendations
- **research/ARCHITECTURE.md** - System design patterns

---
*Last updated: 2026-01-29*

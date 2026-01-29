# Research Summary: AI Marketing Automation Platform

> Synthesized: 2026-01-29
> Research documents: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

---

## Platform Foundations (Before Code)

> **See PLATFORM.md for full details on these decisions.**

| Area | Decision |
|------|----------|
| **Data Ownership** | Tenant owns campaign data; platform owns logs; explicit retention periods |
| **Data Residency** | Single region MVP (US); multi-region V2+ |
| **Observability** | Prometheus + Grafana + Loki + Sentry from Day One |
| **AI Non-Goals** | No autonomous budget/launch/delete; human-in-the-loop required |
| **AI Cost Controls** | Monthly caps per plan; hard stop on Free/Starter |
| **Admin Tooling** | Internal roles, tenant suspension, support impersonation |
| **Exit Paths** | Safe disconnect, full export, 30-day deletion |
| **Support Boundaries** | Tiers per plan; explicit "will not do" list |
| **Threat Model** | Account takeover, token leakage, automation abuse acknowledged |

---

## Security First (Day One)

> **53 security requirements must be implemented before first deploy.**

| Category | Requirements |
|----------|--------------|
| Data Protection | Encryption at rest (AES-256), TLS 1.3, token encryption |
| App Security | Input validation, SQL injection prevention, XSS, CSRF, rate limiting |
| Auth Security | Argon2id hashing, secure sessions, JWT short expiry |
| Infrastructure | Firewall, DB not public, encrypted backups |
| Compliance | Privacy policy, GDPR (consent, deletion, export) |
| Threat Model | 6 primary threats acknowledged with mitigations |

---

## Key Decisions

| Area | Recommendation | Rationale |
|------|---------------|-----------|
| **Security** | Security-first from Day One | Can't retrofit security; build it in |
| **Architecture** | Modular monolith | Simpler for solo dev; split later if needed |
| **Ad Platform Abstraction** | Adapter pattern | Clean separation; testable; platform-agnostic core |
| **Background Jobs** | arq (or Celery) + Redis | Async-native; scheduling; retries |
| **AI Integration** | litellm + instructor | Multi-provider fallbacks; structured outputs |
| **Analytics Storage** | TimescaleDB on PostgreSQL | Time-series optimized; no new DB to manage |
| **Multi-tenancy** | PostgreSQL Row-Level Security | Built-in isolation; no app-level leaks |
| **UI Components** | shadcn/ui + Tremor | Copy-paste components; dashboard-ready |
| **State Management** | TanStack Query + Zustand | Server state + client state separation |

---

## Critical Timeline Risks

1. **Platform API approvals take 2-4 weeks** - Apply immediately
2. **Meta App Review is rigorous** - Start documentation in week 1
3. **Token refresh bugs cause silent failures** - Build robust from day 1
4. **AI costs can explode** - Implement per-user limits early

---

## Recommended Build Order (26 weeks)

| Phase | Weeks | Focus | Deliverable |
|-------|-------|-------|-------------|
| 1 | 1-3 | Foundation | Auth, DB schema, React shell |
| 2 | 4-6 | OAuth | Google Ads connection working |
| 3 | 7-9 | Campaigns | Create/manage Google campaigns |
| 4 | 10-11 | AI | Ad copy generation integrated |
| 5 | 12-14 | Analytics | Dashboard with metrics |
| 6 | 15-17 | Automation | Rules engine live |
| 7 | 18-22 | Multi-platform | Meta + TikTok added |
| 8 | 23-26 | Billing | Stripe + production polish |

---

## Features by Priority

### Must Ship (V1)
- Multi-platform dashboard (Google first, then Meta/TikTok)
- OAuth account connections
- Campaign CRUD
- AI ad copy generation
- Basic metrics (spend, clicks, conversions)
- Automated rules (pause on threshold)
- Stripe billing with tiers
- **Email notifications** (alerts, scheduled reports, system notifications)
- **WhatsApp Business notifications** (mobile alerts for campaigns/budgets)
- **Signal notifications** (privacy-focused mobile alerts)
- **Conversion pixel setup wizard** (guide users to install tracking)
- **Affiliate program** (referral codes, commission tracking)
- **Outbound webhooks** (send events to user systems)
- **CSV/bulk import** (import campaigns from spreadsheets)
- **Google SSO login** (Sign in with Google Workspace)
- **MFA (TOTP)** (Google Authenticator, Authy support)
- **RBAC** (Admin → Manager → User roles)
- **Session management** (view/revoke active sessions)
- **Audit logging** (who did what, when)

### Differentiators to Add
- AI budget allocation across platforms
- Creative performance insights
- Anomaly detection
- Predictive performance forecasting

### Explicitly NOT Building (V1)
- AI image/video generation
- LinkedIn/Twitter/Pinterest
- Custom attribution models
- Mobile apps
- White-label/reseller

---

## Tech Stack Summary

**Backend:**
```
fastapi + uvicorn + gunicorn
sqlalchemy + asyncpg + alembic
arq + redis
google-ads + facebook-business + httpx
litellm + instructor + openai + anthropic
authlib + fastapi-users + cryptography
resend (or sendgrid) - transactional email
pyotp + qrcode - MFA/TOTP support
```

**Frontend:**
```
react + typescript
@tanstack/react-query + zustand
shadcn/ui + @radix-ui/* + tailwindcss
recharts + @tremor/react
@tanstack/react-table
react-hook-form + zod
```

**Infrastructure:**
```
docker + docker-compose
nginx or caddy (reverse proxy + HTTPS)
postgresql 16 + timescaledb
redis 7
```

---

## Top 5 Pitfalls to Avoid

1. **Storing OAuth tokens in plain text** - Encrypt with Fernet from day 1
2. **Synchronous API calls** - Use background jobs for all platform calls
3. **Ignoring platform rate limits** - Implement adaptive rate limiting
4. **AI-generated policy violations** - Build content filters before launch
5. **No usage tracking** - Meter AI costs per-user from the start

---

## Next Step

With research complete, proceed to **Requirements Definition**:
- Review features by category
- Scope what's in V1 vs V2 vs out
- Create REQUIREMENTS.md with REQ-IDs
- Create ROADMAP.md with phases

---

*This summary synthesizes 2,057 lines of research across 4 documents.*

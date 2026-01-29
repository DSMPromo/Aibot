# Development Roadmap

> AI Marketing Automation Platform
> Version: 1.0
> Last Updated: 2026-01-29

---

## Overview

| Metric | Value |
|--------|-------|
| **Total Phases** | 8 |
| **Total Duration** | 26 weeks |
| **Total Requirements** | 248 (189 Must-Have for V1) |
| **Team** | Solo developer + Claude assistance |

---

## Phase Summary

| Phase | Weeks | Focus | Key Deliverable |
|-------|-------|-------|-----------------|
| 1 | 1-3 | Foundation | Auth, DB, Security, React shell |
| 2 | 4-6 | OAuth | Ad platform connections working |
| 3 | 7-9 | Campaigns | Campaign CRUD across platforms |
| 4 | 10-11 | AI | Ad copy generation integrated |
| 5 | 12-14 | Analytics | Unified dashboard with metrics |
| 6 | 15-17 | Automation | Rules engine live |
| 7 | 18-22 | Multi-Platform | Meta + TikTok complete |
| 8 | 23-26 | Billing + Launch | Stripe, polish, production |

---

## Phase 1: Foundation (Weeks 1-3)

> **Goal:** Security-first foundation, auth working, core database schema, React shell

### Week 1: Project Setup & Security Foundation

**Infrastructure:**
- [ ] Initialize Git repository (private)
- [ ] Create Docker Compose development environment
- [ ] Set up PostgreSQL 16 + TimescaleDB
- [ ] Set up Redis 7
- [ ] Configure Caddy reverse proxy with auto-TLS

**Backend Foundation:**
- [ ] FastAPI project structure (modular monolith)
- [ ] Pydantic settings configuration
- [ ] Database connection pooling (asyncpg)
- [ ] Alembic migrations setup
- [ ] Structured logging (structlog)

**Security (Day One - SEC-001 to SEC-044):**
- [ ] TLS 1.3 configuration
- [ ] Secure HTTP headers middleware
- [ ] Rate limiting setup (slowapi)
- [ ] Input validation patterns (Pydantic)
- [ ] Token encryption utilities (Fernet)
- [ ] Password hashing (Argon2id)

**Requirements:** SEC-001 to SEC-015, SEC-027 to SEC-033

### Week 2: Authentication System

**Core Auth:**
- [ ] User registration with email verification
- [ ] Login/logout with JWT (15 min access, 7 day refresh)
- [ ] Password reset flow
- [ ] Session management (store, revoke)
- [ ] Google SSO integration (OAuth 2.0)

**MFA:**
- [ ] TOTP setup with QR code generation
- [ ] MFA verification flow
- [ ] Recovery codes (10 single-use)

**Requirements:** AUTH-001 to AUTH-010, SEC-016 to SEC-021

### Week 3: User Management & Frontend Shell

**User Management:**
- [ ] Organization creation
- [ ] User invitation via email
- [ ] RBAC implementation (Admin, Manager, User)
- [ ] Role assignment
- [ ] Audit logging foundation

**Frontend:**
- [ ] React + Vite + TypeScript setup
- [ ] TanStack Query configuration
- [ ] Zustand stores setup
- [ ] shadcn/ui components installation
- [ ] Authentication flows (login, register, MFA)
- [ ] Protected routes

**Requirements:** USER-001 to USER-011, SEC-034 to SEC-038

### Phase 1 Exit Criteria

- [ ] User can register, verify email, login with MFA
- [ ] Google SSO working
- [ ] RBAC enforced on all endpoints
- [ ] All SEC requirements for Phase 1 passing
- [ ] Audit logs capturing user actions
- [ ] Observability stack running (Prometheus, Grafana, Loki)
- [ ] Security scan passing (OWASP top 10 addressed)

---

## Phase 2: OAuth & Ad Connections (Weeks 4-6)

> **Goal:** Connect Google Ads accounts, establish adapter pattern

### Week 4: OAuth Infrastructure

**OAuth Framework:**
- [ ] AuthLib integration
- [ ] OAuth state management (CSRF protection)
- [ ] Token encryption before storage
- [ ] Token refresh job setup

**Google Ads OAuth:**
- [ ] Google Ads API credentials setup
- [ ] OAuth authorization flow
- [ ] Token exchange and storage
- [ ] Account listing after connection

**Requirements:** CAMP-001, CAMP-006, INTG-001

### Week 5: Ad Platform Adapter Pattern

**Adapter Implementation:**
- [ ] Base adapter abstract class
- [ ] Google Ads adapter (list accounts, basic operations)
- [ ] Adapter factory pattern
- [ ] Error handling and retry logic

**Background Jobs:**
- [ ] arq worker setup
- [ ] Token refresh worker
- [ ] Dead letter queue implementation
- [ ] Job retry with exponential backoff

**Requirements:** PLAT-007 to PLAT-016

### Week 6: Connection Management UI

**Frontend:**
- [ ] Ad account connection wizard
- [ ] Connected accounts list view
- [ ] Account disconnect flow
- [ ] Connection status indicators
- [ ] Connection error handling UI

**Admin Tooling:**
- [ ] Internal admin dashboard shell
- [ ] Tenant search and view
- [ ] Support impersonation (read-only)

**Requirements:** CAMP-004, CAMP-005, ADMIN-001 to ADMIN-014

### Phase 2 Exit Criteria

- [ ] User can connect Google Ads account via OAuth
- [ ] Tokens stored encrypted, refresh working
- [ ] Dead letter queue capturing failed jobs
- [ ] Admin can search tenants and view details
- [ ] Connection health monitoring active

---

## Phase 3: Campaign Management (Weeks 7-9)

> **Goal:** Create and manage campaigns on Google Ads

### Week 7: Campaign Data Model

**Database:**
- [ ] Campaigns table with unified schema
- [ ] Campaign status workflow (draft → pending_review → active)
- [ ] Campaign versioning/history
- [ ] Platform-specific fields (JSONB)

**Backend:**
- [ ] Campaign CRUD endpoints
- [ ] Campaign validation rules
- [ ] Status transitions

**Requirements:** CAMP-007 to CAMP-011

### Week 8: Campaign Creation UI

**Frontend:**
- [ ] Campaign creation wizard (multi-step form)
- [ ] Platform selection
- [ ] Budget configuration
- [ ] Targeting options (basic)
- [ ] Ad copy input (manual)
- [ ] Review and submit

**Approval Workflow:**
- [ ] Manager approval queue
- [ ] Approval/rejection flow
- [ ] Notification on status change

**Requirements:** CAMP-016, CAMP-017

### Week 9: Campaign Sync & Bulk Operations

**Platform Sync:**
- [ ] Create campaign on Google Ads
- [ ] Status sync from platform
- [ ] Campaign update sync
- [ ] Pause/resume operations

**Bulk Operations:**
- [ ] Bulk pause/resume
- [ ] Campaign duplication
- [ ] CSV import foundation

**Requirements:** CAMP-012 to CAMP-015

### Phase 3 Exit Criteria

- [ ] User can create campaign and launch to Google Ads
- [ ] Manager approval workflow functional
- [ ] Campaign status synced from Google Ads
- [ ] Bulk operations working
- [ ] Campaign history tracked

---

## Phase 4: AI Integration (Weeks 10-11)

> **Goal:** AI-powered ad copy generation with guardrails

### Week 10: AI Service Setup

**AI Infrastructure:**
- [ ] litellm integration
- [ ] instructor for structured outputs
- [ ] Multi-provider fallback (OpenAI → Anthropic)
- [ ] Usage tracking per organization
- [ ] Cost tracking per generation

**AI Boundaries (Non-Goals):**
- [ ] Enforce AI-013 to AI-019 in code
- [ ] Human-in-the-loop required for all AI outputs
- [ ] AI output labeling ("AI-assisted")

**Requirements:** AI-008, AI-013 to AI-019

### Week 11: Ad Copy Generation

**Copy Generation:**
- [ ] Headline generation (multiple variations)
- [ ] Description generation
- [ ] CTA suggestions
- [ ] Platform-specific formatting
- [ ] Character limit enforcement

**Usage Controls:**
- [ ] Generation limits per plan
- [ ] Usage warnings at 80%
- [ ] Hard stop when limit reached
- [ ] Manual fallback when AI unavailable

**UI:**
- [ ] AI generation UI in campaign wizard
- [ ] Regenerate/iterate interface
- [ ] Side-by-side variation comparison
- [ ] Copy editing before publish

**Requirements:** AI-001 to AI-012, AI-020 to AI-027

### Phase 4 Exit Criteria

- [ ] AI generates ad copy variations
- [ ] Human must approve before publish
- [ ] Usage tracked and limited per plan
- [ ] Fallback to secondary provider working
- [ ] AI output clearly labeled

---

## Phase 5: Analytics Dashboard (Weeks 12-14)

> **Goal:** Unified dashboard showing metrics from Google Ads

### Week 12: Metrics Sync

**Data Pipeline:**
- [ ] Metrics sync worker (every 15 min)
- [ ] TimescaleDB hypertable for metrics
- [ ] Continuous aggregates for rollups
- [ ] Data retention policies

**Metrics Captured:**
- [ ] Impressions, clicks, CTR
- [ ] Spend (daily, total)
- [ ] Conversions, conversion value
- [ ] CPA, ROAS calculations

**Requirements:** ANAL-002 to ANAL-004

### Week 13: Dashboard UI

**Dashboard Components:**
- [ ] Overview cards (key metrics)
- [ ] Tremor charts (time series)
- [ ] Date range selector
- [ ] Period comparison (vs previous period)
- [ ] Campaign breakdown table

**Real-time Features:**
- [ ] Today's spend tracker
- [ ] Live data refresh

**Requirements:** ANAL-001, ANAL-005 to ANAL-008, ANAL-013

### Week 14: Reports & Export

**Export:**
- [ ] CSV export
- [ ] PDF report generation
- [ ] Scheduled reports (daily/weekly)

**Notifications:**
- [ ] Budget threshold alerts
- [ ] Performance anomaly detection (basic)
- [ ] Email notifications

**Requirements:** ANAL-009 to ANAL-011, NOTIF-001, NOTIF-002, NOTIF-009

### Phase 5 Exit Criteria

- [ ] Dashboard shows unified metrics
- [ ] Metrics syncing every 15 minutes
- [ ] CSV/PDF export working
- [ ] Scheduled reports sending
- [ ] Budget alerts functional

---

## Phase 6: Automation Rules (Weeks 15-17)

> **Goal:** Rule-based automation with human oversight

### Week 15: Rules Engine Core

**Rule System:**
- [ ] Rule data model (conditions, actions)
- [ ] Condition types (CPA, ROAS, spend thresholds)
- [ ] Action types (pause, resume, notify)
- [ ] Rule evaluation engine

**Execution:**
- [ ] Rule evaluation worker (every 5 min)
- [ ] Execution logging
- [ ] Manual override capability

**Requirements:** AUTO-001 to AUTO-007, AUTO-013, AUTO-014

### Week 16: Human-in-the-Loop

**Approval Mode:**
- [ ] Rules can require approval before action
- [ ] Pending actions queue
- [ ] Approve/reject interface
- [ ] Action timeout handling

**Notifications:**
- [ ] Rule triggered notification
- [ ] Action pending notification
- [ ] Action completed notification

**Requirements:** AUTO-009, AUTO-012

### Week 17: Advanced Rules & Templates

**Advanced Features:**
- [ ] Budget adjustment actions (increase/decrease %)
- [ ] Time-based conditions (schedules)
- [ ] Rule templates (pre-built)
- [ ] Rule history/audit log

**Requirements:** AUTO-005, AUTO-008, AUTO-010, AUTO-011, AUTO-015

### Phase 6 Exit Criteria

- [ ] Rules evaluate automatically
- [ ] Actions require human approval (configurable)
- [ ] Rule execution logged
- [ ] Templates available
- [ ] Manual override always available

---

## Phase 7: Multi-Platform (Weeks 18-22)

> **Goal:** Meta Ads and TikTok Ads integration

### Weeks 18-19: Meta Ads Integration

**OAuth:**
- [ ] Meta Marketing API credentials
- [ ] Facebook Login for Business
- [ ] Token exchange and refresh

**Adapter:**
- [ ] Meta Ads adapter implementation
- [ ] Campaign creation
- [ ] Metrics sync
- [ ] Status sync

**Requirements:** CAMP-002, INTG-002

### Weeks 20-21: TikTok Ads Integration

**OAuth:**
- [ ] TikTok Marketing API credentials
- [ ] OAuth flow

**Adapter:**
- [ ] TikTok adapter implementation
- [ ] Campaign creation
- [ ] Metrics sync

**Requirements:** CAMP-003, INTG-003

### Week 22: Cross-Platform Features

**Unified Experience:**
- [ ] Cross-platform campaign creation
- [ ] Unified metrics aggregation
- [ ] Platform comparison views
- [ ] UTM parameter auto-generation

**Requirements:** INTG-013

### Phase 7 Exit Criteria

- [ ] Meta Ads connection working
- [ ] TikTok Ads connection working
- [ ] Cross-platform campaigns possible
- [ ] Unified dashboard showing all platforms

---

## Phase 8: Billing & Launch (Weeks 23-26)

> **Goal:** Stripe integration, production hardening, launch

### Week 23: Stripe Integration

**Billing Core:**
- [ ] Stripe customer creation
- [ ] Subscription plans setup
- [ ] Checkout flow
- [ ] Webhook handling

**Plan Management:**
- [ ] Plan limits enforcement
- [ ] Upgrade/downgrade flow
- [ ] Billing history

**Requirements:** BILL-001 to BILL-007, BILL-011

### Week 24: Notifications & Integrations

**Notification Channels:**
- [ ] Slack integration
- [ ] WhatsApp Business API
- [ ] Signal (self-hosted bridge)
- [ ] In-app notification center
- [ ] Notification preferences

**Outbound Webhooks:**
- [ ] Webhook configuration UI
- [ ] Event delivery
- [ ] Retry logic
- [ ] Signature verification

**Requirements:** INTG-004 to INTG-007, NOTIF-001 to NOTIF-011

### Week 25: Production Hardening

**Security Review:**
- [ ] Full security audit
- [ ] Penetration testing basics
- [ ] OWASP checklist review
- [ ] Dependency vulnerability scan

**Performance:**
- [ ] Load testing
- [ ] Database query optimization
- [ ] Caching strategy validation
- [ ] CDN configuration

**Documentation:**
- [ ] API documentation
- [ ] User documentation
- [ ] Privacy policy final review
- [ ] Terms of service final review

**Requirements:** SEC-051, SEC-052

### Week 26: Launch Preparation

**Final Checks:**
- [ ] Backup and restore testing
- [ ] Disaster recovery plan
- [ ] Support workflow ready
- [ ] Status page setup

**Launch:**
- [ ] Production deployment
- [ ] DNS configuration
- [ ] Monitoring alerts active
- [ ] On-call rotation (solo)

### Phase 8 Exit Criteria

- [ ] Stripe billing fully functional
- [ ] All notification channels working
- [ ] Security review passed
- [ ] Production environment stable
- [ ] Launch checklist complete

---

## Post-Launch (V1.1+)

### V1.1 (Weeks 27-30)
- Affiliate program (BILL-008 to BILL-010)
- Google Analytics 4 integration (INTG-011, INTG-012)
- Conversion pixel wizard (ANAL-012)
- Landing page tracking (ANAL-014 to ANAL-016)

### V1.2 (Weeks 31-34)
- Ad policy pre-validation (AI-028 to AI-034)
- Anomaly detection improvements (NOTIF-010)
- AI targeting recommendations (AI-006)
- AI budget suggestions (AI-007)

### V2.0 (Future)
- Additional ad platforms (LinkedIn, Pinterest)
- AI image generation
- Advanced attribution
- White-label features
- Multi-region deployment

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Platform API approval delays | High | High | Apply in Week 1, have workarounds |
| AI cost overruns | Medium | Medium | Hard caps from Day 1, monitor closely |
| Security vulnerability | Low | Critical | Security-first approach, regular audits |
| Solo dev burnout | Medium | High | Realistic timeline, take breaks |
| Scope creep | High | Medium | Strict V1 scope, defer to V1.1+ |

---

## Milestones

| Milestone | Week | Success Criteria |
|-----------|------|------------------|
| **M1: Foundation** | 3 | Auth + RBAC + security passing |
| **M2: Connected** | 6 | Google Ads OAuth working |
| **M3: Campaigns** | 9 | Campaign creation to Google Ads |
| **M4: AI-Powered** | 11 | AI copy generation live |
| **M5: Insights** | 14 | Dashboard with metrics |
| **M6: Automated** | 17 | Rules engine operational |
| **M7: Multi-Platform** | 22 | Meta + TikTok integrated |
| **M8: Launch** | 26 | Production deployment |

---

*Roadmap assumes ~40 hours/week development. Adjust timeline based on actual velocity.*

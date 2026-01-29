# Platform Decisions

> Foundational platform-level decisions that must be made before engineering starts.
> These are not features. These are constraints and boundaries.

---

## 1. Data Ownership and Retention

### Ownership

| Data Type | Owner | Notes |
|-----------|-------|-------|
| Campaign configurations | Tenant | Exportable, deletable on request |
| Ad copy (user-written) | Tenant | Full ownership |
| Ad copy (AI-generated) | Tenant | Licensed for their use; we retain training rights unless opted out |
| Performance metrics | Tenant | Sourced from ad platforms; we store copies |
| Audit logs | Platform | Required for security; tenant can request copy |
| System logs | Platform | Not tenant data; operational only |
| OAuth tokens | Platform | Encrypted; deleted on disconnect |

### Retention Periods

| Data Type | Active Retention | Archive | Hard Delete |
|-----------|------------------|---------|-------------|
| Campaign data | While subscribed | 90 days post-churn | On request |
| Performance metrics | 2 years | 1 year archived | After archive |
| Audit logs | 90 days hot | 2 years cold | After cold storage |
| AI generation history | 90 days | None | After 90 days |
| System logs | 30 days | None | After 30 days |
| OAuth tokens | While connected | None | Immediate on disconnect |
| User PII | While active | 30 days post-deletion | After 30 days |

### Deletion Workflows

| Trigger | Action | Timeline |
|---------|--------|----------|
| User requests account deletion | Soft delete, queue hard delete | 30 days |
| User disconnects ad account | Delete tokens, keep metrics | Immediate / retained |
| Subscription cancelled | Archive data, downgrade access | 90 days retention |
| GDPR erasure request | Hard delete all PII | 30 days max |
| Tenant admin removes user | Remove user access, retain audit logs | Immediate |

### Export Rights

- **Always exportable:** Campaigns, ad copy, performance metrics, audit logs
- **Format:** JSON, CSV (user choice)
- **Timeline:** Export available within 24 hours of request
- **Cost:** Included in all plans (no export fees)

---

## 2. Multi-Region and Residency Strategy

### MVP Decision: Single Region (US)

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Primary region** | US-East (or your VPS location) | Simplicity, lowest latency to ad platform APIs |
| **Database location** | Same region as app | No cross-region latency |
| **Backups** | Same region (encrypted) | Cost control |
| **User restriction** | None (global users, US data) | Accept latency tradeoff |

### Future Multi-Region (V2+)

| Trigger | Action |
|---------|--------|
| EU customer demand >20% | Add EU region option |
| Enterprise compliance requirement | Offer data residency selection |
| Latency complaints >10% of support | Evaluate CDN or regional read replicas |

### What We Tell Users (MVP)

> "Your data is stored in the United States. All data is encrypted at rest and in transit.
> If you require data residency in a specific region, contact us for enterprise options."

### Compliance Notes

- **GDPR:** US storage is compliant with appropriate safeguards (SCCs)
- **No health/financial data:** Not subject to HIPAA/PCI-DSS (ad campaigns only)
- **Ad platform data:** Subject to Google/Meta/TikTok data policies (pass-through)

---

## 3. Observability and Operations

### System Health Metrics (Internal Only)

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| API response time p95 | > 2s for 5 min | Page on-call |
| Error rate | > 1% for 5 min | Alert Slack |
| Database connections | > 80% pool | Alert Slack |
| Redis memory | > 80% | Alert Slack |
| Disk usage | > 85% | Alert Slack |
| Background job queue depth | > 1000 | Alert Slack |
| Background job failure rate | > 5% | Page on-call |

### Connector Failure Alerts

| Connector | Failure Condition | Alert |
|-----------|-------------------|-------|
| Google Ads API | 3 consecutive failures | Alert + disable sync for account |
| Meta Ads API | 3 consecutive failures | Alert + disable sync for account |
| TikTok Ads API | 3 consecutive failures | Alert + disable sync for account |
| Stripe | Any payment failure | Alert + notify user |
| AI Provider | Primary + fallback fail | Alert + degrade gracefully |

### Job Retry and Dead Letter Handling

| Job Type | Max Retries | Backoff | Dead Letter Action |
|----------|-------------|---------|-------------------|
| Metrics sync | 3 | Exponential (1m, 5m, 15m) | Log, alert, skip until next cycle |
| Campaign push | 3 | Exponential | Log, alert, notify user |
| Token refresh | 5 | Exponential | Alert, mark account as disconnected |
| AI generation | 2 | Linear (30s) | Return error to user, log |
| Webhook delivery | 5 | Exponential | Log to dead letter, provide retry UI |
| Email send | 3 | Exponential | Log, alert if batch fails |

### Dead Letter Queue

- All failed jobs after max retries go to dead letter table
- Dead letters retained for 7 days
- Admin UI to inspect, retry, or dismiss
- Daily digest of dead letter count to ops channel

### Minimum Ops Stack

```
# Observability (self-hosted friendly)
- Prometheus + Grafana (metrics)
- Loki (logs)
- Sentry (errors)
- UptimeRobot or similar (external health check)

# Alerts
- Slack webhook for all alerts
- PagerDuty or phone for critical (optional)
```

---

## 4. Ad Policy Pre-Validation

### Pre-Launch Checks (Before Campaign Publish)

| Check | Scope | Action on Fail |
|-------|-------|----------------|
| Forbidden terms scan | Headlines, descriptions | Block publish, show violations |
| Character limits | Per platform specs | Block publish, show errors |
| URL validation | Landing page URLs | Block publish if unreachable |
| URL safety check | Landing page URLs | Warn if flagged by Safe Browsing |
| Trademark scan | Headlines, descriptions | Warn (don't block) |
| Policy keyword scan | All text | Warn with specific policy reference |

### Forbidden Terms List (Examples)

```
# Absolute blocks
- Profanity
- Hate speech indicators
- Illegal product terms
- Competitor trademark misuse

# Platform-specific warnings
- "Guaranteed" (Google policy)
- "Best" without qualification (Meta policy)
- Health claims without disclaimer
- Financial return promises
```

### Landing Page Validation

| Check | Implementation | Frequency |
|-------|----------------|-----------|
| URL reachable | HEAD request | On campaign create/edit |
| HTTPS required | URL scheme check | On campaign create/edit |
| Safe Browsing | Google Safe Browsing API | On campaign create/edit |
| Page load time | Optional lighthouse check | On request |

### Policy Violation Handling

1. **Pre-publish:** Block or warn based on severity
2. **Post-publish (platform rejection):**
   - Sync rejection status from platform
   - Notify user with specific violation
   - Suggest AI-assisted fix
3. **Account warning from platform:**
   - Surface in dashboard prominently
   - Require acknowledgment before new campaigns

---

## 5. AI Scope Boundaries

### AI Will Do (Assisted Drafting)

- Generate ad copy variations from user input
- Suggest headlines and descriptions
- Recommend targeting options (user reviews before applying)
- Analyze performance and suggest improvements
- Summarize campaign performance in natural language

### AI Will NEVER Do (Non-Goals)

| Action | Why Not |
|--------|---------|
| **Autonomous budget changes** | Financial risk; user must approve all spend changes |
| **Autonomous campaign launches** | Brand risk; human must review and publish |
| **Autonomous account-wide edits** | Blast radius too large; single campaign max |
| **Autonomous pause/unpause without rule** | Unexpected behavior; only via explicit automation rules |
| **Access to payment methods** | Separation of concerns; AI never touches billing |
| **Delete campaigns without confirmation** | Irreversible; always require explicit user action |
| **Modify other users' campaigns** | RBAC boundary; AI operates in user's permission scope |

### AI Transparency

- All AI-generated content is labeled as "AI-assisted"
- Users can see prompt/input that generated output
- Users can regenerate or edit all AI output
- AI suggestions require explicit "Apply" action

### AI Liability Boundary

> "AI-generated content is provided as suggestions only. Users are responsible
> for reviewing and approving all content before publication. [Platform] is not
> liable for ad policy violations or performance of AI-suggested content."

---

## 6. Cost Controls for AI Usage

### Usage Caps by Plan

| Plan | Monthly AI Generations | Overage Behavior |
|------|------------------------|------------------|
| Free | 50 | Hard stop |
| Starter | 500 | Hard stop |
| Pro | 2,000 | Warn at 80%, hard stop at 100% |
| Agency | 10,000 | Warn at 80%, soft cap (degraded speed) |
| Enterprise | Custom | Custom alerts, no hard stop |

### What Counts as "Generation"

| Action | Cost |
|--------|------|
| Generate ad copy (1 campaign) | 1 generation |
| Regenerate/iterate | 1 generation |
| AI targeting suggestion | 1 generation |
| AI performance summary | 0.5 generation |
| Bulk generate (5 campaigns) | 5 generations |

### Hard Stop Behavior

When limit reached:
1. Block new AI generation requests
2. Show clear message: "AI generation limit reached. Upgrade or wait until [date]."
3. Allow manual ad copy creation (no AI)
4. Allow all other platform features

### Admin Visibility

| Metric | Visibility |
|--------|------------|
| AI generations this month | User dashboard |
| AI generations by tenant | Internal admin |
| AI cost ($) by tenant | Internal admin |
| AI cost ($) total | Internal admin |
| Token usage breakdown | Internal admin (debugging) |

### Cost Tracking Implementation

```python
# Track every AI call
class AIUsageLog(Base):
    id: UUID
    org_id: UUID
    user_id: UUID
    generation_type: str  # "ad_copy", "targeting", "summary"
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal  # Calculated from token pricing
    created_at: datetime
```

### Monthly Cost Alerts (Internal)

| Threshold | Action |
|-----------|--------|
| Tenant AI cost > $10/month | Log for review |
| Tenant AI cost > $50/month | Alert ops |
| Total AI cost > budget | Alert + review pricing |

---

## 7. Internal Admin Tooling

### Internal Roles (Not User-Facing)

| Role | Permissions |
|------|-------------|
| **Platform Admin** | Full system access, all tenants, all operations |
| **Support Agent** | Read tenant data, impersonate users (with audit), no billing access |
| **Finance** | Billing data, refunds, no tenant data access |
| **On-Call Engineer** | System metrics, job queues, no tenant data |

### Tenant Management

| Action | Role Required | Audit Logged |
|--------|---------------|--------------|
| View tenant list | Support+ | Yes |
| View tenant details | Support+ | Yes |
| Suspend tenant | Platform Admin | Yes |
| Unsuspend tenant | Platform Admin | Yes |
| Delete tenant | Platform Admin (2-person approval) | Yes |
| Modify tenant plan | Finance, Platform Admin | Yes |
| Issue refund | Finance | Yes |

### Support Impersonation

| Requirement | Implementation |
|-------------|----------------|
| Explicit "impersonate" action | Not automatic |
| Time-limited session | 1 hour max |
| Audit log entry | Who, when, tenant, duration |
| Visual indicator | Banner in UI showing impersonation mode |
| User notification | Optional email to tenant admin |
| Read-only by default | Write actions require additional approval |

### Abuse Handling

| Signal | Action |
|--------|--------|
| Spam content detected | Flag for review, suspend if confirmed |
| Unusual API volume | Rate limit, alert |
| Payment fraud | Suspend immediately, investigate |
| ToS violation reported | Review within 24h, suspend if confirmed |
| Ad platform ban (user's account) | Notify user, no platform action |

### Admin UI Requirements

- Tenant search (by email, org name, ID)
- Tenant detail view (subscription, usage, connected accounts)
- Impersonation button (with confirmation)
- Suspension toggle
- Usage graphs (AI, API calls, storage)
- Job queue health
- Dead letter queue inspector
- System health dashboard

---

## 8. Migration and Exit Paths

### Disconnect Ad Accounts

| Step | Action |
|------|--------|
| 1 | User clicks "Disconnect" |
| 2 | Revoke OAuth token with platform |
| 3 | Delete stored tokens (immediate) |
| 4 | Stop all sync jobs for account |
| 5 | Retain historical metrics (user can delete separately) |
| 6 | Confirm disconnection in UI |

### Export Data

| Data Type | Format | Included |
|-----------|--------|----------|
| Campaigns | JSON, CSV | All campaign configs |
| Ad copy | JSON, CSV | All ad copy (including AI-generated) |
| Performance metrics | CSV | All historical metrics |
| Automation rules | JSON | All rules and execution history |
| Audit logs | JSON | User's activity logs |

### Export Process

1. User requests export from Settings
2. Background job generates export
3. Notify user when ready (email + in-app)
4. Download link valid for 7 days
5. Export includes README with data schema

### Account Deletion

| Option | What Happens |
|--------|--------------|
| **Soft delete** | Account disabled, data retained 30 days, recoverable |
| **Hard delete** | All data permanently removed, not recoverable |
| **Org deletion (admin)** | Soft delete all users, data retained 30 days |

### Deletion Process

1. User requests deletion
2. Confirm via email link
3. Disconnect all ad accounts
4. Cancel subscription (prorate refund if applicable)
5. Soft delete (30 day hold)
6. Hard delete after 30 days (automated job)
7. Confirm deletion via email

### What We Keep After Hard Delete

- Aggregate analytics (no PII)
- Audit logs of deletion request (compliance)
- Nothing else

---

## 9. SLA and Support Boundaries

### Support Tiers by Plan

| Plan | Support Channel | Response Target | Hours |
|------|-----------------|-----------------|-------|
| Free | Help docs only | N/A | N/A |
| Starter | Email | 48h (business) | Business hours |
| Pro | Email + Chat | 24h (business) | Business hours |
| Agency | Email + Chat + Priority | 4h (business) | Extended (8am-8pm) |
| Enterprise | Dedicated + Phone | 1h (critical) | 24/7 for critical |

### What Support Will Do

- Help with platform usage questions
- Investigate sync issues
- Explain error messages
- Assist with account/billing issues
- Report bugs to engineering
- Provide workarounds for known issues

### What Support Will NOT Do

| Request | Response |
|---------|----------|
| Write ad copy for users | Provide AI tool guidance |
| Manage user's ad accounts | Explain how to connect/use |
| Guarantee ad performance | Explain platform is a tool, not a service |
| Debug user's landing pages | Out of scope |
| Provide marketing strategy | Out of scope, recommend consultants |
| Recover data after hard delete | Not possible |
| Expedite ad platform approvals | No control over Google/Meta/TikTok |

### Escalation Path

1. **Tier 1 (Support Agent):** Common questions, known issues
2. **Tier 2 (Senior Support):** Complex issues, billing disputes
3. **Tier 3 (Engineering):** Bugs, system issues
4. **Tier 4 (Management):** Legal, major incidents, enterprise escalations

### Incident Communication

| Severity | User Communication |
|----------|-------------------|
| **Critical (platform down)** | Status page, email to all, social media |
| **Major (feature broken)** | Status page, email to affected |
| **Minor (degraded)** | Status page only |
| **Maintenance (planned)** | 48h advance email + status page |

---

## 10. Threat Model (Light)

### Primary Threats

| Threat | Impact | Mitigation |
|--------|--------|------------|
| **Account takeover** | Attacker gains access to user account | MFA required, session management, login alerts |
| **Token leakage** | OAuth tokens exposed | Encryption at rest, never log tokens, short expiry |
| **Automation abuse** | Malicious rules drain budgets | Human-in-the-loop, budget caps, anomaly detection |
| **Cross-tenant data access** | User sees another tenant's data | Row-level security, authorization checks on every request |
| **AI prompt injection** | User manipulates AI to bypass policies | Input sanitization, output filtering, separate system prompts |
| **Credential stuffing** | Automated login attempts | Rate limiting, account lockout, breach detection |
| **Insider threat** | Support agent abuses access | Audit logging, impersonation controls, least privilege |

### Attack Surface

| Surface | Exposure | Protection |
|---------|----------|------------|
| Public API | Internet | Auth required, rate limiting, input validation |
| Admin API | Internal | VPN/IP restriction, separate auth, audit logging |
| Database | Internal | Not publicly accessible, encrypted connections |
| Redis | Internal | Not publicly accessible, auth enabled |
| Background jobs | Internal | No external trigger, job validation |
| Webhooks (inbound) | Internet | Signature verification, IP allowlist where possible |
| OAuth callbacks | Internet | State parameter, origin validation |

### Incident Response (Light)

| Phase | Action |
|-------|--------|
| **Detection** | Alerts from monitoring, user reports, anomaly detection |
| **Triage** | Assess severity, identify affected scope |
| **Containment** | Disable affected accounts/features, revoke tokens |
| **Communication** | Notify affected users, update status page |
| **Recovery** | Fix root cause, restore service |
| **Post-mortem** | Document incident, improve defenses |

### Security Review Triggers

- Before launch
- After any security incident
- Before major new feature (especially auth/payment)
- Annually (minimum)
- When adding new external integration

---

## Summary Checklist

Before engineering starts, confirm:

- [ ] Data ownership and retention periods defined
- [ ] Single region MVP decision documented
- [ ] Observability stack chosen
- [ ] Ad policy pre-checks specified
- [ ] AI non-goals explicitly stated
- [ ] AI usage caps per plan defined
- [ ] Internal admin roles and tooling scoped
- [ ] Export and deletion workflows designed
- [ ] Support tiers and boundaries documented
- [ ] Threat model acknowledged

---

*These decisions are foundational. They affect architecture, cost, compliance, and trust.*
*Review and approve before writing code.*

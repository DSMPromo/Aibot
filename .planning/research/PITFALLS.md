# AI Marketing Automation Platform - Common Pitfalls

## Overview
Critical mistakes and gotchas when building a multi-platform ad management SaaS (Google Ads, Meta Ads, TikTok Ads) with AI content generation.

---

## 1. Ad Platform API Pitfalls

### 1.1 Google Ads API

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Developer token approval takes weeks** | Stuck in "test account" mode; can't access real customer data | Apply for Basic access immediately; have test accounts ready; plan 2-4 week approval buffer | Phase 1 |
| **Rate limits are per-developer-token, not per-user** | 429 errors spike when onboarding multiple customers | Implement request queuing with exponential backoff; batch operations; cache aggressively | Phase 2 |
| **Mutate operations counted differently than reads** | Hit limits faster than expected during campaign creation | Separate read/write quotas in your rate limiter; prioritize writes | Phase 2 |
| **API versioning deprecation cycles** | Sudden breakages after ignoring deprecation warnings | Subscribe to Google Ads API announcements; implement version abstraction layer | Phase 2 |
| **Customer ID format inconsistencies** | API errors with "invalid customer ID" | Always strip hyphens; validate format before API calls | Phase 1 |

### 1.2 Meta (Facebook) Ads API

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **App Review process is rigorous and slow** | Blocked from production access for weeks | Start App Review in Phase 1; document every permission justification thoroughly | Phase 1 |
| **Rate limits are dynamic and opaque** | Unpredictable throttling; "User request limit reached" | Implement adaptive rate limiting; monitor X-Business-Use-Case-Usage headers | Phase 2 |
| **Ad account access requires Business Manager** | Can't manage customer accounts without complex BM setup | Design for Business Manager integration from day one | Phase 1 |
| **Insights API has different rate limits** | Reporting crashes while campaign management works | Separate rate limit pools for Insights vs. Management APIs | Phase 2 |
| **Creative hash requirements** | Image uploads fail silently or duplicate | Hash images client-side; implement deduplication | Phase 2 |

### 1.3 TikTok Ads API

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Sandbox limitations are severe** | Features work in sandbox but fail in production | Test with real (low-budget) accounts early; don't trust sandbox parity | Phase 2 |
| **Advertiser ID onboarding complexity** | Users can't connect accounts; unclear error messages | Build clear onboarding wizard with step-by-step verification | Phase 2 |
| **Fewer client libraries/community resources** | More custom code needed; fewer Stack Overflow answers | Budget extra development time; consider building abstraction early | Phase 1 |
| **Regional API endpoint differences** | API calls fail for international users | Implement region detection and endpoint routing | Phase 3 |

---

## 2. OAuth Token Management Pitfalls

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Token expiration not handled gracefully** | Users suddenly see "disconnected" status; jobs fail silently | Implement proactive token refresh (before expiry); queue retry mechanism | Phase 2 |
| **Storing tokens insecurely** | Tokens in plain text in database; logs expose tokens | Encrypt at rest; use secrets manager; never log tokens | Phase 1 |
| **Refresh token rotation not handled** | Meta's rotating refresh tokens cause disconnections | Store and update both access AND refresh tokens atomically | Phase 1 |
| **Scope creep during OAuth** | Requesting too many permissions triggers platform review | Request minimum viable scopes; add incrementally with re-auth | Phase 1 |
| **Missing token revocation handling** | Users revoke access but your app keeps trying | Webhook for revocation events; graceful degradation; clear user notification | Phase 2 |
| **Multi-account token confusion** | Wrong account's token used for API calls | Strong account-token binding; validate account ID before operations | Phase 1 |
| **Google Ads requires manager account hierarchy** | Direct customer OAuth doesn't give API access | Design for MCC (Manager Account) pattern from start | Phase 1 |

---

## 3. AI Content Generation Pitfalls

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Generated ads violate platform policies** | Ads rejected; account warnings; potential bans | Build policy-checking layer; prohibited word lists; pre-submission validation | Phase 2 |
| **AI generates misleading claims** | "Best in the world" / "Guaranteed results" triggers rejection | Constrain prompts; implement claim detection; require human review for first campaigns | Phase 2 |
| **Trademark/brand name issues** | Ads using competitor names get rejected or legal issues | Trademark detection; brand safety filters | Phase 3 |
| **Character limit violations** | Headlines too long; descriptions truncated | Enforce limits in prompts; validate output before submission | Phase 2 |
| **Inconsistent quality/tone** | Ads don't match brand voice; generic output | User-configurable brand guidelines; fine-tuning or few-shot examples | Phase 3 |
| **AI hallucinations in product details** | Wrong prices, features, URLs in generated ads | Ground generation in verified product data; always validate URLs/prices | Phase 2 |
| **Over-reliance on AI without human loop** | Low conversion rates; brand damage | Mandatory review queue for high-spend campaigns; A/B test AI vs. human | Phase 2 |
| **Prompt injection via user input** | Users manipulate AI to generate policy-violating content | Sanitize inputs; separate user data from system prompts | Phase 1 |

---

## 4. Billing and Metering Pitfalls

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Usage tracking is eventually consistent** | Customers dispute charges; free tier abuse | Implement real-time metering with reconciliation; clear usage dashboards | Phase 2 |
| **AI API costs explode unexpectedly** | OpenAI/Anthropic bills spike; margins disappear | Token counting; cost caps per user; tiered limits; cache common generations | Phase 1 |
| **Failed operations still incur AI costs** | Paying for generations that never become ads | Cache AI outputs; only charge on successful ad creation | Phase 2 |
| **Free tier abuse** | Multiple accounts; API scraping | Rate limiting; email verification; usage anomaly detection | Phase 2 |
| **Unclear pricing model** | Users confused about what they're paying for | Simple, predictable pricing (per campaign? per ad? per month?) | Phase 1 |
| **No spending alerts** | Customers get surprise bills; churn and chargebacks | Configurable spend alerts; hard caps option | Phase 2 |
| **Stripe webhook failures** | Payments succeed but access not granted; or opposite | Idempotent webhook handlers; reconciliation jobs; manual override tools | Phase 2 |

---

## 5. Security Vulnerabilities

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Ad account credentials as high-value target** | You're storing access to real ad spend budgets | Encryption at rest; minimal token scopes; audit logging; 2FA required | Phase 1 |
| **IDOR in campaign/account access** | Users can view/modify other users' campaigns | Strict authorization checks on every endpoint; row-level security | Phase 1 |
| **API keys exposed in frontend** | Platform API keys in JavaScript bundles | Backend proxies all platform API calls; never expose credentials client-side | Phase 1 |
| **Insufficient audit logging** | Can't determine who changed what; compliance issues | Log all mutations with user, timestamp, before/after states | Phase 2 |
| **Webhook endpoint vulnerabilities** | Spoofed webhooks trigger actions; data exfiltration | Verify webhook signatures; IP allowlisting where possible | Phase 1 |
| **SQL injection in reporting queries** | Dynamic report builders are injection-prone | Parameterized queries only; ORM for all database access | Phase 1 |
| **Stored XSS via ad content** | User-submitted ad copy rendered unsanitized | Sanitize all user input; Content Security Policy headers | Phase 1 |

---

## 6. Scaling Issues That Hit Early

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **Synchronous API calls block requests** | Timeouts on campaign creation; slow UI | Background job queue from day one (Celery, RQ, or similar) | Phase 1 |
| **N+1 queries in reporting** | Dashboard load times grow with data | Eager loading; query optimization; denormalized stats tables | Phase 2 |
| **No connection pooling** | Database connection exhaustion under load | Configure connection pools; use async database drivers | Phase 1 |
| **Unbounded data fetching** | "Fetch all campaigns" works until it doesn't | Pagination everywhere; cursor-based for large datasets | Phase 1 |
| **Monolithic background jobs** | One slow job blocks all others | Separate queues by priority/type; job timeout limits | Phase 2 |
| **Polling instead of webhooks** | API rate limits hit; stale data | Implement webhooks where available; smart polling intervals | Phase 2 |
| **No caching layer** | Repeated identical API calls; slow responses | Redis for session/token caching; CDN for static assets | Phase 2 |
| **VPS resource exhaustion** | Single server can't handle growth | Design for horizontal scaling; containerize early; DB on managed service | Phase 2 |

---

## 7. Scope Creep Traps

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **"Just add one more platform"** | LinkedIn, Twitter, Pinterest requests before core is solid | Explicitly defer; build platform abstraction layer first | Phase 3+ |
| **Advanced analytics before basics work** | Building attribution models before campaigns reliably create | Ship MVP with basic metrics; iterate based on actual usage | Phase 2 |
| **AI features beyond ad copy** | Auto-bidding, audience AI, creative testing before manual works | AI copy generation first; prove value; expand cautiously | Phase 2+ |
| **Multi-tenancy complexity** | Building white-label before single product works | Single-tenant MVP; refactor for multi-tenant only if validated | Phase 3+ |
| **Custom reporting builder** | Weeks on drag-and-drop report UX | Pre-built report templates; export to CSV; custom reports later | Phase 3 |
| **Real-time everything** | WebSocket dashboards before batch reporting works | Batch updates with reasonable intervals; real-time for specific features only | Phase 3 |
| **Mobile app** | Building native apps before web is stable | Responsive web first; PWA if needed; native only if validated | Phase 3+ |

---

## 8. Integration Testing Gaps

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| **No sandbox/test environment** | Testing against production APIs | Set up isolated test accounts for each platform immediately | Phase 1 |
| **Mocking hides real API behavior** | Tests pass but production fails | Integration tests against real sandbox APIs in CI | Phase 2 |
| **Edge cases in API responses** | Partial failures, rate limits not tested | Chaos testing; intentionally trigger error conditions | Phase 2 |
| **Date/timezone handling** | Reports off by a day; scheduling issues | UTC everywhere internally; explicit timezone handling for display | Phase 1 |

---

## Phase Summary

### Phase 1 (Foundation) - Address Immediately
- Platform developer account applications and approvals
- Secure token storage architecture
- Basic security (auth, authorization, input validation)
- Background job infrastructure
- Database connection management
- UTC-based date handling

### Phase 2 (Core Features) - Build Robustly
- Rate limiting and quota management
- Token refresh and revocation handling
- AI content policy compliance
- Billing/metering accuracy
- Caching and performance optimization
- Comprehensive audit logging

### Phase 3 (Scale & Expand) - Plan For Later
- Additional platforms
- Advanced AI features
- Multi-tenancy/white-label
- Custom reporting
- International/regional support

---

## Red Flags Checklist

Before each phase, verify:

- [ ] Have I applied for all platform developer access? (Takes weeks)
- [ ] Are OAuth tokens encrypted at rest?
- [ ] Do I have background job processing?
- [ ] Is every endpoint authorization-checked?
- [ ] Am I tracking AI API costs per user?
- [ ] Do I have rate limiting on my own APIs?
- [ ] Are platform API calls wrapped with retry logic?
- [ ] Is there a human review step for AI-generated content?
- [ ] Do I have usage limits to prevent runaway costs?
- [ ] Am I logging enough to debug production issues?

---

*Last updated: 2026-01-29*

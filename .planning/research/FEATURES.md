# AI Marketing Automation Platform - Feature Research

## Executive Summary

This document outlines feature expectations for an AI-powered SaaS platform managing paid ad campaigns across Google Ads, Meta Ads, and TikTok Ads. Features are categorized by competitive necessity and strategic value.

---

## Table Stakes (Must-Have or Users Leave)

### 1. Multi-Platform Campaign Management

| Feature | Description | Complexity |
|---------|-------------|------------|
| Unified Dashboard | Single view of all campaigns across Google, Meta, TikTok | Medium - API integration with 3 platforms |
| Campaign Creation Wizard | Step-by-step campaign setup with platform-specific options | Medium - Different requirements per platform |
| Bulk Campaign Operations | Edit, pause, duplicate multiple campaigns at once | Low-Medium |
| Campaign Status Monitoring | Real-time status, delivery issues, policy violations | Medium - Requires webhook/polling infrastructure |
| Budget Management | Set, monitor, and adjust budgets across platforms | Low |
| Scheduling | Campaign start/end dates, dayparting options | Low |

**Why Table Stakes:** Users expect to manage everything in one place. Without this, they'll just use native platform tools.

### 2. Core Analytics & Reporting

| Feature | Description | Complexity |
|---------|-------------|------------|
| Cross-Platform Metrics | Unified view of spend, impressions, clicks, conversions | Medium - Data normalization across platforms |
| Custom Date Ranges | Compare periods, rolling windows, custom ranges | Low |
| Export to CSV/Excel | Download reports for stakeholders | Low |
| Basic Dashboards | Pre-built views for common KPIs | Low-Medium |
| Conversion Tracking Setup | Pixel/tag management across platforms | Medium |
| Attribution Overview | Basic last-click and platform-reported attribution | Medium |

**Why Table Stakes:** Agencies and marketing managers need to report to stakeholders. No reporting = no purchase.

### 3. User & Access Management

| Feature | Description | Complexity |
|---------|-------------|------------|
| Multi-User Accounts | Team members can access shared workspace | Low |
| **RBAC (Admin/Manager/User)** | Hierarchical permissions with granular access control | Medium |
| **Google SSO Login** | Sign in with Google Workspace accounts | Medium |
| **MFA (TOTP)** | Multi-factor auth via authenticator apps (Google Auth, Authy) | Medium |
| **Session Management** | View active sessions, force logout, configurable timeout | Low-Medium |
| **Audit Logging** | Who did what, when, with before/after state tracking | Medium |
| Ad Account Connections | OAuth-based connection to ad platform accounts | Medium - OAuth flows for each platform |

**RBAC Role Definitions:**
| Role | Permissions |
|------|-------------|
| **Admin** | Full system access, billing, user management, organization settings |
| **Manager** | Team oversight, approve campaigns, view all team reports, manage team members |
| **User** | Create/edit own campaigns, view assigned ad accounts only |

**Why Table Stakes:** Agencies manage multiple clients; brands have multiple team members. Security (MFA, audit logs) is expected for platforms handling ad spend.

### 4. Basic Automation

| Feature | Description | Complexity |
|---------|-------------|------------|
| Automated Rules | If/then rules (pause if CPA > X, increase budget if ROAS > Y) | Medium |
| Scheduled Reports | Email reports daily/weekly/monthly | Low |
| Alert Notifications | Email/Slack alerts for budget caps, performance drops | Low-Medium |
| Auto-Pause on Thresholds | Stop campaigns before overspending | Low |

**Why Table Stakes:** Manual management doesn't scale. Even basic automation is expected in 2025+.

### 5. Billing & Subscription Basics

| Feature | Description | Complexity |
|---------|-------------|------------|
| Self-Service Signup | Credit card signup, instant access | Low (use Stripe) |
| Tiered Pricing | Free/Starter/Pro/Enterprise tiers | Low |
| Usage-Based Billing | Charge based on ad spend managed or # of accounts | Medium |
| Billing History | Invoices, receipts, payment history | Low (Stripe provides) |

**Why Table Stakes:** Users expect modern SaaS purchasing. No demo-required, contract-first sales.

---

## Differentiators (Competitive Advantage)

### 1. AI-Powered Optimization

| Feature | Description | Complexity | Competitive Value |
|---------|-------------|------------|-------------------|
| AI Budget Allocation | Automatically shift budget to best-performing campaigns/platforms | High - ML models needed | Very High |
| Predictive Performance | Forecast ROAS, conversions, spend before it happens | High - Time-series forecasting | High |
| AI Creative Analysis | Score ad creatives, predict performance, suggest improvements | High - Vision AI + performance data | Very High |
| Automated Bid Optimization | AI-driven bidding strategies beyond platform defaults | High - Requires careful testing | High |
| Anomaly Detection | Proactively flag unusual performance patterns | Medium-High | Medium |
| AI Audience Suggestions | Recommend targeting based on performance patterns | High | High |

**Why Differentiating:** This is where the "AI" in AI marketing automation matters. Most tools just aggregate; few truly optimize.

### 2. Creative Intelligence

| Feature | Description | Complexity | Competitive Value |
|---------|-------------|------------|-------------------|
| Creative Performance Insights | Deep analysis of what creative elements work | High - Image/video analysis | Very High |
| A/B Test Automation | Auto-generate variants, auto-declare winners | Medium-High | High |
| Creative Fatigue Detection | Alert when ads are losing effectiveness | Medium | High |
| AI Ad Copy Generation | Generate headlines, descriptions using AI | Medium - LLM integration | Medium-High |
| Dynamic Creative Recommendations | Suggest new creatives based on top performers | High | Very High |

**Why Differentiating:** Creative is the #1 lever in paid social. Platforms that help here win.

### 3. Advanced Analytics

| Feature | Description | Complexity | Competitive Value |
|---------|-------------|------------|-------------------|
| Cross-Platform Attribution | Understand true customer journeys across platforms | Very High - Requires tracking infrastructure | Very High |
| Incrementality Testing | Measure true lift vs. platform-reported conversions | Very High - Statistical rigor required | Very High |
| Cohort Analysis | Track user cohorts over time | High | High |
| Custom Metrics Builder | Create calculated metrics (blended ROAS, etc.) | Medium | Medium |
| Real-Time Dashboards | Live-updating metrics, not just daily | Medium-High | Medium |

**Why Differentiating:** Attribution and incrementality are the biggest pain points. Solutions here are rare.

### 4. Agency-Specific Features

| Feature | Description | Complexity | Competitive Value |
|---------|-------------|------------|-------------------|
| White-Label Reporting | Brand reports with agency logo | Low-Medium | High for agencies |
| Client Workspaces | Isolated environments per client | Medium | High for agencies |
| Client Billing Passthrough | Bill clients directly through platform | Medium | Medium |
| Approval Workflows | Client approves before campaigns go live | Medium | High for agencies |
| Multi-Account Optimization | Optimize across all clients intelligently | High | Very High for agencies |

**Why Differentiating:** Agencies are a key segment. Agency-specific features create stickiness.

### 5. Intelligent Automation

| Feature | Description | Complexity | Competitive Value |
|---------|-------------|------------|-------------------|
| AI Campaign Builder | Generate full campaigns from product/landing page | High | Very High |
| Automated Scaling | AI decides when/how to scale winning campaigns | High | High |
| Smart Budget Pacing | Automatically pace spend for optimal delivery | Medium-High | Medium |
| Cross-Platform Sync | Keep campaigns in sync across platforms automatically | Medium | Medium |
| Natural Language Rules | Create rules using plain English ("pause if doing badly") | Medium - LLM integration | Medium |

---

## Anti-Features (Things to Deliberately NOT Build)

### 1. Overly Complex Features

| Anti-Feature | Why NOT to Build |
|--------------|------------------|
| Full Ad Platform Replacement | Trying to replicate every Google/Meta feature creates maintenance nightmare and confuses users |
| Custom Attribution Models | Let users define their own attribution = infinite complexity, minimal value |
| Real-Time Bidding Engine | Platforms do this; competing with Google's ML is a losing battle |
| Full CRM Integration | Stay in your lane; don't become HubSpot |

### 2. Scope Creep Traps

| Anti-Feature | Why NOT to Build |
|--------------|------------------|
| Email Marketing | Different market, different expertise |
| Landing Page Builder | Many good options exist (Unbounce, Instapage) |
| SEO Tools | Completely different discipline |
| Social Media Scheduling | Organic social is a different product category |
| Influencer Management | Different market, different buying cycle |

### 3. Premature Complexity

| Anti-Feature | Why NOT to Build (Initially) |
|--------------|------------------------------|
| Custom API Access | Wait until enterprise customers demand it |
| Offline Conversion Upload | Complex, only needed by sophisticated advertisers |
| Data Warehouse Sync | Build integrations, not infrastructure |
| Custom ML Model Training | Use pre-built models; don't let users train custom ones |
| Multi-Touch Attribution | Incredibly complex; start with simpler approaches |

### 4. Dangerous Features

| Anti-Feature | Why NOT to Build |
|--------------|------------------|
| Fully Autonomous Campaigns | Users need control; "set it and forget it" leads to disasters |
| Automated Creative Generation (No Approval) | AI-generated ads without human review = brand risk |
| Auto-Scaling Without Limits | Runaway spend is a support nightmare |
| Password-Based Account Access | Always use OAuth; never store ad platform credentials |

---

## Integrations Users Commonly Need

### Tier 1: Essential (Build First)

| Integration | Use Case | Complexity |
|-------------|----------|------------|
| Google Ads API | Core platform | High - Complex API, frequent changes |
| Meta Marketing API | Core platform | High - Strict review process |
| TikTok Marketing API | Core platform | Medium-High - Newer, less mature |
| Stripe | Billing | Low - Well-documented |
| Slack | Notifications | Low |
| **Email Service (Resend/SendGrid)** | Transactional emails, notifications, reports | Low |
| **Conversion Pixel Helper** | Guide users to install Meta Pixel, Google Tag, TikTok Pixel | Medium |

### Tier 1.5: V1 Features (Build alongside core)

| Integration | Use Case | Complexity |
|-------------|----------|------------|
| **Affiliate Tracking System** | Referral codes, commission tracking, payouts | Medium |
| **Outbound Webhooks** | Let users receive campaign events in their systems | Low-Medium |
| **CSV/Bulk Import** | Import campaigns from spreadsheets | Medium |

### Tier 2: High Value (Build Second)

| Integration | Use Case | Complexity |
|-------------|----------|------------|
| Shopify | E-commerce data, conversions | Medium |
| Google Analytics 4 | Attribution, analytics | Medium |
| Zapier | Connect to anything | Medium |
| Google Sheets | Report exports | Low |
| HubSpot | CRM sync for lead gen advertisers | Medium |

### Tier 3: Nice to Have (Build Later)

| Integration | Use Case | Complexity |
|-------------|----------|------------|
| WooCommerce | E-commerce alternative | Medium |
| Salesforce | Enterprise CRM | High |
| BigQuery | Data warehouse | Medium |
| Segment | CDP integration | Medium |
| LinkedIn Ads | Additional platform | Medium-High |
| Pinterest Ads | Additional platform | Medium |
| Microsoft Ads | Additional platform | Medium |

---

## Billing & Subscription Models in This Space

### Common Pricing Models

| Model | Description | Pros | Cons |
|-------|-------------|------|------|
| **Flat Monthly Tiers** | $49/$149/$499 per month | Predictable revenue, easy to understand | May leave money on table with big spenders |
| **% of Ad Spend** | 1-3% of managed ad spend | Scales with customer success | Unpredictable revenue, customers may hide spend |
| **Per Ad Account** | $X per connected account | Clear value metric | Encourages account consolidation |
| **Per User** | $X per seat | Common in SaaS | Encourages seat sharing |
| **Hybrid** | Base fee + usage component | Balances predictability and upside | More complex to explain |

### Recommended Approach

**Hybrid model** with:
- Free tier: 1 ad account, basic features, $1K/mo spend limit
- Starter ($49/mo): 3 ad accounts, core automation, $10K/mo spend
- Pro ($149/mo): 10 ad accounts, AI features, $100K/mo spend
- Agency ($399/mo): Unlimited accounts, white-label, client workspaces
- Enterprise (Custom): Dedicated support, SLAs, custom integrations

### Feature Gating Strategy

| Feature Category | Free | Starter | Pro | Agency/Enterprise |
|-----------------|------|---------|-----|-------------------|
| Multi-platform dashboard | Yes | Yes | Yes | Yes |
| Basic reporting | Yes | Yes | Yes | Yes |
| Automated rules | 3 | 10 | Unlimited | Unlimited |
| AI optimization | No | Limited | Full | Full |
| Creative analysis | No | No | Yes | Yes |
| White-label | No | No | No | Yes |
| API access | No | No | No | Yes |

---

## Complexity Notes Summary

### Low Complexity (Build First)
- Basic dashboard and metrics display
- User authentication and roles
- Stripe billing integration
- CSV exports
- Email notifications
- Campaign status monitoring

### Medium Complexity (Build Second)
- OAuth connections to ad platforms
- Automated rules engine
- Cross-platform data normalization
- Custom dashboards
- Slack integration
- Basic AI features (using existing APIs)

### High Complexity (Build Carefully)
- AI budget optimization
- Creative performance analysis
- Predictive analytics
- Cross-platform attribution
- Agency white-labeling
- TikTok API (newer, less stable)

### Very High Complexity (Consider Carefully)
- True incrementality testing
- Custom attribution modeling
- Real-time bidding optimization
- Multi-touch attribution

---

## Key Takeaways

1. **Start with aggregation, then add intelligence**: Users first need a unified view before they trust AI recommendations.

2. **Creative intelligence is the biggest opportunity**: Platform bidding is commoditized; creative insight is not.

3. **Agency features drive stickiness**: Multi-client management and white-labeling create switching costs.

4. **Don't compete with platforms on their strengths**: Enhance their capabilities; don't try to replace core ad serving.

5. **Attribution is a minefield**: Important but dangerous. Start simple, add complexity only when demanded.

6. **Billing should align with value**: Spend-based or account-based pricing ties cost to customer value.

---

*Research compiled: January 2026*
*Target platforms: Google Ads, Meta Ads, TikTok Ads*
*Target users: Marketing managers, agencies, e-commerce brands*

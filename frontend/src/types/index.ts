// Common types used across the application

export type UserRole = 'admin' | 'manager' | 'user'

export type PlanTier = 'free' | 'starter' | 'pro' | 'agency' | 'enterprise'

export type CampaignStatus =
  | 'draft'
  | 'pending_review'
  | 'approved'
  | 'active'
  | 'paused'
  | 'archived'
  | 'rejected'

export type AdPlatform = 'google' | 'meta' | 'tiktok'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  organizationId: string
  mfaEnabled: boolean
  createdAt: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  planTier: PlanTier
  aiGenerationsUsed: number
  aiGenerationsLimit: number
  createdAt: string
}

export interface Campaign {
  id: string
  name: string
  status: CampaignStatus
  platforms: AdPlatform[]
  budgetDaily?: number
  budgetTotal?: number
  startDate?: string
  endDate?: string
  createdAt: string
  updatedAt: string
}

export interface CampaignMetrics {
  impressions: number
  clicks: number
  spend: number
  conversions: number
  conversionValue: number
  ctr: number
  cpc: number
  cpa: number
  roas: number
}

export interface AdAccount {
  id: string
  platform: AdPlatform
  platformAccountId: string
  name: string
  isActive: boolean
  lastSyncAt?: string
  syncStatus: 'pending' | 'syncing' | 'success' | 'error' | 'auth_error'
}

export interface AutomationRule {
  id: string
  name: string
  isEnabled: boolean
  conditions: RuleCondition[]
  actions: RuleAction[]
  lastTriggeredAt?: string
}

export interface RuleCondition {
  metric: 'cpa' | 'roas' | 'spend' | 'impressions' | 'clicks'
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'eq'
  value: number
}

export interface RuleAction {
  type: 'pause' | 'resume' | 'adjust_budget' | 'notify'
  params?: Record<string, unknown>
}

export interface AuditLogEntry {
  id: string
  action: string
  resourceType?: string
  resourceId?: string
  userId?: string
  userName?: string
  changes?: Record<string, unknown>
  ipAddress?: string
  createdAt: string
}

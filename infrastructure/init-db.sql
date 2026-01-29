-- Database initialization script for AI Marketing Platform
-- This runs automatically when PostgreSQL container is first created

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create application user with limited privileges (for production)
-- In development, we use the main user

-- Set timezone
SET timezone = 'UTC';

-- Create enum types
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'user');
CREATE TYPE plan_tier AS ENUM ('free', 'starter', 'pro', 'agency', 'enterprise');
CREATE TYPE campaign_status AS ENUM ('draft', 'pending_review', 'approved', 'active', 'paused', 'archived', 'rejected');
CREATE TYPE ad_platform AS ENUM ('google', 'meta', 'tiktok');
CREATE TYPE sync_status AS ENUM ('pending', 'syncing', 'success', 'error', 'auth_error');
CREATE TYPE job_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'dead');
CREATE TYPE mfa_method AS ENUM ('totp', 'recovery_code');
CREATE TYPE audit_action AS ENUM (
    'user.created', 'user.updated', 'user.deleted', 'user.login', 'user.logout', 'user.login_failed',
    'user.mfa_enabled', 'user.mfa_disabled', 'user.password_changed', 'user.password_reset',
    'org.created', 'org.updated', 'org.deleted', 'org.user_invited', 'org.user_removed',
    'campaign.created', 'campaign.updated', 'campaign.deleted', 'campaign.launched', 'campaign.paused',
    'campaign.approved', 'campaign.rejected',
    'ad_account.connected', 'ad_account.disconnected', 'ad_account.sync_failed',
    'rule.created', 'rule.updated', 'rule.deleted', 'rule.triggered', 'rule.action_executed',
    'billing.subscription_created', 'billing.subscription_updated', 'billing.payment_failed',
    'ai.generation_requested', 'ai.limit_reached',
    'admin.impersonation_started', 'admin.impersonation_ended', 'admin.tenant_suspended', 'admin.tenant_unsuspended'
);

-- Log that initialization completed
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully with extensions and enum types';
END $$;

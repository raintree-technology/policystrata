-- source: packages/db/migrations/0001_add_report_types.sql
-- Add new report types to the reportTypes enum
ALTER TYPE "reportTypes" ADD VALUE IF NOT EXISTS 'monthly_revenue';
ALTER TYPE "reportTypes" ADD VALUE IF NOT EXISTS 'revenue_forecast';
ALTER TYPE "reportTypes" ADD VALUE IF NOT EXISTS 'runway';
ALTER TYPE "reportTypes" ADD VALUE IF NOT EXISTS 'category_expenses';

-- source: packages/db/migrations/0004_add_error_code.sql
-- Migration: Add error_code column to accounting_sync_records
-- This allows structured error handling with standardized codes for frontend display

ALTER TABLE accounting_sync_records 
  ADD COLUMN error_code TEXT;

-- Add comment for documentation
COMMENT ON COLUMN accounting_sync_records.error_code IS 'Standardized error code for frontend handling (e.g., ATTACHMENT_UNSUPPORTED_TYPE, AUTH_EXPIRED)';

-- source: packages/db/migrations/0005_add_line_item_tax.sql
-- Migration: Add line item tax support
-- Adds tax_rate to invoice_products for per-product default tax rates
-- Adds include_line_item_tax toggle and label to invoice_templates

ALTER TABLE invoice_products 
  ADD COLUMN tax_rate NUMERIC(10, 2);

ALTER TABLE invoice_templates 
  ADD COLUMN include_line_item_tax BOOLEAN DEFAULT false,
  ADD COLUMN line_item_tax_label TEXT;

-- Add comments for documentation
COMMENT ON COLUMN invoice_products.tax_rate IS 'Default tax rate percentage for this product (0-100)';
COMMENT ON COLUMN invoice_templates.include_line_item_tax IS 'When true, tax is calculated per line item instead of invoice level';
COMMENT ON COLUMN invoice_templates.line_item_tax_label IS 'Custom label for the line item tax column (default: Tax)';

-- source: packages/db/migrations/0007_add_invoice_template_id.sql
-- Migration: Add templateId to invoices for template traceability
-- Adds template_id column to invoices table with foreign key to invoice_templates

-- Add new column
ALTER TABLE invoices 
  ADD COLUMN template_id UUID;

-- Add index for efficient lookups
CREATE INDEX IF NOT EXISTS invoices_template_id_idx ON invoices(template_id);

-- Add foreign key constraint (set null on delete to preserve invoice history)
ALTER TABLE invoices 
  ADD CONSTRAINT invoices_template_id_fkey 
  FOREIGN KEY (template_id) 
  REFERENCES invoice_templates(id) 
  ON DELETE SET NULL;

-- source: packages/db/migrations/0008_add_invoice_payments.sql
-- Migration: Add native invoice payment support with Stripe Connect
-- Enables teams to accept invoice payments via Stripe

-- Add Stripe Connect fields to teams table
ALTER TABLE teams 
  ADD COLUMN IF NOT EXISTS stripe_account_id TEXT,
  ADD COLUMN IF NOT EXISTS stripe_connect_status TEXT;

-- Add payment enabled toggle to invoice templates
ALTER TABLE invoice_templates 
  ADD COLUMN IF NOT EXISTS payment_enabled BOOLEAN DEFAULT false;

-- Add payment intent tracking to invoices
ALTER TABLE invoices 
  ADD COLUMN IF NOT EXISTS payment_intent_id TEXT;

-- Add index for efficient payment intent lookups
CREATE INDEX IF NOT EXISTS invoices_payment_intent_id_idx ON invoices(payment_intent_id);

-- Add index for efficient team lookups by Stripe account ID (used by webhooks)
CREATE INDEX IF NOT EXISTS teams_stripe_account_id_idx ON teams(stripe_account_id) WHERE stripe_account_id IS NOT NULL;

-- source: packages/db/migrations/0009_add_refunded_status.sql
-- Migration: Add refunded status to invoice_status enum
-- Allows invoices to have a distinct "refunded" status when payment is refunded

ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'refunded';

-- Add refunded_at timestamp to track when refund occurred
ALTER TABLE invoices 
  ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMP WITH TIME ZONE;

-- source: packages/db/migrations/0010_add_customer_enrichment.sql
-- Customer Enrichment Migration
-- Adds relationship fields and AI-enriched company intelligence fields

-- ===========================================
-- CUSTOMER RELATIONSHIP FIELDS
-- ===========================================

-- Status: active, inactive, prospect, churned
ALTER TABLE customers ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

-- Financial defaults for invoicing
ALTER TABLE customers ADD COLUMN IF NOT EXISTS preferred_currency TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS default_payment_terms INTEGER;

-- Organization
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT false;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS external_id TEXT;

-- ===========================================
-- ENRICHMENT FIELDS (from Gemini + Grounding)
-- ===========================================

-- Visual / Brand
ALTER TABLE customers ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS brand_color TEXT;

-- Company basics
ALTER TABLE customers ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_type TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS employee_count TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS founded_year INTEGER;

-- Financial intelligence
ALTER TABLE customers ADD COLUMN IF NOT EXISTS estimated_revenue TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS funding_stage TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS total_funding TEXT;

-- Location / Timezone
ALTER TABLE customers ADD COLUMN IF NOT EXISTS headquarters_location TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS timezone TEXT;

-- Social links
ALTER TABLE customers ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS twitter_url TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS instagram_url TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS facebook_url TEXT;

-- Enrichment metadata (null = not attempted, pending, processing, completed, failed)
ALTER TABLE customers ADD COLUMN IF NOT EXISTS enrichment_status TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP WITH TIME ZONE;

-- ===========================================
-- INDEXES
-- ===========================================

CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_is_archived ON customers(is_archived);
CREATE INDEX IF NOT EXISTS idx_customers_enrichment_status ON customers(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_customers_website ON customers(website) WHERE website IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_industry ON customers(industry) WHERE industry IS NOT NULL;

-- ===========================================
-- SUPABASE REALTIME
-- Enable realtime for the customers table
-- ===========================================
ALTER PUBLICATION supabase_realtime ADD TABLE customers;

-- source: packages/db/migrations/0010_add_invoice_recurring.sql
-- Migration: Add recurring invoice support
-- Enables teams to create recurring invoice series that auto-generate invoices on a schedule

-- Create frequency enum
CREATE TYPE invoice_recurring_frequency AS ENUM (
  'weekly',
  'monthly_date',
  'monthly_weekday',
  'custom'
);

-- Create end type enum
CREATE TYPE invoice_recurring_end_type AS ENUM (
  'never',
  'on_date',
  'after_count'
);

-- Create status enum
CREATE TYPE invoice_recurring_status AS ENUM (
  'active',
  'paused',
  'completed',
  'canceled'
);

-- Create invoice_recurring table
CREATE TABLE IF NOT EXISTS invoice_recurring (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
  -- Frequency settings
  frequency invoice_recurring_frequency NOT NULL,
  frequency_day INTEGER, -- 0-6 for weekly (day of week), 1-31 for monthly_date
  frequency_week INTEGER, -- 1-5 for monthly_weekday (e.g., 1st, 2nd Friday)
  frequency_interval INTEGER, -- For custom: every X days
  -- End conditions
  end_type invoice_recurring_end_type NOT NULL,
  end_date TIMESTAMPTZ,
  end_count INTEGER,
  -- Status tracking
  status invoice_recurring_status DEFAULT 'active' NOT NULL,
  invoices_generated INTEGER DEFAULT 0 NOT NULL,
  consecutive_failures INTEGER DEFAULT 0 NOT NULL, -- Track failures for auto-pause
  next_scheduled_at TIMESTAMPTZ,
  last_generated_at TIMESTAMPTZ,
  timezone TEXT NOT NULL,
  -- Invoice template data
  due_date_offset INTEGER DEFAULT 30 NOT NULL,
  amount NUMERIC(10, 2),
  currency TEXT,
  line_items JSONB,
  template JSONB,
  payment_details JSONB,
  from_details JSONB,
  note_details JSONB,
  customer_name TEXT,
  vat NUMERIC(10, 2),
  tax NUMERIC(10, 2),
  discount NUMERIC(10, 2),
  subtotal NUMERIC(10, 2),
  top_block JSONB,
  bottom_block JSONB,
  template_id UUID REFERENCES invoice_templates(id) ON DELETE SET NULL
);

-- Add indexes for invoice_recurring
CREATE INDEX IF NOT EXISTS invoice_recurring_team_id_idx ON invoice_recurring(team_id);
CREATE INDEX IF NOT EXISTS invoice_recurring_next_scheduled_at_idx ON invoice_recurring(next_scheduled_at);
CREATE INDEX IF NOT EXISTS invoice_recurring_status_idx ON invoice_recurring(status);
-- Compound partial index for scheduler query (WHERE status = 'active' AND next_scheduled_at <= now)
CREATE INDEX IF NOT EXISTS invoice_recurring_active_scheduled_idx ON invoice_recurring(next_scheduled_at) WHERE status = 'active';

-- Add RLS policy for invoice_recurring
ALTER TABLE invoice_recurring ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Invoice recurring can be handled by a member of the team"
  ON invoice_recurring
  FOR ALL
  TO public
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

-- Add recurring invoice fields to invoices table
ALTER TABLE invoices 
  ADD COLUMN IF NOT EXISTS invoice_recurring_id UUID REFERENCES invoice_recurring(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS recurring_sequence INTEGER;

-- Add index for efficient recurring invoice lookups
CREATE INDEX IF NOT EXISTS invoices_invoice_recurring_id_idx ON invoices(invoice_recurring_id) WHERE invoice_recurring_id IS NOT NULL;

-- Unique constraint for idempotency (prevents duplicate invoices for same sequence)
CREATE UNIQUE INDEX IF NOT EXISTS invoices_recurring_sequence_unique_idx ON invoices(invoice_recurring_id, recurring_sequence) WHERE invoice_recurring_id IS NOT NULL;

-- source: packages/db/migrations/0011_add_customer_ceo_name.sql
-- Add CEO/founder name field to customers table
-- This field stores the name of the CEO, founder, or primary executive

ALTER TABLE customers ADD COLUMN IF NOT EXISTS ceo_name TEXT;

-- source: packages/db/migrations/0011_add_upcoming_notification_tracking.sql
-- Migration: Add upcoming notification tracking for recurring invoices
-- Tracks when the 24-hour upcoming notification was sent to avoid duplicates

-- Add column to track when upcoming notification was sent
ALTER TABLE invoice_recurring 
  ADD COLUMN IF NOT EXISTS upcoming_notification_sent_at TIMESTAMPTZ;

-- Index for efficient querying of upcoming invoices that need notification
-- Used by the scheduler to find series due within 24 hours that haven't been notified
CREATE INDEX IF NOT EXISTS invoice_recurring_upcoming_notification_idx 
  ON invoice_recurring(next_scheduled_at, upcoming_notification_sent_at) 
  WHERE status = 'active';

-- source: packages/db/migrations/0012_add_customer_enrichment_fields.sql
-- Add new customer enrichment fields
ALTER TABLE customers ADD COLUMN IF NOT EXISTS finance_contact TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS finance_contact_email TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS primary_language TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS fiscal_year_end TEXT;

-- source: packages/db/migrations/0012_add_recurring_frequency_options.sql
-- Migration: Add quarterly, semi_annual, and annual frequency options for recurring invoices
-- These new options allow businesses to set up invoices that repeat quarterly, semi-annually, or annually

-- Add new enum values to invoice_recurring_frequency
-- Note: PostgreSQL allows adding values to enums, but not removing them
ALTER TYPE invoice_recurring_frequency ADD VALUE IF NOT EXISTS 'quarterly';
ALTER TYPE invoice_recurring_frequency ADD VALUE IF NOT EXISTS 'semi_annual';
ALTER TYPE invoice_recurring_frequency ADD VALUE IF NOT EXISTS 'annual';

-- Add recurring_invoice_upcoming to activity_type enum for 24-hour advance notifications
ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'recurring_invoice_upcoming';

-- source: packages/db/migrations/0013_add_biweekly_and_last_day.sql
-- Migration: Add biweekly and monthly_last_day frequency options for recurring invoices
-- 
-- biweekly: Every 2 weeks on the same weekday as the issue date
-- monthly_last_day: Last day of each month (handles 28/30/31 day months automatically)

-- Add new enum values to invoice_recurring_frequency
ALTER TYPE invoice_recurring_frequency ADD VALUE IF NOT EXISTS 'biweekly';
ALTER TYPE invoice_recurring_frequency ADD VALUE IF NOT EXISTS 'monthly_last_day';

-- source: packages/db/migrations/0013_fix_enrichment_status_default.sql
-- Fix enrichment_status for customers without websites
-- These customers should not have a "pending" status since enrichment requires a website

-- Remove the default from enrichment_status column
ALTER TABLE customers ALTER COLUMN enrichment_status DROP DEFAULT;

-- Reset enrichment_status to null for customers without websites
-- These were incorrectly set to "pending" by the old default
UPDATE customers 
SET enrichment_status = NULL 
WHERE website IS NULL 
  AND enrichment_status = 'pending';

-- Also reset customers that have been "pending" for more than 24 hours
-- These likely had a failed job trigger and are stuck
UPDATE customers 
SET enrichment_status = NULL 
WHERE enrichment_status = 'pending' 
  AND enriched_at IS NULL
  AND created_at < NOW() - INTERVAL '24 hours';

-- source: packages/db/migrations/0014_add_payment_terms.sql
-- Migration: Add payment_terms_days to invoice_templates
-- Allows users to customize the default due date offset (in days) for invoices
-- Default is 30 days, matching the current behavior

ALTER TABLE invoice_templates 
  ADD COLUMN IF NOT EXISTS payment_terms_days INTEGER DEFAULT 30;

-- source: packages/db/migrations/0015_add_customer_portal.sql
-- Migration: Add customer portal support
-- Adds portal_enabled and portal_id columns to customers table
-- portal_id is a short nanoid(8) used for public portal URLs

ALTER TABLE customers 
  ADD COLUMN IF NOT EXISTS portal_enabled BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS portal_id TEXT;

-- Index for efficient portal lookups by portal_id
CREATE UNIQUE INDEX IF NOT EXISTS customers_portal_id_idx 
  ON customers(portal_id) 
  WHERE portal_id IS NOT NULL;

-- source: packages/db/migrations/0016_add_insights.sql
-- ============================================================================
-- INSIGHTS FEATURE - Complete Migration
-- ============================================================================
-- AI-powered business insights with per-user read/dismiss tracking
-- ============================================================================

-- Create insight period type enum
CREATE TYPE insight_period_type AS ENUM ('weekly', 'monthly', 'quarterly', 'yearly');

-- Create insight status enum
CREATE TYPE insight_status AS ENUM ('pending', 'generating', 'completed', 'failed');

-- Add insight_ready to activity_type enum (for notifications)
ALTER TYPE "activity_type" ADD VALUE IF NOT EXISTS 'insight_ready';

-- ============================================================================
-- INSIGHTS TABLE
-- ============================================================================

CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    
    -- Flexible period definition
    period_type insight_period_type NOT NULL,
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_year SMALLINT NOT NULL,
    period_number SMALLINT NOT NULL, -- Week 1-53, Month 1-12, Quarter 1-4
    
    status insight_status NOT NULL DEFAULT 'pending',
    
    -- Selected key metrics (dynamically chosen, typically 4)
    selected_metrics JSONB,
    
    -- Full metrics snapshot (for drill-down)
    all_metrics JSONB,
    
    -- Detected anomalies and patterns
    anomalies JSONB,
    
    -- Expense category anomalies (spikes, new categories, decreases)
    expense_anomalies JSONB,
    
    -- Streaks and milestones
    milestones JSONB,
    
    -- Activity context (invoices, time tracking, etc.)
    activity JSONB,
    
    currency VARCHAR(3) NOT NULL,
    
    -- AI-generated content (sentiment, opener, story, actions, celebration)
    content JSONB,
    
    -- Audio narration storage path: {teamId}/insights/{insightId}.mp3
    -- URLs generated on demand via presigned URLs
    audio_path TEXT,
    
    generated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for insights table
CREATE UNIQUE INDEX insights_team_period_unique 
    ON insights(team_id, period_type, period_year, period_number);
CREATE INDEX insights_team_id_idx ON insights(team_id);
CREATE INDEX insights_team_period_type_idx 
    ON insights(team_id, period_type, generated_at DESC);
CREATE INDEX insights_status_idx ON insights(status);

-- Enable RLS
ALTER TABLE insights ENABLE ROW LEVEL SECURITY;

-- RLS policies for insights
CREATE POLICY "Team members can view their insights" ON insights
    FOR SELECT
    TO public
    USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "System can insert insights" ON insights
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "System can update insights" ON insights
    FOR UPDATE
    TO service_role
    USING (true);

-- ============================================================================
-- INSIGHT USER STATUS TABLE (per-user read/dismiss tracking)
-- ============================================================================

CREATE TABLE insight_user_status (
    insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMP WITH TIME ZONE,
    dismissed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (insight_id, user_id)
);

-- Indexes for insight_user_status
CREATE INDEX insight_user_status_user_idx ON insight_user_status(user_id);
CREATE INDEX insight_user_status_insight_idx ON insight_user_status(insight_id);
CREATE INDEX insight_user_status_user_dismissed_idx 
    ON insight_user_status(user_id, dismissed_at) 
    WHERE dismissed_at IS NOT NULL;
CREATE INDEX insight_user_status_unread_idx 
    ON insight_user_status(user_id, insight_id) 
    WHERE read_at IS NULL;

-- Enable RLS
ALTER TABLE insight_user_status ENABLE ROW LEVEL SECURITY;

-- RLS policies for insight_user_status
CREATE POLICY "Users can view their own insight status" ON insight_user_status
    FOR SELECT
    TO public
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own insight status" ON insight_user_status
    FOR INSERT
    TO public
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own insight status" ON insight_user_status
    FOR UPDATE
    TO public
    USING (user_id = auth.uid());

-- ============================================================================
-- ACTIVITY DATA INDEXES (optimize insights generation queries)
-- ============================================================================

-- Invoices: optimize sent/paid date range queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_sent_at_idx 
    ON invoices(team_id, sent_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_status_paid_at_idx 
    ON invoices(team_id, status, paid_at);

-- Tracker entries: optimize date range queries for time tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS tracker_entries_team_date_idx 
    ON tracker_entries(team_id, date);

-- Customers: composite for created_at range queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS customers_team_created_at_idx 
    ON customers(team_id, created_at);

-- Inbox: optimize status + date range queries for receipt matching stats
CREATE INDEX CONCURRENTLY IF NOT EXISTS inbox_team_status_created_at_idx 
    ON inbox(team_id, status, created_at);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE insights IS 'AI-generated periodic business insights for teams';
COMMENT ON COLUMN insights.audio_path IS 'Storage path: {teamId}/insights/{insightId}.mp3 - URLs generated via presigned URLs';
COMMENT ON TABLE insight_user_status IS 'Per-user read and dismiss tracking for insights';

-- source: packages/db/migrations/0017_add_insights_title.sql
-- ============================================================================
-- ADD TITLE COLUMN TO INSIGHTS TABLE
-- ============================================================================
-- AI-generated summary title for card headers and email subjects
-- ============================================================================

ALTER TABLE insights
ADD COLUMN title TEXT;

COMMENT ON COLUMN insights.title IS 'AI-generated summary combining revenue, expenses, net, and key metrics (max 15 words). Used for card titles and email subjects.';

-- source: packages/db/migrations/0018_add_insights_realtime.sql
-- Enable realtime on insights table
-- This allows the dashboard to receive live updates when new insights are generated

ALTER PUBLICATION supabase_realtime ADD TABLE insights;

-- RLS SELECT policy for insights (same pattern as inbox)
-- Uses the shared team membership function
CREATE POLICY "Insights can be selected by a member of the team" ON insights
    FOR SELECT
    TO public
    USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

-- source: packages/db/migrations/0019_fix_stuck_pending_documents.sql
-- Migration: Fix stuck pending documents
-- This migration fixes documents that are stuck in "pending" status due to previous pipeline issues

-- 1. Fix documents that have been processed (have title or content) but status was never updated
-- These are documents where classification succeeded but status wasn't set to completed
UPDATE documents 
SET 
  processing_status = 'completed',
  updated_at = NOW()
WHERE 
  processing_status = 'pending' 
  AND (title IS NOT NULL OR content IS NOT NULL);

-- 2. Mark truly stale documents as failed
-- Documents that have been pending for more than 1 hour with no content are likely stuck
-- These can be retried by users using the new reprocess functionality
UPDATE documents 
SET 
  processing_status = 'failed',
  updated_at = NOW()
WHERE 
  processing_status = 'pending' 
  AND created_at < NOW() - INTERVAL '1 hour'
  AND title IS NULL 
  AND content IS NULL;

-- source: packages/db/migrations/0020_add_bank_account_fields.sql
-- Add additional bank account fields for reconnect matching and user display
-- EU/UK account fields
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "iban" text;
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "subtype" text;
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "bic" text;

-- US bank account details (Teller, Plaid)
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "routing_number" text;
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "wire_routing_number" text;
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "account_number" text;
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "sort_code" text;

-- Credit account balances
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "available_balance" numeric(10, 2);
ALTER TABLE "bank_accounts" ADD COLUMN IF NOT EXISTS "credit_limit" numeric(10, 2);

-- Add index on iban for faster lookups during reconnect
CREATE INDEX IF NOT EXISTS "bank_accounts_iban_idx" ON "bank_accounts" ("iban") WHERE "iban" IS NOT NULL;

-- source: packages/db/migrations/0021_add_insights_predictions.sql
-- Add predictions column to insights table for forward-looking data
-- Used to create the "addiction loop" - tracking what we predicted vs what happened
ALTER TABLE insights ADD COLUMN predictions jsonb;

COMMENT ON COLUMN insights.predictions IS 'Forward-looking predictions for follow-through tracking (invoices due, streaks at risk, etc.)';

-- source: packages/db/migrations/0022_add_inbox_other_type.sql
-- Add "other" value to inbox_status enum
-- This allows documents that are not invoices/receipts (contracts, newsletters, etc.) to be classified
ALTER TYPE inbox_status ADD VALUE IF NOT EXISTS 'other';

-- Add "other" value to inbox_type enum
-- This allows classifying documents as: invoice, expense (receipt), or other
ALTER TYPE inbox_type ADD VALUE IF NOT EXISTS 'other';

-- source: packages/db/migrations/0023_add_email_template_fields.sql
-- Add customizable email content fields to invoice_templates
ALTER TABLE "public"."invoice_templates"
  ADD COLUMN "email_subject" text,
  ADD COLUMN "email_heading" text,
  ADD COLUMN "email_body" text,
  ADD COLUMN "email_button_text" text;

-- source: packages/db/migrations/0024_add_institution_trigram_search.sql
-- Enable the pg_trgm extension for trigram-based fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Replace the B-tree index on name with a GIN trigram index.
-- This supports efficient ILIKE and similarity() / word_similarity() queries.
DROP INDEX IF EXISTS "institutions_name_idx";
CREATE INDEX "institutions_name_trgm_idx" ON "institutions" USING gin ("name" gin_trgm_ops);

-- source: packages/db/migrations/0025_add_transactions_reports_index.sql
CREATE INDEX CONCURRENTLY idx_transactions_reports
ON transactions (team_id, date, category_slug)
WHERE internal = false AND status != 'excluded';

-- source: packages/db/migrations/0026_add_invoice_indexes.sql
-- Index for paymentStatus query: WHERE team_id = ? AND due_date IS NOT NULL ORDER BY due_date DESC
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_due_date_idx
ON invoices (team_id, due_date DESC)
WHERE due_date IS NOT NULL;

-- Index for paymentStatus query: WHERE team_id = ? AND status IN (...) AND due_date < CURRENT_DATE
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_status_due_date_idx
ON invoices (team_id, status, due_date DESC);

-- Index for invoice.get customer filter: WHERE team_id = ? AND customer_id IN (?)
-- Also supports the LEFT JOIN on customer_id (PostgreSQL does not auto-create FK indexes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_customer_id_idx
ON invoices (team_id, customer_id)
WHERE customer_id IS NOT NULL;

-- Index for JOIN lookups on customer_id foreign key
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_customer_id_idx
ON invoices (customer_id)
WHERE customer_id IS NOT NULL;

-- source: packages/db/migrations/0027_add_invoice_created_at_index.sql
-- Index for getInvoicePaymentAnalysis: WHERE team_id = ? AND created_at BETWEEN ? AND ?
-- Also benefits any query filtering invoices by team + date range
CREATE INDEX CONCURRENTLY IF NOT EXISTS invoices_team_created_at_idx
ON invoices (team_id, created_at DESC);

-- source: packages/db/migrations/0028_add_team_company_type.sql
ALTER TABLE "teams" ADD COLUMN "company_type" text;

-- source: packages/db/migrations/0029_add_team_heard_about.sql
ALTER TABLE teams ADD COLUMN IF NOT EXISTS heard_about TEXT;

-- source: packages/db/migrations/0030_add_transaction_trgm_indexes.sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_name_trgm
  ON transactions USING GIN (name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_merchant_name_trgm
  ON transactions USING GIN (merchant_name gin_trgm_ops);

-- source: packages/db/migrations/0031_add_matching_indexes.sql
-- Composite index for fetchTeamPairHistory and getTeamCalibration queries
-- which filter by (team_id, status IN (...), created_at > interval)
-- and ORDER BY created_at DESC.
CREATE INDEX CONCURRENTLY IF NOT EXISTS transaction_match_suggestions_team_status_created_idx
  ON transaction_match_suggestions (team_id, status, created_at DESC);

-- Trigram index on inbox.display_name for word_similarity in findInboxMatches
-- (reverse matching: transaction → inbox candidates).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inbox_display_name_trgm
  ON inbox USING GIN (display_name gin_trgm_ops);

-- source: packages/db/migrations/0032_drop_transaction_embeddings.sql
DROP TABLE IF EXISTS transaction_embeddings;
DROP TABLE IF EXISTS inbox_embeddings;
ALTER TABLE transaction_match_suggestions DROP COLUMN IF EXISTS embedding_score;

-- source: packages/db/migrations/0033_drop_duplicate_trigram_index.sql
-- Drop duplicate GIN trigram index on transactions.name
-- idx_transactions_name_trigram is identical to idx_transactions_name_trgm (both GIN gin_trgm_ops)
-- Production stats: 0 scans, 219 MB wasted space
DROP INDEX CONCURRENTLY IF EXISTS idx_transactions_name_trigram;

-- source: packages/db/migrations/0034_drop_team_limits_metrics.sql
-- Drop the get_team_limits_metrics function that reads from the matview
DROP FUNCTION IF EXISTS get_team_limits_metrics(uuid);

-- Drop the team_limits_metrics materialized view
DROP MATERIALIZED VIEW IF EXISTS team_limits_metrics;

-- source: packages/db/migrations/0035_drop_unused_vector_indexes.sql
-- Drop unused HNSW vector index on document_tag_embeddings (86 MB, 0 scans)
-- Queries look up by slug, not by vector similarity
DROP INDEX CONCURRENTLY IF EXISTS document_tag_embeddings_idx;

-- Drop unused HNSW vector index on transaction_category_embeddings (5 MB, 0 scans)
DROP INDEX CONCURRENTLY IF EXISTS transaction_category_embeddings_vector_idx;

-- source: packages/db/migrations/0036_add_dcr_support.sql
-- Allow oauth_applications to be created without a team or user (for Dynamic Client Registration)
ALTER TABLE oauth_applications ALTER COLUMN team_id DROP NOT NULL;
ALTER TABLE oauth_applications ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE oauth_applications ALTER COLUMN client_secret DROP NOT NULL;

-- source: packages/db/migrations/0037_add_platform_identity_tables.sql
CREATE TYPE platform_provider AS ENUM ('slack', 'telegram', 'whatsapp', 'sendblue');

CREATE TABLE platform_identities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  provider platform_provider NOT NULL,
  team_id uuid NOT NULL,
  user_id uuid NOT NULL,
  external_user_id text NOT NULL,
  external_team_id text NOT NULL DEFAULT '',
  external_channel_id text,
  metadata jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT platform_identities_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
  CONSTRAINT platform_identities_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT platform_identities_provider_external_unique
    UNIQUE (provider, external_team_id, external_user_id)
);

CREATE INDEX platform_identities_provider_external_idx
  ON platform_identities (provider, external_team_id, external_user_id);
CREATE INDEX platform_identities_team_id_idx
  ON platform_identities (team_id);
CREATE INDEX platform_identities_user_id_idx
  ON platform_identities (user_id);

ALTER TABLE platform_identities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Platform identities can be created by a member of the team"
  ON platform_identities
  AS PERMISSIVE
  FOR INSERT
  TO authenticated
  WITH CHECK (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform identities can be selected by a member of the team"
  ON platform_identities
  AS PERMISSIVE
  FOR SELECT
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform identities can be updated by a member of the team"
  ON platform_identities
  AS PERMISSIVE
  FOR UPDATE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform identities can be deleted by a member of the team"
  ON platform_identities
  AS PERMISSIVE
  FOR DELETE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE TABLE platform_link_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  code text NOT NULL,
  provider platform_provider NOT NULL,
  team_id uuid NOT NULL,
  user_id uuid NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  metadata jsonb,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT platform_link_tokens_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
  CONSTRAINT platform_link_tokens_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT platform_link_tokens_code_unique
    UNIQUE (code)
);

CREATE INDEX platform_link_tokens_code_idx
  ON platform_link_tokens (code);
CREATE INDEX platform_link_tokens_team_id_idx
  ON platform_link_tokens (team_id);
CREATE INDEX platform_link_tokens_user_id_idx
  ON platform_link_tokens (user_id);

ALTER TABLE platform_link_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Platform link tokens can be created by a member of the team"
  ON platform_link_tokens
  AS PERMISSIVE
  FOR INSERT
  TO authenticated
  WITH CHECK (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform link tokens can be selected by a member of the team"
  ON platform_link_tokens
  AS PERMISSIVE
  FOR SELECT
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform link tokens can be updated by a member of the team"
  ON platform_link_tokens
  AS PERMISSIVE
  FOR UPDATE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Platform link tokens can be deleted by a member of the team"
  ON platform_link_tokens
  AS PERMISSIVE
  FOR DELETE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

-- source: packages/db/migrations/0038_add_provider_notification_batches.sql
CREATE TABLE provider_notification_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  batch_key text NOT NULL,
  platform_identity_id uuid NOT NULL,
  team_id uuid NOT NULL,
  user_id uuid NOT NULL,
  provider platform_provider NOT NULL,
  event_family text NOT NULL,
  payload jsonb NOT NULL,
  notification_context jsonb,
  window_ends_at timestamptz NOT NULL,
  sent_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT provider_notification_batches_identity_id_fkey
    FOREIGN KEY (platform_identity_id) REFERENCES platform_identities(id) ON DELETE CASCADE,
  CONSTRAINT provider_notification_batches_team_id_fkey
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
  CONSTRAINT provider_notification_batches_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT provider_notification_batches_batch_key_unique
    UNIQUE (batch_key)
);

CREATE INDEX provider_notification_batches_due_idx
  ON provider_notification_batches (sent_at, window_ends_at);
CREATE INDEX provider_notification_batches_identity_idx
  ON provider_notification_batches (platform_identity_id);
CREATE INDEX provider_notification_batches_team_id_idx
  ON provider_notification_batches (team_id);

ALTER TABLE provider_notification_batches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Provider notification batches can be created by a member of the team"
  ON provider_notification_batches
  AS PERMISSIVE
  FOR INSERT
  TO authenticated
  WITH CHECK (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Provider notification batches can be selected by a member of the team"
  ON provider_notification_batches
  AS PERMISSIVE
  FOR SELECT
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Provider notification batches can be updated by a member of the team"
  ON provider_notification_batches
  AS PERMISSIVE
  FOR UPDATE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));

CREATE POLICY "Provider notification batches can be deleted by a member of the team"
  ON provider_notification_batches
  AS PERMISSIVE
  FOR DELETE
  TO authenticated
  USING (team_id IN (SELECT private.get_teams_for_authenticated_user()));


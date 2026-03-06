-- Outreach pipeline tables for BARN-scan
-- Run this against Supabase SQL Editor

-- 1. Outreach tracking table (one row per APN)
CREATE TABLE IF NOT EXISTS outreach (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    apn TEXT NOT NULL UNIQUE REFERENCES bills(apn),
    stage TEXT NOT NULL DEFAULT 'identified',
    outreach_score REAL DEFAULT 0,
    pitch_subject TEXT,
    pitch_draft TEXT,
    contacted_at TIMESTAMPTZ,
    last_response_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ,
    followup_count INTEGER DEFAULT 0,
    notes TEXT,
    openclaw_session_id TEXT,
    owner_group_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_apn ON outreach(apn);
CREATE INDEX IF NOT EXISTS idx_outreach_stage ON outreach(stage);
CREATE INDEX IF NOT EXISTS idx_outreach_score ON outreach(outreach_score DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_owner_group ON outreach(owner_group_id);

-- 2. Outreach messages log
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    apn TEXT NOT NULL REFERENCES bills(apn),
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel TEXT NOT NULL DEFAULT 'email' CHECK (channel IN ('email', 'whatsapp', 'phone', 'in_person')),
    subject TEXT,
    content TEXT,
    from_address TEXT,
    to_address TEXT,
    sent_at TIMESTAMPTZ DEFAULT now(),
    openclaw_message_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_outreach_messages_apn ON outreach_messages(apn);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_sent ON outreach_messages(sent_at DESC);

-- 3. Add outreach_score column to bills for fast filtering
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'outreach_score'
    ) THEN
        ALTER TABLE bills ADD COLUMN outreach_score REAL DEFAULT 0;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'contact_completeness'
    ) THEN
        ALTER TABLE bills ADD COLUMN contact_completeness REAL DEFAULT 0;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'outreach_stage'
    ) THEN
        ALTER TABLE bills ADD COLUMN outreach_stage TEXT DEFAULT 'identified';
    END IF;
END $$;

-- 4. Outreach settings (key-value store for SMTP config, thresholds, etc.)
CREATE TABLE IF NOT EXISTS outreach_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Structured AI vacancy fields from Gemini deep research (additive; does not replace has_vpt).
-- Apply in Supabase SQL Editor.

ALTER TABLE bills ADD COLUMN IF NOT EXISTS ai_vacancy_verdict TEXT;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS ai_vacancy_confidence REAL;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS ai_vacancy_rationale TEXT;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS ai_vacancy_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN bills.ai_vacancy_verdict IS 'likely_vacant | likely_occupied | unknown';
COMMENT ON COLUMN bills.ai_vacancy_confidence IS '0.0–1.0 confidence for vacancy_verdict';
COMMENT ON COLUMN bills.ai_vacancy_rationale IS 'Short evidence summary from the model';

-- Scanner worker state, job tracking, and discovery metadata for the BARN hybrid architecture.
-- Adds tables for worker heartbeats, job lifecycle tracking, and per-job checkpoints.
-- Also adds discovery metadata columns to bills and extends get_bills_filtered with p_new filter.
-- Apply manually via Supabase SQL Editor.

-- ============================================================
-- 1. scanner_workers — one row per scanner process / VM
-- ============================================================
CREATE TABLE IF NOT EXISTS public.scanner_workers (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT        NOT NULL,
    last_heartbeat TIMESTAMPTZ,
    tunnel_url   TEXT,
    status       TEXT        NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline')),
    capabilities JSONB,
    created_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.scanner_workers DISABLE ROW LEVEL SECURITY;

-- ============================================================
-- 2. scanner_jobs — one row per scan run / job dispatch
-- ============================================================
CREATE TABLE IF NOT EXISTS public.scanner_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id       UUID        REFERENCES public.scanner_workers(id),
    job_type        TEXT        NOT NULL,
    scope           JSONB,
    status          TEXT        NOT NULL CHECK (status IN ('running', 'interrupted', 'completed', 'failed')),
    started_at      TIMESTAMPTZ,
    stopped_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    current_city    TEXT,
    current_apn     TEXT,
    processed_count INT         DEFAULT 0,
    hit_count       INT         DEFAULT 0,
    error_summary   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.scanner_jobs DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_scanner_jobs_status
    ON public.scanner_jobs (status);

CREATE INDEX IF NOT EXISTS idx_scanner_jobs_worker_id
    ON public.scanner_jobs (worker_id);

CREATE INDEX IF NOT EXISTS idx_scanner_jobs_job_type_status
    ON public.scanner_jobs (job_type, status);

-- ============================================================
-- 3. scanner_job_checkpoints — resumable progress snapshots
-- ============================================================
CREATE TABLE IF NOT EXISTS public.scanner_job_checkpoints (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id     UUID        NOT NULL REFERENCES public.scanner_jobs(id),
    city       TEXT,
    apn        TEXT,
    row_offset INT,
    phase      TEXT,
    extra      JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.scanner_job_checkpoints DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_scanner_job_checkpoints_job_id_created_at
    ON public.scanner_job_checkpoints (job_id, created_at DESC);

-- ============================================================
-- 4. Discovery metadata columns on bills
-- ============================================================
ALTER TABLE public.bills
    ADD COLUMN IF NOT EXISTS first_seen_at       TIMESTAMPTZ;

ALTER TABLE public.bills
    ADD COLUMN IF NOT EXISTS discovered_by_job_id UUID REFERENCES public.scanner_jobs(id) ON DELETE SET NULL;

ALTER TABLE public.bills
    ADD COLUMN IF NOT EXISTS new_reviewed_at     TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_bills_new_reviewed_at_null
    ON public.bills (new_reviewed_at)
    WHERE new_reviewed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_bills_first_seen_at
    ON public.bills (first_seen_at);

-- Backfill existing rows: mark all pre-existing bills (those without first_seen_at)
-- as already-reviewed so they don't pollute the new discoveries queue.
UPDATE public.bills SET new_reviewed_at = now() WHERE new_reviewed_at IS NULL AND first_seen_at IS NULL;

-- ============================================================
-- 5. get_bills_filtered — add p_new parameter
--    -1 = all (default, no change)
--     1 = only rows where new_reviewed_at IS NULL
--     0 = only rows where new_reviewed_at IS NOT NULL
-- ============================================================

-- Drop the previous canonical signature before replacing so Postgres
-- doesn't complain about a default-value change on an existing overload.
DROP FUNCTION IF EXISTS public.get_bills_filtered(
    TEXT, TEXT, TEXT, TEXT,
    INTEGER, INTEGER,
    TEXT,
    INTEGER, INTEGER,
    TEXT, TEXT,
    INTEGER, INTEGER,
    TEXT, TEXT
);

CREATE OR REPLACE FUNCTION public.get_bills_filtered(
    p_q          TEXT    DEFAULT '',
    p_zip        TEXT    DEFAULT '',
    p_power      TEXT    DEFAULT '',
    p_city       TEXT    DEFAULT '',
    p_vpt        INTEGER DEFAULT -1,
    p_delinquent INTEGER DEFAULT -1,
    p_condition  TEXT    DEFAULT '',
    p_outofstate INTEGER DEFAULT -1,
    p_fav        INTEGER DEFAULT -1,
    p_sort       TEXT    DEFAULT 'location_of_property',
    p_order      TEXT    DEFAULT 'asc',
    p_limit      INTEGER DEFAULT 50,
    p_offset     INTEGER DEFAULT 0,
    p_research   TEXT    DEFAULT '',
    p_owner_name TEXT    DEFAULT '',
    p_new        INTEGER DEFAULT -1
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    result JSON;
BEGIN
    WITH filtered AS (
        SELECT b.*, p.row_json
        FROM public.bills b
        LEFT JOIN public.parcels p ON p."APN" = b.apn
        WHERE
            (p_q = '' OR p_q IS NULL OR b.location_of_property ILIKE '%' || p_q || '%' OR b.apn ILIKE '%' || p_q || '%' OR b.owner_name ILIKE '%' || p_q || '%')
            AND (p_zip = '' OR p_zip IS NULL OR
                EXISTS (
                    SELECT 1 FROM unnest(string_to_array(p_zip, ',')) AS z(val)
                    WHERE
                        b.location_of_property ILIKE '%' || trim(z.val) || '%'
                        OR (p.row_json->>'SitusZip') ILIKE '%' || trim(z.val) || '%'
                        OR (p.row_json->>'MailingZip') ILIKE '%' || trim(z.val) || '%'
                )
            )
            AND (p_power = '' OR p_power IS NULL OR b.power_status = p_power)
            AND (p_city = '' OR p_city IS NULL OR LOWER(b.city) = LOWER(p_city))
            AND (p_vpt = -1 OR p_vpt IS NULL OR b.has_vpt = p_vpt)
            AND (p_delinquent = -1 OR p_delinquent IS NULL OR b.delinquent = p_delinquent)
            AND (p_condition = '' OR p_condition IS NULL OR (
                CASE
                    WHEN p_condition = 'good'     THEN b.condition_score >= 7
                    WHEN p_condition = 'fair'     THEN b.condition_score >= 4 AND b.condition_score < 7
                    WHEN p_condition = 'poor'     THEN b.condition_score < 4
                    WHEN p_condition = 'unscored' THEN b.condition_score IS NULL
                    ELSE true
                END
            ))
            AND (p_fav = -1 OR p_fav IS NULL OR (p_fav = 1 AND EXISTS (SELECT 1 FROM public.favorites f WHERE f.apn = b.apn)))
            AND (p_research = '' OR p_research IS NULL OR (
                CASE
                    WHEN p_research = 'completed' THEN b.research_status = 'completed'
                    WHEN p_research = 'unchecked' THEN b.research_status IS NULL OR b.research_status = 'unchecked'
                    ELSE b.research_status = p_research
                END
            ))
            AND (p_owner_name = '' OR p_owner_name IS NULL OR b.owner_name ILIKE '%' || p_owner_name || '%')
            AND (
                p_new = -1 OR p_new IS NULL
                OR (p_new = 1 AND b.new_reviewed_at IS NULL)
                OR (p_new = 0 AND b.new_reviewed_at IS NOT NULL)
            )
    ),
    counted AS (
        SELECT COUNT(*) AS total FROM filtered
    ),
    paged AS (
        SELECT f.* FROM filtered f, counted c
        ORDER BY
            CASE WHEN p_order = 'asc'  AND p_sort = 'added_at'            THEN f.added_at            END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'added_at'            THEN f.added_at            END DESC NULLS LAST,
            CASE WHEN p_order = 'asc'  AND p_sort = 'city'                THEN f.city                END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc' AND p_sort = 'city'                THEN f.city                END DESC NULLS LAST,
            CASE WHEN p_order = 'asc'                                     THEN f.location_of_property END ASC  NULLS LAST,
            CASE WHEN p_order = 'desc'                                    THEN f.location_of_property END DESC NULLS LAST
        LIMIT p_limit OFFSET p_offset
    )
    SELECT json_build_object(
        'rows',  COALESCE(json_agg(paged), '[]'::json),
        'total', (SELECT total FROM counted)
    ) INTO result
    FROM paged;

    RETURN result;
END;
$$;

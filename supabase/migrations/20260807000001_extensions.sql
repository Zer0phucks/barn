-- BARN baseline, 1/6: extensions.
--
-- This migration set is a clean-slate baseline for a NEW Supabase project. It
-- replaces two divergent prior schemas (barn/scan/db_migrations/*.sql and the
-- barn-scan repo's supabase/migrations/) that were never reconciled and are
-- both retired. There is no data to preserve, so these run from empty.
--
-- Conventions, chosen once and applied throughout:
--   * lowercase snake_case for every identifier, so nothing ever needs
--     double-quoting. The old schema had parcels."APN", which forced every
--     query in every language to remember the casing; that is gone.
--   * has_vpt / delinquent are integer 0/1, not boolean, matching the tax
--     portal scrape and the existing scanner code.
--   * bills.apn is the join key everywhere.

create extension if not exists postgis;
create extension if not exists pgcrypto;

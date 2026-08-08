# BARN database

Supabase project **`barn`** — `ndjqmzfqifafsuygdqdz`, created 2026-08-07.

`migrations/` is a **clean-slate baseline**, not an incremental history. It
replaces two schemas that were never reconciled and are both retired:

| Retired | Was | Fate |
|---|---|---|
| `scan/db_migrations/*.sql` | 12 unversioned files applied by hand in the SQL editor | folded in here |
| `barn-scan` repo's `supabase/migrations/` | the PostGIS scouting layer | folded in here |

Those targeted older projects (`nrfbgtmbginpcdxmttrq`, `vzgmmlaojvkpbakvgcwh`,
`kawsyqariasjpzlrrkcc`), all of which predate this one and hold no data worth
keeping. Don't apply them.

## Applying

The migrations have **not been applied yet** and have never been executed
against a live Postgres. Expect to fix something on the first push.

```bash
cd barn
npx supabase link --project-ref ndjqmzfqifafsuygdqdz   # prompts for the DB password
npx supabase db push
```

`db push` needs the database password (Dashboard → Settings → Database), not
the publishable key. To verify afterwards:

```bash
npx supabase db diff --linked      # should print nothing
```

## Layout

| File | Contents |
|---|---|
| `20260807000001_extensions.sql` | postgis, pgcrypto |
| `20260807000002_core_property_tables.sql` | `parcels`, `bills` (57 cols), geom trigger, indexes |
| `20260807000003_scouting.sql` | `lists`, `list_properties`, `scout_results` |
| `20260807000004_research_outreach_worker_state.sql` | `cbc_image_extractions`, `outreach*`, `scanner_*` |
| `20260807000005_views_and_rpcs.sql` | `map_markers` view, `scout_next()`, route-queue RPCs |
| `20260807000006_rls_and_storage.sql` | RLS policies, `streetview-images` bucket |

## Design decisions

**Lowercase snake_case everywhere.** The old schema had `parcels."APN"`, which
forced every query in Python, SQL, and Kotlin to remember the casing — and one
of the two prior schemas got it wrong, so its `map_markers` view could not have
applied. Nothing here needs double-quoting.

**`has_vpt` / `delinquent` are `integer` 0/1, not boolean.** Matches the tax
portal scrape and the existing scanner code.

**`bills.geom` is derived, never written.** The `trg_bills_set_geom` trigger
maintains it from `lat`/`lng`, so writers only ever set the two ordinates.
`idx_bills_geom` (GIST) backs `scout_next()`'s `<->` KNN ordering.

**`streetview_image_path` holds a Storage URL, not a disk path.** The Android
app reads that column directly and cannot fetch a path on the scanner VM. See
`scan/condition_scanner.py::_upload_to_storage`.

**Dropped on purpose:** `favorites` (a list named `Favorites` replaces it),
`scouting_collections` / `collection_properties` (dead in both codebases),
`get_bills_for_map()` (→ `map_markers`),
`android_get_next_scoutable_property()` (→ `scout_next()`, PostGIS instead of a
full-scan haversine), and `get_bills_filtered()` (15 scalar params
reimplementing what PostgREST does from the query string).

**RLS.** Scanners and Flask connect as `service_role` and bypass RLS entirely;
the policies exist to constrain the Android app and anything else holding only
the publishable key. Back-office tables (`outreach*`, `cbc_image_extractions`,
`scanner_*`) have RLS enabled with **no policies** — deliberate, so they are
service-role-only.

## Reseeding data

The database starts empty and all prior data is gone, so everything gets
rescanned:

```bash
cd scan && source .venv/bin/activate
python find_meas_w_addresses.py            # tax portal -> bills (writes lat/lng inline)
python pge_scanner.py                      # power status
python condition_scanner.py                # Street View + Gemini condition score
python intake_autopilot.py                 # ongoing daily intake + enrichment
```

`scan/.env` needs `SUPABASE_SERVICE_KEY` for any of these to write — the
publishable key hits RLS and silently writes zero rows.

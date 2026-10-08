# BARN database

Supabase project **`barn`** — `zezhsmgtdzlagqwlvjui`, created 2026-09-18.

> **2026-09-18.** The previous project (`ndjqmzfqifafsuygdqdz`) was deleted.
> Deleting a Supabase project destroys its PITR and daily backups with it, so
> there was nothing to restore from — only Supabase support can recover a
> recently-deleted project, and only within a short window. This project is its
> replacement: same migrations, data reloaded from a `bills` CSV export by
> `scripts/restore_db.py`. See **Recovering from a CSV export** below.

`migrations/` is a **clean-slate baseline**, not an incremental history. It
replaces two schemas that were never reconciled and are both retired:

| Retired                                       | Was                                                    | Fate           |
| --------------------------------------------- | ------------------------------------------------------ | -------------- |
| `scan/db_migrations/*.sql`                  | 12 unversioned files applied by hand in the SQL editor | folded in here |
| `barn-scan` repo's `supabase/migrations/` | the PostGIS scouting layer                             | folded in here |

Those targeted older projects (`nrfbgtmbginpcdxmttrq`, `vzgmmlaojvkpbakvgcwh`, `ndjqmzfqifafsuygdqdz`,
`kawsyqariasjpzlrrkcc`), all of which predate this one and hold no data worth
keeping. Don't apply them.

## Applying

All seven migrations are applied to `zezhsmgtdzlagqwlvjui` and have been
executed against a live Postgres, so they no longer carry the "never run"
caveat. On a fresh project:

```bash
cd barn
npx supabase link --project-ref zezhsmgtdzlagqwlvjui   # prompts for the DB password
npx supabase db push
```

`db push` needs the database password (Dashboard → Settings → Database), not
the publishable key. To verify afterwards:

```bash
npx supabase db diff --linked      # should print nothing
```

## Layout

| File                                                  | Contents                                                 |
| ----------------------------------------------------- | -------------------------------------------------------- |
| `20260807000001_extensions.sql`                     | postgis, pgcrypto                                        |
| `20260807000002_core_property_tables.sql`           | `parcels`, `bills` (57 cols), geom trigger, indexes  |
| `20260807000003_scouting.sql`                       | `lists`, `list_properties`, `scout_results`        |
| `20260807000004_research_outreach_worker_state.sql` | `cbc_image_extractions`, `outreach*`, `scanner_*`  |
| `20260807000005_views_and_rpcs.sql`                 | `map_markers` view, `scout_next()`, route-queue RPCs |
| `20260807000006_rls_and_storage.sql`                | RLS policies,`streetview-images` bucket                |

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

## Recovering from a CSV export

`scripts/restore_db.py` rebuilds `bills` and the image bucket from a CSV export
with the admin UI's column set. It is what restored this project on 2026-09-18:

```bash
export SUPABASE_URL=https://zezhsmgtdzlagqwlvjui.supabase.co
export SUPABASE_ANON_KEY=sb_publishable_...
export SUPABASE_EMAIL=... SUPABASE_PASSWORD=...     # or SUPABASE_SERVICE_KEY
python scripts/restore_db.py --csv list.csv
```

Two things the export does **not** carry, which the script reconstructs:

**Coordinates.** The export has no `lat`/`lng`. That is not cosmetic —
`map_markers` filters `where lat is not null and lng is not null` and
`scout_next()` orders by `geom <->`, so an uncoded row is invisible to both the
web map and the scout app. Berkeley rows resolve against `berkeley.csv`'s parcel
centroids; everything else goes to the Census batch geocoder, which needs no API
key. Census matches street ranges, not parcels, so those pins sit on the street
rather than the rooftop — close enough to navigate to, worth re-deriving from a
real Alameda County parcel export (into `parcels.row_json`, then
`scan/backfill_coordinates.py`) if precision starts to matter.

**Image links.** `streetview_image_path` is a Storage URL, so it dies with the
old project. The script re-uploads `scan/streetview_images/<apn>.jpg` — the
corpus is committed, so no rescan or Gemini spend is needed — and repoints the
column.

Writes go through PostgREST under RLS rather than with the service key, so the
load needs four temporary policies; the script's docstring has them, and
dropping them afterwards is part of the restore. With `SUPABASE_SERVICE_KEY` set
they are unnecessary.

## Reseeding data

`bills` holds the 519 rows restored from the CSV export, so this is no longer a
from-empty rescan — these extend and refresh what is already there. `parcels` is
still empty, which is why coordinates came from the Census geocoder rather than
parcel centroids:

```bash
cd scan && source .venv/bin/activate
python find_meas_w_addresses.py            # tax portal -> bills (writes lat/lng inline)
python pge_scanner.py                      # power status
python condition_scanner.py                # Street View + Gemini condition score
python intake_autopilot.py                 # ongoing daily intake + enrichment
```

`scan/.env` needs `SUPABASE_SERVICE_KEY` for any of these to write — the
publishable key hits RLS and silently writes zero rows.

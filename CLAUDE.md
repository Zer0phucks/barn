# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BARN (Bay Area Renovating Neighbors) is a monorepo with two deployed apps:
- **`scan/`** — Flask app at `app.barnhousing.org`: VPT Scanner for identifying vacant properties in Alameda County via tax portal scraping, PG&E power checks, and AI-powered ownership research.
- **`web/`** — React SPA at `barnhousing.org`: Public-facing site for property reporting, volunteer signup, housing applications, and admin dashboard.

See `scan/CLAUDE.md` for detailed scan-specific guidance.

## Commands

### Web (from `web/`)
```bash
npm install
npm run dev          # Vite dev server on :8080
npm run build        # Production build to dist/
npm run lint         # ESLint
npm run test         # Vitest (single run)
npm run test:watch   # Vitest watch mode
```

### Scan (from `scan/`)
```bash
./install.sh                          # First-time setup (venv, deps, Playwright)
source .venv/bin/activate
python run_all.py --city=OAKLAND      # Scan + web UI on :5000
python run_all.py --continuous        # All cities loop + web UI
python webgui/app.py                  # Web UI only (no scanning)
```

### Deploy (on VM)
```bash
cd /home/nsnfrd768/barn/barn
./deploy.sh    # git pull + npm build + systemd restart
```

## Architecture

### Two Separate Apps, One Database

Both apps share a Supabase backend. The scan app writes property data; the React admin dashboard reads it. They don't share code.

### Scan App: Dual-Mode Design
- **Local/VM mode** (`run_all.py`): Multi-threaded orchestrator runs VPT scraping + PGE Playwright checks + Flask web UI together. Caches to `measw_cache.jsonl`, syncs to Supabase.
- **Vercel/cloud mode** (`app.py` → `webgui/app.py`): Web UI only, no scanning. The root `app.py` explicitly registers `db.py` before `webgui/` to avoid module shadowing.

### Scan App: Enrichment Pipeline
New properties flow: `intake_autopilot.py` → `enrichment_runner.py` → parallel research scanners (`gemini_research_scanner.py`, `cyber_research_agent.py`, `contact_scanner.py`, `condition_scanner.py`) → Supabase `bills` table.

### React Admin: VPT Scanner Control
`web/src/components/admin/vpt/` contains the admin UI for scanner state. `web/src/services/vptApi.ts` talks to the Supabase `vpt-scanner-control` edge function, which forwards to the scan VM. `web/src/integrations/supabase/types.ts` is auto-generated — don't edit manually.

### Key Supabase Tables
- **`bills`** (PK: `apn`): Core property records. Fields: `has_vpt`, `vpt_marker`, `delinquent`, `power_status`, `city`, research status, contact info, condition scores.
- **`parcels`** (PK: `APN`): Raw Alameda County parcel data stored as `row_json`.
- **`cbc_image_extractions`**: Gemini-extracted data from background check screenshots.

### Scan Conventions
- All Supabase ops go through `db.py` `_with_retry()` (exponential backoff).
- Web scraping uses `curl_cffi` for TLS impersonation; Playwright as fallback.
- `scanner/` package mirrors root-level modules for import flexibility.
- Frontend in `webgui/templates/` is vanilla JS + Leaflet.js — no build step.

## Environment Variables

**Scan** (`.env` in `scan/`):
- Required: `SUPABASE_URL`, `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_KEY`
- Optional: `GOOGLE_API_KEY` (Gemini), `OPENROUTER_API_KEY`, `SCRAPER_API_KEY`, `SCOUT_API_KEY`
- Tuning: `VPT_MAX_WORKERS` (default 8), `VPT_REQUEST_DELAY_SEC` (default 0.05), `VPT_ENABLE_PGE`

**Web** (`.env` in `web/`): Supabase URL and anon key for the React client.

## Systemd

`barn-scan.service` WorkingDirectory and ExecStart point to `/home/nsnfrd768/barn/barn/scan/`. The intake autopilot runs on a timer via `barn-intake-autopilot.service` / `.timer`.

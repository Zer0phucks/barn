# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BARN-scan (VPT Scanner) is a property research and monitoring tool for Alameda County, CA. It identifies properties subject to Vacant Property Tax (VPT), tracks tax delinquency, checks PG&E power status as a vacancy indicator, and gathers ownership/contact information via AI-powered research.

## Commands

### Installation
```bash
./install.sh                          # Full setup (venv, deps, Playwright)
# Or manually:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Running Locally
```bash
source .venv/bin/activate
python run_all.py --city=OAKLAND      # Scan specific city + start web UI on :5000
python run_all.py --continuous         # Scan all cities in loop + web UI
python run_all.py --no-pge            # Disable PGE power scanner
```

### Running Web UI Only (no scanning)
```bash
python webgui/app.py                  # Flask dev server on :5000
```

### Deployment
Deployed to Vercel. Only the web UI runs on Vercel (`app.py` → `webgui/app.py` + `db.py`). Scanning scripts are local-only. Health check: `GET /health`.

### Database Migrations
SQL migration files in `db_migrations/` are applied manually against Supabase.

## Architecture

### Dual-Mode Design
- **Local mode** (`run_all.py`): Orchestrates scanning + web UI together. Background threads run VPT scanning and PGE power checking. Results cached locally in `measw_cache.jsonl` and synced to Supabase.
- **Cloud mode** (Vercel): `app.py` bootstraps `webgui/app.py`. Database-only UI, no scanning capability. Forces project root `db.py` to load before `webgui/` via explicit module registration.

### Key Modules

| Module | Purpose |
|--------|---------|
| `run_all.py` | Main orchestrator: scan threads + Flask startup |
| `find_meas_w_addresses.py` | Core VPT scanner: scrapes Alameda County tax portal, detects MEAS-W/MEAS-M markers and delinquency |
| `pge_scanner.py` | PG&E power status checker via Playwright browser automation |
| `db.py` | Supabase database layer with retry logic (exponential backoff for transient errors) |
| `webgui/app.py` | Flask app: 45+ routes for property list, detail, map, admin, API endpoints |
| `webgui/db_impl.py` | Supabase query implementations for the web UI |
| `gemini_research_scanner.py` | Deep property research using Google Gemini + CBC scraping |
| `cyber_research_agent.py` | Property research via OpenRouter (Kimi K2.5) |
| `contact_scanner.py` | Contact info extraction from CBC pages |
| `ingest_cbc_images_to_supabase.py` | CBC screenshot processing + Gemini extraction |
| `app.py` (root) | Vercel entrypoint: bootstraps db.py and webgui |

### Database (Supabase/Postgres)
Primary tables:
- **bills**: Property tax bills (PK: `apn`). Core fields: `has_vpt`, `vpt_marker`, `delinquent`, `power_status`, `city`, `location_of_property`. Also stores research status, contact info, condition scores, occupancy/ownership type.
- **parcels**: Master parcel data from Alameda County CSV (PK: `APN`, stores full row as `row_json`).
- **cbc_image_extractions**: Gemini-extracted data from CBC screenshots (UNIQUE: `source_image_name`).

### Data Flow
1. CSV parcel data (`Parcels_*.csv`) → `find_meas_w_addresses.py` scrapes tax portal per APN
2. VPT/delinquent properties → `db.upsert_bill()` → Supabase
3. PGE scanner (Playwright) checks power status → updates bills
4. Research scanners enrich with ownership, contacts, condition data
5. Web UI reads from Supabase, renders list/map/detail views

### Authentication
Supabase Auth (email/password). Flask routes verify Supabase JWT tokens. Login page uses `SUPABASE_URL` and `SUPABASE_ANON_KEY` client-side.

## Environment Variables

**Required:** `SUPABASE_URL`, `SUPABASE_ANON_KEY` (or `SUPABASE_SERVICE_KEY`)

**Optional APIs:** `GOOGLE_API_KEY` (Gemini), `OPENROUTER_API_KEY` (Kimi K2.5), `SCRAPER_API_KEY` (Cloudflare bypass), `SCOUT_API_KEY` (mobile app)

**Tuning:** `VPT_MAX_WORKERS` (default 8), `VPT_REQUEST_DELAY_SEC` (default 0.05), `VPT_ENABLE_PGE` (true/false), `SUPABASE_RETRY_ATTEMPTS` (default 3)

## Conventions

- Python 3.10+ with type hints (`from __future__ import annotations`)
- Supabase client is a lazy singleton via `db.get_client()`
- All Supabase operations use retry with exponential backoff (see `db.py` `_with_retry()`)
- Web scraping uses `curl_cffi` for TLS impersonation and Playwright as fallback
- Frontend is vanilla JS + Leaflet.js for maps, no build step
- `scanner/` package mirrors root-level scanner modules for import flexibility

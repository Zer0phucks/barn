# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BARN (Bay Area Renovating Neighbors)** identifies and tracks vacant properties in Alameda County, CA. It combines a tax-portal scraper, AI-powered research, a Flask admin UI, a React public site, and a Kotlin Android scout app — all backed by Supabase (PostgreSQL).

---

## Commands

### Web Frontend (`web/`)
```bash
cd web
npm install
npm run dev          # Dev server at http://localhost:8080
npm run build        # Production build
npm run lint         # ESLint
npm run test         # Vitest (run once)
npm run test:watch   # Vitest watch mode
```

### Python Scanner (`scan/`)
```bash
cd scan
./install.sh                              # Full setup: venv + pip + playwright chromium
source .venv/bin/activate

python run_all.py --city=OAKLAND          # Scan one city + start Flask UI on :5000
python run_all.py --continuous            # Continuous multi-city loop
python webgui/app.py                      # Flask UI only (no scanning)
python intake_autopilot.py               # Daily backlog intake + enrichment pipeline

python -m unittest discover -s tests     # Run all unit tests
python -m unittest tests.test_foo        # Run a single test module
```

### Android (`android/`)
```bash
cd android
./gradlew test           # JVM unit tests
./gradlew assembleDebug  # Build debug APK
```

### Deployment
```bash
./deploy.sh              # Full redeploy (git pull → pip → npm build → systemd restart)
```

---

## Architecture

The repo is a monorepo with four components sharing a Supabase backend:

```
barnhousing.org (web/)          → Vercel, React SPA, public landing page
app.barnhousing.org (scan/webgui/) → Vercel, Flask admin UI (45+ routes)
Local VM (scan/)                → Python scanners running as systemd services
Android (android/)              → Scout app for on-the-ground field work
```

**Data pipeline:**
1. `find_meas_w_addresses.py` scrapes the Alameda County tax portal for VPT/delinquent markers → upserts to `bills` table
2. `pge_scanner.py` uses Playwright to check PG&E power status per address
3. `gemini_research_scanner.py` / `enrichment_runner.py` run parallel AI research (Gemini + Kimi K2.5 via OpenRouter) to extract ownership, contacts, condition scores
4. `intake_autopilot.py` runs daily to ingest new parcels and trigger enrichment
5. `webgui/app.py` (Flask) reads Supabase to serve the admin UI
6. Android app reads the same Supabase data for field scouts

**Key files:**
- `scan/db.py` — all Supabase operations (lazy singleton client, `_with_retry()` pattern)
- `scan/webgui/app.py` — Flask app with all admin routes
- `scan/run_all.py` — orchestrates scanning threads + Flask startup
- `web/src/integrations/supabase/types.ts` — **auto-generated from Supabase schema, do not hand-edit**

**Primary DB tables:** `bills` (PK: `apn`), `parcels` (PK: `APN`), `cbc_image_extractions`

---

## Environment Variables

**`scan/` requires:**
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (or `SUPABASE_ANON_KEY`)
- Optional: `GOOGLE_API_KEY` (Gemini), `OPENROUTER_API_KEY` (Kimi), `SCRAPER_API_KEY`, `SCOUT_API_KEY`
- Tuning: `VPT_MAX_WORKERS` (default 8), `VPT_REQUEST_DELAY_SEC` (default 0.05), `SUPABASE_RETRY_ATTEMPTS` (default 3)

**`web/` requires:**
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

---

## Key Conventions

- **Web scraping**: Use `curl_cffi` for TLS impersonation (Cloudflare bypass); fall back to Playwright only when necessary.
- **Supabase access**: Always use `db.get_client()` (lazy singleton). Wrap DB calls with `_with_retry()` for exponential backoff.
- **Vercel vs VM**: The Flask app runs on Vercel (web UI only); all scanning scripts run on the GCloud VM. Never expect scanning to work in Vercel's environment.
- **Scanner parallelism**: `enrichment_runner.py` runs multiple AI scanners in parallel threads; mind rate limits and `VPT_MAX_WORKERS`.
- **Android proxy**: The scout app calls Supabase through a proxy Edge Function, not directly.

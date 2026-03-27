# GEMINI.md

This file provides context and instructions for the Gemini CLI when working with the **BARN (Bay Area Renovating Neighbors)** monorepo.

## Project Overview

BARN is a multi-platform system for identifying, researching, and tracking vacant properties in Alameda County, CA. It aims to revitalize the community by identifying housing opportunities through tax portal scraping, utility checks, and AI-powered ownership research.

### Monorepo Structure

- **`scan/`**: A Python/Flask application. It is the core data engine that scrapes the Alameda County tax portal for Vacant Property Tax (VPT) markers, checks PG&E power status via Playwright, and performs deep property research using Google Gemini and OpenRouter.
- **`web/`**: A React Single Page Application (SPA) built with Vite, TypeScript, and Tailwind CSS (Shadcn UI). It serves as the public-facing site and the primary administrative dashboard for managing property data.
- **`android/`**: A Kotlin-based Android application ("Scout") for on-the-ground property scouting. It connects to the same Supabase backend via a proxy Edge Function.
- **`scripts/`**: Deployment and maintenance scripts.

## Core Technologies

- **Database/Backend**: Supabase (PostgreSQL, Auth, Edge Functions).
- **Scan Engine**: Python 3.10+, Flask, Playwright (Chromium), Google Gemini (google-genai), OpenRouter (Kimi K2.5), `curl_cffi` (TLS impersonation).
- **Web Frontend**: React, Vite, TypeScript, Tailwind CSS, Shadcn UI, TanStack Query, Radix UI.
- **Mobile App**: Kotlin, Android SDK, Google Maps SDK.

## Key Commands

### `scan/` (Python Engine)
```bash
cd scan
./install.sh                          # Initial setup (venv, deps, Playwright)
source .venv/bin/activate
python run_all.py --city=OAKLAND      # Run scan + web UI on :5000
python run_all.py --continuous        # Continuous scan loop + web UI
python webgui/app.py                  # Web UI only (no scanning)
```

### `web/` (React Frontend)
```bash
cd web
npm install
npm run dev                           # Vite dev server on :8080
npm run build                         # Production build
npm run lint                          # ESLint check
npm run test                          # Run Vitest tests
```

### `android/` (Scout App)
- Open in Android Studio.
- Require `MAPS_API_KEY` in `android/local.properties`.
- Configuration in `app/src/main/res/values/strings.xml` for `api_base_url`.

### Deployment
```bash
./deploy.sh                           # Root script for VM deployment
```

## Development Conventions

### Backend & Scanning (`scan/`)
- **Supabase Access**: Use `db.get_client()` for a lazy singleton. All operations should use `_with_retry()` for exponential backoff.
- **Scraping**: Use `curl_cffi` for TLS impersonation to bypass Cloudflare; fallback to Playwright only when necessary.
- **Type Safety**: Use Python type hints (`from __future__ import annotations`).
- **Research Pipeline**: `intake_autopilot.py` -> `enrichment_runner.py` -> parallel AI scanners -> `bills` table.

### Web Frontend (`web/`)
- **Styling**: Tailwind CSS with Shadcn UI components.
- **Data Fetching**: TanStack Query (React Query) for API interactions.
- **State Management**: React Router for navigation; Supabase Auth for session management.
- **Types**: `web/src/integrations/supabase/types.ts` is auto-generated; do not edit manually.

### Mobile App (`android/`)
- Uses Supabase Auth (email/password).
- Communicates with the scanner API via a proxy Edge Function.

## Environment Variables

### `scan/` (`.env`)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY` (or `SUPABASE_SERVICE_KEY`)
- `GOOGLE_API_KEY` (for Gemini research)
- `OPENROUTER_API_KEY` (for Kimi K2.5 research)
- `SCRAPER_API_KEY` (for Cloudflare bypass)
- `VPT_MAX_WORKERS` (default 8)

### `web/` (`.env`)
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

## Systemd Services (VM)
- `barn-vpt-worker.service`: Scanning worker.
- `barn-vpt-tunnel.service`: Reverse proxy/tunnel.
- `barn-intake-autopilot.timer`: Scheduled intake tasks.

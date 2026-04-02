# Vercel + Local Scanner Worker Hybrid Design

**Date:** 2026-04-02

## Goal

Move the public BARN web experience from the current GCloud VM to Vercel while keeping Supabase as the shared backend for the web app, scanner, and Android app.

The scanner should continue running on the local machine because it depends on long-running Python processes, Playwright, and local operator control. The system must preserve scan history and progress across machine restarts, support manual resume, and make newly discovered properties easy to identify and triage from the admin UI.

## Current Context

- `web/` is a Vite + React + TypeScript app that already reads and writes most application data directly through Supabase.
- `scan/` contains the Python scanner, Flask-backed worker endpoints, and checked-in user services for a local worker and tunnel.
- `android/` already talks to the same Supabase-backed data model.
- `web/src/services/vptApi.ts` already treats scan control as a separate worker API behind the Supabase Edge Function `vpt-scanner-control`.
- `scan/service/barn-vpt-worker.service` and `scan/service/barn-vpt-tunnel.service` already establish the pattern of a local worker plus public tunnel URL sync.

This means the desired architecture is already partially present in the codebase. The main work is to formalize the split, make worker state durable, and surface new-property discovery in the UI.

## Desired Architecture

### Vercel

Vercel hosts the `web/` application only.

Responsibilities:

- Serve the public landing page and admin UI
- Read and write application data through Supabase
- Call Supabase Edge Functions for server-side integrations such as donation checkout and scanner control

Vercel should not attempt to run the Python scanner or any long-lived Playwright automation.

### Supabase

Supabase remains the central source of truth for:

- Application data already used by `web/` and `android/`
- Scanner tables and RPCs
- Durable scan job state and checkpoints
- Worker heartbeat and availability metadata
- Discovery metadata for newly found properties
- Edge Functions used as the control plane between Vercel and the local worker

### Local Machine

This machine runs the scanner worker and is not expected to stay online 24/7.

Responsibilities:

- Execute scans, enrichment jobs, condition jobs, PG&E checks, and browser automation
- Maintain local caches and artifacts that are expensive to recompute
- Expose worker control/status endpoints through the existing Flask worker app
- Publish a public tunnel URL while online so the admin UI can control scans remotely

Because this machine is intermittently online, durable progress state must not live only in process memory or local ad hoc cache files.

## Operating Model

The chosen operating model is a durable hybrid:

- Web app on Vercel
- Shared backend on Supabase
- Local worker on this machine
- Public tunnel for remote control while online
- Manual restart only after interruption or machine downtime

When the machine is offline:

- The admin UI still loads from Vercel
- Existing Supabase-backed property data remains visible
- Worker status should show offline
- Scan actions should fail clearly and non-destructively

When the machine is online:

- The worker publishes a tunnel URL
- The tunnel URL is synced into Supabase Edge Function config or another central lookup path
- The admin UI can start, stop, and monitor scan jobs remotely

## Worker Control Flow

The worker control plane should continue using the existing pattern:

1. Admin UI in `web/` invokes scanner actions through `web/src/services/vptApi.ts`
2. The client calls Supabase Edge Function `vpt-scanner-control`
3. The edge function forwards the request to the current worker base URL
4. The local Flask worker handles the action and writes progress updates to Supabase

This keeps the browser from depending directly on the tunnel endpoint and centralizes worker auth and routing in Supabase.

## Durable Scan State

### Requirements

The scanner must be able to survive:

- local process crashes
- machine reboots
- manual stopping and later resumption
- the machine being offline for long periods

The operator should always be able to answer:

- Is a worker online?
- Is a job currently running?
- What city or APN is it on?
- What was the last completed checkpoint?
- Can the last interrupted job be resumed?

### Proposed Data Model

Add durable Supabase-backed worker state for:

- `scanner_workers`
  - identifies this machine or worker instance
  - stores worker name, last heartbeat, tunnel URL, online/offline state, supported capabilities
- `scanner_jobs`
  - one row per scan, enrichment, condition, research, or PG&E job
  - stores job type, requested scope, status, started/stopped/completed timestamps, current city, current APN, processed counters, hit counters, error summary, and worker assignment
- `scanner_job_checkpoints`
  - append-only or latest-checkpoint records for resumable position
  - stores enough context to continue manually later, such as city, APN, row offset, phase, and any additional state required by the job type
- optional `scanner_job_events`
  - structured progress or audit events for admin visibility without scraping log files

The exact table names can vary, but these concepts should exist explicitly in Supabase rather than only in Python globals.

### Checkpoint Strategy

Each long-running job writes periodic checkpoints to Supabase.

For city/APN scans, a checkpoint should include:

- current city
- last completed APN or current APN in progress
- processed count
- hit count
- job phase if the workflow has multiple phases
- timestamp

On interruption, the job moves to an interrupted or paused state with its last checkpoint preserved.

Manual restart behavior:

- The operator can resume the most recent interrupted job from its checkpoint
- The operator can also choose to start a fresh job
- Resume is explicit, not automatic at machine startup

## Local Cache Strategy

Local cache remains important for performance, but it is not the authoritative record of operational state.

Local cache should continue to store things like:

- fetched bill HTML
- Playwright-derived intermediate artifacts
- expensive lookup results
- local parcel processing aids

Supabase should store the authoritative operational state:

- what job exists
- whether it is running or interrupted
- where to resume
- when a property was first discovered
- whether a discovery was acknowledged

This split avoids losing important state when the machine is off while preserving local efficiency.

## New Discovery Workflow

The scanner is primarily a discovery system for finding newly tracked properties, not just re-reading previously known properties.

### Discovery Rule

A property becomes a new discovery the first time the scanner promotes it into the tracked dataset.

At that moment, write discovery metadata into Supabase:

- `first_seen_at`
- `discovered_by_job_id`
- `new_reviewed_at` as nullable

If useful, `first_seen_source` or `discovery_reason` can also be stored for auditing.

### Acknowledgement-Based Semantics

The authoritative rule is:

- `new_reviewed_at is null` means the property is still new
- once acknowledged, `new_reviewed_at` is set and the property leaves the new queue

This is preferred over a pure date window because a property should remain visibly new until someone intentionally reviews it.

### UX Surfaces

Add both:

- a `New` filter in the scanner property list
- a `New discoveries` section in the admin UI

The list filter allows day-to-day triage in the existing main workflow.

The admin section should show:

- recently discovered properties
- discovery timestamp
- job that discovered them
- current city and major flags
- actions to open or acknowledge a discovery

This gives the operator a dedicated discovery inbox without losing integration with the main property views.

## Admin UI Behavior

The Vercel-hosted admin UI should show both availability and progress.

Suggested states:

- worker online, idle
- worker online, running job
- worker online, interrupted job available to resume
- worker offline

Suggested admin capabilities:

- start a new scan
- resume the latest interrupted scan
- stop a running scan
- view current job progress
- view recent job history
- review and acknowledge new discoveries

Progress should come from Supabase-backed job state, not only from in-memory Flask status responses.

## API and Integration Expectations

### Existing Reusable Pieces

- `web/src/services/vptApi.ts` already supports worker control actions
- `web/supabase/functions/vpt-scanner-control/index.ts` already forwards worker requests
- `scan/webgui/app.py` already provides worker-oriented API routes
- `scan/service/run_vpt_tunnel_sync.sh` already publishes the tunnel URL into Supabase secrets

### Required Changes

- formalize worker heartbeat reporting into Supabase
- formalize job creation, status transitions, and checkpoints in Supabase
- extend worker status endpoints to surface durable job state
- extend web UI queries to read worker/job/discovery data
- add discovery acknowledgement actions
- ensure tunnel URL updates remain safe and visible when the worker reconnects

## Deployment Plan

### Slice 1: Public Web To Vercel

- configure Vercel project for `web/`
- set `VITE_SUPABASE_URL`
- set `VITE_SUPABASE_PUBLISHABLE_KEY`
- verify donation and edge-function-related env dependencies
- point `barnhousing.org` and `www` to Vercel
- remove VM responsibility for serving the landing page

### Slice 2: Durable Worker State

- add Supabase schema for workers, jobs, checkpoints, and discovery metadata
- update Python worker and scanner code to write heartbeat and progress
- add explicit resume support from last checkpoint
- preserve local cache usage without relying on it for control state

### Slice 3: Admin And Discovery UX

- add worker online/offline and current progress to admin UI
- add resume controls for interrupted jobs
- add `New` filter to the main property list
- add `New discoveries` admin queue and acknowledge action

## Error Handling

The system should handle these cases explicitly:

- worker offline: show clear offline status and disable destructive controls
- tunnel stale or unreachable: fail requests with a friendly worker-unavailable message
- interrupted job: preserve checkpoint and allow manual resume
- duplicate discovery: do not re-mark already discovered properties as new
- partial progress update failure: prefer append-safe checkpoints and idempotent status updates

## Testing Strategy

### Web

- verify Vercel build and environment wiring
- verify scanner control UI states for online, offline, running, and interrupted jobs
- verify `New` filter behavior
- verify discovery acknowledgement behavior

### Python Worker

- unit tests for job state transitions
- unit tests for checkpoint persistence and resume selection
- tests for discovery metadata writes on first promotion only
- tests for worker status payloads

### Integration

- end-to-end worker control through `vpt-scanner-control`
- tunnel-connected worker status read from the admin UI
- interrupted run followed by manual resume from checkpoint

## Out Of Scope

- automatic restart of scanning when the machine boots
- moving the scanner runtime itself onto Vercel
- replacing the tunnel model with a queue-driven polling model in this phase
- redesigning unrelated application flows in `web/` or `android/`

## Recommendation

Implement the durable hybrid architecture described above.

It preserves the practical strengths of the current local scanner setup while giving the project a cleaner hosting model:

- Vercel for the public web app
- Supabase as the shared durable backend
- local worker for scanning and automation
- explicit discovery workflow for newly found properties

This is the lowest-risk path that matches the current codebase and the operator workflow.

# Scanner Worker State Integration

**Date:** 2026-04-02
**Depends on:** `2026-04-02-vercel-local-worker-hybrid-design.md` (already implemented)

## Context

The durable worker state layer was built and merged in the Vercel hybrid work. The plumbing is complete:

- `scan/worker_state.py` — heartbeat, job CRUD, checkpoints, discovery marking
- `scan/db_migrations/supa_migration_scanner_worker_state.sql` — applied to Supabase (scanner_workers, scanner_jobs, scanner_job_checkpoints tables + discovery fields on bills)
- Flask routes + Edge Function + React UI are all wired up and ready

**The gap:** None of the actual scanner threads call `worker_state`. Until they do, the admin UI will always show "Worker offline" and the discoveries panel will always be empty.

## What Needs to Be Wired In

### 1. Worker heartbeat (`scan/run_all.py`)

When the Flask worker starts up (the main thread in `run_all.py`), it should begin a background heartbeat loop:

```python
import worker_state
import threading

def _heartbeat_loop(worker_name, stop_event):
    while not stop_event.wait(30):  # every 30 seconds
        try:
            tunnel_url = os.environ.get("VPT_WORKER_BASE_URL")
            worker_state.heartbeat(worker_name, tunnel_url=tunnel_url)
        except Exception:
            pass  # non-fatal

# Start in run_all.py startup:
_heartbeat_stop = threading.Event()
_heartbeat_thread = threading.Thread(
    target=_heartbeat_loop, args=("barn-worker", _heartbeat_stop), daemon=True
)
_heartbeat_thread.start()
```

The worker name can be read from an env var (`BARN_WORKER_NAME`, default `"barn-worker"`).

### 2. Job creation and status transitions (`scan/run_all.py` — `start_scan`, `stop_scan`)

`start_scan()` should:
1. Call `worker_state.heartbeat()` to get/ensure the worker_id
2. Call `worker_state.create_job(worker_id, "scan", {"city": city, "continuous": continuous})` → store `job_id` in `scan_state`
3. Pass `job_id` down to the scan thread

`stop_scan()` should:
1. Call `worker_state.update_job(job_id, status="interrupted")` (not "completed" — the operator stopped it manually, so it's resumable)

When the scan thread finishes naturally:
1. Call `worker_state.update_job(job_id, status="completed")`

On unhandled exception in the scan thread:
1. Call `worker_state.update_job(job_id, status="interrupted", error_summary=str(e))`

### 3. Periodic checkpoints (`scan/find_meas_w_addresses.py` or wherever the APN loop lives)

Inside the main APN scanning loop, write a checkpoint roughly every N APNs (e.g. every 50):

```python
if processed_count % 50 == 0:
    worker_state.write_checkpoint(
        job_id,
        city=current_city,
        apn=current_apn,
        row_offset=processed_count,
        phase="vpt_scan",
    )
```

Also update the job's current position:
```python
worker_state.update_job(
    job_id,
    current_city=current_city,
    current_apn=current_apn,
    processed_count=processed_count,
    hit_count=hit_count,
)
```

### 4. Discovery marking (`scan/find_meas_w_addresses.py` or wherever bills are promoted)

When a bill is upserted/promoted into the `bills` table for the first time, call:

```python
newly_discovered = worker_state.mark_discovery(apn, job_id)
if newly_discovered:
    hit_count += 1
```

`mark_discovery` is idempotent — it only sets `first_seen_at` if it's currently NULL, so calling it on re-scanned properties is safe.

### 5. Resume support (`scan/run_all.py` — `start_scan`)

`api_scan_resume` in `app.py` already calls `run_all.start_scan(city=checkpoint_city)`. The scan just needs to accept an optional `resume_from_apn` parameter and skip APNs before that position in the sorted list. The checkpoint's `row_offset` or `apn` field can be used for this.

## Files to Modify

| File | Change |
|------|--------|
| `scan/run_all.py` | Heartbeat loop at startup; create_job on start_scan; update_job on stop/complete/error |
| `scan/find_meas_w_addresses.py` | Periodic checkpoint writes; mark_discovery on new bill promotion |
| `scan/intake_autopilot.py` | Same job/checkpoint pattern if it runs as a separate job type |

## Out of Scope for This Task

- Enrichment, condition, PG&E, and research jobs — same pattern applies but lower priority. They can follow once the VPT scan is working.
- Automatic heartbeat going offline — currently the heartbeat loop is daemon-threaded and just stops when the process exits. A graceful shutdown hook that calls `worker_state.update_job(job_id, status="interrupted")` and sets the worker status to "offline" would be nice but is not required for basic functionality.

## Acceptance Criteria

After this work:
1. Starting the Flask worker sets the `scanner_workers` row to "online" (visible in Supabase)
2. Starting a scan creates a `scanner_jobs` row with status="running"
3. While scanning, `current_city` and `current_apn` update live in the DB
4. Stopping a scan marks it "interrupted" with last checkpoint preserved
5. Resuming from the admin UI continues from the checkpointed city
6. New properties discovered for the first time have `first_seen_at` set and appear in the DiscoveriesPanel

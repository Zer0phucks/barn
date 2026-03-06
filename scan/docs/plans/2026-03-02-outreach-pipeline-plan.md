# Outreach Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a full outreach pipeline to BARN-scan that scores properties for outreach readiness, generates AI-personalized pitches for the BARN caretaker program, tracks pipeline stages, and integrates with OpenClaw for automated email outreach and reply handling.

**Architecture:** BARN-scan (Flask + Supabase) handles scoring, pipeline tracking, pitch generation, and the outreach UI. OpenClaw (separate Gateway process) handles email sending via SMTP, reply detection via IMAP, and AI-powered conversational responses. The two systems communicate via webhooks and a shared Supabase database.

**Tech Stack:** Python 3.10+, Flask, Supabase (Postgres), Google Gemini (pitch generation), OpenClaw (Node.js Gateway), SMTP/IMAP (email)

**Design Doc:** `docs/plans/2026-03-02-outreach-pipeline-design.md`

---

## Phase 1: Database Foundation

### Task 1: Create outreach tables migration

**Files:**
- Create: `db_migrations/supa_migration_add_outreach.sql`

**Step 1: Write the migration SQL**

```sql
-- Outreach pipeline tables for BARN-scan
-- Run this against Supabase SQL Editor

-- 1. Outreach tracking table (one row per APN)
CREATE TABLE IF NOT EXISTS outreach (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    apn TEXT NOT NULL UNIQUE REFERENCES bills(apn),
    stage TEXT NOT NULL DEFAULT 'identified',
    outreach_score REAL DEFAULT 0,
    pitch_subject TEXT,
    pitch_draft TEXT,
    contacted_at TIMESTAMPTZ,
    last_response_at TIMESTAMPTZ,
    next_followup_at TIMESTAMPTZ,
    followup_count INTEGER DEFAULT 0,
    notes TEXT,
    openclaw_session_id TEXT,
    owner_group_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_apn ON outreach(apn);
CREATE INDEX IF NOT EXISTS idx_outreach_stage ON outreach(stage);
CREATE INDEX IF NOT EXISTS idx_outreach_score ON outreach(outreach_score DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_owner_group ON outreach(owner_group_id);

-- 2. Outreach messages log
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    apn TEXT NOT NULL REFERENCES bills(apn),
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel TEXT NOT NULL DEFAULT 'email' CHECK (channel IN ('email', 'whatsapp', 'phone', 'in_person')),
    subject TEXT,
    content TEXT,
    from_address TEXT,
    to_address TEXT,
    sent_at TIMESTAMPTZ DEFAULT now(),
    openclaw_message_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_outreach_messages_apn ON outreach_messages(apn);
CREATE INDEX IF NOT EXISTS idx_outreach_messages_sent ON outreach_messages(sent_at DESC);

-- 3. Add outreach_score column to bills for fast filtering
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'outreach_score'
    ) THEN
        ALTER TABLE bills ADD COLUMN outreach_score REAL DEFAULT 0;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'contact_completeness'
    ) THEN
        ALTER TABLE bills ADD COLUMN contact_completeness REAL DEFAULT 0;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'outreach_stage'
    ) THEN
        ALTER TABLE bills ADD COLUMN outreach_stage TEXT DEFAULT 'identified';
    END IF;
END $$;

-- 4. Outreach settings (key-value store for SMTP config, thresholds, etc.)
CREATE TABLE IF NOT EXISTS outreach_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Step 2: Apply the migration**

Run the SQL in Supabase SQL Editor (Dashboard → SQL Editor → New Query → Paste → Run).

**Step 3: Commit**

```bash
git add db_migrations/supa_migration_add_outreach.sql
git commit -m "feat: add outreach pipeline database migration"
```

---

### Task 2: Add outreach database functions to db.py

**Files:**
- Modify: `db.py` (append after existing functions, ~line 1229)
- Modify: `webgui/db_impl.py` (mirror the same functions)

**Step 1: Add outreach scoring function**

Add to `db.py` after the last function:

```python
# ---------------------------------------------------------------------------
# Outreach Pipeline
# ---------------------------------------------------------------------------

OUTREACH_STAGES = [
    "identified", "qualified", "outreach_ready", "contacted",
    "responding", "negotiating", "partnered", "declined", "no_response",
]


def calculate_outreach_score(bill: dict) -> float:
    """Calculate outreach readiness score (0-100) for a property."""
    score = 0.0
    has_email = bool(bill.get("owner_email"))

    # Has owner email (25 pts) -- required for email outreach
    if has_email:
        score += 25.0

    # VPT status (20 pts)
    if bill.get("has_vpt"):
        score += 20.0

    # Delinquent (15 pts)
    if bill.get("delinquent"):
        score += 15.0

    # Power off (15 pts)
    if bill.get("power_status") == "off":
        score += 15.0

    # Poor condition (10 pts)
    cond = bill.get("condition_score")
    if cond is not None and cond < 5.0:
        score += 10.0

    # Out-of-state owner (10 pts)
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        import json
        try:
            row_json = json.loads(row_json)
        except (json.JSONDecodeError, TypeError):
            row_json = {}
    mail_state = (row_json.get("MailState") or "").upper()
    if mail_state and mail_state != "CA":
        score += 10.0

    # Research completed (5 pts)
    if bill.get("research_status") == "completed":
        score += 5.0

    # Cap at 30 if no email
    if not has_email:
        score = min(score, 30.0)

    return round(score, 1)


def calculate_contact_completeness(bill: dict) -> float:
    """Calculate contact data completeness (0-100%)."""
    score = 0.0
    if bill.get("owner_email"):
        score += 40.0
    if bill.get("owner_phone") or bill.get("owner_mobile_phone"):
        score += 20.0
    # Check mailing address from parcel data
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        import json
        try:
            row_json = json.loads(row_json)
        except (json.JSONDecodeError, TypeError):
            row_json = {}
    if row_json.get("MailAddress"):
        score += 20.0
    if bill.get("primary_resident_name"):
        score += 20.0
    return round(score, 1)


def determine_outreach_stage(bill: dict, outreach: dict | None = None) -> str:
    """Determine the current outreach stage for a property."""
    if outreach:
        # If manually set to terminal stages, respect that
        if outreach.get("stage") in ("partnered", "declined", "no_response"):
            return outreach["stage"]
        if outreach.get("stage") == "negotiating":
            return "negotiating"
        if outreach.get("last_response_at"):
            return "responding"
        if outreach.get("contacted_at"):
            return "contacted"

    score = calculate_outreach_score(bill)
    has_email = bool(bill.get("owner_email"))
    has_research = bill.get("research_status") == "completed"

    if has_email and has_research and score >= 50:
        return "outreach_ready"
    if score >= 50:
        return "qualified"
    return "identified"


def upsert_outreach(apn: str, **kwargs) -> None:
    """Create or update an outreach record for a property."""
    payload = {"apn": apn, "updated_at": "now()"}
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    get_client().table("outreach").upsert(payload, on_conflict="apn").execute()


def get_outreach(apn: str) -> dict | None:
    """Get outreach record for a property."""
    resp = get_client().table("outreach").select("*").eq("apn", apn).execute()
    rows = resp.data or []
    return rows[0] if rows else None


def get_outreach_messages(apn: str, limit: int = 50) -> list[dict]:
    """Get outreach messages for a property, newest first."""
    resp = (
        get_client()
        .table("outreach_messages")
        .select("*")
        .eq("apn", apn)
        .order("sent_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def insert_outreach_message(
    apn: str,
    direction: str,
    content: str,
    channel: str = "email",
    subject: str | None = None,
    from_address: str | None = None,
    to_address: str | None = None,
    openclaw_message_id: str | None = None,
) -> None:
    """Log an outreach message."""
    payload = {
        "apn": apn,
        "direction": direction,
        "channel": channel,
        "content": content,
    }
    if subject:
        payload["subject"] = subject
    if from_address:
        payload["from_address"] = from_address
    if to_address:
        payload["to_address"] = to_address
    if openclaw_message_id:
        payload["openclaw_message_id"] = openclaw_message_id
    get_client().table("outreach_messages").insert(payload).execute()


def get_outreach_pipeline_counts() -> dict[str, int]:
    """Get count of properties at each pipeline stage."""
    counts = {}
    for stage in OUTREACH_STAGES:
        resp = (
            get_client()
            .table("outreach")
            .select("id", count="exact")
            .eq("stage", stage)
            .execute()
        )
        counts[stage] = resp.count or 0
    return counts


def get_outreach_list(
    stage: str | None = None,
    min_score: float | None = None,
    city: str | None = None,
    sort: str = "outreach_score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get filtered list of outreach records joined with bill data."""
    query = (
        get_client()
        .table("outreach")
        .select("*, bills!inner(location_of_property, city, owner_email, has_vpt, delinquent, power_status, condition_score, primary_resident_name, research_status)", count="exact")
    )
    if stage:
        query = query.eq("stage", stage)
    if min_score is not None:
        query = query.gte("outreach_score", min_score)
    if city:
        query = query.eq("bills.city", city)

    desc = order.lower() == "desc"
    query = query.order(sort, desc=desc).range(offset, offset + limit - 1)

    resp = query.execute()
    return resp.data or [], resp.count or 0


def update_outreach_stage(apn: str, stage: str, **kwargs) -> None:
    """Update the pipeline stage for a property."""
    if stage not in OUTREACH_STAGES:
        raise ValueError(f"Invalid stage: {stage}. Must be one of {OUTREACH_STAGES}")
    payload = {"stage": stage, "updated_at": "now()"}
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    get_client().table("outreach").update(payload).eq("apn", apn).execute()


def recalculate_outreach_scores(apns: list[str] | None = None) -> int:
    """Recalculate outreach scores for given APNs (or all). Returns count updated."""
    if apns:
        resp = get_client().table("bills").select("*").in_("apn", apns).execute()
    else:
        resp = get_client().table("bills").select("*").execute()

    bills = resp.data or []
    updated = 0
    for bill in bills:
        score = calculate_outreach_score(bill)
        completeness = calculate_contact_completeness(bill)
        stage = determine_outreach_stage(bill, get_outreach(bill["apn"]))

        # Update bills table
        get_client().table("bills").update({
            "outreach_score": score,
            "contact_completeness": completeness,
            "outreach_stage": stage,
        }).eq("apn", bill["apn"]).execute()

        # Upsert outreach record
        upsert_outreach(bill["apn"], outreach_score=score, stage=stage)
        updated += 1

    return updated


def get_outreach_setting(key: str, default: str = "") -> str:
    """Get an outreach setting value."""
    resp = get_client().table("outreach_settings").select("value").eq("key", key).execute()
    rows = resp.data or []
    return rows[0]["value"] if rows else default


def set_outreach_setting(key: str, value: str) -> None:
    """Set an outreach setting value."""
    get_client().table("outreach_settings").upsert(
        {"key": key, "value": value, "updated_at": "now()"},
        on_conflict="key",
    ).execute()
```

**Step 2: Mirror functions in webgui/db_impl.py**

Copy the same functions to `webgui/db_impl.py` (this file mirrors `db.py` for the web UI module).

**Step 3: Commit**

```bash
git add db.py webgui/db_impl.py
git commit -m "feat: add outreach pipeline database functions"
```

---

## Phase 2: Outreach Scoring Engine

### Task 3: Create the outreach scoring scanner

**Files:**
- Create: `outreach_scorer.py` (root level)
- Create: `scanner/outreach_scorer.py` (proxy)

**Step 1: Write the scoring scanner**

Create `outreach_scorer.py`:

```python
"""Outreach scoring engine -- calculates outreach readiness scores for all properties."""
from __future__ import annotations

import logging
import threading
from typing import Any

import db

logger = logging.getLogger(__name__)

scorer_state: dict[str, Any] = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "failed": 0,
}


def get_scorer_state() -> dict[str, Any]:
    return {
        "is_running": scorer_state["is_running"],
        "total": scorer_state["total"],
        "completed": scorer_state["completed"],
        "failed": scorer_state["failed"],
    }


def _run_scoring(apns: list[str] | None = None) -> None:
    """Score properties. If apns is None, score all."""
    global scorer_state
    try:
        if apns:
            resp = db.get_client().table("bills").select("*").in_("apn", apns).execute()
        else:
            resp = db.get_client().table("bills").select("*").execute()

        bills = resp.data or []
        scorer_state["total"] = len(bills)
        scorer_state["completed"] = 0
        scorer_state["failed"] = 0

        for bill in bills:
            try:
                apn = bill["apn"]
                score = db.calculate_outreach_score(bill)
                completeness = db.calculate_contact_completeness(bill)
                outreach = db.get_outreach(apn)
                stage = db.determine_outreach_stage(bill, outreach)

                db.get_client().table("bills").update({
                    "outreach_score": score,
                    "contact_completeness": completeness,
                    "outreach_stage": stage,
                }).eq("apn", apn).execute()

                db.upsert_outreach(apn, outreach_score=score, stage=stage)
                scorer_state["completed"] += 1

            except Exception:
                logger.exception("Failed to score APN %s", bill.get("apn"))
                scorer_state["failed"] += 1

    except Exception:
        logger.exception("Scoring run failed")
    finally:
        scorer_state["is_running"] = False


def start_scoring(apns: list[str] | None = None) -> bool:
    """Start the scoring engine in a background thread."""
    global scorer_state
    if scorer_state["is_running"]:
        return False
    scorer_state["is_running"] = True
    thread = threading.Thread(target=_run_scoring, args=(apns,), daemon=True)
    thread.start()
    return True
```

**Step 2: Create the proxy module**

Create `scanner/outreach_scorer.py`:

```python
"""Proxy for root-level outreach_scorer module."""
import outreach_scorer as _impl

scorer_state = _impl.scorer_state
get_scorer_state = _impl.get_scorer_state
start_scoring = _impl.start_scoring
```

**Step 3: Commit**

```bash
git add outreach_scorer.py scanner/outreach_scorer.py
git commit -m "feat: add outreach readiness scoring engine"
```

---

## Phase 3: AI Pitch Generation

### Task 4: Create the pitch generator

**Files:**
- Create: `pitch_generator.py` (root level)

**Step 1: Write the pitch generator**

```python
"""AI pitch generator -- creates personalized outreach emails using Gemini."""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import db

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

pitch_state: dict[str, Any] = {
    "is_running": False,
    "queue": [],
    "completed": 0,
    "failed": 0,
    "current_apn": None,
}


def get_pitch_state() -> dict[str, Any]:
    return {
        "is_running": pitch_state["is_running"],
        "queue_length": len(pitch_state["queue"]),
        "completed": pitch_state["completed"],
        "failed": pitch_state["failed"],
        "current_apn": pitch_state["current_apn"],
        "api_configured": bool(GOOGLE_API_KEY),
    }


PITCH_SYSTEM_PROMPT = """You are a professional outreach writer for BARN Housing (Bay Area Renewal Network), a nonprofit in Alameda County, CA.

BARN operates a Caretaker Program for vacant properties. Here's how it works:
- Property owners grant BARN access to their vacant property
- BARN rehabs and maintains the property
- BARN places a caretaker (a person experiencing homelessness who needs housing) to watch over the property
- The owner SAVES MONEY by no longer paying the Vacant Property Tax (VPT) -- because the property is no longer vacant
- The owner can write off the fair market value of the rent as a CHARITABLE DONATION for tax purposes
- Since caretakers are there for work (not as tenants), owners avoid tenant/eviction complications
- The owner retains full control and can end the arrangement when ready to rent normally

Your job: Write a personalized first-contact email to a property owner. Be:
- Professional and warm -- this is a nonprofit, not a sales pitch
- Specific about THEIR property and situation (use the details provided)
- Clear about the mutual benefits (they save on VPT, get a tax write-off, property gets maintained)
- Brief -- aim for 150-200 words in the body
- Include a clear call to action (reply to learn more, or schedule a call)

Output format (use these exact headers):
SUBJECT: [subject line]
BODY:
[email body]
"""


def _build_property_context(bill: dict, research_report: str | None = None) -> str:
    """Build context string about a property for the AI."""
    parts = []
    parts.append(f"Property address: {bill.get('location_of_property', 'Unknown')}")
    parts.append(f"City: {bill.get('city', 'Unknown')}")

    if bill.get("has_vpt"):
        parts.append(f"VPT marker: {bill.get('vpt_marker', 'Yes')} -- owner is currently paying Vacant Property Tax")
    if bill.get("delinquent"):
        parts.append("Property taxes are DELINQUENT")
    if bill.get("power_status") == "off":
        parts.append("Power is OFF -- property appears vacant")

    cond = bill.get("condition_score")
    if cond is not None:
        parts.append(f"Property condition score: {cond}/10.0")
        if bill.get("condition_notes"):
            parts.append(f"Condition notes: {bill['condition_notes']}")

    owner_name = bill.get("primary_resident_name") or "Property Owner"
    parts.append(f"Owner name: {owner_name}")

    if bill.get("owner_email"):
        parts.append(f"Owner email: {bill['owner_email']}")

    # Check if out-of-state
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        import json
        try:
            row_json = json.loads(row_json)
        except (json.JSONDecodeError, TypeError):
            row_json = {}
    mail_state = (row_json.get("MailState") or "").upper()
    if mail_state and mail_state != "CA":
        parts.append(f"Owner mailing address is out of state ({mail_state}) -- absentee owner")

    if research_report:
        parts.append(f"\nResearch report summary:\n{research_report[:2000]}")

    return "\n".join(parts)


def generate_pitch(apn: str) -> dict[str, str] | None:
    """Generate a pitch for a single property. Returns {subject, body} or None."""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai not installed")
        return None

    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not set")
        return None

    genai.configure(api_key=GOOGLE_API_KEY)

    # Get property data
    bill = db.get_bill(apn)
    if not bill:
        logger.error("No bill found for APN %s", apn)
        return None

    # Get research report if available
    research_report = None
    report_path = bill.get("research_report_path")
    if report_path and os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                research_report = f.read()
        except Exception:
            pass

    context = _build_property_context(bill, research_report)

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        [PITCH_SYSTEM_PROMPT, f"Generate a first-contact email for this property:\n\n{context}"],
    )

    text = response.text.strip()

    # Parse the response
    subject = ""
    body = ""
    if "SUBJECT:" in text and "BODY:" in text:
        subject_start = text.index("SUBJECT:") + len("SUBJECT:")
        body_start = text.index("BODY:")
        subject = text[subject_start:body_start].strip()
        body = text[body_start + len("BODY:"):].strip()
    else:
        # Fallback: use first line as subject, rest as body
        lines = text.split("\n", 1)
        subject = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else text

    return {"subject": subject, "body": body}


def _process_pitch_queue() -> None:
    """Process the pitch generation queue."""
    global pitch_state
    try:
        while pitch_state["queue"]:
            apn = pitch_state["queue"].pop(0)
            pitch_state["current_apn"] = apn
            try:
                result = generate_pitch(apn)
                if result:
                    db.upsert_outreach(
                        apn,
                        pitch_subject=result["subject"],
                        pitch_draft=result["body"],
                    )
                    # Update stage if appropriate
                    bill = db.get_bill(apn)
                    outreach = db.get_outreach(apn)
                    if outreach and outreach.get("stage") in ("identified", "qualified"):
                        stage = db.determine_outreach_stage(bill, outreach)
                        if stage == "outreach_ready":
                            db.update_outreach_stage(apn, "outreach_ready")
                    pitch_state["completed"] += 1
                else:
                    pitch_state["failed"] += 1
            except Exception:
                logger.exception("Failed to generate pitch for APN %s", apn)
                pitch_state["failed"] += 1
    finally:
        pitch_state["is_running"] = False
        pitch_state["current_apn"] = None


def start_pitch_generation(apns: list[str]) -> bool:
    """Start generating pitches for the given APNs."""
    global pitch_state
    if pitch_state["is_running"]:
        pitch_state["queue"].extend(apns)
        return True
    pitch_state["is_running"] = True
    pitch_state["queue"] = list(apns)
    pitch_state["completed"] = 0
    pitch_state["failed"] = 0
    thread = threading.Thread(target=_process_pitch_queue, daemon=True)
    thread.start()
    return True
```

**Step 2: Create proxy module**

Create `scanner/pitch_generator.py`:

```python
"""Proxy for root-level pitch_generator module."""
import pitch_generator as _impl

pitch_state = _impl.pitch_state
get_pitch_state = _impl.get_pitch_state
generate_pitch = _impl.generate_pitch
start_pitch_generation = _impl.start_pitch_generation
```

**Step 3: Commit**

```bash
git add pitch_generator.py scanner/pitch_generator.py
git commit -m "feat: add AI pitch generator for caretaker program outreach"
```

---

## Phase 4: Outreach API Routes

### Task 5: Add outreach API endpoints to Flask app

**Files:**
- Modify: `webgui/app.py` (add routes after existing API routes)

**Step 1: Add outreach API routes**

Add these routes to `webgui/app.py` after the existing scout API routes (around line 1750):

```python
# ---------------------------------------------------------------------------
# Outreach Pipeline API
# ---------------------------------------------------------------------------

@app.route("/outreach")
@login_required
def outreach():
    return render_template("outreach.html")


@app.route("/api/outreach/pipeline", methods=["GET"])
@login_required
def api_outreach_pipeline():
    """Get pipeline stage counts."""
    try:
        counts = db.get_outreach_pipeline_counts()
        return jsonify({"success": True, "data": counts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/list", methods=["GET"])
@login_required
def api_outreach_list():
    """Get filtered outreach list."""
    stage = request.args.get("stage")
    min_score = request.args.get("min_score", type=float)
    city = request.args.get("city")
    sort = request.args.get("sort", "outreach_score")
    order = request.args.get("order", "desc")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    try:
        rows, total = db.get_outreach_list(
            stage=stage, min_score=min_score, city=city,
            sort=sort, order=order, limit=limit, offset=offset,
        )
        return jsonify({"success": True, "data": rows, "total": total})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/score", methods=["POST"])
@login_required
def api_outreach_score():
    """Recalculate outreach scores."""
    data = request.get_json(silent=True) or {}
    apns = data.get("apns")  # None = score all

    try:
        import outreach_scorer
        started = outreach_scorer.start_scoring(apns)
        if started:
            return jsonify({"status": "ok", "message": "Scoring started"})
        else:
            return jsonify({"status": "error", "message": "Scoring already running"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/outreach/score/status", methods=["GET"])
@login_required
def api_outreach_score_status():
    """Get scoring engine status."""
    try:
        import outreach_scorer
        return jsonify(outreach_scorer.get_scorer_state())
    except Exception as e:
        return jsonify({"is_running": False, "error": str(e)})


@app.route("/api/outreach/pitch/generate", methods=["POST"])
@login_required
def api_outreach_pitch_generate():
    """Generate AI pitch drafts for given APNs."""
    data = request.get_json(silent=True) or {}
    apns = data.get("apns", [])
    if not apns:
        return jsonify({"success": False, "error": "No APNs provided"}), 400

    try:
        import pitch_generator
        started = pitch_generator.start_pitch_generation(apns)
        if started:
            return jsonify({"status": "ok", "message": f"Generating pitches for {len(apns)} properties"})
        else:
            return jsonify({"status": "error", "message": "Already running, APNs queued"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/outreach/pitch/status", methods=["GET"])
@login_required
def api_outreach_pitch_status():
    """Get pitch generation status."""
    try:
        import pitch_generator
        return jsonify(pitch_generator.get_pitch_state())
    except Exception as e:
        return jsonify({"is_running": False, "error": str(e)})


@app.route("/api/outreach/<apn>", methods=["GET"])
@login_required
def api_outreach_detail(apn):
    """Get outreach detail for a property."""
    try:
        outreach = db.get_outreach(apn)
        messages = db.get_outreach_messages(apn)
        return jsonify({"success": True, "outreach": outreach, "messages": messages})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/stage", methods=["POST"])
@login_required
def api_outreach_update_stage(apn):
    """Update pipeline stage for a property."""
    data = request.get_json(silent=True) or {}
    stage = data.get("stage")
    if not stage:
        return jsonify({"success": False, "error": "stage required"}), 400

    try:
        notes = data.get("notes")
        db.update_outreach_stage(apn, stage, notes=notes)
        return jsonify({"success": True, "stage": stage})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/pitch", methods=["PUT"])
@login_required
def api_outreach_update_pitch(apn):
    """Update/edit the pitch draft for a property."""
    data = request.get_json(silent=True) or {}
    subject = data.get("subject")
    body = data.get("body")

    try:
        db.upsert_outreach(apn, pitch_subject=subject, pitch_draft=body)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/<apn>/send", methods=["POST"])
@login_required
def api_outreach_send(apn):
    """Send outreach email for a property via OpenClaw webhook."""
    try:
        outreach = db.get_outreach(apn)
        if not outreach:
            return jsonify({"success": False, "error": "No outreach record found"}), 404
        if not outreach.get("pitch_draft"):
            return jsonify({"success": False, "error": "No pitch draft generated"}), 400

        bill = db.get_bill(apn)
        if not bill or not bill.get("owner_email"):
            return jsonify({"success": False, "error": "No owner email available"}), 400

        # Send via OpenClaw webhook
        openclaw_url = db.get_outreach_setting("openclaw_gateway_url")
        if not openclaw_url:
            return jsonify({"success": False, "error": "OpenClaw Gateway URL not configured"}), 400

        import urllib.request
        import json

        webhook_payload = json.dumps({
            "action": "send_outreach",
            "apn": apn,
            "to_email": bill["owner_email"],
            "subject": outreach.get("pitch_subject", "BARN Housing Caretaker Program"),
            "body": outreach["pitch_draft"],
            "owner_name": bill.get("primary_resident_name", "Property Owner"),
            "property_address": bill.get("location_of_property", ""),
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{openclaw_url.rstrip('/')}/api/webhook/barn-outreach",
            data=webhook_payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": db.get_outreach_setting("openclaw_webhook_secret", ""),
            },
        )
        urllib.request.urlopen(req, timeout=10)

        # Log the message and update stage
        from_addr = db.get_outreach_setting("smtp_from_address", "outreach@barnhousing.org")
        db.insert_outreach_message(
            apn=apn,
            direction="outbound",
            channel="email",
            subject=outreach.get("pitch_subject"),
            content=outreach["pitch_draft"],
            from_address=from_addr,
            to_address=bill["owner_email"],
        )
        db.update_outreach_stage(apn, "contacted", contacted_at="now()")

        return jsonify({"success": True, "message": "Email sent"})

    except Exception as e:
        logger.exception("Failed to send outreach for APN %s", apn)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/settings", methods=["GET"])
@login_required
def api_outreach_settings_get():
    """Get all outreach settings."""
    try:
        resp = db.get_client().table("outreach_settings").select("*").execute()
        settings = {row["key"]: row["value"] for row in (resp.data or [])}
        return jsonify({"success": True, "data": settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/settings", methods=["POST"])
@login_required
def api_outreach_settings_save():
    """Save outreach settings."""
    data = request.get_json(silent=True) or {}
    try:
        for key, value in data.items():
            db.set_outreach_setting(key, str(value))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/outreach/webhook/reply", methods=["POST"])
def api_outreach_webhook_reply():
    """Webhook endpoint for OpenClaw to report incoming replies."""
    # Verify webhook secret
    secret = request.headers.get("X-Webhook-Secret", "")
    expected = db.get_outreach_setting("openclaw_webhook_secret", "")
    if expected and secret != expected:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    apn = data.get("apn")
    if not apn:
        return jsonify({"error": "apn required"}), 400

    try:
        # Log the inbound message
        db.insert_outreach_message(
            apn=apn,
            direction="inbound",
            channel=data.get("channel", "email"),
            content=data.get("content", ""),
            subject=data.get("subject"),
            from_address=data.get("from_address"),
            to_address=data.get("to_address"),
            openclaw_message_id=data.get("openclaw_message_id"),
        )

        # Update stage
        new_stage = data.get("new_stage")
        if new_stage and new_stage in db.OUTREACH_STAGES:
            db.update_outreach_stage(apn, new_stage, last_response_at="now()")
        else:
            db.update_outreach_stage(apn, "responding", last_response_at="now()")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

**Step 2: Commit**

```bash
git add webgui/app.py
git commit -m "feat: add outreach pipeline API routes"
```

---

## Phase 5: Outreach Web UI

### Task 6: Create the outreach page template

**Files:**
- Create: `webgui/templates/outreach.html`

This is the largest single task. The template follows the same pattern as existing pages: standalone HTML doc with inline CSS and JS, data loaded via fetch() from API endpoints.

Key sections:
- **Pipeline funnel** -- colored bars showing count at each stage
- **Filterable table** -- properties with outreach data, sortable columns
- **Quick actions** -- Generate Pitches, Score All, Send buttons
- **Settings modal** -- SMTP config, OpenClaw URL, thresholds

The template should be written following the exact patterns from `admin.html` (dark header, client-side API loading, inline CSS/JS). Refer to `webgui/templates/admin.html` for structure.

**Step 1: Create the outreach template**

Write `webgui/templates/outreach.html` (full standalone HTML page with ~500-700 lines of inline CSS + JS).

**Step 2: Add nav link to other pages**

Add "Outreach" link to the nav bars in:
- `webgui/templates/index.html` -- add after the "My Lists" link
- `webgui/templates/admin.html` -- add to header links
- `webgui/templates/property.html` -- add to link buttons

**Step 3: Add outreach section to property detail page**

Modify `webgui/templates/property.html` to add an "Outreach" section showing:
- Current pipeline stage (with stage change dropdown)
- Outreach readiness score breakdown
- Pitch draft (editable textarea)
- "Generate Pitch" and "Send Outreach" buttons
- Communication history timeline

**Step 4: Commit**

```bash
git add webgui/templates/outreach.html webgui/templates/index.html webgui/templates/admin.html webgui/templates/property.html
git commit -m "feat: add outreach pipeline web UI"
```

---

## Phase 6: OpenClaw Integration

### Task 7: Create the OpenClaw outreach skill

**Files:**
- Create: `openclaw/barn-outreach-skill/SKILL.md`
- Create: `openclaw/setup-guide.md`

**Step 1: Write the BARN outreach skill for OpenClaw**

Create `openclaw/barn-outreach-skill/SKILL.md`:

```markdown
---
name: barn-outreach
description: Use when handling outreach emails for the BARN Housing caretaker program
---

# BARN Housing Outreach Agent

You are the outreach agent for BARN Housing (Bay Area Renewal Network), a nonprofit in Alameda County, CA.

## The Caretaker Program

BARN operates a Caretaker Program that benefits both property owners and people experiencing homelessness:

### How It Works
1. Property owner grants BARN access to their vacant property
2. BARN rehabs and maintains the property at no cost to the owner
3. BARN places a caretaker (someone experiencing homelessness) to watch over the property
4. The caretaker lives on-site as part of their work arrangement

### Benefits for Property Owners
- **Save on Vacant Property Tax (VPT)**: Property is no longer vacant, so VPT no longer applies
- **Tax write-off**: Fair market value of rent can be written off as a charitable donation to BARN
- **Property maintenance**: BARN handles upkeep and rehabilitation
- **No tenant complications**: Caretakers are workers, not tenants. No lease, no eviction process needed
- **Owner retains control**: Can end the arrangement when ready to rent or sell

### Common Questions and Answers

**Q: Is the caretaker a tenant?**
A: No. Caretakers are workers with BARN, not tenants. They have a work arrangement, not a lease. If the owner wants to use the property, the caretaker is reassigned by BARN.

**Q: What about liability?**
A: BARN carries insurance. The caretaker program operates under BARN's organizational umbrella.

**Q: How long does it last?**
A: Flexible. Some arrangements are 6 months, some ongoing. The owner decides.

**Q: What condition is the property left in?**
A: Better than when we started. BARN invests in rehabilitation and the caretaker maintains the property.

**Q: What does it cost me?**
A: Nothing. BARN covers rehab and maintenance. You actually save money (no VPT) and gain a tax deduction.

## Your Role

When sending outreach emails or responding to property owner replies:

1. **Be professional and warm** -- you represent a nonprofit, not a corporation
2. **Be specific** -- reference their property address, VPT status, and situation
3. **Be honest** -- don't oversell. If you don't know something, say so and offer to connect them with a BARN team member
4. **Respect boundaries** -- if someone says no or asks you to stop, immediately comply and update their status to "declined"
5. **Escalate when appropriate** -- complex legal questions, specific dollar amounts, or angry/hostile responses should be escalated to a human

## Escalation Rules

Escalate to human (send notification) when:
- Owner asks about specific legal liability details
- Owner is hostile or threatening
- Owner asks to speak to a person
- Owner has questions about specific dollar amounts or tax implications
- Owner expresses interest and wants to move forward (congratulations -- human takes over)
- Anything you're not confident answering

## Webhook Integration

After handling a reply, report back to BARN-scan:
- POST to the BARN-scan webhook URL with: apn, content, new_stage, channel
- Stage updates: "responding" for general replies, "negotiating" if interested, "declined" if they say no
```

**Step 2: Write the OpenClaw setup guide**

Create `openclaw/setup-guide.md` documenting:
- How to install OpenClaw (`npm install -g openclaw@latest`)
- How to configure SMTP channel for outbound email
- How to configure IMAP for reply detection
- How to install the barn-outreach skill
- How to configure the webhook connection to BARN-scan
- SMTP/IMAP environment variables needed

**Step 3: Commit**

```bash
git add openclaw/
git commit -m "feat: add OpenClaw outreach skill and setup guide"
```

---

## Phase 7: Data Quality & Polish

### Task 8: Wire up auto-scoring after scans complete

**Files:**
- Modify: `contact_scanner.py` (trigger re-score after contact scan finishes)
- Modify: `gemini_research_scanner.py` (trigger re-score after research completes)
- Modify: `condition_scanner.py` (trigger re-score after condition scan)

**Step 1: Add score recalculation hooks**

In each scanner's main processing function, after successfully updating a bill, add:

```python
# After updating bill data, recalculate outreach score
try:
    import db
    bill = db.get_bill(apn)
    if bill:
        score = db.calculate_outreach_score(bill)
        completeness = db.calculate_contact_completeness(bill)
        outreach = db.get_outreach(apn)
        stage = db.determine_outreach_stage(bill, outreach)
        db.get_client().table("bills").update({
            "outreach_score": score,
            "contact_completeness": completeness,
            "outreach_stage": stage,
        }).eq("apn", apn).execute()
        db.upsert_outreach(apn, outreach_score=score, stage=stage)
except Exception:
    logger.debug("Failed to update outreach score for %s", apn, exc_info=True)
```

**Step 2: Commit**

```bash
git add contact_scanner.py gemini_research_scanner.py condition_scanner.py
git commit -m "feat: auto-recalculate outreach scores after scans"
```

---

### Task 9: Add outreach columns to existing list view filters

**Files:**
- Modify: `webgui/app.py` (add outreach_score and outreach_stage to the bills query/filtering)
- Modify: `webgui/templates/index.html` (add outreach score column and filter)

**Step 1: Add outreach_score to the property list display**

In `webgui/templates/index.html`, add a new column showing the outreach score with a colored badge (green for 70+, yellow for 50-69, red for <50).

**Step 2: Add outreach stage filter**

Add a dropdown filter for outreach_stage alongside the existing filters (power, VPT, delinquent, etc.).

**Step 3: Commit**

```bash
git add webgui/app.py webgui/templates/index.html
git commit -m "feat: add outreach score column and stage filter to property list"
```

---

## Execution Order Summary

| Phase | Task | Description | Dependencies |
|-------|------|-------------|--------------|
| 1 | 1 | Database migration SQL | None |
| 1 | 2 | Database functions in db.py | Task 1 (migration applied) |
| 2 | 3 | Outreach scoring scanner | Task 2 |
| 3 | 4 | AI pitch generator | Task 2 |
| 4 | 5 | Flask API routes | Tasks 2, 3, 4 |
| 5 | 6 | Outreach web UI template | Task 5 |
| 6 | 7 | OpenClaw skill + setup guide | Task 5 |
| 7 | 8 | Auto-scoring hooks in scanners | Task 2 |
| 7 | 9 | Outreach columns in list view | Task 2 |

Tasks 3, 4 can run in parallel. Tasks 8, 9 can run in parallel. Task 7 is independent of tasks 8, 9.

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

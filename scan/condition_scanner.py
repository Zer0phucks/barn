#!/usr/bin/env python3
"""
Property Condition Scanner - Uses Google Gemini vision to analyze Street View
images and rate properties on a 1.0-10.0 scale based on their visual condition.
"""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("Warning: google-genai not installed. Run: pip install google-genai")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests not installed. Run: pip install requests")

# Load environment variables from the correct path
BASE_DIR = Path(__file__).resolve().parent
STREETVIEW_DIR = BASE_DIR / "streetview_images"
ENV_FILE = BASE_DIR / ".env"

# Load .env file explicitly from BASE_DIR
if ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        # Manual loading if dotenv not available
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = value.strip('"').strip("'")

# Ensure directories exist
STREETVIEW_DIR.mkdir(exist_ok=True)

# Configuration - read API key AFTER loading .env
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# Scanner state
condition_state = {
    "is_running": False,
    "current_apn": None,
    "queue": [],
    "completed": 0,
    "failed": 0,
}


def ensure_condition_columns() -> None:
    """No-op: Supabase bills table already has condition columns."""
    pass


def web_mercator_to_latlng(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (EPSG:3857) to WGS84 lat/lng."""
    lng = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return lat, lng


def get_property_coords(apn: str) -> tuple[float, float] | None:
    """Get lat/lng coordinates for a property."""
    import db
    row = db.get_bill_with_parcel(apn)
    if not row or not row.get("row_json"):
        return None
    try:
        parcel = json.loads(row["row_json"]) if isinstance(row["row_json"], str) else row["row_json"]
        x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or 0)
        y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or 0)
        if x and y:
            return web_mercator_to_latlng(x, y)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


def fetch_streetview_image(lat: float, lng: float, apn: str) -> Path | None:
    """Fetch satellite map image for coordinates using Google Maps Static API."""
    if not REQUESTS_AVAILABLE:
        print("  requests library not available")
        return None

    if not GOOGLE_API_KEY:
        print("  No API key configured")
        return None

    # Google Maps Static API — hybrid satellite view (satellite + road/label overlay)
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lng}"
        f"&zoom=19"
        f"&size=640x480"
        f"&maptype=hybrid"
        f"&markers=color:red%7C{lat},{lng}"
        f"&key={GOOGLE_API_KEY}"
    )

    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "image" in content_type and len(response.content) > 1000:
                safe_apn = apn.replace("/", "_").replace("\\", "_")
                image_path = STREETVIEW_DIR / f"{safe_apn}.jpg"

                with open(image_path, "wb") as f:
                    f.write(response.content)

                return image_path
            else:
                print(f"  Image too small ({len(response.content)} bytes), likely an error response")
        else:
            print(f"  Maps Static API returned status {response.status_code}")
    except Exception as e:
        print(f"  Error fetching map image: {e}")

    return None


def update_condition(apn: str, score: float, notes: str, image_path: str | None = None) -> None:
    """Update condition data for a property."""
    import db
    now = datetime.now().isoformat()
    db.update_bill_condition(apn, score, notes, condition_updated_at=now, streetview_image_path=str(image_path) if image_path else None)


async def analyze_property_condition(apn: str) -> tuple[bool, float, str, Path | None]:
    """
    Analyze property condition using Gemini vision.
    Returns (success, score, notes, image_path).
    """
    if not GENAI_AVAILABLE:
        return False, 0, "google-genai package not installed", None
    
    if not GOOGLE_API_KEY:
        return False, 0, "GOOGLE_API_KEY not configured", None
    
    # Get coordinates
    coords = get_property_coords(apn)
    if not coords:
        return False, 0, "Could not get property coordinates", None
    
    lat, lng = coords
    
    # Fetch Street View image (now synchronous)
    image_path = fetch_streetview_image(lat, lng, apn)
    if not image_path or not image_path.exists():
        return False, 0, "Could not fetch Street View image", None
    
    # Read image for Gemini
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        prompt = """Analyze this Street View image of a property and assess its visual condition.

Rate the property on a scale of 1.0 to 10.0 where:
- 1.0-2.0: Excellent condition, well-maintained, pristine
- 3.0-4.0: Good condition, minor wear visible
- 5.0-6.0: Fair condition, noticeably worn but habitable
- 7.0-8.0: Poor condition, significant neglect visible
- 9.0-10.0: Very poor/abandoned, severe deterioration

Look for signs of:
- Overgrown vegetation or dead landscaping
- Damaged or missing roof sections
- Boarded up or broken windows
- Peeling paint or damaged siding
- Debris, junk, or abandoned vehicles
- Structural damage or sagging
- Missing doors or significant damage
- General signs of abandonment

Respond in this exact JSON format:
{
  "score": <number between 1.0 and 10.0>,
  "summary": "<one sentence summary of condition>",
  "observations": ["<observation 1>", "<observation 2>", ...]
}

Be objective and base your assessment only on what is visible in the image."""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                        types.Part.from_text(text=prompt)
                    ]
                )
            ]
        )
        
        if not response or not response.text:
            return False, 0, "Empty response from Gemini", image_path
        
        # Parse JSON response
        text = response.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:].strip()
        
        result = json.loads(text)
        score = float(result.get("score", 5.0))
        score = max(1.0, min(10.0, score))  # Clamp to valid range
        
        summary = result.get("summary", "")
        observations = result.get("observations", [])
        notes = f"{summary}\n\nObservations:\n" + "\n".join(f"• {obs}" for obs in observations)
        
        return True, score, notes, image_path
        
    except json.JSONDecodeError as e:
        return False, 0, f"Failed to parse Gemini response: {e}", image_path
    except Exception as e:
        return False, 0, f"Gemini API error: {str(e)}", image_path


async def process_condition_queue() -> None:
    """Process the condition scan queue."""
    global condition_state
    
    while condition_state["queue"]:
        apn = condition_state["queue"].pop(0)
        condition_state["current_apn"] = apn
        
        print(f"Scanning condition for: {apn}")
        
        success, score, notes, image_path = await analyze_property_condition(apn)
        
        if success:
            update_condition(apn, score, notes, image_path)

            # After updating bill data, recalculate outreach score
            try:
                import db as _db_mod
                _bill = _db_mod.get_bill(apn)
                if _bill:
                    _score = _db_mod.calculate_outreach_score(_bill)
                    _completeness = _db_mod.calculate_contact_completeness(_bill)
                    _outreach = _db_mod.get_outreach(apn)
                    _stage = _db_mod.determine_outreach_stage(_bill, _outreach)
                    _db_mod.get_client().table("bills").update({
                        "outreach_score": _score,
                        "contact_completeness": _completeness,
                        "outreach_stage": _stage,
                    }).eq("apn", apn).execute()
                    _db_mod.upsert_outreach(apn, outreach_score=_score, stage=_stage)
            except Exception:
                pass  # Non-critical: don't break scanner if outreach scoring fails

            condition_state["completed"] += 1
            print(f"  ✓ Score: {score:.1f}")
        else:
            update_condition(apn, 0, notes, image_path)
            condition_state["failed"] += 1
            print(f"  ✗ Failed: {notes}")
        
        await asyncio.sleep(0.5)
    
    condition_state["current_apn"] = None
    condition_state["is_running"] = False


def start_condition_scan(apns: list[str]) -> bool:
    """Start condition scan for a list of APNs."""
    global condition_state
    
    if condition_state["is_running"]:
        condition_state["queue"].extend(apns)
        return True
    
    condition_state["is_running"] = True
    condition_state["queue"] = list(apns)
    condition_state["completed"] = 0
    condition_state["failed"] = 0
    
    import threading
    def run_async():
        asyncio.run(process_condition_queue())
    
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    return True


def get_condition_state() -> dict[str, Any]:
    """Get current condition scanner state."""
    return {
        "is_running": condition_state["is_running"],
        "current_apn": condition_state["current_apn"],
        "queue_length": len(condition_state["queue"]),
        "completed": condition_state["completed"],
        "failed": condition_state["failed"],
        "api_configured": bool(GOOGLE_API_KEY),
    }


def get_condition_score(apn: str) -> dict[str, Any] | None:
    """Get condition data for a property."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT condition_score, condition_notes, condition_updated_at, streetview_image_path
        FROM bills WHERE apn = ?
    """, (apn,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "score": row["condition_score"],
        "notes": row["condition_notes"],
        "updated_at": row["condition_updated_at"],
        "image_path": row["streetview_image_path"],
    }


async def test_single_property(apn: str) -> None:
    """Test condition scan on a single property."""
    ensure_condition_columns()
    
    print(f"Testing condition scan for APN: {apn}")
    print("-" * 50)
    
    success, score, notes, image_path = await analyze_property_condition(apn)
    
    if success:
        update_condition(apn, score, notes, image_path)
        print(f"✓ Condition Score: {score:.1f}/10.0")
        print(f"✓ Image saved: {image_path}")
        print(f"\nNotes:\n{notes}")
    else:
        print(f"✗ Failed: {notes}")


def main() -> None:
    """Run the condition scanner."""
    ensure_condition_columns()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test-single" and len(sys.argv) > 2:
            asyncio.run(test_single_property(sys.argv[2]))
            return
        elif sys.argv[1] == "--help":
            print("Usage: python condition_scanner.py [options]")
            print()
            print("Options:")
            print("  --test-single <APN>  Test condition scan on a single property")
            print("  --help               Show this help message")
            return
    
    print("Property Condition Scanner")
    print("-" * 50)
    print(f"API Key Configured: {'Yes' if GOOGLE_API_KEY else 'No'}")
    print(f"Street View Images: {STREETVIEW_DIR}")
    print()
    print("Use --test-single <APN> to test on a specific property")
    print("Or start condition scan via the web UI at /admin")


if __name__ == "__main__":
    main()

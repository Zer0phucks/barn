#!/usr/bin/env python3
"""
Batch Deceased Owner/Resident Research

Fetches CBC address pages via Playwright (headless Chromium), analyzes them
with Kimi K2.5 (OpenRouter) to count deceased owners/residents, and writes
the `deceased_count` back to the Supabase `bills` table.

Usage:
    source .venv/bin/activate
    python batch_deceased_research.py                   # Both cities
    python batch_deceased_research.py --city OAKLAND     # Oakland only
    python batch_deceased_research.py --city BERKELEY    # Berkeley only
    python batch_deceased_research.py --apn 4-101-26    # Single property
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load .env
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = value.strip('"').strip("'")

import db
from cyber_research_agent import (
    call_openrouter,
    extract_json_block,
    parse_address_to_parts,
    build_cyber_url,
)
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
from gemini_research_scanner import (
    _html_to_text,
    _is_challenge_page,
)
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("ERROR: curl_cffi is required. Install with: pip install curl_cffi")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
DELAY_BETWEEN_PROPERTIES = 4  # seconds


DECEASED_SYSTEM_PROMPT = """You are analyzing a CyberBackgroundChecks.com address page.
Your ONLY task is to count how many people listed at this address appear to be DECEASED.

CyberBackgroundChecks marks deceased people with indicators like:
- "[Deceased]" tag next to a name
- A death date listed
- Obituary references
- "Date of Death" or "DOD" fields

Respond with ONLY a JSON object in this exact format:
{
  "deceased_count": 0,
  "deceased_names": [],
  "notes": "Brief explanation of what you found"
}

Rules:
- deceased_count: integer, how many distinct people are marked as deceased. 0 if none.
- deceased_names: list of names of deceased individuals found. Empty list if none.
- notes: brief explanation.
- Do NOT invent data. Only report what the page content shows.
- If the page content is empty or blocked, set deceased_count to 0 and explain in notes.
"""


def fetch_cbc_fresh(url: str, max_chars: int = 30000) -> str:
    """Fetch a CBC page with curl_cffi using safari15_5 TLS impersonation."""
    if not CURL_CFFI_AVAILABLE:
        print("  ERROR: curl_cffi not available")
        return ""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    for impersonate in ("safari15_5", "chrome120"):
        try:
            r = curl_requests.get(url, impersonate=impersonate, timeout=25, headers=headers)
            if r.status_code != 200:
                continue
            html = r.text or ""
            # CBC pages keep Cloudflare script tags even after passing challenge,
            # so _is_challenge_page false-positives. Instead, check for actual
            # blocking indicators plus minimal content length.
            lowered = html.lower()
            if "just a moment" in lowered and len(html) < 10000:
                continue  # Actual Cloudflare interstitial
            if "verify you are human" in lowered and len(html) < 10000:
                continue  # Actual verification page
            text = _html_to_text(html, max_chars)
            if text and len(text.strip()) > 200:
                return text
        except Exception as e:
            print(f"  curl_cffi ({impersonate}) error: {e}")
            continue
    return ""


def _analyze_with_gemini(page_text: str, address: str) -> dict:
    """Use Gemini Flash to analyze a CBC page for deceased indicators."""
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        return None
    client = genai.Client(api_key=GOOGLE_API_KEY)
    prompt = f"""{DECEASED_SYSTEM_PROMPT}

## Address being researched
{address}

## CyberBackgroundChecks page content
{page_text[:25000]}

Analyze the above content and identify any deceased owners or residents.
Respond with ONLY a JSON object."""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        if response and response.text:
            obj = extract_json_block(response.text)
            if obj and "deceased_count" in obj:
                return obj
    except Exception as e:
        print(f"  Gemini error: {e}")
    return None


def _analyze_with_regex(page_text: str) -> dict:
    """Regex-based fallback: detect 'Deceased' markers in CBC text without AI."""
    # CBC format: "Name Age: Deceased" or "Name Deceased Lives at..."
    # Find names near "Deceased" markers
    deceased_names = []
    # Pattern 1: "Name Age: Deceased" or "Name Age: XX Deceased"
    for m in re.finditer(
        r'(?:VIEW DETAILS\s+)?([A-Z][a-z]+ (?:[A-Z] )?[A-Z][a-z]+)\s+Age:\s*(?:\d+\s+)?Deceased',
        page_text
    ):
        name = m.group(1).strip()
        if name not in deceased_names:
            deceased_names.append(name)

    # Pattern 2: "Name Deceased Lives at" (no age)
    for m in re.finditer(
        r'(?:VIEW DETAILS\s+)?([A-Z][a-z]+ (?:[A-Z] )?[A-Z][a-z]+)\s+Deceased\s+Lives',
        page_text
    ):
        name = m.group(1).strip()
        if name not in deceased_names:
            deceased_names.append(name)

    # Pattern 3: Simple count of "Deceased" occurrences (case-insensitive)
    # as a minimum bound
    raw_count = len(re.findall(r'\bDeceased\b', page_text, re.IGNORECASE))

    # Use the greater of named matches vs raw deceased markers
    count = max(len(deceased_names), 0)
    if raw_count > 0 and count == 0:
        count = raw_count  # At least some deceased markers found

    return {
        "deceased_count": count,
        "deceased_names": deceased_names,
        "notes": f"Regex detection: found {count} deceased marker(s)" if count else "No deceased markers found (regex)"
    }


def analyze_deceased(page_text: str, address: str) -> dict:
    """Analyze a CBC page for deceased indicators. Tries OpenRouter, Gemini, then regex fallback."""
    if not page_text or len(page_text.strip()) < 100:
        return {"deceased_count": 0, "deceased_names": [], "notes": "No content to analyze"}

    # Try OpenRouter (Kimi K2.5) first
    if OPENROUTER_API_KEY:
        user_prompt = f"""## Address being researched
{address}

## CyberBackgroundChecks page content
{page_text[:25000]}

Analyze the above content and identify any deceased owners or residents.
Respond with ONLY a JSON object."""
        messages = [
            {"role": "system", "content": DECEASED_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = call_openrouter(messages, max_tokens=2048)
            obj = extract_json_block(response)
            if obj and "deceased_count" in obj:
                return obj
        except Exception as e:
            print(f"  OpenRouter failed: {e}, trying Gemini...")

    # Fallback 1: Gemini Flash
    result = _analyze_with_gemini(page_text, address)
    if result:
        return result

    # Fallback 2: Regex-based local detection (no API needed)
    print("  Using regex fallback (no AI APIs available)...")
    return _analyze_with_regex(page_text)


def get_property_address_and_url(apn: str) -> tuple[str, str | None]:
    """Get property address and build CBC URL from database."""
    bill = db.get_bill_with_parcel(apn)
    if not bill:
        return "", None

    address = bill.get("location_of_property") or ""
    row_json = bill.get("row_json") or {}
    if isinstance(row_json, str):
        try:
            row_json = json.loads(row_json)
        except json.JSONDecodeError:
            row_json = {}

    situs_city = row_json.get("SitusCity") or bill.get("city") or ""
    situs_zip = row_json.get("SitusZip") or ""

    # Build full address for display
    full_address = address
    if situs_city:
        full_address = f"{address}, {situs_city}"
    if situs_zip:
        full_address += f" {situs_zip}"

    # Build CBC URL: strip city from the street portion
    # address might be "534 HENRY ST, OAKLAND" — remove trailing city
    street = address.split(",")[0].strip()  # Take only the street part before any comma
    if street and situs_zip:
        street_slug = street.replace(" ", "-")
        city_slug = situs_city.replace(" ", "-") if situs_city else ""
        url = f"https://www.cyberbackgroundchecks.com/address/{street_slug}/{city_slug}/{situs_zip}"
    else:
        # Fallback to parse_address_to_parts
        parts = parse_address_to_parts(full_address)
        url = build_cyber_url(parts)

    return full_address, url


def process_single_property(apn: str, verbose: bool = True) -> dict:
    """Process a single property for deceased research. Returns result dict."""
    address, url = get_property_address_and_url(apn)
    if not url:
        if verbose:
            print(f"  ⚠ No CBC URL for {apn} ({address})")
        return {"apn": apn, "deceased_count": 0, "status": "no_url"}

    if verbose:
        print(f"  Fetching: {url}")

    # Fetch with fresh Playwright context (avoids persistent session challenge issues)
    page_text = fetch_cbc_fresh(url, max_chars=30000)

    if not page_text or len(page_text.strip()) < 100:
        if verbose:
            print(f"  ⚠ No content fetched for {apn}")
        return {"apn": apn, "deceased_count": 0, "status": "no_content"}

    if verbose:
        print(f"  Got {len(page_text)} chars, analyzing with Kimi...")

    # Analyze with Kimi
    result = analyze_deceased(page_text, address)
    deceased_count = result.get("deceased_count", 0)
    deceased_names = result.get("deceased_names", [])
    notes = result.get("notes", "")

    # Write to Supabase
    try:
        db.update_bill_fields(apn, {"deceased_count": deceased_count})
    except Exception as e:
        if verbose:
            print(f"  ⚠ DB update failed: {e}")

    if verbose:
        if deceased_count > 0:
            print(f"  ☠ DECEASED: {deceased_count} — {', '.join(deceased_names)}")
        else:
            print(f"  ✓ No deceased found. {notes[:80]}")

    return {
        "apn": apn,
        "address": address,
        "deceased_count": deceased_count,
        "deceased_names": deceased_names,
        "notes": notes,
        "status": "ok",
    }


def load_apns(city: str) -> list[str]:
    """Load APNs from delinquent file for the given city."""
    if city.upper() == "OAKLAND":
        path = BASE_DIR / "delinquent_over_2_years.txt"
    else:
        path = BASE_DIR / f"delinquent_over_2_years_{city.lower()}.txt"
    if not path.exists():
        print(f"File not found: {path}")
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch deceased owner research via CBC + Kimi K2.5")
    parser.add_argument("--city", default="ALL", help="OAKLAND, BERKELEY, or ALL (default: ALL)")
    parser.add_argument("--apn", help="Process a single APN instead of batch")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_PROPERTIES, help="Seconds between properties")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    if not OPENROUTER_API_KEY and not GOOGLE_API_KEY:
        print("WARNING: No AI API keys set. Using regex-only detection (less accurate).")

    verbose = not args.quiet

    if args.apn:
        print(f"Processing single APN: {args.apn}")
        result = process_single_property(args.apn, verbose)
        print(f"\nResult: {json.dumps(result, indent=2)}")
        return

    cities = []
    if args.city.upper() == "ALL":
        cities = ["OAKLAND", "BERKELEY"]
    else:
        cities = [args.city.upper()]

    all_results = []
    total_deceased = 0

    for city in cities:
        apns = load_apns(city)
        if not apns:
            continue
        print(f"\n{'='*60}")
        print(f" {city}: {len(apns)} properties to research")
        print(f"{'='*60}\n")

        for i, apn in enumerate(apns):
            print(f"[{i+1}/{len(apns)}] APN: {apn}")
            result = process_single_property(apn, verbose)
            all_results.append(result)
            if result.get("deceased_count", 0) > 0:
                total_deceased += result["deceased_count"]

            if i < len(apns) - 1:
                time.sleep(args.delay)

    # Summary
    print(f"\n{'='*60}")
    print(f" SUMMARY")
    print(f"{'='*60}")
    ok_count = sum(1 for r in all_results if r["status"] == "ok")
    deceased_props = [r for r in all_results if r.get("deceased_count", 0) > 0]
    print(f"  Total processed: {len(all_results)}")
    print(f"  Successfully analyzed: {ok_count}")
    print(f"  Properties with deceased: {len(deceased_props)}")
    print(f"  Total deceased individuals: {total_deceased}")
    if deceased_props:
        print(f"\n  Properties with deceased owners/residents:")
        for r in deceased_props:
            names = ", ".join(r.get("deceased_names", []))
            print(f"    {r['apn']}: {r.get('address', '?')} — {r['deceased_count']} ({names})")


if __name__ == "__main__":
    main()

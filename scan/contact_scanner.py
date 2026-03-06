#!/usr/bin/env python3
"""
Owner Contact Scanner - Scrapes cyberbackgroundchecks.com directly
to find property owner contact information (email, phone) using
Playwright to bypass bot protections.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
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

# Scanner state for tracking progress
contact_state: dict[str, Any] = {
    "is_running": False,
    "current_apn": None,
    "queue": [],
    "completed": 0,
    "failed": 0,
}


def get_property_contact_info(apn: str) -> dict[str, Any] | None:
    """Get property info including address from database."""
    import db
    row = db.get_bill_with_parcel(apn)
    if not row:
        return None
    result = dict(row)
    if result.get("row_json"):
        try:
            result["parcel_data"] = json.loads(result["row_json"]) if isinstance(result["row_json"], str) else result["row_json"]
        except json.JSONDecodeError:
            result["parcel_data"] = {}
    else:
        result["parcel_data"] = {}
    return result


def build_address_parts(prop_info: dict[str, Any]) -> dict[str, str]:
    """Extract street, city, zip from property info."""
    parcel = prop_info.get("parcel_data", {})

    street_number = parcel.get("SitusStreetNumber", "")
    street_name = parcel.get("SitusStreetName", "")
    situs_city = parcel.get("SitusCity", "") or prop_info.get("city", "")
    situs_zip = parcel.get("SitusZip", "")

    # Compose the street portion (e.g. "1 ROCHDALE WAY")
    if street_number and street_name:
        street_address = f"{street_number} {street_name}"
    elif parcel.get("SitusAddress"):
        street_address = parcel["SitusAddress"]
    else:
        loc = prop_info.get("location_of_property", "")
        stripped = loc
        if situs_zip and stripped.endswith(situs_zip):
            stripped = stripped[: -len(situs_zip)].strip()
        if situs_city and stripped.upper().endswith(situs_city.upper()):
            stripped = stripped[: -len(situs_city)].strip()
        street_address = stripped if stripped else loc

    return {
        "street": street_address,
        "city": situs_city,
        "zip": situs_zip,
    }


def build_cyber_url(addr: dict[str, str]) -> str:
    """Build cyberbackgroundchecks.com address URL."""
    street_slug = addr["street"].replace(" ", "-")
    city_slug = addr["city"].replace(" ", "-") if addr["city"] else ""
    return f"https://www.cyberbackgroundchecks.com/address/{street_slug}/{city_slug}/{addr['zip']}"


def scrape_address_page_playwright(url: str, verbose: bool = False) -> dict[str, Any]:
    """
    Scrape the cyberbackgroundchecks.com address page using Playwright
    to bypass Cloudflare and extract the first person's info.
    """
    if verbose:
        print(f"\n{'=' * 60}")
        print(f"FETCHING via Playwright: {url}")
        print(f"{'=' * 60}\n")

    content = ""
    try:
        with sync_playwright() as p:
            # Launch headed to bypass Cloudflare
            # We assume DISPLAY is set or we are in an environment that can handle headed
            # If strictly headless is needed, we might need a stealth plugin, but headed works best for now.
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                 user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                 viewport={'width': 1280, 'height': 800}
            )
            
            page = context.new_page()
            
            # Anti-detection script
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Check for Cloudflare challenge and wait a bit
                # Simple wait is often enough if headed
                time.sleep(5) 
                
                content = page.content()
                
            except Exception as e:
                 if verbose:
                     print(f"Playwright navigation error: {e}")
                 return {"error": f"Navigation failed: {e}"}
            finally:
                browser.close()

    except Exception as e:
        if verbose:
            print(f"Playwright error: {e}")
        return {"error": f"Playwright error: {e}"}

    if verbose:
        print(f"Content retrieved, length: {len(content)} bytes\n")
        with open("debug_last_scan.html", "w") as f:
            f.write(content)
        print("Saved HTML to debug_last_scan.html")

    soup = BeautifulSoup(content, "html.parser")

    # Check for Cloudflare block
    if "challenge" in soup.get_text().lower() and "cloudflare" in soup.get_text().lower():
         return {"error": "Blocked by Cloudflare challenge"}
    
    # Extract Property Attributes
    prop_attributes = {}
    for label, key in [
        ("Ownership Type", "prop_ownership_type"), 
        ("Last Sale Date", "prop_last_sale_date"), 
        ("Occupancy Type", "prop_occupancy_type")
    ]:
        element = soup.find(string=re.compile(label, re.IGNORECASE))
        if element and element.parent:
            # Structure: <div class="row property-attr">Label</div> <div class="row property-val">Value</div>
            parent = element.parent
            next_sibling = parent.find_next_sibling()
            if next_sibling:
                prop_attributes[key] = next_sibling.get_text(strip=True)
    
    if verbose:
        print("  Property Attributes found:", prop_attributes)

    # Find all person cards
    cards = soup.select("div.card.mt-3")
    if not cards:
        cards = soup.select("div.card") # fallback

    if verbose:
        print(f"Found {len(cards)} person cards\n")

    if not cards:
        return {
            "owner_name": None,
            "emails": [],
            "phones": [],
            "tenant_verified": False,
            "confidence": "none",
            "source_notes": f"No people found at this address on cyberbackgroundchecks.com ({url})",
            **prop_attributes,
            "property_search_url": url,
        }

    # Process cards until we find a valid person
    valid_result = {
        "owner_name": None,
        "emails": [],
        "phones": [],
        "tenant_verified": False,
        "confidence": "none",
        "source_notes": f"No valid people found at this address ({url})",
        **prop_attributes,
        "property_search_url": url,
    }

    for i, card in enumerate(cards):
        if verbose:
            print(f"Checking card {i+1}...")
        
        result = parse_person_card(card, verbose=verbose)
        
        # Check validity criteria
        name = result.get("owner_name")
        if name and name.lower() != "name" and "results for" not in name.lower():
            # Found a valid person!
            result["source_notes"] = f"cyberbackgroundchecks.com (Card {i+1})"
            
            # Extract View Details URL
            details_link = card.select_one("a.btn-primary")
            if details_link:
                 href = details_link.get("href")
                 if href:
                     # It's usually a relative URL
                     if href.startswith("/"):
                         result["owner_details_url"] = f"https://www.cyberbackgroundchecks.com{href}"
                     else:
                         result["owner_details_url"] = href
            
            # Add property attributes
            result.update(prop_attributes)
            result["property_search_url"] = url
            
            return result
            
    return valid_result


def scrape_details_page(url: str, verbose: bool = False) -> dict[str, Any]:
    """
    Scrape the person details page for mobile phone and email.
    """
    if verbose:
        print(f"  Fetching details: {url}")

    content = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                 user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                 viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3) # Wait for dynamic content
                content = page.content()
            except Exception as e:
                 if verbose:
                      print(f"    Details navigation error: {e}")
                 return {"error": f"Navigation failed: {e}"}
            finally:
                browser.close()

    except Exception as e:
        return {"error": f"Playwright error: {e}"}

    if verbose and not os.path.exists("debug_last_details.html"):
        with open("debug_last_details.html", "w") as f:
            f.write(content)
        print("    Saved HTML to debug_last_details.html")

    soup = BeautifulSoup(content, "html.parser")
    
    # Extract Mobile Phone
    # Looking for phones with "Wireless" or "Mobile" label
    mobile_phone = None
    phones = []
    
    # Analyze phone section (usually .row or similar)
    # For now, grab all phones and try to prioritize
    phone_links = soup.select("a.phone")
    for ph in phone_links:
        phone_text = ph.get_text(strip=True)
        # Check label if possible
        # Parent of 'a' might have a sibling or container with label
        # This part is tricky without seeing HTML.
        # We will iterate and dump all found phones.
        if phone_text and phone_text not in phones:
            phones.append(phone_text)
            
    # As a heuristic, first phone is often primary/mobile if not specific labels found
    if phones:
        mobile_phone = phones[0]

    # Extract Email
    email_addresses = []
    email_links = soup.select("a.email")
    for em in email_links:
        email_text = em.get_text(strip=True)
        if email_text and "@" in email_text and email_text not in email_addresses:
            email_addresses.append(email_text)

    return {
        "mobile_phone": mobile_phone,
        "emails": email_addresses,
        "all_phones": phones # For debugging or fallback
    }


def parse_person_card(card, verbose: bool = False) -> dict[str, Any]:
    """Parse a single person card from cyberbackgroundchecks.com."""

    # Extract name
    owner_name = None
    
    # Priority 1: span.name-given (seen in debug HTML)
    name_el = card.select_one("span.name-given")
    if name_el:
        owner_name = name_el.get_text(strip=True)
    
    # Priority 2: h2 .name-primary
    if not owner_name:
        name_el = card.select_one("h2 .name-primary")
        if name_el:
            owner_name = name_el.get_text(strip=True)
            
    # Priority 3: direct h2 text (fallback)
    if not owner_name:
        name_el = card.find("h2")
        if name_el:
            # Be careful to exclude children if possible, or just take the whole text and clean it
            raw_text = name_el.get_text(strip=True)
            # Remove "Age: ..." pattern
            raw_text = re.sub(r"Age:\s*\d+", "", raw_text, flags=re.IGNORECASE).strip()
            owner_name = raw_text

    if verbose:
        print(f"  Name candidate: {owner_name}")
        # print("  DEBUG: Raw Card Text:", card.get_text(separator="|", strip=True)[:200], "...")

    # Extract phone numbers
    phones = []
    phone_links = card.select("a.phone")
    for ph in phone_links:
        phone_text = ph.get_text(strip=True)
        if phone_text and phone_text not in phones:
            phones.append(phone_text)

    if verbose:
        print(f"  Phones: {phones}")

    # Check if person currently lives at the address
    tenant_verified = False
    # Look for "Lives at" label
    # In debug HTML, text is "Lives at|Address..."
    # Warning: .address-current-label might not be the class name.
    # We'll search for the text "Lives at"
    if card.find(string=re.compile(r"Lives at", re.IGNORECASE)):
        tenant_verified = True
        if verbose:
            print("  Status: Current resident (Verified)")
    else:
        if verbose:
            print("  Status: Past resident or unknown")

    # Extract emails if any (rare on summary page)
    emails = []
    email_links = card.select("a.email, a[href^='mailto:']")
    for em in email_links:
        email_text = em.get_text(strip=True)
        if email_text and "@" in email_text and email_text not in emails:
            emails.append(email_text)

    # Determine confidence
    if owner_name and (phones or emails):
        confidence = "high"
    elif owner_name:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "owner_name": owner_name,
        "emails": emails,
        "phones": phones,
        "tenant_verified": tenant_verified,
        "confidence": confidence,
    }


async def scan_owner_contact(apn: str, verbose: bool = False) -> tuple[bool, dict[str, Any]]:
    """
    Scan for owner contact info by scraping cyberbackgroundchecks.com.
    Returns (success, result_dict).
    """
    prop_info = get_property_contact_info(apn)
    if not prop_info:
        return False, {"error": f"Property not found: {apn}"}

    addr = build_address_parts(prop_info)
    if not addr["street"]:
        return False, {"error": "No street address available for this property"}

    url = build_cyber_url(addr)

    if verbose:
        parcel = prop_info.get("parcel_data", {})
        print(f"Property Address: {addr['street']}, {addr['city']} {addr['zip']}")
        print(f"Mailing Address: {parcel.get('MailingAddress', 'N/A')}")
        print()

    # Stage 1: Scrape Address Page
    # (Playwright sync API is blocking, so strictly we should use async_playwright
    # but threading is fine for this simple case)
    result = await asyncio.to_thread(scrape_address_page_playwright, url, verbose)

    if "error" in result:
        return False, result

    # Stage 2: Scrape Details Page if available
    if result.get("owner_details_url"):
         if verbose:
             print(f"  Found Details URL: {result['owner_details_url']}")
             print("  Initiating Stage 2: Scrape Details Page...")
         
         details_result = await asyncio.to_thread(scrape_details_page, result['owner_details_url'], verbose)
         
         if "error" not in details_result:
             # Merge details into result
             result["owner_mobile_phone"] = details_result.get("mobile_phone")
             
             # Merge emails (avoid duplicates)
             existing_emails = set(result.get("emails", []))
             new_emails = set(details_result.get("emails", []))
             result["emails"] = list(existing_emails.union(new_emails))
             
             # Merge phones (all_phones)
             existing_phones = set(result.get("phones", []))
             new_phones = set(details_result.get("all_phones", []))
             result["phones"] = list(existing_phones.union(new_phones))
             
             if verbose:
                 print("  Stage 2 Complete. Merged details.")

    return True, result


async def process_contact_queue() -> None:
    """Process the contact scan queue."""
    global contact_state
    import db

    while contact_state["queue"]:
        apn = contact_state["queue"].pop(0)
        contact_state["current_apn"] = apn

        print(f"  🔍 Scanning contact info for: {apn}")
        db.update_bill_owner_contact(
            apn, "in_progress",
            owner_contact_updated_at=datetime.now().isoformat(),
        )

        success, result = await scan_owner_contact(apn)

        if success:
            emails = result.get("emails", [])
            phones = result.get("phones", [])
            email_str = "; ".join(emails) if emails else None
            phone_str = "; ".join(phones) if phones else None
            tenant_verified = result.get("tenant_verified", False)
            
            # New fields
            owner_mobile_phone = result.get("owner_mobile_phone")
            owner_details_url = result.get("owner_details_url")
            property_search_url = result.get("property_search_url")
            prop_ownership_type = result.get("prop_ownership_type")
            prop_last_sale_date = result.get("prop_last_sale_date")
            prop_occupancy_type = result.get("prop_occupancy_type")

            db.update_bill_owner_contact(
                apn, "completed",
                owner_email=email_str,
                owner_phone=phone_str,
                owner_contact_updated_at=datetime.now().isoformat(),
                tenant_verified=tenant_verified,
                owner_mobile_phone=owner_mobile_phone,
                owner_details_url=owner_details_url,
                property_search_url=property_search_url,
                prop_ownership_type=prop_ownership_type,
                prop_last_sale_date=prop_last_sale_date,
                prop_occupancy_type=prop_occupancy_type,
            )

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

            contact_state["completed"] += 1
            found_parts = []
            if result.get("owner_name"):
                found_parts.append(f"name: {result['owner_name']}")
            if phones:
                found_parts.append(f"phone: {phone_str}")
            if emails:
                found_parts.append(f"email: {email_str}")
            if owner_mobile_phone:
                found_parts.append(f"mobile: {owner_mobile_phone}")
                
            if found_parts:
                verified = " ✓ current resident" if tenant_verified else ""
                print(f"    ✓ Found: {', '.join(found_parts)}{verified}")
            else:
                print(f"    ✓ Completed (no contact info found)")
        else:
            db.update_bill_owner_contact(
                apn, "failed",
                owner_contact_updated_at=datetime.now().isoformat(),
            )
            contact_state["failed"] += 1
            print(f"    ✗ Failed: {result.get('error', 'Unknown error')}")

        # Rate limit between requests
        await asyncio.sleep(2.0)

    contact_state["current_apn"] = None
    contact_state["is_running"] = False
    print(f"  Contact scan complete: {contact_state['completed']} completed, {contact_state['failed']} failed")


def start_contact_scan(apns: list[str]) -> bool:
    """Start contact scan for a list of APNs."""
    global contact_state

    if contact_state["is_running"]:
        contact_state["queue"].extend(apns)
        return True

    contact_state["is_running"] = True
    contact_state["queue"] = list(apns)
    contact_state["completed"] = 0
    contact_state["failed"] = 0

    def run_async():
        asyncio.run(process_contact_queue())

    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    return True


def get_contact_state() -> dict[str, Any]:
    """Get current contact scanner state."""
    # API key check removed as it's no longer needed
    return {
        "is_running": contact_state["is_running"],
        "current_apn": contact_state["current_apn"],
        "queue_length": len(contact_state["queue"]),
        "completed": contact_state["completed"],
        "failed": contact_state["failed"],
        "api_configured": True, # Always true now as we don't need external key
    }


async def test_single_property(apn: str, verbose: bool = False) -> None:
    """Test contact scan on a single property (CLI)."""
    print(f"Testing contact scan for APN: {apn}")
    print("-" * 50)

    success, result = await scan_owner_contact(apn, verbose=verbose)

    if success:
        print("\n✓ Contact info found:")
        print(f"  Name: {result.get('owner_name', 'Unknown')}")
        print(f"  Phones: {', '.join(result.get('phones', [])) or 'None found'}")
        print(f"  Emails: {', '.join(result.get('emails', [])) or 'None found'}")
        print(f"  Tenant Verified: {'Yes' if result.get('tenant_verified') else 'No'}")
        print(f"  Confidence: {result.get('confidence', 'unknown')}")
        print(f"  Source: {result.get('source_notes', '')}")
    else:
        print(f"\n✗ Failed: {result.get('error', 'Unknown error')}")


def main() -> None:
    """CLI entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    # Remove flags so positional parsing still works
    args = [a for a in sys.argv if a not in ("--verbose", "-v")]

    if len(args) > 1:
        if args[1] == "--test-single" and len(args) > 2:
            asyncio.run(test_single_property(args[2], verbose=verbose))
            return
        elif args[1] == "--help":
            print("Usage: python contact_scanner.py [options]")
            print()
            print("Options:")
            print("  --test-single <APN>  Test contact scan on a single property")
            print("  -v, --verbose        Print detailed scraping output")
            print("  --help               Show this help message")
            return

    print("Owner Contact Scanner")
    print("-" * 50)
    print("Scrapes cyberbackgroundchecks.com using Playwright (headed) to find property contacts.")
    print()
    print("Use --test-single <APN> to test on a specific property")
    print("Or start via the web UI API endpoints")


if __name__ == "__main__":
    main()

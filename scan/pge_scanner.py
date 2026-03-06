#!/usr/bin/env python3
"""
PGE Power Status Scanner - checks power status for VPT database entries.
Runs in parallel with the main VPT scan.
"""
from __future__ import annotations

import asyncio
import re
import sys
import threading
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Warning: playwright not installed. Run: pip install playwright && playwright install chromium")
    async_playwright = None

BASE_DIR = Path(__file__).resolve().parent

# Scanner state for admin panel
pge_state = {
    "is_running": False,
    "current_address": None,
    "checked": 0,
    "power_on": 0,
    "power_off": 0,
    "total_queue": 0,
    "stop_requested": False,
}


def get_pge_state() -> dict:
    """Get current PGE scanner state for API."""
    return {
        "is_running": pge_state["is_running"],
        "current_address": pge_state["current_address"],
        "checked": pge_state["checked"],
        "power_on": pge_state["power_on"],
        "power_off": pge_state["power_off"],
        "total_queue": pge_state["total_queue"],
    }


def start_pge_scan(apns: list[str] | None = None) -> bool:
    """Start PGE scan in background thread. If apns is None, scan all unchecked."""
    if pge_state["is_running"]:
        return False
    
    pge_state["stop_requested"] = False
    
    def run_scan():
        asyncio.run(scan_power_statuses(apns))
    
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()
    return True


def stop_pge_scan() -> bool:
    """Request stop of current PGE scan."""
    if not pge_state["is_running"]:
        return False
    pge_state["stop_requested"] = True
    return True

# PGE Configuration
PGE_URL = "https://pgealerts.alerts.pge.com/outages/map/"
SEARCH_INPUT_SELECTOR = "#outage-center-address-lookup"
SEARCH_RESULT_ITEM = '[id^="search-result-"]'


async def check_power_status(page, address: str) -> bool | None:
    """
    Check power status for an address using an existing page.
    Returns: True = has power, False = no power, None = error/unknown
    """
    try:
        search_input = page.locator(SEARCH_INPUT_SELECTOR)
        await search_input.click()
        await search_input.fill("")
        await search_input.type(address, delay=50)

        try:
            first_result = page.locator(SEARCH_RESULT_ITEM).first
            await first_result.wait_for(state="visible", timeout=8000)

            results = page.locator(SEARCH_RESULT_ITEM)
            count = await results.count()

            # Normalize address for matching
            suffixes = [
                "road", "rd", "street", "st", "avenue", "ave", "drive", "dr",
                "lane", "ln", "court", "ct", "place", "pl", "boulevard", "blvd",
                "circle", "cir", "way", "terrace", "ter", "highway", "hwy",
                "north", "n", "south", "s", "east", "e", "west", "w"
            ]

            clean_address = re.sub(r'[^\w\s]', '', address.lower())
            parts = clean_address.split()

            if not parts:
                return None

            house_number = parts[0]
            street_parts = [p for p in parts[1:] if p not in suffixes and not p.isdigit()]
            if not street_parts:
                street_parts = [p for p in parts[1:] if not p.isdigit()]

            for i in range(count):
                text = await results.nth(i).inner_text()
                text_clean = re.sub(r'[^\w\s]', '', text.lower())
                result_words = text_clean.split()

                if house_number not in result_words:
                    continue

                street_match = False
                if not street_parts:
                    street_match = True
                else:
                    for part in street_parts:
                        if part in result_words:
                            street_match = True
                            break

                if street_match:
                    return True  # Has power

            return False  # No power (not found in results)

        except Exception:
            return False  # No results = no power

    except Exception as e:
        print(f"  Error checking {address}: {e}")
        return None


def get_unchecked_entries() -> list[tuple[str, str]]:
    """Get VPT entries that haven't been checked for power status."""
    import db
    r = db.get_client().table("bills").select("apn, location_of_property").not_.is_("location_of_property", "null").or_("power_status.is.null,power_status.eq.").execute()
    return [(row["apn"], row.get("location_of_property") or "") for row in (r.data or []) if (row.get("location_of_property") or "").strip()]


def update_power_status(apn: str, status: bool | None) -> None:
    """Update power status for an APN in the database."""
    import db
    if status is None:
        status_str = "unknown"
    elif status:
        status_str = "on"
    else:
        status_str = "off"
    db.update_bill_power_status(apn, status_str)


async def scan_power_statuses(apns: list[str] | None = None) -> None:
    """Scan power status for specified APNs or all unchecked VPT entries."""
    if async_playwright is None:
        print("PGE Scanner: playwright not available, skipping")
        return

    if apns:
        import db
        r = db.get_client().table("bills").select("apn, location_of_property").in_("apn", apns).not_.is_("location_of_property", "null").execute()
        entries = [(row["apn"], row.get("location_of_property") or "") for row in (r.data or []) if (row.get("location_of_property") or "").strip()]
    else:
        entries = get_unchecked_entries()
    
    if not entries:
        print("PGE Scanner: No entries need power status check")
        return

    # Initialize state
    pge_state["is_running"] = True
    pge_state["checked"] = 0
    pge_state["power_on"] = 0
    pge_state["power_off"] = 0
    pge_state["total_queue"] = len(entries)
    pge_state["current_address"] = None

    print(f"PGE Scanner: Checking power status for {len(entries)} entries...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(PGE_URL, timeout=60000)
                search_input = page.locator(SEARCH_INPUT_SELECTOR)
                await search_input.wait_for(state="visible", timeout=30000)

                for apn, address in entries:
                    # Check for stop request
                    if pge_state["stop_requested"]:
                        print("PGE Scanner: Stop requested, stopping...")
                        break
                    
                    pge_state["current_address"] = address[:50] if len(address) > 50 else address
                    
                    status = await check_power_status(page, address)
                    update_power_status(apn, status)

                    pge_state["checked"] += 1
                    if status is True:
                        pge_state["power_on"] += 1
                    elif status is False:
                        pge_state["power_off"] += 1

                    if pge_state["checked"] % 10 == 0:
                        print(f"PGE Scanner: Checked {pge_state['checked']}/{len(entries)} - On: {pge_state['power_on']}, Off: {pge_state['power_off']}")

                    # Small delay between checks
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"PGE Scanner error: {e}")
            finally:
                await browser.close()

        print(f"PGE Scanner complete: {pge_state['checked']} checked, {pge_state['power_on']} on, {pge_state['power_off']} off")
        
    finally:
        pge_state["is_running"] = False
        pge_state["current_address"] = None


def main() -> None:
    """Run the PGE power status scanner."""
    asyncio.run(scan_power_statuses())


if __name__ == "__main__":
    main()

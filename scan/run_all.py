#!/home/noob/BARN-scan/venv/bin/python
"""
Run scan + web UI together.
On startup, ensure all positive cache APNs exist in DB.
Also runs PGE power status scanner in parallel.
Supports continuous multi-city scanning.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env (if present) BEFORE importing
# modules that read configuration from os.environ (e.g. scanner).
load_dotenv()

from webgui import app as webapp
import find_meas_w_addresses as scanner
import pge_scanner
import db

BASE_DIR = Path(__file__).resolve().parent
# Main parcels CSV from Alameda County (see README)
CSV_PATH = BASE_DIR / "Parcels_5567367248157875843.csv"

# Cities to scan (in order of priority)
SCAN_CITIES = [
    "OAKLAND",
    "BERKELEY", 
    "EMERYVILLE",
    "SAN LEANDRO",
    "RICHMOND",
    "EL CERRITO",
    "ALAMEDA",
    "HAYWARD",
    "FREMONT",
    "UNION CITY",
    "NEWARK",
    "PIEDMONT",
    "ALBANY",
]

# Global scan state
scan_state = {
    "current_city": None,
    "cities_completed": [],
    "is_running": False,
    "continuous_mode": False,
    "total_scanned": 0,
    "total_hits": 0,
}


def load_apn_rowjson() -> dict[str, str]:
    apn_to_rowjson: dict[str, str] = {}
    with CSV_PATH.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apn = (row.get("APN") or "").strip()
            if not apn:
                continue
            if apn not in apn_to_rowjson:
                apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)
    return apn_to_rowjson


def get_db_apns() -> set[str]:
    return db.get_results_apns()


def ensure_cache_in_db() -> None:
    cache = scanner.load_cache()
    apn_to_rowjson = load_apn_rowjson()
    db_apns = get_db_apns()

    for apn, entry in cache.items():
        has_vpt = entry.get("has_vpt") or entry.get("has_meas_w")
        is_delinquent = entry.get("is_delinquent", False)
        if not has_vpt and not is_delinquent:
            continue
        if apn in db_apns:
            continue
        bill_url = entry.get("bill_url")
        roll_year = entry.get("roll_year")
        if not bill_url:
            bill_url, roll_year = scanner.get_latest_bill_info(apn)
        if not bill_url:
            continue
        bill_html = scanner.fetch_text(bill_url)
        scanner.upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))


def get_cities_from_csv() -> list[str]:
    """Get list of unique cities from CSV that have parcels."""
    cities = set()
    with CSV_PATH.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = (row.get("CITY") or row.get("SitusCity") or "").strip().upper()
            if city:
                cities.add(city)
    # Return in preferred order, then add any others
    ordered = [c for c in SCAN_CITIES if c in cities]
    others = sorted(cities - set(SCAN_CITIES))
    return ordered + others


def run_continuous_scan() -> None:
    """Continuously scan all cities in a loop."""
    global scan_state
    scan_state["is_running"] = True
    scan_state["continuous_mode"] = True
    
    while scan_state["continuous_mode"]:
        cities = get_cities_from_csv()
        
        for city in cities:
            if not scan_state["continuous_mode"]:
                break
                
            scan_state["current_city"] = city
            print(f"\n{'='*60}")
            print(f"Starting scan for {city}")
            print(f"{'='*60}")
            
            try:
                scanner.main(city=city)
                scan_state["cities_completed"].append(city)
            except Exception as e:
                print(f"Error scanning {city}: {e}")
            
            # Brief pause between cities
            if scan_state["continuous_mode"]:
                time.sleep(5)
        
        # Reset for next cycle
        if scan_state["continuous_mode"]:
            print("\n" + "="*60)
            print("Completed full scan cycle. Starting over...")
            print("="*60 + "\n")
            scan_state["cities_completed"] = []
            time.sleep(60)  # Wait 1 minute before restarting
    
    scan_state["is_running"] = False
    scan_state["current_city"] = None


def run_single_city_scan(city: str) -> None:
    """Scan a single city."""
    global scan_state
    scan_state["is_running"] = True
    scan_state["current_city"] = city
    
    try:
        scanner.main(city=city)
        scan_state["cities_completed"].append(city)
    except Exception as e:
        print(f"Error scanning {city}: {e}")
    finally:
        scan_state["is_running"] = False
        scan_state["current_city"] = None


def run_pge_scan() -> None:
    """Run PGE power status scanner in a loop."""
    while True:
        try:
            asyncio.run(pge_scanner.scan_power_statuses())
        except Exception as e:
            print(f"PGE Scanner error: {e}")
        time.sleep(60)


def get_scan_state() -> dict:
    """Return current scan state for API."""
    return {
        "current_city": scan_state["current_city"],
        "cities_completed": scan_state["cities_completed"],
        "is_running": scan_state["is_running"],
        "continuous_mode": scan_state["continuous_mode"],
        "available_cities": get_cities_from_csv(),
    }


def start_scan(city: str | None = None, continuous: bool = False) -> bool:
    """Start a scan (can be called from web UI)."""
    global scan_state
    
    if scan_state["is_running"]:
        return False  # Already running
    
    if continuous:
        thread = threading.Thread(target=run_continuous_scan, daemon=True)
    elif city:
        thread = threading.Thread(target=run_single_city_scan, args=(city,), daemon=True)
    else:
        return False
    
    thread.start()
    return True


def stop_scan() -> bool:
    """Stop current scan (only works for continuous mode)."""
    global scan_state
    if scan_state["continuous_mode"]:
        scan_state["continuous_mode"] = False
        return True
    return False


def main(
    city: str | None = None,
    continuous: bool = False,
    enable_pge: bool | None = None,
) -> None:
    global scan_state
    
    print("Using Supabase database (see .env SUPABASE_URL / SUPABASE_ANON_KEY)")
    
    print("Ensuring all cache positives are in DB...")
    ensure_cache_in_db()

    print("Fixing entries with missing fields...")
    scanner.fix_missing_fields()

    # Decide whether to start PGE power scanner
    if enable_pge is None:
        # Default enabled unless explicitly disabled via env
        env_flag = (os.getenv("VPT_ENABLE_PGE") or "").strip().lower()
        if env_flag in {"0", "false", "no", "off"}:
            enable_pge = False
        else:
            enable_pge = True

    if enable_pge:
        print("Starting PGE power scanner in background...")
        pge_thread = threading.Thread(target=run_pge_scan, daemon=True)
        pge_thread.start()
    else:
        print("PGE power scanner disabled (VPT only).")

    # Start VPT scanner
    if continuous:
        print("Starting CONTINUOUS multi-city scan in background...")
        scan_thread = threading.Thread(target=run_continuous_scan, daemon=True)
        scan_thread.start()
    elif city:
        city_upper = city.upper()
        print(f"Starting VPT scan for {city_upper} in background...")
        scan_thread = threading.Thread(target=run_single_city_scan, args=(city_upper,), daemon=True)
        scan_thread.start()
    else:
        print("No city specified. Use --city=CITYNAME or --continuous")

    print("Starting web UI on http://0.0.0.0:5000")
    webapp.app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    import sys
    # Register this module under 'run_all' name so imports get the same instance
    # (when running as __main__, the module isn't auto-registered as 'run_all')
    sys.modules["run_all"] = sys.modules["__main__"]
    
    city = None
    continuous = False
    enable_pge: bool | None = None
    
    for arg in sys.argv[1:]:
        if arg.startswith("--city="):
            city = arg.split("=", 1)[1].strip()
        elif arg == "--continuous":
            continuous = True
        elif arg == "--no-pge":
            enable_pge = False
        elif arg == "--pge-only":
            enable_pge = True
        elif arg == "--help":
            print("Usage: python run_all.py [options]")
            print("Options:")
            print("  --city=CITYNAME    Scan a specific city")
            print("  --continuous       Continuously scan all cities in a loop")
            print("  --no-pge           Disable PGE power status scanner (VPT only)")
            print("  --pge-only         Force-enable PGE scanner (overrides env)")
            print("  --help             Show this help")
            sys.exit(0)
    
    main(city=city, continuous=continuous, enable_pge=enable_pge)

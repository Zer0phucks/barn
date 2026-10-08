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
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env (if present) BEFORE importing
# modules that read configuration from os.environ (e.g. scanner).
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from webgui import app as webapp
import find_meas_w_addresses as scanner
import intake_autopilot
import pge_scanner
import db

# Main parcels CSV from Alameda County (see README)
CSV_PATH = intake_autopilot.canonical_parcels_path()

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
    "removed": 0,
    "unflagged": 0,
}

# Set from the command line; apply to every scan this process starts.
scan_options = {"recheck_only": False, "dry_run": False}


def _run_city_scan(city: str) -> None:
    stats = scanner.main(city=city, **scan_options) or {}
    scan_state["total_scanned"] += stats.get("scanned", 0)
    scan_state["total_hits"] += stats.get("added", 0)
    scan_state["removed"] += stats.get("removed", 0)
    scan_state["unflagged"] += stats.get("unflagged", 0)


def ensure_cache_in_db() -> None:
    # Cached bill URLs can't be re-fetched (the site serves bills per session),
    # so cached VPT parcels missing from the DB are looked up again.
    scanner.recheck_cached_positives(dry_run=scan_options["dry_run"])


def get_cities_from_csv() -> list[str]:
    """Get list of unique cities from CSV files that have parcels."""
    cities = set()

    # Discover known city CSVs in BASE_DIR (e.g. oakland.csv, berkeley.csv)
    for p in BASE_DIR.glob("*.csv"):
        stem = p.stem.upper()
        if stem in SCAN_CITIES:
            cities.add(stem)

    # Read canonical parcels path
    canonical = intake_autopilot.canonical_parcels_path()
    if canonical.exists():
        try:
            with canonical.open(newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    city = (row.get("CITY") or row.get("SitusCity") or "").strip().upper()
                    if city and city != "CITY":
                        cities.add(city)
        except Exception as e:
            print(f"Error reading canonical parcels CSV: {e}")

    # Explicitly ensure Oakland and Berkeley are included if their respective CSVs exist
    if (BASE_DIR / "oakland.csv").exists():
        cities.add("OAKLAND")
    if (BASE_DIR / "berkeley.csv").exists():
        cities.add("BERKELEY")

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
                _run_city_scan(city)
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
    city_clean = city.strip().upper()
    scan_state["is_running"] = True
    scan_state["current_city"] = city_clean

    try:
        _run_city_scan(city_clean)
        scan_state["cities_completed"].append(city_clean)
    except Exception as e:
        print(f"Error scanning {city_clean}: {e}")
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
    if intake_autopilot.intake_state["is_running"]:
        intake = intake_autopilot.get_intake_state()
        return {
            "current_city": None,
            "cities_completed": [],
            "is_running": True,
            "continuous_mode": False,
            "available_cities": get_cities_from_csv(),
            "mode": intake.get("mode"),
            "processed": intake.get("processed", 0),
            "promoted": intake.get("promoted", 0),
            "remaining": intake.get("remaining", 0),
            "current_apn": intake.get("current_apn"),
        }
    return {
        "current_city": scan_state["current_city"],
        "cities_completed": scan_state["cities_completed"],
        "is_running": scan_state["is_running"],
        "continuous_mode": scan_state["continuous_mode"],
        "available_cities": get_cities_from_csv(),
        "mode": "legacy_scan" if scan_state["is_running"] else None,
        "total_scanned": scan_state["total_scanned"],
        "total_hits": scan_state["total_hits"],
        "removed": scan_state["removed"],
        "unflagged": scan_state["unflagged"],
        "progress": dict(scanner.scan_progress) if scan_state["is_running"] else None,
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
        return intake_autopilot.start_daily_intake()
    
    thread.start()
    return True


def stop_scan() -> bool:
    """Stop current scan (both continuous mode and single-city scans)."""
    global scan_state
    stopped = False
    if scan_state["continuous_mode"]:
        scan_state["continuous_mode"] = False
        stopped = True
    if scan_state["is_running"]:
        scanner.request_stop()
        stopped = True
    return stopped


def main(
    city: str | None = None,
    continuous: bool = False,
    enable_pge: bool | None = None,
) -> None:
    global scan_state
    
    print("Using Supabase database (see .env SUPABASE_URL / SUPABASE_ANON_KEY)")
    
    print("Ensuring all cache positives are in DB...")
    ensure_cache_in_db()

    if not scan_options["dry_run"]:
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
        elif arg == "--recheck-only":
            scan_options["recheck_only"] = True
        elif arg == "--dry-run":
            scan_options["dry_run"] = True
        elif arg == "--help":
            print("Usage: python run_all.py [options]")
            print("Options:")
            print("  --city=CITYNAME    Scan a specific city")
            print("  --continuous       Continuously scan all cities in a loop")
            print("  --no-pge           Disable PGE power status scanner (VPT only)")
            print("  --pge-only         Force-enable PGE scanner (overrides env)")
            print("  --recheck-only     Only re-check properties already in the DB (removes lapsed VPT)")
            print("  --dry-run          Report what would be added/removed without changing the DB")
            print("  --help             Show this help")
            sys.exit(0)
    
    main(city=city, continuous=continuous, enable_pge=enable_pge)

#!/usr/bin/env python3
"""
Find mailing addresses tied to parcels with Measure W VPT charges.

Process:
1) Read parcel CSV and collect APNs for Oakland situs parcels.
2) For each APN, fetch latest bill and check for "MEAS-W OAKLAND VPT".
3) Save a PDF copy of the bill in /home/noob/vpt/bandos.

The script is resumable via a cache file to avoid re-checking APNs.
"""
import csv
import sys
import html
import json
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
PdfReader = None

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "Parcels_5567367248157875843.csv"
CACHE_JSONL = BASE_DIR / "measw_cache.jsonl"

BASE_URL = "https://propertytax.alamedacountyca.gov"
ACCOUNT_SUMMARY = BASE_URL + "/account-summary?apn="

# Tax markers by city (substring match on bill HTML)
MEAS_W_MARKER = "MEAS-W OAKLAND VPT"  # Oakland Vacant Property Tax
# Berkeley Measure M - county may use various formats
MEAS_M_MARKERS = [
    "MEAS-M BERKELEY",
    "MEAS-M",
    "MEAS M BERKELEY",
    "MEAS M",
    "BERKELEY VPT",
    "Measure M",
    "MEASURE M",
    # Berkeley VPT is exactly $6,000
    "$6,000.00",
    "$6000.00",
    "6,000.00",
    # Additional patterns
    "VACANT PROPERTY TAX",
    "VACANT PARCEL TAX",
    "VPT BERKELEY",
]
VPT_MARKERS = [MEAS_W_MARKER] + MEAS_M_MARKERS

MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 1.5
# Allow tuning via environment variables; fall back to safe defaults.
REQUEST_DELAY_SEC = float(os.getenv("VPT_REQUEST_DELAY_SEC", "0.05"))  # polite pacing between requests
MAX_WORKERS = int(os.getenv("VPT_MAX_WORKERS", "8"))

# Adaptive throttling state (best-effort, process-wide)
_slow_mode = False
_slow_mode_multiplier = 1.0
CHROME_PATH = "/usr/bin/google-chrome"


def fetch_text(url: str) -> str:
    """Fetch a URL with basic retry and adaptive throttling.

    If we start seeing HTTP 429/503 responses, we:
    - Sleep longer before retrying this request.
    - Enable "slow mode" for the rest of the run, which multiplies
      the polite REQUEST_DELAY_SEC between successful calls.
    """
    global _slow_mode, _slow_mode_multiplier

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", "replace")
                # Base delay, scaled if we've previously been rate-limited.
                delay = REQUEST_DELAY_SEC * _slow_mode_multiplier
                if delay > 0:
                    time.sleep(delay)
                return text
        except HTTPError as exc:
            status = getattr(exc, "code", None)
            # Treat 429 / 503 as rate limiting and slow down aggressively.
            if status in (429, 503):
                print(
                    f"Rate-limit detected (HTTP {status}) on {url} "
                    "- backing off and slowing scan."
                )
                _slow_mode = True
                # Increase delay multiplier (cap at a reasonable ceiling)
                _slow_mode_multiplier = min(_slow_mode_multiplier * 2.0, 8.0)
                # Long backoff before retrying this request
                time.sleep(30)
            else:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(RETRY_BACKOFF_SEC * attempt)
        except URLError as exc:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SEC * attempt)
    return ""


def get_latest_bill_info(apn: str) -> tuple[str | None, int | None]:
    html_text = fetch_text(ACCOUNT_SUMMARY + apn)
    # Extract view-bill links and pick the highest rollYear
    links = re.findall(r'href="([^"]+view-bill[^"]+)"', html_text)
    if not links:
        return None, None
    best_link = None
    best_year = -1
    for link in links:
        link = html.unescape(link)
        m = re.search(r"rollYear=([0-9]{4})", link)
        year = int(m.group(1)) if m else -1
        if year > best_year:
            best_year = year
            best_link = link
    if not best_link:
        return None, None
    return BASE_URL + best_link, (best_year if best_year > 0 else None)


def _is_bill_delinquent(html_text: str, debug_apn: str | None = None) -> bool:
    """
    Detect if bill HTML indicates actual tax delinquency (not boilerplate).
    Uses multiple patterns to match Alameda County bill wording. Set
    VPT_DEBUG_DELINQUENCY=1 to log near-misses (page has keywords but no pattern matched).
    """
    patterns = [
        r'TOTAL\s+REDEMPTION',
        r'REDEMPTION\s+AMOUNT',
        r'REDEMPTION\s+AMOUNT\s+DUE',
        r'REDEMPTION\s+DUE',
        r'PRIOR\s+YEAR\s+TAXES?\s+\$[\d,]+\.\d{2}',
        r'PRIOR\s+YEAR\s+\$[\d,]+\.\d{2}',
        r'PRIOR\s+YEAR.*?\$[\d,]+\.\d{2}',
        r'DELINQUENT\s+\$[\d,]+',
        r'DELINQUENT\s+AMOUNT\s*:\s*\$[\d,]+',
        r'STATUS\s*:\s*DELINQUENT',
        r'TAX\s+DEFAULTED\s+(?:ON\s+)?\d{1,2}/\d{1,2}/\d{2,4}',
        r'DEFAULTED\s+(?:ON\s+)?\d{1,2}/\d{1,2}/\d{2,4}',
        r'PROPERTY\s+(?:HAS\s+)?DEFAULTED',
        r'AMOUNT\s+DUE\s+FOR\s+REDEMPTION',
        r'TAX\s+DEFAULT\s+REDEMPTION',
    ]
    for pat in patterns:
        if re.search(pat, html_text, re.IGNORECASE | re.DOTALL):
            return True
    if debug_apn and os.getenv("VPT_DEBUG_DELINQUENCY", "").strip().lower() in ("1", "true", "yes"):
        text = re.sub(r'\s+', ' ', html_text)[:600]
        low = text.lower()
        if any(kw in low for kw in ("redemption amount", "prior year", "delinquent", "tax defaulted", "defaulted on")):
            print(f"[delinquency debug] APN {debug_apn}: keywords present but no pattern matched. Snippet: {text!r}...")
    return False


def check_property_taxes(apn: str) -> dict:
    """
    Check property tax status for an APN.
    Returns dict with: has_vpt, is_delinquent, bill_url, roll_year, vpt_marker.
    VPT is only detected for Oakland (MEAS-W) and Berkeley (MEAS-M); other cities have no VPT in this scanner.
    """
    bill_url, roll_year = get_latest_bill_info(apn)
    if not bill_url:
        return {"has_vpt": False, "is_delinquent": False, "bill_url": None, "roll_year": None, "vpt_marker": None}
    
    html_text = fetch_text(bill_url)
    
    # Check for VPT markers
    has_vpt = False
    vpt_marker = None
    for marker in VPT_MARKERS:
        if marker in html_text:
            has_vpt = True
            vpt_marker = marker
            break
    
    is_delinquent = _is_bill_delinquent(html_text, debug_apn=apn)

    return {
        "has_vpt": has_vpt,
        "is_delinquent": is_delinquent,
        "bill_url": bill_url,
        "roll_year": roll_year,
        "vpt_marker": vpt_marker
    }


def check_meas_w(apn: str) -> tuple[bool, str | None, int | None]:
    """Legacy function for compatibility - checks for MEAS-W VPT."""
    result = check_property_taxes(apn)
    return result["has_vpt"], result["bill_url"], result["roll_year"]


def load_cache() -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if CACHE_JSONL.exists():
        with CACHE_JSONL.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                apn = obj.get("apn")
                if apn:
                    # Support both old and new cache formats
                    cache[apn] = {
                        "has_meas_w": obj.get("has_meas_w", obj.get("has_vpt", False)),
                        "has_vpt": obj.get("has_vpt", obj.get("has_meas_w", False)),
                        "is_delinquent": obj.get("is_delinquent", False),
                        "bill_url": obj.get("bill_url"),
                        "roll_year": obj.get("roll_year"),
                        "vpt_marker": obj.get("vpt_marker"),
                    }
    return cache


def append_cache(
    apn: str,
    has_vpt: bool,
    is_delinquent: bool,
    bill_url: str | None,
    roll_year: int | None,
    vpt_marker: str | None = None,
) -> None:
    with CACHE_JSONL.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "apn": apn,
                    "has_meas_w": has_vpt,  # Keep for backward compatibility
                    "has_vpt": has_vpt,
                    "is_delinquent": is_delinquent,
                    "bill_url": bill_url,
                    "roll_year": roll_year,
                    "vpt_marker": vpt_marker,
                }
            )
            + "\n"
        )

def pdf_path_for(apn: str, roll_year: int | None) -> Path:
    year = roll_year or "unknown"
    safe_apn = re.sub(r"[^A-Za-z0-9_-]+", "_", apn)
    return OUTPUT_DIR / f"bill_{safe_apn}_{year}.pdf"


def html_to_text(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_bill_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    def grab(prefix: str) -> str | None:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(prefix):
                return line.replace(prefix, "", 1).strip()
        return None

    parcel = grab("Parcel Number:")
    if parcel:
        fields["parcel_number"] = parcel

    tracer = grab("Tracer Number:")
    if tracer:
        fields["tracer_number"] = tracer

    location = grab("Location of Property:")
    if location:
        fields["location_of_property"] = location

    tax_year = grab("Tax Year:")
    if tax_year:
        fields["tax_year"] = tax_year

    # Last payment date (e.g. "PAID DEC 10, 2025")
    last_payment = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^PAID\s+([A-Z]{3}\s+\d{1,2},\s+\d{4})", line)
        if m:
            last_payment = m.group(1)
    if last_payment:
        fields["last_payment"] = last_payment

    # Delinquent indicator: look for explicit "DELINQUENT" (not "delinquency")
    delinquent = False
    for line in text.splitlines():
        upper = line.upper()
        if "DELINQUENT" in upper and "DELINQUENCY" not in upper:
            delinquent = True
            break
    fields["delinquent"] = "1" if delinquent else "0"

    return fields


def extract_bill_fields_from_html(html_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    # Parcel Number (inside <span class="no-link">)
    m = re.search(r'Parcel Number:</strong>\s*<span[^>]*>\s*([^<]+)', html_text)
    if m:
        fields["parcel_number"] = m.group(1).strip()

    # Tracer Number
    m = re.search(r'Tracer Number:</strong>\s*<span[^>]*>\s*([^<]+)', html_text)
    if m:
        fields["tracer_number"] = m.group(1).strip()

    # Location of Property
    m = re.search(r'Location of Property:</strong>\s*([^<\n]+)', html_text)
    if m:
        fields["location_of_property"] = m.group(1).strip()

    # Tax Year
    m = re.search(r'Tax Year:\s*([0-9]{4}-[0-9]{4})', html_text)
    if m:
        fields["tax_year"] = m.group(1).strip()

    # Last payment date (e.g. "PAID DEC 10, 2025")
    m = re.search(r'PAID\s+([A-Z]{3}\s+\d{1,2},\s+\d{4})', html_text)
    if m:
        fields["last_payment"] = m.group(1)

    # Check for VPT markers
    has_vpt = False
    vpt_marker = None
    for marker in VPT_MARKERS:
        if marker in html_text:
            has_vpt = True
            vpt_marker = marker
            break
    fields["has_vpt"] = "1" if has_vpt else "0"
    fields["vpt_marker"] = vpt_marker or ""

    fields["delinquent"] = "1" if _is_bill_delinquent(html_text) else "0"

    return fields


def init_db(conn=None) -> None:
    """No-op: Supabase schema is managed in cloud."""
    pass


def upsert_db(apn: str, bill_url: str, bill_html: str, row_json: str | None) -> None:
    import db
    city = None
    if row_json:
        try:
            row_data = json.loads(row_json)
            city = row_data.get("CITY", row_data.get("SitusCity", "")).strip().upper()
        except json.JSONDecodeError:
            pass
        db.upsert_parcel(apn, row_json)

    fields = extract_bill_fields_from_html(bill_html)
    raw_text = html_to_text(bill_html)
    db.upsert_bill(
        apn=apn,
        pdf_file=None,
        parcel_number=fields.get("parcel_number"),
        tracer_number=fields.get("tracer_number"),
        location_of_property=fields.get("location_of_property"),
        tax_year=fields.get("tax_year"),
        last_payment=fields.get("last_payment"),
        delinquent=int(fields.get("delinquent") or 0),
        raw_text=raw_text,
        bill_url=bill_url,
        has_vpt=int(fields.get("has_vpt") or 0),
        vpt_marker=fields.get("vpt_marker"),
        city=city,
    )
    db.upsert_result(apn, None)


def find_address_for_apn(apn: str) -> str | None:
    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("APN", "").strip() == apn:
                address = row.get("ADDRESS", row.get("MailingAddress", "")).strip()
                return address or None
    return None


def run_single_apn(apn: str) -> None:
    flagged, bill_url, roll_year = check_meas_w(apn)
    print(f"APN {apn} MEAS-W: {flagged}")
    if not flagged or not bill_url:
        return
    bill_html = fetch_text(bill_url)
    row_json = None
    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("APN", "").strip() == apn:
                row_json = json.dumps(row, ensure_ascii=True)
                break
    upsert_db(apn, bill_url, bill_html, row_json)
    print("Saved bill data to database.")


def backfill_pdfs() -> None:
    apn_to_address: dict[str, str] = {}
    apn_order: list[str] = []
    apn_to_rowjson: dict[str, str] = {}

    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("CITY", row.get("SitusCity", "")).strip().upper() != "OAKLAND":
                continue
            apn = row.get("APN", "").strip()
            address = row.get("ADDRESS", row.get("MailingAddress", "")).strip()
            if not apn:
                continue
            if apn not in apn_to_address:
                apn_to_address[apn] = address
                apn_order.append(apn)
                apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)

    cache = load_cache()

    total = len(apn_order)
    processed = 0
    hits = 0

    to_process = [apn for apn in apn_order if apn not in cache]

    to_download: list[tuple[str, str | None, int | None]] = []

    # Gather cached positives, resolve bill URLs if missing
    for apn, entry in cache.items():
        processed += 1
        if entry.get("has_meas_w"):
            bill_url = entry.get("bill_url")
            roll_year = entry.get("roll_year")
            if not bill_url:
                bill_url, roll_year = get_latest_bill_info(apn)
            to_download.append((apn, bill_url, roll_year))

    # Fetch bill HTML in parallel
    def _fetch(item: tuple[str, str | None, int | None]) -> bool:
        apn, bill_url, _ = item
        if not bill_url:
            return False
        bill_html = fetch_text(bill_url)
        upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))
        return True

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_fetch, item): item for item in to_download}
        for future in as_completed(futures):
            try:
                if future.result():
                    hits += 1
            except Exception:
                continue

    print(f"Backfill complete. PDFs written: {hits}")


def retry_missing_pdfs() -> None:
    apn_to_rowjson: dict[str, str] = {}
    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apn = row.get("APN", "").strip()
            if not apn:
                continue
            if apn not in apn_to_rowjson:
                apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)

    cache = load_cache()
    missing: list[tuple[str, str | None, int | None]] = []
    for apn, entry in cache.items():
        if not entry.get("has_meas_w"):
            continue
        bill_url = entry.get("bill_url")
        roll_year = entry.get("roll_year")
        if not bill_url:
            bill_url, roll_year = get_latest_bill_info(apn)
        if bill_url:
            missing.append((apn, bill_url, roll_year))

    if not missing:
        print("No missing PDFs to retry.")
        return

    hits = 0
    def _fetch(item: tuple[str, str | None, int | None]) -> bool:
        apn, bill_url, _ = item
        if not bill_url:
            return False
        bill_html = fetch_text(bill_url)
        upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_fetch, item): item for item in missing}
        for future in as_completed(futures):
            try:
                if future.result():
                    hits += 1
            except Exception:
                continue

    print(f"Retry complete. PDFs written: {hits} (missing: {len(missing)})")


TARGET_CITY: str | None = None  # Set via --city argument


def main(city: str | None = None) -> None:
    global TARGET_CITY
    if city:
        TARGET_CITY = city.upper()
    
    apn_to_address: dict[str, str] = {}
    apn_order: list[str] = []
    apn_to_rowjson: dict[str, str] = {}

    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_city = row.get("CITY", row.get("SitusCity", "")).strip().upper()
            # Filter by target city if specified
            if TARGET_CITY and row_city != TARGET_CITY:
                continue
            apn = row.get("APN", "").strip()
            address = row.get("ADDRESS", row.get("MailingAddress", "")).strip()
            if not apn:
                continue
            if apn not in apn_to_address:
                apn_to_address[apn] = address
                apn_order.append(apn)
                apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)

    cache = load_cache()

    total = len(apn_order)
    if total == 0:
        print(f"No parcels found for city: {TARGET_CITY or 'ALL'}")
        return
    
    # APNs that are already in the cache will NOT be re-scanned.
    # They may still be synced into the DB by other utilities
    # (e.g. ensure_cache_in_db), but this main scanner only
    # hits the tax site for brand‑new APNs.
    cached_apns_in_city = {apn for apn in apn_order if apn in cache}
    to_process = [apn for apn in apn_order if apn not in cache]

    print(f"Scanning {total} parcels for city: {TARGET_CITY or 'ALL'}")
    print(f"  - {len(cached_apns_in_city)} already in cache; {len(to_process)} to scan")

    # 'processed' counts both cached APNs (already handled in prior runs)
    # and newly scanned APNs, to keep progress logs intuitive.
    processed = len(cached_apns_in_city)
    hits = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_property_taxes, apn): apn for apn in to_process}
        for future in as_completed(futures):
            apn = futures[future]
            processed += 1
            try:
                result = future.result()
            except Exception:
                # Leave un-cached so it can be retried later.
                continue

            has_vpt = result["has_vpt"]
            is_delinquent = result["is_delinquent"]
            bill_url = result["bill_url"]
            roll_year = result["roll_year"]
            vpt_marker = result["vpt_marker"]

            append_cache(apn, has_vpt, is_delinquent, bill_url, roll_year, vpt_marker)
            
            # Save to DB if VPT or delinquent
            if (has_vpt or is_delinquent) and bill_url:
                bill_html = fetch_text(bill_url)
                upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))
                hits += 1

            if processed % 100 == 0:
                print(f"[{TARGET_CITY or 'ALL'}] Processed {processed}/{total} APNs; VPT/Delinquent: {hits}")
    
    print(f"[{TARGET_CITY or 'ALL'}] Scan complete. Total: {total}, VPT/Delinquent found: {hits}")


def fix_missing_fields() -> None:
    """Re-fetch bill HTML for DB entries with missing location_of_property."""
    import db
    apn_to_rowjson: dict[str, str] = {}
    with INPUT_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apn = row.get("APN", "").strip()
            if not apn:
                continue
            if apn not in apn_to_rowjson:
                apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)

    rows = db.get_bills_missing_location()

    if not rows:
        print("No entries with missing fields.")
        return

    print(f"Found {len(rows)} entries with missing fields. Re-fetching...")
    hits = 0
    for apn, bill_url in rows:
        if not bill_url:
            bill_url, _ = get_latest_bill_info(apn)
        if not bill_url:
            continue
        bill_html = fetch_text(bill_url)
        upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))
        hits += 1

    print(f"Fixed {hits} entries.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg == "--backfill-only":
            backfill_pdfs()
        elif arg == "--retry-missing":
            retry_missing_pdfs()
        elif arg == "--fix-missing":
            fix_missing_fields()
        elif arg == "--city" and len(sys.argv) > 2:
            city = sys.argv[2].strip()
            main(city=city)
        elif arg.startswith("--city="):
            city = arg.split("=", 1)[1].strip()
            main(city=city)
        else:
            run_single_apn(arg)
    else:
        main()

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
INPUT_CSV = BASE_DIR / "parcels.csv"
LEGACY_INPUT_CSV = BASE_DIR / "Parcels_5567367248157875843.csv"
CACHE_JSONL = BASE_DIR / "measw_cache.jsonl"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from geo_utils import derive_latlng  # noqa: E402

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
OUTPUT_DIR = BASE_DIR / "bills"
CDP_URL = os.environ.get("CDP_URL", "").strip()
_stop_requested = False


def request_stop() -> None:
    """Request the running scanner to stop gracefully."""
    global _stop_requested
    _stop_requested = True


def is_stop_requested() -> bool:
    """Check if stop has been requested."""
    return _stop_requested


def get_browser(playwright_instance, cdp_url: str | None = None):
    """
    Get browser for scanning. Defaults to an isolated headless Chrome/Chromium
    process so it runs quietly in the background without stealing OS focus or
    mouse cursor from the user.
    If CDP_URL is explicitly configured, it connects via CDP.
    Returns (browser, is_cdp).
    """
    url = cdp_url if cdp_url is not None else CDP_URL
    if url:
        try:
            browser = playwright_instance.chromium.connect_over_cdp(url)
            print(f"Connected to Chrome CDP session at {url}")
            return browser, True
        except Exception as e:
            print(f"Could not connect to Chrome CDP at {url} ({e}); using headless browser")

    executable = CHROME_PATH if os.path.exists(CHROME_PATH) else None
    browser = playwright_instance.chromium.launch(
        headless=True,
        executable_path=executable,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    return browser, False


def get_input_csv_path(city: str | None = None) -> Path:
    if city:
        city_slug = re.sub(r"[^a-zA-Z0-9_-]", "", city.strip().lower())
        city_csv = BASE_DIR / f"{city_slug}.csv"
        if city_csv.exists():
            return city_csv

    configured_path = os.environ.get("PARCELS_CSV_PATH", "").strip()
    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        if path.exists():
            return path
    if INPUT_CSV.exists():
        return INPUT_CSV
    oakland_csv = BASE_DIR / "oakland.csv"
    if oakland_csv.exists():
        return oakland_csv
    return LEGACY_INPUT_CSV


def _safe_url(url: str) -> str:
    import urllib.parse
    parts = urllib.parse.urlsplit(url.strip())
    path = urllib.parse.quote(parts.path)
    query = urllib.parse.quote(parts.query, safe="=&?+")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def fetch_text(url: str) -> str:
    """Fetch a URL with basic retry, safe URL quoting, and adaptive throttling."""
    global _slow_mode, _slow_mode_multiplier

    safe_url = _safe_url(url)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", "replace")
                delay = REQUEST_DELAY_SEC * _slow_mode_multiplier
                if delay > 0:
                    time.sleep(delay)
                return text
        except HTTPError as exc:
            status = getattr(exc, "code", None)
            if status in (429, 503):
                print(
                    f"Rate-limit detected (HTTP {status}) on {url} "
                    "- backing off and slowing scan."
                )
                _slow_mode = True
                _slow_mode_multiplier = min(_slow_mode_multiplier * 2.0, 8.0)
                time.sleep(30)
            else:
                if attempt == MAX_RETRIES:
                    return ""
                time.sleep(RETRY_BACKOFF_SEC * attempt)
        except Exception:
            if attempt == MAX_RETRIES:
                return ""
            time.sleep(RETRY_BACKOFF_SEC * attempt)
    return ""


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


def check_bill_vpt(bill_html: str, city: str | None = None) -> tuple[bool, str | None]:
    """
    Check bill HTML for Oakland Measure W or Berkeley Measure M VPT charges.
    Eliminates false positives from large assessments (e.g. $756,000.00).
    """
    if not bill_html:
        return False, None

    city_upper = (city or "").strip().upper()

    # 1. Direct explicit text markers
    explicit_markers = [
        "MEAS-W OAKLAND VPT",
        "MEAS-W",
        "MEAS-M BERKELEY",
        "MEAS-M",
        "MEAS M BERKELEY",
        "MEAS M",
        "BERKELEY VPT",
        "VACANT PROPERTY TAX",
        "VACANT PARCEL TAX",
        "VPT BERKELEY",
    ]
    for marker in explicit_markers:
        if marker in bill_html:
            return True, marker

    # 2. Check table.fixed-charges specifically for Berkeley Measure M charges
    fixed_charges_match = re.search(
        r'<table[^>]*class=["\'][^"\']*fixed-charges[^"\']*["\'][^>]*>(.*?)</table>',
        bill_html,
        re.DOTALL | re.IGNORECASE,
    )
    if fixed_charges_match:
        table_html = fixed_charges_match.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
        for r in rows:
            for marker in explicit_markers:
                if marker in r:
                    return True, marker
            if city_upper == "BERKELEY" or not city_upper:
                if re.search(r'(?<![\d,])\$\s*(?:3,000|6,000)\.00(?!\d)', r):
                    desc_match = re.search(r'<td[^>]*>(.*?)</td>', r, re.DOTALL | re.IGNORECASE)
                    desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""
                    if "PARAMEDIC" not in desc.upper():
                        return True, f"BERKELEY VPT {desc} $6,000.00".strip()

    return False, None


def check_property_taxes_with_page(apn: str, page, city: str | None = None) -> dict:
    """
    Check property tax status using an existing Playwright/CDP page.
    """
    clean_apn = re.sub(r"\s+", " ", (apn or "")).strip()
    if not clean_apn:
        return {
            "has_vpt": False,
            "is_delinquent": False,
            "bill_url": None,
            "roll_year": None,
            "vpt_marker": None,
            "bill_html": "",
        }

    try:
        # Navigate to search page if not already there
        if not page.url.startswith("https://propertytax.alamedacountyca.gov/search"):
            page.goto("https://propertytax.alamedacountyca.gov/search", timeout=15000)

        # Switch to Parcel Number search via DOM click to avoid hijacking cursor
        page.evaluate("""() => {
            const toggle = document.querySelector('#toggleParcel');
            if (toggle) toggle.click();
        }""")
        page.wait_for_timeout(200)

        # Populate APN inputs and submit search via DOM events (zero mouse/pointer hijacking)
        page.evaluate("""(cleanApn) => {
            const disp = document.querySelector('#displayApn');
            if (disp) {
                disp.value = cleanApn;
                disp.dispatchEvent(new Event('input', { bubbles: true }));
                disp.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const hidden = document.querySelector('#apn');
            if (hidden) {
                hidden.value = cleanApn;
            }
            const search = document.querySelector('#searchButton');
            if (search) search.click();
        }""", clean_apn)

        # Wait for account summary or results
        try:
            page.wait_for_url("**/account-summary*", timeout=10000)
        except Exception:
            pass

        try:
            page.wait_for_selector('form[id^="view-bill-form"]', state="attached", timeout=6000)
        except Exception:
            pass

        forms = page.query_selector_all('form[id^="view-bill-form"]')
        if not forms:
            return {
                "has_vpt": False,
                "is_delinquent": False,
                "bill_url": None,
                "roll_year": None,
                "vpt_marker": None,
                "bill_html": "",
            }

        # Select highest rollYear SEC bill (or highest rollYear)
        best_form = forms[0]
        best_year = -1
        for f in forms:
            ry = f.query_selector('input[name="rollYear"]')
            tt = f.query_selector('input[name="taxType"]')
            val = ry.get_attribute("value") if ry else None
            tax_type = tt.get_attribute("value") if tt else ""
            y = int(val) if val and val.isdigit() else 0
            if tax_type == "SEC":
                y += 10000
            if y > best_year:
                best_year = y
                best_form = f

        ry = best_form.query_selector('input[name="rollYear"]')
        val = ry.get_attribute("value") if ry else None
        roll_year = int(val) if val and val.isdigit() else None

        with page.expect_navigation(timeout=10000):
            best_form.evaluate("f => f.submit()")

        bill_url = page.url
        bill_html = page.content()

        has_vpt, vpt_marker = check_bill_vpt(bill_html, city)
        is_delinquent = _is_bill_delinquent(bill_html, debug_apn=clean_apn)

        return {
            "has_vpt": has_vpt,
            "is_delinquent": is_delinquent,
            "bill_url": bill_url,
            "roll_year": roll_year,
            "vpt_marker": vpt_marker,
            "bill_html": bill_html,
        }
    except Exception as exc:
        print(f"Error checking APN {clean_apn}: {exc}")
        return {
            "has_vpt": False,
            "is_delinquent": False,
            "bill_url": None,
            "roll_year": None,
            "vpt_marker": None,
            "bill_html": "",
        }


def check_property_taxes(apn: str, page=None, city: str | None = None) -> dict:
    """
    Check property tax status for an APN.
    Returns dict with: has_vpt, is_delinquent, bill_url, roll_year, vpt_marker, bill_html.
    """
    if page is not None:
        return check_property_taxes_with_page(apn, page, city=city)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser, is_cdp = get_browser(p)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                p_page = context.new_page()
                try:
                    return check_property_taxes_with_page(apn, p_page, city=city)
                finally:
                    p_page.close()
            finally:
                browser.close()
    except Exception as exc:
        print(f"Browser check failed for {apn}: {exc}")
        return {
            "has_vpt": False,
            "is_delinquent": False,
            "bill_url": None,
            "roll_year": None,
            "vpt_marker": None,
            "bill_html": "",
        }


def get_latest_bill_info(apn: str) -> tuple[str | None, int | None]:
    result = check_property_taxes(apn)
    return result["bill_url"], result["roll_year"]


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


def extract_bill_fields_from_html(html_text: str, city: str | None = None) -> dict[str, str]:
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

    # Check for VPT markers (Oakland Measure W & Berkeley Measure M)
    has_vpt, vpt_marker = check_bill_vpt(html_text, city=city)
    fields["has_vpt"] = "1" if has_vpt else "0"
    fields["vpt_marker"] = vpt_marker or ""

    fields["delinquent"] = "1" if _is_bill_delinquent(html_text) else "0"

    return fields


def init_db(conn=None) -> None:
    """No-op: Supabase schema is managed in cloud."""
    pass


def _zip_from_row_json(row_json: str | None) -> str | None:
    """ZIP from a county parcel row; current files use ZIPCODE, older ones SitusZip."""
    if not row_json:
        return None
    try:
        row_data = json.loads(row_json)
    except (TypeError, json.JSONDecodeError):
        return None
    zip_code = str(row_data.get("ZIPCODE") or row_data.get("SitusZip") or "").strip()
    return zip_code or None


def upsert_db(
    apn: str,
    bill_url: str,
    bill_html: str,
    row_json: str | None,
    power_status: str | None = None,
    added_at: str | None = None,
) -> None:
    import db
    city = None
    lat = lng = None
    if row_json:
        try:
            row_data = json.loads(row_json)
            city = row_data.get("CITY", row_data.get("SitusCity", "")).strip().upper()
        except json.JSONDecodeError:
            pass
        # Derive coordinates here rather than in a separate backfill pass: the
        # parcel centroid is already in hand, and bills.lat/lng feed the
        # bills_set_geom trigger that scout_next()'s KNN ordering depends on.
        latlng = derive_latlng(row_json)
        if latlng:
            lat, lng = latlng
        db.upsert_parcel(apn, row_json)

    fields = extract_bill_fields_from_html(bill_html, city=city)
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
        power_status=power_status,
        has_vpt=int(fields.get("has_vpt") or 0),
        vpt_marker=fields.get("vpt_marker"),
        city=city,
        lat=lat,
        lng=lng,
        zip_code=_zip_from_row_json(row_json),
        added_at=added_at,
    )
    db.upsert_result(apn, None)


def find_address_for_apn(apn: str) -> str | None:
    with get_input_csv_path().open(newline="", encoding="utf-8", errors="replace") as f:
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
    with get_input_csv_path().open(newline="", encoding="utf-8", errors="replace") as f:
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

    with get_input_csv_path().open(newline="", encoding="utf-8", errors="replace") as f:
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
    with get_input_csv_path().open(newline="", encoding="utf-8", errors="replace") as f:
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
    global TARGET_CITY, _stop_requested
    _stop_requested = False
    if city:
        TARGET_CITY = city.strip().upper()

    csv_path = get_input_csv_path(city=TARGET_CITY)
    if not csv_path.exists():
        print(f"Parcel CSV not found at {csv_path}")
        return

    apn_to_address: dict[str, str] = {}
    apn_order: list[str] = []
    apn_to_rowjson: dict[str, str] = {}

    with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_city = row.get("CITY", row.get("SitusCity", "")).strip().upper()
            # Filter by target city if specified and city field is present
            if TARGET_CITY and row_city and row_city != TARGET_CITY:
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

    cached_apns_in_city = {apn for apn in apn_order if apn in cache}
    to_process = [apn for apn in apn_order if apn not in cache]

    print(f"Scanning {total} parcels for city: {TARGET_CITY or 'ALL'}")
    print(f"  - {len(cached_apns_in_city)} already in cache; {len(to_process)} to scan")

    if not to_process:
        print(f"All {total} parcels for {TARGET_CITY or 'ALL'} are already cached.")
        return

    processed = len(cached_apns_in_city)
    hits = 0

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, is_cdp = get_browser(p)
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            try:
                for apn in to_process:
                    if _stop_requested:
                        print(f"[{TARGET_CITY or 'ALL'}] Stop requested. Ending scan.")
                        break

                    processed += 1
                    try:
                        if page.is_closed():
                            page = context.new_page()
                        result = check_property_taxes_with_page(apn, page, city=TARGET_CITY)
                    except Exception as e:
                        print(f"[{TARGET_CITY or 'ALL'}] Error scanning {apn}: {e}")
                        continue

                    has_vpt = result["has_vpt"]
                    is_delinquent = result["is_delinquent"]
                    bill_url = result["bill_url"]
                    roll_year = result["roll_year"]
                    vpt_marker = result["vpt_marker"]
                    bill_html = result.get("bill_html", "")

                    append_cache(apn, has_vpt, is_delinquent, bill_url, roll_year, vpt_marker)

                    if (has_vpt or is_delinquent) and bill_url:
                        if not bill_html:
                            bill_html = fetch_text(bill_url)
                        upsert_db(apn, bill_url, bill_html, apn_to_rowjson.get(apn))
                        hits += 1

                    if processed % 10 == 0:
                        print(f"[{TARGET_CITY or 'ALL'}] Processed {processed}/{total} APNs; VPT/Delinquent: {hits}")
            finally:
                if not page.is_closed():
                    page.close()
        finally:
            browser.close()

    print(f"[{TARGET_CITY or 'ALL'}] Scan complete. Total: {total}, VPT/Delinquent found: {hits}")


def fix_missing_fields() -> None:
    """Re-fetch bill HTML for DB entries with missing location_of_property."""
    import db
    apn_to_rowjson: dict[str, str] = {}
    with get_input_csv_path().open(newline="", encoding="utf-8", errors="replace") as f:
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

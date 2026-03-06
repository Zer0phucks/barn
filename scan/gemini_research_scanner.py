#!/usr/bin/env python3
"""
Gemini Deep Research Scanner - Researches property ownership, contact info, and
public records using Google Gemini. Pre-fetches CyberBackgroundChecks (and similar)
pages via Playwright/curl_cffi; no Google Search tool.
"""
from __future__ import annotations

import asyncio
import atexit
import json
import os
import sys
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# Import db module for database access
try:
    import db
except ImportError:
    # Add parent directory to path if running as script
    sys.path.append(str(Path(__file__).resolve().parent))
    import db

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("Warning: google-genai not installed. Run: pip install google-genai")

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    print("Warning: cloudscraper not installed, improved fetching disabled.")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests not installed; HTTP fetching will be limited.")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("Warning: beautifulsoup4 not installed; HTML parsing will be basic.")

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: playwright not installed; run 'pip install playwright' and 'playwright install chromium'.")

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Load environment variables from the correct path
BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "research_reports"
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

# Ensure reports directory exists
REPORTS_DIR.mkdir(exist_ok=True)

# Configuration - read API key AFTER loading .env
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
RESEARCH_ENABLED = os.environ.get("VPT_ENABLE_RESEARCH", "true").lower() == "true"
CBC_PERSISTENT_PROFILE_DIR = Path(os.environ.get("CBC_PERSISTENT_PROFILE_DIR", str(BASE_DIR / ".cbc_profile")))
CBC_MANUAL_CHALLENGE = os.environ.get("CBC_MANUAL_CHALLENGE", "false").lower() == "true"
CBC_MANUAL_CHALLENGE_TIMEOUT_SECONDS = max(30, int(os.environ.get("CBC_MANUAL_CHALLENGE_TIMEOUT_SECONDS", "300")))
# For CBC, prefer one persistent browser session before stateless clients.
CBC_PLAYWRIGHT_FIRST = os.environ.get("CBC_PLAYWRIGHT_FIRST", "true").lower() == "true"
# curl_cffi can trigger extra Cloudflare checks; skip for CBC by default.
CBC_SKIP_CURL = os.environ.get("CBC_SKIP_CURL", "true").lower() == "true"
RESEARCH_BETWEEN_PROPERTIES_DELAY_SECONDS = max(
    1.0, float(os.environ.get("RESEARCH_BETWEEN_PROPERTIES_DELAY_SECONDS", "6"))
)

# Research state for tracking progress
research_state = {
    "is_running": False,
    "current_apn": None,
    "queue": [],
    "completed": 0,
    "failed": 0,
    "warning_message": None,
    "last_error": None,
}


class FatalResearchError(RuntimeError):
    """Raised when research must halt instead of continuing with low-quality data."""


_CBC_READY_JS = """
() => {
    const t = (document.title || '').toLowerCase();
    const b = (document.body?.innerText || '').toLowerCase();
    if (t.includes('just a moment')) return false;
    if (b.includes('security verification')) return false;
    if (b.includes('enable javascript and cookies to continue')) return false;
    return b.length > 1200;
}
"""

# One persistent Playwright session for CBC to retain cookies/clearance across requests.
_cbc_lock = threading.Lock()
_cbc_pw = None
_cbc_context = None


def _close_cbc_context() -> None:
    global _cbc_context, _cbc_pw
    try:
        if _cbc_context is not None:
            _cbc_context.close()
    except Exception:
        pass
    finally:
        _cbc_context = None
    try:
        if _cbc_pw is not None:
            _cbc_pw.stop()
    except Exception:
        pass
    finally:
        _cbc_pw = None


atexit.register(_close_cbc_context)


def ensure_research_columns() -> None:
    """No-op: Supabase bills table already has research columns."""
    pass


def get_property_info(apn: str) -> dict[str, Any] | None:
    """Get property information from database."""
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


def update_research_status(apn: str, status: str, report_path: str | None = None) -> None:
    """Update research status for a property."""
    now = datetime.now().isoformat()
    db.update_bill_research(apn, status, research_report_path=report_path, research_updated_at=now)


def _html_to_text(html: str, max_chars: int) -> str:
    """Extract visible text from HTML using BeautifulSoup or regex."""
    if BS4_AVAILABLE:
        # CBC pages often place the useful records after 300KB, so keep a large cap.
        if len(html) > 1_500_000:
            html = html[:1_500_000] + "\n[... truncated ...]"
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
    else:
        # Regex fallback is more memory-sensitive; trim aggressively.
        if len(html) > 300_000:
            html = html[:300_000] + "\n[... truncated ...]"
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if text else ""


def _is_challenge_page(content: str) -> bool:
    """Detect common bot/challenge pages that do not contain real record data."""
    if not content:
        return True
    lowered = content.lower()
    markers = (
        "just a moment...",
        "enable javascript and cookies to continue",
        "challenge-platform",
        "/cdn-cgi/challenge-platform",
        "performing security verification",
        "this website uses a security service to protect itself",
        "this website uses a security service to protect against malicious bots",
        "verify you are human",
        "cf-browser-verification",
    )
    return any(marker in lowered for marker in markers)


def _is_cbc_url(url: str) -> bool:
    return "cyberbackgroundchecks.com" in (url or "").lower()


def _get_or_create_cbc_context() -> Any | None:
    """Create (or reuse) one persistent Chromium context for CBC fetches."""
    global _cbc_pw, _cbc_context
    if not PLAYWRIGHT_AVAILABLE:
        return None
    if _cbc_context is not None:
        return _cbc_context

    CBC_PERSISTENT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    display_available = bool(os.environ.get("DISPLAY"))
    # Headed mode only when user opts into manual challenge solving.
    headless = (not display_available) or (not CBC_MANUAL_CHALLENGE)
    _cbc_pw = sync_playwright().start()
    _cbc_context = _cbc_pw.chromium.launch_persistent_context(
        user_data_dir=str(CBC_PERSISTENT_PROFILE_DIR),
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 900},
        locale="en-US",
    )
    try:
        _cbc_context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass
    return _cbc_context


def _fetch_with_curl_cffi(url: str, max_chars: int = 15000) -> str:
    """
    Fetch URL using curl_cffi with browser TLS impersonation. Often bypasses Cloudflare.
    """
    if not CURL_CFFI_AVAILABLE:
        return ""
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    for impersonate in ("chrome120", "chrome116", "safari15_5"):
        try:
            r = curl_requests.get(url, impersonate=impersonate, timeout=25, headers=headers)
            if r.status_code != 200:
                continue
            html = r.text or ""
            if _is_challenge_page(html):
                continue
            text = _html_to_text(html, max_chars)
            if text:
                return text
        except Exception as e:
            print(f"curl_cffi ({impersonate}) error for {url}: {e}")
            continue
    return ""


def _fetch_with_playwright(url: str, max_chars: int = 15000) -> str:
    """
    Fetch URL using Playwright Chromium with stealth-style settings.
    For CyberBackgroundChecks, it tries headed mode first (if DISPLAY exists),
    then falls back to headless.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ""

    if _is_cbc_url(url):
        # CBC path: reuse one persistent browser context to preserve challenge clearance.
        with _cbc_lock:
            try:
                context = _get_or_create_cbc_context()
                if context is None:
                    return ""
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_function(_CBC_READY_JS, timeout=20000)
                except Exception:
                    page.wait_for_timeout(5000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                html = page.content() or ""
                if _is_challenge_page(html):
                    display_available = bool(os.environ.get("DISPLAY"))
                    if CBC_MANUAL_CHALLENGE and display_available:
                        try:
                            page.bring_to_front()
                        except Exception:
                            pass
                        print(
                            "CBC challenge detected. Solve it in the browser window once. "
                            f"Waiting up to {CBC_MANUAL_CHALLENGE_TIMEOUT_SECONDS}s..."
                        )
                        try:
                            page.wait_for_function(_CBC_READY_JS, timeout=CBC_MANUAL_CHALLENGE_TIMEOUT_SECONDS * 1000)
                        except Exception:
                            pass
                        # Cloudflare challenge may switch page handles.
                        if page.is_closed():
                            if context.pages:
                                page = context.pages[-1]
                            else:
                                page = context.new_page()
                                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        html = page.content() or ""
                if _is_challenge_page(html):
                    print(f"Playwright (persistent CBC session): challenge page for {url}")
                    return ""
                text = _html_to_text(html, max_chars)
                return text if text else ""
            except Exception as e:
                print(f"Playwright fetch error (persistent CBC session) for {url}: {e}")
                _close_cbc_context()
                return ""

    # Non-CBC path: short-lived context is fine.
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 900},
                locale="en-US",
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            html = page.content()
            context.close()
            browser.close()
        if _is_challenge_page(html):
            return ""
        text = _html_to_text(html or "", max_chars)
        return text if text else ""
    except Exception as e:
        print(f"Playwright fetch error for {url}: {e}")
        return ""


def fetch_url_content(url: str, max_chars: int = 15000) -> str:
    """
    Fetch text from a URL. Tries curl_cffi (TLS impersonation) first, then
    Playwright (real browser), then cloudscraper/requests.
    """
    if not url or not url.startswith("http"):
        return ""

    is_cbc = _is_cbc_url(url)

    # For CBC, prefer one persistent browser session over stateless HTTP clients.
    if is_cbc and CBC_PLAYWRIGHT_FIRST and PLAYWRIGHT_AVAILABLE:
        text = _fetch_with_playwright(url, max_chars)
        if text:
            return text
        print(f"Playwright returned no content for {url}, trying fallback methods")

    # 1) curl_cffi: fast, often bypasses Cloudflare via TLS impersonation
    if CURL_CFFI_AVAILABLE and not (is_cbc and CBC_SKIP_CURL):
        text = _fetch_with_curl_cffi(url, max_chars)
        if text:
            return text

    # 2) Playwright: real browser, handles JS challenges
    if PLAYWRIGHT_AVAILABLE and not (is_cbc and CBC_PLAYWRIGHT_FIRST):
        text = _fetch_with_playwright(url, max_chars)
        if text:
            return text
        print(f"Playwright returned no content for {url}, trying HTTP fallback")

    if not CLOUDSCRAPER_AVAILABLE and not REQUESTS_AVAILABLE:
        return ""

    try:
        client = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False}) if CLOUDSCRAPER_AVAILABLE else requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
        for attempt in range(2):
            try:
                response = client.get(url, timeout=25, headers=headers)
            except Exception as req_err:
                print(f"Request error {url} (attempt {attempt + 1}/2): {req_err}")
                continue
            if response.status_code != 200:
                continue
            html = response.text or ""
            if _is_challenge_page(html):
                continue
            text = _html_to_text(html, max_chars)
            if text:
                return text
        if _is_cbc_url(url):
            print("CBC fetch note: request blocked after all methods (curl/playwright/http).")
        return ""
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""


def build_research_prompt(
    prop_info: dict[str, Any],
    prop_search_content: str | None = None,
    mail_search_content: str | None = None,
) -> str:
    """Build the research prompt for Gemini. Optionally pass pre-fetched URL content (e.g. from asyncio.to_thread)."""
    address = prop_info.get("location_of_property", "")
    parcel_data = prop_info.get("parcel_data", {})
    
    situs_address = parcel_data.get("SitusAddress", "")
    situs_city = parcel_data.get("SitusCity", "")
    situs_zip = parcel_data.get("SitusZip", "")
    apn = prop_info.get("apn", "")
    
    # Build full address
    full_address = address or situs_address
    if situs_city:
        full_address += f", {situs_city}"
    if situs_zip:
        full_address += f" {situs_zip}"
    
    # Get Search URLs
    property_search_url = prop_info.get("property_search_url", "Not available")
    mailing_search_url = prop_info.get("mailing_search_url", "Not available")

    # Use pre-fetched content if provided; otherwise fetch here (sync path; avoid from async).
    if prop_search_content is None and property_search_url and str(property_search_url).startswith("http"):
        print(f"Fetching content from Property URL: {property_search_url}")
        prop_search_content = fetch_url_content(property_search_url)
    if mail_search_content is None and mailing_search_url and str(mailing_search_url).startswith("http"):
        print(f"Fetching content from Mailing URL: {mailing_search_url}")
        mail_search_content = fetch_url_content(mailing_search_url)

    prop_search_content = prop_search_content or ""
    mail_search_content = mail_search_content or ""
    fetched_context = ""
    if prop_search_content:
        fetched_context += (
            f"\n### Extracted Content from Property Search ({property_search_url}):\n"
            f"{prop_search_content}\n"
        )
    if mail_search_content:
        fetched_context += (
            f"\n### Extracted Content from Mailing Search ({mailing_search_url}):\n"
            f"{mail_search_content}\n"
        )

    fallback_instruction = ""
    if not fetched_context:
        fallback_instruction = """
**NOTE**: No content could be pre-fetched from the CyberBackgroundChecks URLs.
Base your report only on the Target Property and Research Resources above and any
general knowledge; do not invent or assume data from those URLs.
"""

    prompt = f"""Conduct deep research on the following property and provide a comprehensive report.

## Target Property
- **Address**: {full_address}
- **APN**: {apn}
- **City**: {situs_city or prop_info.get("city", "")}
- **State**: California

## Research Resources (High Priority)
Please use these specific search URLs as primary starting points for your research:
- **Property Owner Search**: {property_search_url}
- **Mailing Address Search**: {mailing_search_url}

## PRE-FETCHED CONTENT
{fallback_instruction}
{fetched_context}

## CRITICAL RESEARCH GOALS
You must prioritize the following three objectives above all else:

1.  **DETERMINE VACANCY STATUS**: 
    - Assess with HIGH PREJUDICE. Look for any and all indicators that the property is vacant, abandoned, or neglected.
    - Check for code enforcement violations, board-up notices, overgrown vegetation complaints, or "zombie property" lists. 
    - **Deliverable**: A clear "Likely Vacant", "Likely Occupied", or "Unknown" verdict with supporting evidence.

2.  **IDENTIFY LEGAL OWNER**: 
    - Confirm the current legal owner(s).
    - If held in an LLC or Trust, dig deeper to find the actual human beneficiaries or signing officers.
    - **Deliverable**: Validated Name(s) of the true owner(s).

3.  **OWNER CONTACT EXTRACTION**:
    - If held in an LLC or Trust, dig deeper to find the actual human beneficiaries or signing officers.
    - **Deliverable**: Validated Name(s) of the true owner(s).

3.  **OWNER CONTACT EXTRACTION**:
    - Find the **result most recent** mobile phone number and email address for the identified owner.
    - Correlate the mailing address with the owner's name to find their contact details.
    - Use the pre-fetched content to find names and contact details if available.
    - **Deliverable**: List of phone numbers (labeled Mobile/Landline if possible) and email addresses.

---

## Secondary Research Tasks

### 4. Property Details
- Property type (residential, commercial, vacant land)
- Lot size, square footage, Year built
- Last sale date and price

### 5. Tax & Financial Status
- Current assessed value
- Tax delinquency status (Check for "Default" or "Tax Sale" risks)
- Liens or judgements

### 6. Market Context
- Estimated current value
- Neighborhood trends (gentrifying, declining, stable)

## Format Requirements
- **Executive Summary**: Start with a bulleted summary of the 3 Critical Goals (Vacancy, Owner, Contact).
- **Scoring**: Provide a dedicated section with the following metrics (0-100%) and a brief rationale for each:
    - **Vacancy Confidence**: Likelihood the property is VACANT. High score = High confidence in vacancy.
    - **Ownership Accuracy**: Confidence in the identified owner.
    - **Contact Info Freshness**: Likelihood the contact info is current/reachability.
    - **Overall Score**: The average of the above three scores.
- **Detailed Findings**: Organize remaining data clearly by section.
- **Sources**: Explicitly cite the URLs used, especially if you found contact info.
- **Confidence**: Mark low-confidence findings clearly.
"""

    return prompt


def _require_cbc_prefetch(
    property_search_url: str,
    mailing_search_url: str,
    prop_content: str,
    mail_content: str,
) -> None:
    """Fail fast when no CBC content could be fetched."""
    configured_urls: list[tuple[str, str]] = []
    if property_search_url and str(property_search_url).startswith("http"):
        configured_urls.append(("property", property_search_url))
    if mailing_search_url and str(mailing_search_url).startswith("http"):
        configured_urls.append(("mailing", mailing_search_url))

    if not configured_urls:
        raise FatalResearchError(
            "Deep research halted: no CyberBackgroundChecks URL is configured for this property."
        )

    has_any_content = bool((prop_content or "").strip() or (mail_content or "").strip())
    if has_any_content:
        return

    failed_sources = ", ".join(f"{kind}={url}" for kind, url in configured_urls)
    raise FatalResearchError(
        "Deep research halted: failed to fetch required CyberBackgroundChecks data. "
        f"Sources attempted: {failed_sources}. "
        "If challenges persist, enable CBC_MANUAL_CHALLENGE=true and solve once in the CBC browser session."
    )


async def research_property(apn: str) -> tuple[bool, str]:
    """
    Conduct deep research on a property using Gemini.
    Returns (success, report_content_or_error).
    """
    if not GENAI_AVAILABLE:
        return False, "google-genai package not installed"
    
    if not GOOGLE_API_KEY:
        return False, "GOOGLE_API_KEY not configured in .env"
    
    # Get property info
    prop_info = get_property_info(apn)
    if not prop_info:
        return False, f"Property not found: {apn}"

    # Fetch CBC URLs in this worker thread so the persistent Playwright session is reused.
    property_search_url = prop_info.get("property_search_url") or ""
    mailing_search_url = prop_info.get("mailing_search_url") or ""
    prop_content = ""
    mail_content = ""
    if property_search_url and str(property_search_url).startswith("http"):
        print(f"Fetching content from Property URL: {property_search_url}")
        prop_content = fetch_url_content(property_search_url)
    if (
        mailing_search_url
        and str(mailing_search_url).startswith("http")
        and mailing_search_url == property_search_url
    ):
        mail_content = prop_content
    elif mailing_search_url and str(mailing_search_url).startswith("http"):
        print(f"Fetching content from Mailing URL: {mailing_search_url}")
        mail_content = fetch_url_content(mailing_search_url)

    # CBC data is mandatory for Deep Research quality. Halt immediately if unavailable.
    _require_cbc_prefetch(property_search_url, mailing_search_url, prop_content, mail_content)

    # Build prompt with pre-fetched content
    prompt = build_research_prompt(prop_info, prop_search_content=prop_content, mail_search_content=mail_content)
    
    try:
        # Create client with API key
        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Call Gemini **without** Google Search tools; rely only on the prompt
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )
        
        if not response or not response.text:
            return False, "Empty response from Gemini"
        
        # Build the report
        address = prop_info.get("location_of_property", apn)
        report = f"""# Property Research Report

**Property**: {address}  
**APN**: {apn}  
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{response.text}

---

*This report was generated using Google Gemini with web search grounding. Information should be verified independently before making any decisions.*
"""
        return True, report
        
    except Exception as e:
        return False, f"Gemini API error: {str(e)}"


async def process_research_queue() -> None:
    """Process the research queue."""
    global research_state
    
    while research_state["queue"]:
        apn = research_state["queue"].pop(0)
        research_state["current_apn"] = apn
        
        print(f"Researching property: {apn}")
        update_research_status(apn, "in_progress")
        
        try:
            success, result = await research_property(apn)
        except FatalResearchError as e:
            result = str(e)
            update_research_status(apn, "failed")
            research_state["failed"] += 1
            research_state["warning_message"] = result
            research_state["last_error"] = result
            print(f"  ✗ Fatal: {result}")
            # Stop all remaining queued research to avoid low-quality output.
            research_state["queue"].clear()
            break
        except Exception as e:
            success, result = False, f"Unhandled research error: {e}"
        
        if success:
            # Save report to file
            safe_apn = apn.replace("/", "_").replace("\\", "_")
            report_filename = f"report_{safe_apn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            report_path = REPORTS_DIR / report_filename
            
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(result)
            
            update_research_status(apn, "completed", str(report_path))

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

            research_state["completed"] += 1
            print(f"  ✓ Report saved: {report_path}")
        else:
            update_research_status(apn, "failed")
            research_state["failed"] += 1
            research_state["last_error"] = result
            print(f"  ✗ Failed: {result}")
        
        # Small delay between properties to reduce challenge frequency.
        await asyncio.sleep(RESEARCH_BETWEEN_PROPERTIES_DELAY_SECONDS)
    
    research_state["current_apn"] = None
    research_state["is_running"] = False


def start_research(apns: list[str]) -> bool:
    """Start research for a list of APNs."""
    global research_state
    
    if research_state["is_running"]:
        # Add to existing queue
        research_state["queue"].extend(apns)
        return True
    
    research_state["is_running"] = True
    research_state["queue"] = list(apns)
    research_state["completed"] = 0
    research_state["failed"] = 0
    research_state["warning_message"] = None
    research_state["last_error"] = None
    
    # Run in background thread
    import threading
    def run_async():
        asyncio.run(process_research_queue())
    
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    return True


def get_research_state() -> dict[str, Any]:
    """Get current research state."""
    return {
        "is_running": research_state["is_running"],
        "current_apn": research_state["current_apn"],
        "queue_length": len(research_state["queue"]),
        "completed": research_state["completed"],
        "failed": research_state["failed"],
        "warning_message": research_state["warning_message"],
        "last_error": research_state["last_error"],
        "api_configured": bool(GOOGLE_API_KEY),
        "enabled": RESEARCH_ENABLED,
    }


def get_research_report(apn: str) -> str | None:
    """Get the research report content for an APN."""
    # Use db methods instead of raw SQL/sqlite
    r = db.get_client().table("bills").select("research_report_path").eq("apn", apn).limit(1).execute()
    
    if not r.data or len(r.data) == 0:
        return None
        
    row = r.data[0]
    if not row or not row.get("research_report_path"):
        return None
    
    report_path = Path(row["research_report_path"])
    if not report_path.exists():
        return None
    
    with open(report_path, "r", encoding="utf-8") as f:
        return f.read()


async def test_single_property(apn: str) -> None:
    """Test research on a single property (for command-line testing)."""
    ensure_research_columns()
    
    print(f"Testing deep research for APN: {apn}")
    print("-" * 50)
    
    try:
        success, result = await research_property(apn)
    except FatalResearchError as e:
        success, result = False, str(e)
    except Exception as e:
        success, result = False, f"Unhandled research error: {e}"
    
    if success:
        # Save report
        safe_apn = apn.replace("/", "_").replace("\\", "_")
        report_filename = f"report_{safe_apn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = REPORTS_DIR / report_filename
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(result)
        
        print(f"✓ Report saved to: {report_path}")
        print("\nReport preview:")
        print("-" * 50)
        print(result[:2000] + "..." if len(result) > 2000 else result)
    else:
        print(f"✗ Research failed: {result}")


def main() -> None:
    """Run the research scanner."""
    ensure_research_columns()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test-single" and len(sys.argv) > 2:
            asyncio.run(test_single_property(sys.argv[2]))
            return
        elif sys.argv[1] == "--help":
            print("Usage: python gemini_research_scanner.py [options]")
            print()
            print("Options:")
            print("  --test-single <APN>  Test research on a single property")
            print("  --help               Show this help message")
            return
    
    print("Gemini Research Scanner")
    print("-" * 50)
    print(f"API Key Configured: {'Yes' if GOOGLE_API_KEY else 'No'}")
    print(f"Research Enabled: {RESEARCH_ENABLED}")
    print(f"Reports Directory: {REPORTS_DIR}")
    print()
    print("Use --test-single <APN> to test on a specific property")
    print("Or start research via the web UI at /admin")


if __name__ == "__main__":
    main()

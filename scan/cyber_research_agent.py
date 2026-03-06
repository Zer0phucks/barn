#!/usr/bin/env python3
"""
Property Research Agent using CyberBackgroundChecks.com and Kimi K2.5 (OpenRouter).

Given: property address, mailing address, tax bill summary, vacant tax penalties (y/n),
       PGE power on/off, and optional APN.

The agent:
1. Searches https://www.cyberbackgroundchecks.com (property + mailing address pages).
2. Uses Kimi K2.5 via OpenRouter to analyze results and decide whether to perform
   further searches (e.g. person detail pages).
3. Continues until satisfied or max iterations.
4. Produces a detailed report focused on:
   - Whether the property appears currently vacant of tenants
   - As much contact information for the current owner as possible
   - Content suitable for drafting a personalized first-contact email to the owner.

Requires: OPENROUTER_API_KEY in .env (get key from https://openrouter.ai/settings/keys).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Load .env from project root
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

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = "moonshotai/kimi-k2.5"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MAX_ITERATIONS = 6
REPORTS_DIR = BASE_DIR / "research_reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Reuse existing fetch from gemini_research_scanner (curl_cffi / Playwright / HTTP fallback)
try:
    from gemini_research_scanner import fetch_url_content
except ImportError:
    sys.path.insert(0, str(BASE_DIR))
    from gemini_research_scanner import fetch_url_content


def parse_address_to_parts(full_address: str) -> dict[str, str]:
    """
    Parse a full address string into street, city, zip for CBC URL.
    Handles: "404 SANTA CLARA AVE, OAKLAND, CA 94610" or "404 SANTA CLARA AVE OAKLAND 94610"
    """
    if not (full_address or "").strip():
        return {"street": "", "city": "", "zip": ""}
    s = full_address.strip()
    # Try "..., CITY, STATE ZIP" or "..., CITY ZIP"
    zip_match = re.search(r"\b(\d{5}(?:-\d{4})?)\s*$", s)
    zip_code = zip_match.group(1) if zip_match else ""
    if zip_match:
        s = s[: zip_match.start()].strip().rstrip(",").strip()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2:
        city = parts[-1]
        street = ", ".join(parts[:-1])
    elif len(parts) == 1:
        # "STREET CITY 94610" style - last word might be city if no comma
        tokens = parts[0].split()
        if len(tokens) >= 2 and zip_code:
            city = tokens[-1]
            street = " ".join(tokens[:-1])
        else:
            street = parts[0]
            city = ""
    else:
        street = full_address
        city = ""
    return {"street": street.strip(), "city": city.strip(), "zip": zip_code.strip()}


def build_cyber_url(addr: dict[str, str]) -> str | None:
    """Build cyberbackgroundchecks.com address URL. Requires street and zip."""
    if not (addr.get("street") or "").strip() or not (addr.get("zip") or "").strip():
        return None
    street_slug = addr["street"].replace(" ", "-")
    city_slug = (addr.get("city") or "").replace(" ", "-")
    return f"https://www.cyberbackgroundchecks.com/address/{street_slug}/{city_slug}/{addr['zip']}"


@dataclass
class PropertyResearchInput:
    """Input context for the research agent."""
    property_address: str
    mailing_address: str
    tax_bill_summary: str = ""
    vacant_tax_penalties: bool = False
    pge_power_on: bool = True
    apn: str | None = None

    @classmethod
    def from_apn(cls, apn: str) -> "PropertyResearchInput | None":
        """Build input from database by APN."""
        try:
            import db
        except ImportError:
            sys.path.insert(0, str(BASE_DIR))
            import db
        row = db.get_bill_with_parcel(apn)
        if not row:
            return None
        parcel = row.get("parcel_data") or row.get("row_json") or {}
        if isinstance(parcel, str):
            try:
                parcel = json.loads(parcel)
            except json.JSONDecodeError:
                parcel = {}
        loc = row.get("location_of_property") or parcel.get("SitusAddress") or ""
        situs_city = parcel.get("SitusCity") or row.get("city") or ""
        situs_zip = parcel.get("SitusZip") or ""
        if situs_city:
            loc = f"{loc}, {situs_city}" if loc else situs_city
        if situs_zip:
            loc = f"{loc} {situs_zip}".strip()
        mailing = (
            parcel.get("MailingAddress")
            or f"{parcel.get('MailingAddressStreet', '')} {parcel.get('MailingAddressCityState', '')} {parcel.get('MailingAddressZip', '')}".strip()
        )
        return cls(
            property_address=loc or apn,
            mailing_address=mailing or "",
            tax_bill_summary=row.get("tax_bill_summary") or "",
            vacant_tax_penalties=bool(row.get("has_vpt")),
            pge_power_on=row.get("pge_power_on", True),
            apn=apn,
        )


def call_openrouter(messages: list[dict[str, str]], max_tokens: int = 8192) -> str:
    """Call OpenRouter chat completions (Kimi K2.5). Returns assistant content or raises."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set in .env")
    import urllib.request
    import urllib.error
    body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://github.com/BARN-scan",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {body}")
    choice = (data.get("choices") or [None])[0]
    if not choice:
        raise RuntimeError("OpenRouter returned no choices")
    content = (choice.get("message") or {}).get("content") or ""
    return content.strip()


def extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract first JSON object from markdown code block or raw text."""
    # ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        raw = m.group(1).strip()
    else:
        raw = text.strip()
    # Find first { ... }
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


SYSTEM_PROMPT = """You are a property research analyst. You analyze content from CyberBackgroundChecks.com (and any person detail pages) to:

1. Determine whether the property appears to be currently VACANT of any tenants (high prejudice toward vacancy indicators).
2. Identify the current legal owner(s) and, if held in LLC/Trust, the beneficial owners or officers.
3. Gather as much contact information as possible: phone numbers (mobile preferred), email addresses, mailing address.

You must respond in the exact JSON format requested. Do not invent data; only use information present in the provided page content. If the content is empty or blocked, say so in your analysis."""


def build_analysis_prompt(
    ctx: PropertyResearchInput,
    fetched: list[dict[str, Any]],
    iteration: int,
) -> str:
    """Build user prompt for analysis + next steps."""
    parts = [
        "## Property context",
        f"- Property address: {ctx.property_address}",
        f"- Mailing address: {ctx.mailing_address}",
        f"- Tax bill summary: {ctx.tax_bill_summary or 'Not provided'}",
        f"- Property tax includes vacant property tax penalties: {ctx.vacant_tax_penalties}",
        f"- PGE power status: {'ON' if ctx.pge_power_on else 'OFF'}",
        f"- APN: {ctx.apn or 'N/A'}",
        "",
        "## Fetched page content (CyberBackgroundChecks.com)",
    ]
    for i, item in enumerate(fetched):
        url = item.get("url", "")
        text = (item.get("text") or "")[:20000]
        parts.append(f"\n### Page {i+1}: {url}\n{text or '(no content)'}\n")
    parts.append("""
## Your task
Analyze the content above. Then respond with a single JSON object (no markdown, no extra text) in this exact shape:

{
  "satisfied": true or false,
  "reason": "One sentence: why you are satisfied or what is still missing.",
  "next_searches": [
    { "type": "person_details", "url": "https://www.cyberbackgroundchecks.com/..." }
  ],
  "analysis_summary": "2–4 sentences: vacancy likelihood, owner name(s), contact info found so far."
}

Rules:
- "satisfied": true only if you have a clear owner name and at least one contact (phone or email), and vacancy assessment is clear; otherwise false.
- "next_searches": include only person-detail URLs that appear in the fetched content (e.g. "View Details" links). Do not invent URLs. If no such links exist, use [].
- Limit next_searches to at most 3 URLs per round.
- "analysis_summary": use only information present in the content; say "no data" if a page was empty.
""")
    return "\n".join(parts)


def build_report_prompt(ctx: PropertyResearchInput, all_fetched: list[dict[str, Any]], final_analysis: str) -> str:
    """Build user prompt for final report generation."""
    combined = "\n\n---\n\n".join(
        f"URL: {item.get('url', '')}\n{(item.get('text') or '')[:15000]}"
        for item in all_fetched
    )
    return f"""## Property context
- Property address: {ctx.property_address}
- Mailing address: {ctx.mailing_address}
- Tax bill: {ctx.tax_bill_summary or 'Not provided'}
- Vacant property tax penalties on bill: {ctx.vacant_tax_penalties}
- PGE power: {'ON' if ctx.pge_power_on else 'OFF'}
- APN: {ctx.apn or 'N/A'}

## All fetched CyberBackgroundChecks content
{combined[:60000]}

## Latest analysis summary
{final_analysis}

## Your task
Write a detailed property research report in Markdown with these sections:

1. **Executive summary** – Bullet points: vacancy verdict (Likely Vacant / Likely Occupied / Unknown), owner name(s), and contact info (phones, emails) found.
2. **Vacancy assessment** – Evidence from the data and from context (PGE off, vacant tax penalty, etc.); confidence level.
3. **Owner identification** – Legal owner; if LLC/Trust, beneficial owners or officers.
4. **Owner contact information** – All phones (label Mobile/Landline if evident), emails, mailing address; note freshness/confidence.
5. **Property and tax context** – Brief use of tax bill summary and any property attributes from the pages.
6. **First-contact email draft guidance** – 3–5 bullet points to personalize a first email to the owner (tone, key facts to mention, what to avoid).

End with a **Sources** section listing the URLs used. Do not invent data; mark low-confidence items clearly.
"""


async def fetch_pages(urls: list[str], max_chars: int = 20000) -> list[dict[str, Any]]:
    """Fetch multiple URLs (in threads) and return list of {url, text}."""
    async def one(url: str) -> dict[str, Any]:
        text = await asyncio.to_thread(fetch_url_content, url, max_chars)
        return {"url": url, "text": text or ""}
    results = await asyncio.gather(*[one(u) for u in urls], return_exceptions=True)
    out = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            out.append({"url": urls[i], "text": f"(fetch error: {r})"})
        else:
            out.append(r)
    return out


async def run_agent(ctx: PropertyResearchInput, verbose: bool = True) -> tuple[bool, str]:
    """
    Run the research agent: gather CBC pages, loop with Kimi until satisfied, then generate report.
    Returns (success, report_markdown_or_error).
    """
    if not OPENROUTER_API_KEY:
        return False, "OPENROUTER_API_KEY is not set. Add it to .env (get key from https://openrouter.ai/settings/keys)."

    prop_parts = parse_address_to_parts(ctx.property_address)
    mail_parts = parse_address_to_parts(ctx.mailing_address)
    initial_urls = []
    if build_cyber_url(prop_parts):
        initial_urls.append(build_cyber_url(prop_parts))
    if build_cyber_url(mail_parts) and build_cyber_url(mail_parts) not in initial_urls:
        initial_urls.append(build_cyber_url(mail_parts))
    if not initial_urls:
        return False, "Could not build any CyberBackgroundChecks URL from property or mailing address."

    if verbose:
        print("Initial URLs:", initial_urls)
    all_fetched: list[dict[str, Any]] = []
    fetched_urls: set[str] = set()

    # First fetch
    batch = await fetch_pages(initial_urls)
    for b in batch:
        if b["url"] not in fetched_urls:
            all_fetched.append(b)
            fetched_urls.add(b["url"])
    if verbose:
        print(f"Fetched {len(batch)} pages, total content blocks: {len(all_fetched)}")

    last_analysis = ""
    for iteration in range(MAX_ITERATIONS):
        user_prompt = build_analysis_prompt(ctx, all_fetched, iteration)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await asyncio.to_thread(call_openrouter, messages, max_tokens=4096)
        except Exception as e:
            return False, f"OpenRouter error: {e}"
        last_analysis = response
        obj = extract_json_block(response)
        if not obj:
            # Try using raw response as analysis and assume satisfied to avoid infinite loop
            last_analysis = response
            if verbose:
                print("Could not parse JSON from model; treating as final analysis.")
            break
        analysis_summary = obj.get("analysis_summary") or ""
        satisfied = obj.get("satisfied", False)
        next_searches = obj.get("next_searches") or []
        if verbose:
            print(f"Iteration {iteration + 1}: satisfied={satisfied}, next_searches={len(next_searches)}")
            print(f"Analysis: {analysis_summary[:200]}...")
        last_analysis = analysis_summary
        if satisfied or not next_searches:
            break
        # Fetch only new URLs
        to_fetch = [s["url"] for s in next_searches if s.get("url") and s["url"] not in fetched_urls][:3]
        if not to_fetch:
            break
        batch = await fetch_pages(to_fetch)
        for b in batch:
            if b["url"] not in fetched_urls:
                all_fetched.append(b)
                fetched_urls.add(b["url"])
        if verbose:
            print(f"Fetched {len(batch)} additional pages.")

    # Generate final report
    report_prompt = build_report_prompt(ctx, all_fetched, last_analysis)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nOutput only the Markdown report, no JSON."},
        {"role": "user", "content": report_prompt},
    ]
    try:
        report_body = await asyncio.to_thread(call_openrouter, messages, max_tokens=8192)
    except Exception as e:
        return False, f"OpenRouter report error: {e}"

    safe_apn = (ctx.apn or "unknown").replace("/", "_").replace("\\", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# Property Research Report

**Property**: {ctx.property_address}
**Mailing**: {ctx.mailing_address}
**APN**: {ctx.apn or 'N/A'}
**Generated**: {timestamp}

---

{report_body}

---

*Report generated by Cyber Research Agent (Kimi K2.5 via OpenRouter). Verify important details independently.*
"""
    return True, report


def save_report(report: str, apn: str | None) -> Path:
    """Save report to research_reports/ and return path."""
    safe_apn = (apn or "unknown").replace("/", "_").replace("\\", "_")
    filename = f"report_{safe_apn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = REPORTS_DIR / filename
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Property Research Agent (CyberBackgroundChecks + Kimi K2.5)")
    parser.add_argument("--apn", help="APN to load property/mailing from database")
    parser.add_argument("--property-address", help="Property address (if not using --apn)")
    parser.add_argument("--mailing-address", help="Mailing address (if not using --apn)")
    parser.add_argument("--tax-summary", default="", help="Tax bill summary")
    parser.add_argument("--vacant-penalty", action="store_true", help="Tax bill includes vacant property penalties")
    parser.add_argument("--pge-off", action="store_true", help="PGE power is OFF (default: ON)")
    parser.add_argument("--quiet", action="store_true", help="Less console output")
    args = parser.parse_args()

    if args.apn:
        ctx = PropertyResearchInput.from_apn(args.apn)
        if not ctx:
            print(f"Property not found for APN: {args.apn}")
            sys.exit(1)
        # Override with CLI if provided
        if args.property_address:
            ctx.property_address = args.property_address
        if args.mailing_address:
            ctx.mailing_address = args.mailing_address
    else:
        if not args.property_address or not args.mailing_address:
            print("Provide either --apn or both --property-address and --mailing-address.")
            sys.exit(1)
        ctx = PropertyResearchInput(
            property_address=args.property_address,
            mailing_address=args.mailing_address,
            tax_bill_summary=args.tax_summary,
            vacant_tax_penalties=args.vacant_penalty,
            pge_power_on=not args.pge_off,
        )
    ctx.tax_bill_summary = ctx.tax_bill_summary or args.tax_summary
    ctx.vacant_tax_penalties = ctx.vacant_tax_penalties or args.vacant_penalty
    ctx.pge_power_on = ctx.pge_power_on if not args.pge_off else False

    success, result = asyncio.run(run_agent(ctx, verbose=not args.quiet))
    if success:
        path = save_report(result, ctx.apn)
        print(f"Report saved: {path}")
    else:
        print(f"Error: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()

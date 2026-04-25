#!/usr/bin/env python3
"""
Updates properties that do not have owners listed by checking cyberbackgroundchecks.com
and adding the first resident listed on the property.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Add scan dir to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import db
from cyber_research_agent import parse_address_to_parts, build_cyber_url, call_openrouter
from gemini_research_scanner import fetch_url_content

def extract_first_resident_with_kimi(content: str) -> str | None:
    if not content or len(content.strip()) < 100:
        return None
        
    prompt = f"""Extract the first resident listed in the following CyberBackgroundChecks page HTML/text.
Return ONLY their full name as a plain string, nothing else. If no resident is found, return "NOT_FOUND".

Content:
{content[:15000]}
"""
    messages = [
        {"role": "system", "content": "You are a data extractor. Return only the extracted name, no conversational text."},
        {"role": "user", "content": prompt}
    ]
    try:
        response = call_openrouter(messages, max_tokens=100)
        name = response.strip()
        if not name or "NOT_FOUND" in name or "NOT FOUND" in name:
            return None
        return name
    except Exception as e:
        print(f"Error calling OpenRouter: {e}")
        return None

def extract_first_resident_bs4(html_content: str) -> str | None:
    """Fallback extraction using BeautifulSoup."""
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, "html.parser")
    # Common classes for CBC
    name_tag = soup.select_one(".name-given, .name a, h2.name, h3.name, .card-title a")
    if name_tag and name_tag.text:
        return name_tag.text.strip()
    return None

def main():
    print("Fetching properties with no owner_name...")
    client = db.get_client()
    
    # We select all bills where owner_name is null
    res = client.table("bills").select("apn, property_search_url").is_("owner_name", "null").execute()
    rows = res.data or []
    
    print(f"Found {len(rows)} properties without an owner.")
    
    updated_count = 0
    
    for row in rows:
        apn = row.get("apn")
        url = row.get("property_search_url")
            
        print(f"\nProcessing APN: {apn}")
        
        if not url:
            print("  No property_search_url in database.")
            continue
            
        if not "cyberbackgroundchecks.com" in url:
            print("  URL is not CyberBackgroundChecks.")
            continue
            
        print(f"  Fetching: {url}")
        content = fetch_url_content(url, max_chars=100000)
        
        if not content:
            print("  Failed to fetch content (likely blocked by Cloudflare).")
            continue
            
        print(f"  Fetched {len(content)} chars. Extracting resident...")
        
        resident_name = extract_first_resident_bs4(content)
        if not resident_name:
            resident_name = extract_first_resident_with_kimi(content)
            
        if resident_name:
            print(f"  Found Resident: {resident_name}")
            # Update database
            try:
                client.table("bills").update({"owner_name": resident_name}).eq("apn", apn).execute()
                print("  Successfully updated database.")
                updated_count += 1
            except Exception as e:
                print(f"  Error updating database: {e}")
        else:
            print("  No resident found in the page content.")
            
    print(f"\nFinished processing. Total updated: {updated_count}/{len(rows)}")

if __name__ == "__main__":
    main()

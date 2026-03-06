#!/usr/bin/env python3
"""One-off test: fetch a real CyberBackgroundChecks URL and print extracted text."""
import os
import sys
import threading
from pathlib import Path

# project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from gemini_research_scanner import (
    fetch_url_content,
    PLAYWRIGHT_AVAILABLE,
    CURL_CFFI_AVAILABLE,
)

def _force_exit():
    print("\nTest timed out after 90s (network slow or blocking). Exiting.")
    os._exit(2)

def main():
    url = "https://www.cyberbackgroundchecks.com/address/26555-UNDERWOOD-AVE/HAYWARD/94544"
    print(f"Playwright: {PLAYWRIGHT_AVAILABLE}, curl_cffi: {CURL_CFFI_AVAILABLE}")
    print(f"Fetching: {url} (will abort after 90s if no response)...")
    # Hard cap so the test never hangs
    timer = threading.Timer(90.0, _force_exit)
    timer.daemon = True
    timer.start()
    try:
        text = fetch_url_content(url, max_chars=20000)
    finally:
        timer.cancel()
    print(f"Length: {len(text)} chars")
    if text:
        print("--- First 1200 chars ---")
        print(text[:1200])
        print("--- End ---")
        sys.exit(0)
    print("Fetch returned no content.")
    sys.exit(1)

if __name__ == "__main__":
    main()

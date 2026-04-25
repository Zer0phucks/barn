import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from gemini_research_scanner import fetch_url_content
from cyber_research_agent import parse_address_to_parts, build_cyber_url
import asyncio
from bs4 import BeautifulSoup

async def main():
    address = "1053 LONGRIDGE RD, OAKLAND"
    addr_parts = parse_address_to_parts(address)
    # wait, parse_address_to_parts doesn't get zip if not present. Let's see
    print(addr_parts)
    # build_cyber_url needs zip. 
    addr_parts['zip'] = "94610" # Let's assume a zip or get it from situs_zip
    url = build_cyber_url(addr_parts)
    print("URL:", url)
    html = fetch_url_content(url, 1000000)
    print("Length of HTML:", len(html))
    
    # Actually, fetch_url_content returns _html_to_text if it's successful!
    # Wait, fetch_url_content in gemini_research_scanner strips HTML tags and returns text!
    # "text = _html_to_text(html, max_chars)"
    # If it strips HTML, I can't parse with BeautifulSoup from fetch_url_content output!
    
    print(html[:500])

asyncio.run(main())

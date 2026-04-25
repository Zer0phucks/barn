import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from cyber_research_agent import PropertyResearchInput, build_cyber_url, parse_address_to_parts
from gemini_research_scanner import fetch_url_content
import asyncio

async def test():
    apn = "5-451-6"
    ctx = PropertyResearchInput.from_apn(apn)
    if not ctx:
        print("No ctx")
        return
    parts = parse_address_to_parts(ctx.property_address)
    url = build_cyber_url(parts)
    print("URL:", url)
    if not url:
        return
    text = await asyncio.to_thread(fetch_url_content, url, 100000)
    with open("scratch/cyber_out.html", "w") as f:
        f.write(text or "")
    print("Saved to scratch/cyber_out.html")

if __name__ == "__main__":
    asyncio.run(test())

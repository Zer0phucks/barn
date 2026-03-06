import asyncio
import json
import logging
import os
import re
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def main():
    with open("favs.json", "r") as f:
        data = json.load(f)

    async with async_playwright() as p:
        try:
            # We must connect to the existing browser session where the user logged in, which is outside the sandbox!
            # Since the user logged in on "Page 28625D444C7B0FF78B938AAD915FAA01...", they used the MCP browser instance.
            # So the profile is at ~/.gemini/antigravity/mcp/browser/chrome_profile
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=os.path.expanduser("~/.gemini/antigravity/mcp/browser/chrome_profile"),
                headless=False,
                viewport={"width": 1280, "height": 800}
            )
        except Exception as e:
            logging.error(f"Could not launch persistent chromium: {e}")
            return
            
        page = browser.pages[0] if browser.pages else await browser.new_page()

        for idx, d in enumerate(data):
            if d.get("owner") and d["owner"] != "UNKNOWN" and "ERROR" not in d["owner"]:
                continue
                
            addr = d.get("address", "")
            city = d.get("city", "")
            if not addr or not city:
                continue

            slug = re.sub(r'[^a-z0-9]', '', addr.lower())
            zip_code = re.search(r'\b\d{5}\b', addr)
            zip_val = zip_code.group(0) if zip_code else ""
            city_slug = re.sub(r'[^a-z]', '', city.lower())
            
            url = f"https://app.truthfinder.com/dashboard/reports/ca:{city_slug}:{zip_val}:{slug}"
            logging.info(f"Navigating to {url}")
            
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(8000) # give it more time to load JS
            
            owner = None
            try:
                # get text and find owner block
                body_text = await page.evaluate("() => document.body.innerText")
                
                # We know from subagent that it usually says "Owner\nEleanor Huey | 845 Alma Pl"
                # so let's look for "Owner\n[Name] |"
                matches = re.findall(r'Owner\s*\n\s*([^|]+?)\s*\|', body_text)
                if matches:
                    owner = matches[0].strip()
                else:
                    # Let's try finding the class name that is typically there 
                    js_code = """
                        () => {
                            let textNodes = Array.from(document.querySelectorAll('*')).filter(el => {
                                return el.childNodes.length === 1 && el.childNodes[0].nodeType === 3 && el.innerText;
                            });
                            
                            for (let i = 0; i < textNodes.length; i++) {
                                if (textNodes[i].innerText.trim() === 'Owner') {
                                    // Let's check the next few text nodes
                                    for(let j=i+1; j < textNodes.length && j < i+10; j++) {
                                        if (textNodes[j].innerText.includes('|')) {
                                            return textNodes[j].innerText.split('|')[0].trim();
                                        }
                                    }
                                }
                            }
                            return null;
                        }
                    """
                    owner = await page.evaluate(js_code)
                    
            except Exception as e:
                logging.error(f"Error extracting owner: {e}")
                
            if owner:
                logging.info(f"Found owner for {addr}: {owner}")
                d["owner"] = owner
            else:
                logging.warning(f"Could not find owner for {addr}")
                
            with open("favs.json", "w") as f:
                json.dump(data, f, indent=2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

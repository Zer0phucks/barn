import asyncio
import json
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def main():
    with open("favs.json", "r") as f:
        data = json.load(f)

    # Filter targets that actually have an address
    targets = [t for t in data if t.get("address", "").strip()]
    logging.info(f"Found {len(targets)} targets with a valid address out of {len(data)}")

    # Just test with 3 at first
    targets = targets[:3]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        await page.goto("https://www.sfchronicle.com/projects/2025/ca-property-map", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        logging.info("Page loaded.")

        for item in targets:
            full_addr = f"{item['address']}, {item['city']}".strip(", ")
            logging.info(f"Searching for: {full_addr} (APN: {item['apn']})")

            try:
                # wait for map and input to be ready
                import re
                await page.screenshot(path="debug.png")
                search_input = page.get_by_placeholder(re.compile("address", re.IGNORECASE))
                
                await search_input.wait_for(state="visible", timeout=15000)
                
                # Close any existing popup to start fresh
                close_btn = page.locator(".mapboxgl-popup-close-button")
                if await close_btn.is_visible():
                    await close_btn.click()
                    await page.wait_for_timeout(500)

                # Clear input
                await search_input.fill("")
                await page.wait_for_timeout(500)

                # Type address slowly to trigger autocomplete
                await search_input.press_sequentially(full_addr, delay=50)
                await page.wait_for_timeout(2000)  # wait for suggestions to load
                
                # Press down and enter
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(500)
                await page.keyboard.press("Enter")
                
                owner_locator = page.locator(".mapboxgl-popup-content p:nth-of-type(1) span.data-text")
                try:
                    await owner_locator.wait_for(state="visible", timeout=10000)
                    owner_text = await owner_locator.inner_text()
                    item["owner"] = owner_text.strip()
                    logging.info(f"Found owner: {item['owner']}")
                except Exception as ex:
                    logging.warning(f"Could not find owner for {full_addr}. Exception: {ex}")
                    item["owner"] = "NOT_FOUND"

            except Exception as e:
                logging.error(f"Error processing {full_addr}: {e}")
                item["owner"] = "ERROR"

            with open("favs_with_owners.json", "w") as f:
                json.dump(targets, f, indent=2)

        await browser.close()
        logging.info("Finished.")

if __name__ == "__main__":
    asyncio.run(main())

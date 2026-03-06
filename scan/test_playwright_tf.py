import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def main():
    addr = "845 ALMA PL"
    city = "OAKLAND"
    state = "ca"
    url = f"https://www.truthfinder.com/property-records/{state}/{city.lower().replace(' ', '-')}/{addr.lower().replace(' ', '-')}/"
    
    print(f"Loading {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # TruthFinder might block headless. We can try it anyway.
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"Status Code: {response.status}")
        
        await page.wait_for_timeout(3000)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        print("Page Title:", soup.title.string if soup.title else "No Title")
        
        with open("debug_tf_pw.html", "w") as f:
            f.write(content)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

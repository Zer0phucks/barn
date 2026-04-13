from playwright.sync_api import sync_playwright

def test():
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
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        url = "https://www.cyberbackgroundchecks.com/address/404-santa-clara-ave/oakland/94610"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)
        html = page.content()
        if "just a moment" in html.lower():
            print("Failed: caught by Cloudflare")
        elif "security verification" in html.lower():
            print("Failed: Security Verification")
        else:
            print("Success!")
            print(html[:500])
        context.close()
        browser.close()

test()

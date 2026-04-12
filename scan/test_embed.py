from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    url = "https://maps.google.com/maps?q=3611+West+St,+Oakland&t=k&z=19&output=embed"
    page.goto(url)
    page.wait_for_timeout(3000)
    page.screenshot(path="test_embed.png")
    browser.close()

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 640, "height": 480})
    url = "https://maps.google.com/maps?q=3611+West+St,+Oakland&t=k&z=19&output=embed"
    page.goto(url)
    page.wait_for_timeout(3000)
    page.screenshot(path="test_embed.jpg", type="jpeg")
    browser.close()

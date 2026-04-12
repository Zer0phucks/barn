from playwright.sync_api import sync_playwright

html = """
<!DOCTYPE html>
<html>
<head>
<style>
body { margin: 0; padding: 0; overflow: hidden; background: #eee; }
iframe { border: none; width: 640px; height: 480px; }
/* Hide ugly google maps UI elements later but let's test it first */
</style>
</head>
<body>
<iframe id="map_frame" src="https://maps.google.com/maps?q=3611+West+St,+Oakland&t=k&z=19&output=embed"></iframe>
</body>
</html>
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 640, "height": 480})
    page.set_content(html)
    page.wait_for_timeout(4000) # Wait for maps to load
    
    # Hide the "View larger map" overlay to make it look like a clean static image
    page.evaluate('''() => {
        try {
            const frame = document.getElementById("map_frame");
            // Since it's cross-origin, we can't manipulate inside the iframe easily.
            // Google Maps embed usually puts UI inside the iframe.
        } catch(e) {}
    }''')
    
    element = page.locator("iframe")
    element.screenshot(path="test_embed.jpg", type="jpeg")
    browser.close()

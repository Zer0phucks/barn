from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        print("Navigating to search page...")
        page.goto("https://propertytax.alamedacountyca.gov/search")
        
        page.evaluate('document.getElementById("parcelInputWrapper").style.display = "block"')
        page.evaluate('document.getElementById("addressInputWrapper").style.display = "none"')
        
        # A known delinquent one from DB: "10-822-28"
        apn = "10-822-28"
        page.fill('input#displayApn', apn)
        page.evaluate(f'document.getElementById("apn").value = "{apn}"')
        
        print("Clicking search Button...")
        page.click('button#searchButton')
        
        # wait for some content or network to settle
        page.wait_for_timeout(5000)
        
        page.screenshot(path="scratch/after_search2.png")
        print("URL is now:", page.url)
        content = page.content()
        with open("scratch/search_result2.html", "w") as f:
            f.write(content)

        browser.close()

if __name__ == "__main__":
    run()

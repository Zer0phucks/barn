import time
import undetected_chromedriver as uc

def get_cbc_page():
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = uc.Chrome(options=options, headless=True)
    try:
        url = "https://www.cyberbackgroundchecks.com/address/1053-LONGRIDGE-RD/OAKLAND/94610"
        driver.get(url)
        print("Page loaded. Taking screenshot...")
        time.sleep(10)
        html = driver.page_source
        if "just a moment" in html.lower() or "challenge-platform" in html.lower():
            print("FAILED: Caught by Cloudflare")
            print(html[:500])
        else:
            print("SUCCESS")
            with open("scratch/uc_cbc.html", "w") as f:
                f.write(html)
            print("Saved to scratch/uc_cbc.html")
    finally:
        driver.quit()

get_cbc_page()

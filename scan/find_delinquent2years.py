import os
import json
import time
from playwright.sync_api import sync_playwright
import db

def run(city="OAKLAND"):
    client = db.get_client()
    res = client.table("bills").select("apn").eq("city", city).eq("delinquent", 1).execute()
    apns = [row["apn"] for row in res.data]
    print(f"Checking {len(apns)} delinquent properties in {city}...")
    
    # We will save the ones that are > 2 years delinquent into a text file
    output_file = f"delinquent_over_2_years_{city.lower()}.txt"
    found_apns = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://propertytax.alamedacountyca.gov/search")
        
        for idx, apn in enumerate(apns):
            print(f"[{idx+1}/{len(apns)}] Checking APN: {apn}")
            try:
                # Type the APN
                page.evaluate('document.getElementById("parcelInputWrapper").style.display = "block"')
                page.evaluate('document.getElementById("addressInputWrapper").style.display = "none"')
                page.fill('input#displayApn', apn)
                page.evaluate(f'document.getElementById("apn").value = "{apn}"')
                page.click('button#searchButton', force=True)
                
                # Wait for either result to load or error
                page.wait_for_selector('h1:has-text("Secured Property Summary"), .error-message', timeout=10000)
                
                content = page.content()
                
                if "Add Delinquent Taxes to Cart" in content:
                    found_apns.append(apn)
                    print(f" --> FOUND: {apn} has Defaulted (>2 years)")
                    with open(output_file, "a") as f:
                        f.write(apn + "\n")
                
                # We need to go back to search
                # Just reload the search page
                page.goto("https://propertytax.alamedacountyca.gov/search")
                
            except Exception as e:
                print(f"Error checking APN {apn}: {e}")
                # Reload just in case
                page.goto("https://propertytax.alamedacountyca.gov/search")

        browser.close()
    
    print(f"Finished. Found {len(found_apns)} properties > 2 years delinquent. Saved to {output_file}")

if __name__ == "__main__":
    import sys
    city_arg = "OAKLAND"
    if len(sys.argv) > 1:
        city_arg = sys.argv[1].upper()
    run(city_arg)

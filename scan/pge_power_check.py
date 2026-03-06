import sys
import argparse
import asyncio

# Installation Instructions:
# 1. Create a virtual environment (recommended): `python3 -m venv .venv && source .venv/bin/activate`
# 2. Install Playwright: `pip install playwright`
# 3. Install Browsers: `playwright install chromium`
# 4. Run: `python pge_power_check.py "Your Address"`

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: The 'playwright' library is not installed.")
    print("Please install it using: pip install playwright && playwright install chromium")
    sys.exit(1)

# Configuration
PGE_URL = "https://pgealerts.alerts.pge.com/outages/map/"
SEARCH_INPUT_SELECTOR = "#outage-center-address-lookup"
SEARCH_RESULT_CONTAINER = "#address-lookup-single-search-results-container"
SEARCH_RESULT_ITEM = '[id^="search-result-"]'


async def check_pge_power_status(address, headless=True, verbose=True):
    """
    Checks the power status for a given address on the PG&E Outage Map.
    Returns: True if "Has Power" (Service Found), False if "No Power".
    """
    if verbose:
        print(f"Checking power status for: {address}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        
        try:
            if verbose:
                print(f"Navigating to {PGE_URL}...")
            await page.goto(PGE_URL, timeout=60000)
            
            # Wait for search input to be ready
            search_input = page.locator(SEARCH_INPUT_SELECTOR)
            await search_input.wait_for(state="visible", timeout=30000)
            
            # Clear input (if any) and type address
            await search_input.click()
            await search_input.fill("")
            # Type slowly to trigger autocomplete
            await search_input.type(address, delay=100)
            
            if verbose:
                print("Waiting for search results...")
            
            try:
                # Wait for at least one result
                first_result = page.locator(SEARCH_RESULT_ITEM).first
                await first_result.wait_for(state="visible", timeout=10000)
                
                # Get all results
                results = page.locator(SEARCH_RESULT_ITEM)
                count = await results.count()
                
                found = False
                matched_text = ""
                
                # Improved matching logic:
                # 1. We assume the input address starts with the House Number.
                # 2. We extract the core street name by ignoring common suffixes.
                # 3. We check if the House Number and Core Street Name are present in the result.
                
                import re
                
                # List of common suffixes to ignore during matching
                suffixes = [
                    "road", "rd", "street", "st", "avenue", "ave", "drive", "dr", 
                    "lane", "ln", "court", "ct", "place", "pl", "boulevard", "blvd", 
                    "circle", "cir", "way", "terrace", "ter", "highway", "hwy",
                    "north", "n", "south", "s", "east", "e", "west", "w"
                ]
                
                # Normalize input address
                # Remove commas and extra spaces
                clean_address = re.sub(r'[^\w\s]', '', address.lower())
                parts = clean_address.split()
                
                if not parts:
                    return False # Should not happen with valid input
                    
                house_number = parts[0]
                street_parts = [p for p in parts[1:] if p not in suffixes and not p.isdigit()]
                # If we filtered everything, maybe keep the original parts minus number?
                if not street_parts:
                     street_parts = [p for p in parts[1:] if not p.isdigit()]
                
                if verbose:
                    print(f"Scanning {count} results for match against: Number='{house_number}', Street='{' '.join(street_parts)}'")
                
                for i in range(count):
                    text = await results.nth(i).inner_text()
                    text_clean = re.sub(r'[^\w\s]', '', text.lower())
                    result_words = text_clean.split()
                    
                    # Check 1: House Number must be present as a distinct word
                    if house_number not in result_words:
                        continue
                        
                    # Check 2: At least one significant part of the street name must be present
                    # e.g. "Portsmouth" in "1 Portsmouth Rd"
                    street_match = False
                    if not street_parts:
                        # Fallback if no street name bits found
                        street_match = True
                    else:
                        for part in street_parts:
                            if part in result_words: # Check if the word exists in result
                                street_match = True
                                break
                            # Partial match check? e.g. "Portsmouth" in "PortsmouthRd"?
                            # Usually words are separated.
                    
                    if street_match:
                        found = True
                        matched_text = text
                        break
                
                if found:
                    if verbose:
                        print(f"SUCCESS: Exact address match found: '{matched_text}'")
                        print("Result: HAS POWER")
                    return True
                else:
                    if verbose:
                        print(f"FAILURE: Address '{address}' not found in specific results.")
                        print("Available results were:")
                        for i in range(min(count, 5)):
                            print(f" - {await results.nth(i).inner_text()}")
                        print("Result: NO POWER")
                    return False
                    
            except Exception as e:
                # If timeout or not found
                if verbose:
                    print(f"FAILURE: No search results appeared for '{address}'.")
                    print("Result: NO POWER")
                return False
                
        except Exception as e:
            if verbose:
                print(f"An error occurred: {e}")
            return False
            
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check PG&E Power Status by Address")
    parser.add_argument("address", help="The full address to check (e.g., '77 Beale St, San Francisco')")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode (default: True)")
    parser.add_argument("--show-browser", action="store_false", dest="headless", help="Show the browser UI")
    
    args = parser.parse_args()
    
    result = asyncio.run(check_pge_power_status(args.address, args.headless))
    
    # Optional exit code for shell scripting
    if result:
        sys.exit(0)
    else:
        sys.exit(1)

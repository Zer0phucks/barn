import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Needs a specific Chrome version if installed, otherwise uses default
    driver = uc.Chrome(options=options, headless=True)
    
    try:
        driver.get("https://www.sfchronicle.com/projects/2025/ca-property-map")
        print("Page loaded. Taking screenshot...")
        time.sleep(5)
        driver.save_screenshot("debug_uc.png")
        
        # Check if PerimeterX is there
        if "Press & Hold" in driver.page_source:
            print("FAILED: PerimeterX blocked us.")
        else:
            print("SUCCESS: It looks like we bypassed PerimeterX.")
            
            # Print out some page source to see if mapbox token is there
            if "mapboxgl.accessToken" in driver.page_source:
                print("FOUND mapbox access token in page source!")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

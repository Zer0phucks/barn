import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

payload = {
    'api_key': api_key,
    'url': 'https://www.sfchronicle.com/projects/2025/ca-property-map',
    'render': 'true'
}

r = requests.get('https://api.scraperapi.com/', params=payload)
print(f"Status Code: {r.status_code}")
if r.status_code == 200:
    if "Press & Hold" in r.text or "PerimeterX" in r.text:
       print("FAILED: Caught by PerimeterX even with ScraperAPI")
    else:
       print("SUCCESS: Loaded page via ScraperAPI!")
       if "mapbox" in r.text.lower():
           print("FOUND mapbox references!")
else:
    print(r.text[:500])

with open("debug_scraperapi.html", "w") as f:
    f.write(r.text)

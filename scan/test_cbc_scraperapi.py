import requests
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

addr = "B181284 3" # apn or something. Let's just use an address
# 404 SANTA CLARA AVE 94610 -> 404-santa-clara-ave/oakland/94610
url = "https://www.cyberbackgroundchecks.com/address/404-santa-clara-ave/oakland/94610"

payload = {
    'api_key': api_key,
    'url': url,
    'render': 'true',
    'premium': 'true',
    'country_code': 'us'
}

r = requests.get('https://api.scraperapi.com/', params=payload)
print(f"Status Code: {r.status_code}")
with open("debug_cbc.html", "w") as f:
    f.write(r.text)
if "just a moment" in r.text.lower():
    print("Caught by Cloudflare.")
elif r.status_code == 200:
    print("Success!")
else:
    print("Failed")
print("Saved to debug_cbc.html")

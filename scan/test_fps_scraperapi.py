import requests
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

addr = "404 SANTA CLARA AVE 94610"
# https://www.fastpeoplesearch.com/address/404-santa-clara-ave_oakland-ca
url = "https://www.fastpeoplesearch.com/address/404-santa-clara-ave_oakland-ca-94610"

payload = {
    'api_key': api_key,
    'url': url,
    'render': 'true',
    'premium': 'true',
    'country_code': 'us'
}

r = requests.get('https://api.scraperapi.com/', params=payload)
print(f"Status Code: {r.status_code}")
if r.status_code == 200:
    print(r.text[:200])
else:
    print(r.text[:200])

import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

addr = "404 SANTA CLARA AVE 94610"
# https://www.truepeoplesearch.com/results?streetaddress=404%20santa%20clara%20ave&citystatezip=oakland%2C%20ca%2C%2094610
url = "https://www.truepeoplesearch.com/results?streetaddress=404%20santa%20clara%20ave&citystatezip=oakland,%20ca,%2094610"

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

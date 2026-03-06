import requests
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

addr = "845 ALMA PL"
city = "OAKLAND"
state = "ca"

def test_truthfinder():
    url = f"https://www.truthfinder.com/property-records/{state}/{city.lower().replace(' ', '-')}/{addr.lower().replace(' ', '-')}/"
    print("Fetching:", url)
    payload = {
        'api_key': api_key,
        'url': url,
        'render': 'true'
    }

    r = requests.get('https://api.scraperapi.com/', params=payload)
    print(f"Status Code: {r.status_code}")
    
    with open("debug_tf.html", "w") as f:
        f.write(r.text)

if __name__ == "__main__":
    test_truthfinder()

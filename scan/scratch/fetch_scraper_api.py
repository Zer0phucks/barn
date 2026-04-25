import requests
import os
import urllib.parse
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()
api_key = os.getenv("SCRAPER_API_KEY")

def get_first_resident(street, city, zip_code):
    street_slug = street.replace(" ", "-").replace(",", "")
    city_slug = city.replace(" ", "-")
    url = f"https://www.cyberbackgroundchecks.com/address/{street_slug}/{city_slug}/{zip_code}"
    print(f"URL: {url}")
    
    payload = {
        'api_key': api_key,
        'url': url,
        'render': 'true',
        'premium': 'true',
        'country_code': 'us'
    }
    
    r = requests.get('https://api.scraperapi.com/', params=payload)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        # find residents
        # usually cyberbackgroundchecks lists residents in cards or a list.
        # Let's print out the text of some headers or links to see what it looks like.
        name_tags = soup.select('.name-given') # usually their name tags have a specific class. We can also just look for h3 or a inside the resident blocks.
        if not name_tags:
            name_tags = soup.select('h3.name a') # maybe?
        if not name_tags:
            # let's just find the first h3 or strong that looks like a name
            blocks = soup.select('.card-body .row .col-md-8 a.name-given')
        print(f"Name tags: {name_tags}")
        with open("scratch/cbc_page.html", "w") as f:
            f.write(r.text)
        print("Saved to scratch/cbc_page.html")
    else:
        print(f"Failed: {r.status_code}")

get_first_resident("2643 MARKET ST", "OAKLAND", "94607")

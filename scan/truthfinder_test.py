import requests
import re
from bs4 import BeautifulSoup

def search_truthfinder(address, city, zip_code):
    url = f"https://www.truthfinder.com/property-records/ca/{city.lower().replace(' ', '-')}/{address.lower().replace(' ', '-')}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    print(f"Fetching {url}")
    response = requests.get(url, headers=headers)
    print(response.status_code)
    # print(response.text[:2000])
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to extract the owner's name from the page
    # It might be in a specific div or meta tag or json-ld
    print(soup.title)
    # Just save the html for inspection
    with open('tf_res.html', 'w') as f:
        f.write(response.text)

if __name__ == "__main__":
    search_truthfinder("845 ALMA PL", "OAKLAND", "94610")

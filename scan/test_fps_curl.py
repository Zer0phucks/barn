from curl_cffi import requests
url = "https://www.fastpeoplesearch.com/address/404-santa-clara-ave_oakland-ca-94610"
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}
r = requests.get(url, impersonate="chrome120", timeout=25, headers=headers)
print(f"Status Code: {r.status_code}")
print(r.text[:500])

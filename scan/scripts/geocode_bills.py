"""Fill bills.lat/lng from location_of_property via the US Census batch geocoder.

Only touches rows where lat is null. Pass --dry-run to geocode without writing.
map_markers only shows bills with coordinates.

    python scripts/geocode_bills.py [--dry-run]
"""
import csv
import io
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
import db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv
URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

client = db.get_client()
rows, off = [], 0
while True:
    page = (
        client.table("bills")
        .select("apn,location_of_property,city,zip_code")
        .is_("lat", "null")
        .range(off, off + 999)
        .execute()
        .data
    )
    rows += page
    if len(page) < 1000:
        break
    off += 1000
print("rows missing coordinates:", len(rows))

buf = io.StringIO()
w = csv.writer(buf)
skipped = 0
for r in rows:
    loc = (r["location_of_property"] or "").strip()
    if not loc:
        skipped += 1
        continue
    street = loc.split(",")[0].strip()
    city = (r["city"] or (loc.split(",")[1] if "," in loc else "")).strip()
    w.writerow([r["apn"], street, city, "CA", r.get("zip_code") or ""])

resp = requests.post(
    URL,
    files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
    data={"benchmark": "Public_AR_Current"},
    timeout=600,
)
resp.raise_for_status()

matched, unmatched = [], []
for rec in csv.reader(io.StringIO(resp.text)):
    if len(rec) >= 6 and rec[2] == "Match":
        lng, lat = (float(x) for x in rec[5].split(","))
        matched.append((rec[0], lat, lng, rec[3]))
    elif rec:
        unmatched.append((rec[0], rec[1]))

print(f"matched {len(matched)} (exact {sum(m[3] == 'Exact' for m in matched)}), "
      f"unmatched {len(unmatched)}, no address {skipped}")
for apn, addr in unmatched:
    print("  no match:", apn, addr)

if not DRY_RUN:
    for apn, lat, lng, _ in matched:
        client.table("bills").update({"lat": lat, "lng": lng}).eq("apn", apn).execute()
    print("updated", len(matched))

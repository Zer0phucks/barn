"""Fill bills.zip_code for rows that don't have one yet.

Passes, in order:
  1. Alameda County parcels ArcGIS (by APN, then by street address). This is
     the tax roll itself, so its SitusZip is authoritative for these rows.
  2. oakland.csv / berkeley.csv (the same county files the scanner reads).
  3. Census batch geocoder by address (matched address carries the ZIP).
  4. Census ZCTA lookup by the bill's stored coordinates.
  5. Nominatim coordinates -> Census ZCTA for rows with no stored coordinates.

Only touches rows where zip_code is null, so it is safe to re-run and never
overwrites a zip that an import already set. map_markers exposes bills.zip_code
as its zip_code column, which feeds the list/gallery Zip display and the
"Select Zips" filter.

    python scripts/backfill_zip_codes.py [--dry-run] [--no-geocode]
"""
import csv
import io
import re
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
import db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv
NO_GEOCODE = "--no-geocode" in sys.argv
CENSUS = "https://geocoding.geo.census.gov/geocoder"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = {"User-Agent": "barn-zip-backfill/1.0 (local admin script)"}
COUNTY_PARCELS = (
    "https://services5.arcgis.com/ROBnTHSNjoZ2Wm1P/arcgis/rest/services/Parcels/FeatureServer/0/query"
)

client = db.get_client()


def bills_missing_zip() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = (
            client.table("bills")
            .select("apn,location_of_property,city,lat,lng")
            .is_("zip_code", "null")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        rows += page
        if len(page) < 1000:
            break
        offset += 1000
    return rows


def county_zips(rows: list[dict]) -> dict[str, str]:
    """SitusZip from the Alameda County parcels feature layer, by APN then address."""
    zips: dict[str, str] = {}
    for row in rows:
        apn = (row.get("apn") or "").strip().replace("'", "''")
        features = county_query(f"APN='{apn}'")
        if not features:
            street = (row.get("location_of_property") or "").split(",")[0].strip().upper()
            street = street.replace("'", "''")
            if street:
                features = county_query(f"SitusAddress LIKE '{street} %'")
        for feature in features:
            zip_code = str((feature.get("attributes") or {}).get("SitusZip") or "").strip()
            if zip_code:
                zips[row["apn"]] = zip_code
                break
    return zips


def county_query(where: str) -> list[dict]:
    resp = requests.get(
        COUNTY_PARCELS,
        params={
            "where": where,
            "outFields": "APN,SitusAddress,SitusCity,SitusZip",
            "returnGeometry": "false",
            "f": "json",
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json().get("features") or []


def csv_zips(wanted: set[str]) -> dict[str, str]:
    zips: dict[str, str] = {}
    for name in ("oakland.csv", "berkeley.csv"):
        path = BASE_DIR / name
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                apn = (row.get("APN") or "").strip()
                zip_code = (row.get("ZIPCODE") or "").strip()
                if apn in wanted and zip_code and apn not in zips:
                    zips[apn] = zip_code
    return zips


def geocode_zips(rows: list[dict]) -> tuple[dict[str, str], int]:
    """ZIP from the Census batch geocoder; returns (zips, non_exact_count)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        location = (row.get("location_of_property") or "").strip()
        if not location:
            continue
        street = location.split(",")[0].strip()
        city = (row.get("city") or (location.split(",")[1] if "," in location else "")).strip()
        writer.writerow([row["apn"], street, city, "CA", ""])

    resp = requests.post(
        f"{CENSUS}/locations/addressbatch",
        files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
        data={"benchmark": "Public_AR_Current"},
        timeout=600,
    )
    resp.raise_for_status()

    zips: dict[str, str] = {}
    non_exact = 0
    for rec in csv.reader(io.StringIO(resp.text)):
        if len(rec) < 6 or rec[2] != "Match":
            continue
        zip_match = re.search(r"\b(\d{5})\b", rec[4].rsplit(",", 1)[-1])
        if not zip_match:
            continue
        if rec[3] != "Exact":
            non_exact += 1
        zips[rec[0]] = zip_match.group(1)
    return zips, non_exact


def zcta_for_coords(lat: float, lng: float) -> str | None:
    """ZCTA5 (the Census ZIP area) containing a coordinate."""
    resp = requests.get(
        f"{CENSUS}/geographies/coordinates",
        params={
            "x": lng,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "layers": "2020 Census ZIP Code Tabulation Areas",
            "format": "json",
        },
        timeout=60,
    )
    geographies = (resp.json().get("result") or {}).get("geographies") or {}
    for entries in geographies.values():
        if entries:
            return entries[0].get("ZCTA5")
    return None


def coordinate_zips(rows: list[dict]) -> dict[str, str]:
    zips: dict[str, str] = {}
    for row in rows:
        lat, lng = row.get("lat"), row.get("lng")
        if not (lat and lng):
            continue
        try:
            zcta = zcta_for_coords(float(lat), float(lng))
        except requests.RequestException:
            continue
        if zcta:
            zips[row["apn"]] = zcta
    return zips


def nominatim_zips(rows: list[dict]) -> dict[str, str]:
    zips: dict[str, str] = {}
    for row in rows:
        location = (row.get("location_of_property") or "").strip()
        city = (row.get("city") or "").strip()
        if not location:
            continue
        try:
            resp = requests.get(
                NOMINATIM,
                params={"q": f"{location}, {city}, CA", "format": "json", "limit": 1},
                headers=USER_AGENT,
                timeout=60,
            )
            matches = resp.json()
            if matches:
                zcta = zcta_for_coords(float(matches[0]["lat"]), float(matches[0]["lon"]))
                if zcta:
                    zips[row["apn"]] = zcta
        except (requests.RequestException, KeyError, ValueError):
            pass
        time.sleep(1.1)
    return zips


def write_zips(zips: dict[str, str]) -> int:
    updated = 0
    batch: list[dict[str, str]] = []
    for apn, zip_code in zips.items():
        batch.append({"apn": apn, "zip_code": zip_code})
        if len(batch) >= 200:
            client.table("bills").upsert(batch, on_conflict="apn").execute()
            updated += len(batch)
            batch = []
    if batch:
        client.table("bills").upsert(batch, on_conflict="apn").execute()
        updated += len(batch)
    return updated


missing = bills_missing_zip()
wanted = {row["apn"] for row in missing if row.get("apn")}
print("bills missing zip_code:", len(wanted))

zips = county_zips(missing)
print("pass 1 - Alameda County parcels:", len(zips))

csv_found = {apn: z for apn, z in csv_zips(wanted).items() if apn not in zips}
print("pass 2 - county CSVs:", len(csv_found))
zips.update(csv_found)

if not NO_GEOCODE:
    remaining = [row for row in missing if row["apn"] not in zips]
    geocoded, non_exact = geocode_zips(remaining)
    geocoded = {apn: z for apn, z in geocoded.items() if apn not in zips}
    print(f"pass 3 - Census batch geocoder: {len(geocoded)} ({non_exact} non-exact)")
    zips.update(geocoded)

    remaining = [row for row in missing if row["apn"] not in zips]
    by_coords = coordinate_zips(remaining)
    print("pass 4 - Census ZCTA by stored coordinates:", len(by_coords))
    zips.update(by_coords)

    remaining = [row for row in missing if row["apn"] not in zips]
    by_nominatim = nominatim_zips(remaining)
    print("pass 5 - Nominatim coordinates -> ZCTA:", len(by_nominatim))
    zips.update(by_nominatim)

if DRY_RUN:
    print("dry run; sample:", list(zips.items())[:5])
    raise SystemExit(0)

print("updated:", write_zips(zips))

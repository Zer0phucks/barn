#!/usr/bin/env python3
"""Rebuild the BARN database from a bills CSV export plus the repo's image corpus.

Written during the 2026-09-18 recovery, after the Supabase project holding the
live data was deleted. It is the documented path back from a bills CSV export
(the column set `map_markers` / the admin UI exports) to a working database.

Three stages, each skippable so a partial run can be resumed:

  geocode  bills.lat/lng, which the CSV export does not carry. Berkeley rows
           resolve against berkeley.csv's parcel centroids (EPSG:3857, the
           authoritative source); everything else goes to the Census batch
           geocoder, which needs no API key. This stage matters more than it
           looks: map_markers filters `where lat is not null and lng is not
           null` and scout_next() orders by `geom <->`, so a row without
           coordinates is invisible to both the map and the scout app.
  bills    upsert the CSV rows into bills.
  images   upload scan/streetview_images/<apn>.jpg to the streetview-images
           bucket and point bills.streetview_image_path at the public URL.
           The Android app reads that column directly, so it has to be a URL
           the phone can fetch, never a scanner-VM path.

Writes go through PostgREST as a signed-in user rather than with the service
key, so RLS applies. bills has no INSERT policy by design (scanners use the
service role), so grant one for the duration of the load and drop it after:

    create policy tmp_load_bills_insert on bills
      for insert to authenticated with check (true);
    create policy tmp_load_bills_update on bills
      for update to authenticated using (true) with check (true);
    create policy tmp_load_sv_insert on storage.objects
      for insert to authenticated with check (bucket_id = 'streetview-images');
    create policy tmp_load_sv_update on storage.objects
      for update to authenticated using (bucket_id = 'streetview-images')
      with check (bucket_id = 'streetview-images');

Dropping all four afterwards is part of the restore, not an optional tidy-up.
With SUPABASE_SERVICE_KEY set the policies are unnecessary — the service role
bypasses RLS — and the script uses it directly.

    export SUPABASE_URL=https://<ref>.supabase.co
    export SUPABASE_ANON_KEY=sb_publishable_...
    export SUPABASE_EMAIL=... SUPABASE_PASSWORD=...     # or SUPABASE_SERVICE_KEY
    python scripts/restore_db.py --csv list.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scan"))
from geo_utils import web_mercator_to_latlng  # noqa: E402

BUCKET = "streetview-images"
IMAGE_DIR = REPO / "scan" / "streetview_images"
BERKELEY_CSV = REPO / "berkeley.csv"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

# Census caps a batch at 10k; 200 keeps a failed chunk cheap to retry.
CENSUS_CHUNK = 200
UPSERT_CHUNK = 100
UPLOAD_WORKERS = 12

# The CSV export writes these for "no value"; '' alone would keep "null" as a
# literal four-character owner name.
NULLISH = {"", "null", "none", "nan"}

# Street-suffix spellings differ between the tax portal ("1008 JONES ST") and
# the county address export ("1008 Jones Street"), so normalize before joining.
SUFFIXES = {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD",
    "DRIVE": "DR", "ROAD": "RD", "COURT": "CT", "PLACE": "PL",
    "LANE": "LN", "TERRACE": "TER", "CIRCLE": "CIR",
}


# ---------------------------------------------------------------------------
# CSV value coercion. The export is all strings; bills is typed.
# ---------------------------------------------------------------------------

def s(value):
    value = (value or "").strip()
    return None if value.lower() in NULLISH else value


def as_int(value):
    value = s(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def as_float(value):
    value = s(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_bool(value):
    value = s(value)
    return None if value is None else value.lower() in ("true", "t", "1", "yes")


def norm_address(value):
    """'1008 JONES ST, BERKELEY' -> '1008 JONES ST', unit designators dropped."""
    if not value:
        return None
    import re
    text = value.upper().split(",")[0]
    text = re.sub(r"\b(APT|UNIT|STE|#)\s*\S+", "", text)
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(SUFFIXES.get(w, w) for w in text.split()).strip() or None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def post_json(url, payload, headers, timeout=180):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    return urllib.request.urlopen(request, timeout=timeout)


def build_headers(base_url, anon_key):
    """Service key when present, otherwise a password grant for the app user."""
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if service_key:
        token = service_key
    else:
        email = os.environ.get("SUPABASE_EMAIL")
        password = os.environ.get("SUPABASE_PASSWORD")
        if not (email and password):
            sys.exit("set SUPABASE_SERVICE_KEY, or SUPABASE_EMAIL + SUPABASE_PASSWORD")
        response = post_json(
            f"{base_url}/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
            {"apikey": anon_key, "Content-Type": "application/json"},
        )
        token = json.load(response)["access_token"]
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


# ---------------------------------------------------------------------------
# Stage 1: coordinates
# ---------------------------------------------------------------------------

def berkeley_centroids():
    if not BERKELEY_CSV.exists():
        return {}
    centroids = {}
    with open(BERKELEY_CSV, encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = norm_address(row.get("ADDRESS"))
            if not key or key in centroids:
                continue
            try:
                x, y = float(row.get("x") or 0), float(row.get("y") or 0)
            except ValueError:
                continue
            if x and y:  # 0,0 is Null Island, which the export means as "unknown"
                centroids[key] = (x, y)
    return centroids


def census_batch(chunk):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in chunk:
        street = (row.get("location_of_property") or "").split(",")[0].strip()
        writer.writerow([row["apn"], street, row.get("city") or "", "CA",
                         row.get("situs_zip") or ""])

    boundary = f"----barn{time.time_ns()}"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="benchmark"\r\n\r\n'
        f"Public_AR_Current\r\n".encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="addressFile";'
        f' filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode(),
        buffer.getvalue().encode(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        CENSUS_URL, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return urllib.request.urlopen(request, timeout=300).read().decode()


def geocode(rows, out_path):
    centroids = berkeley_centroids()
    coords = {}
    for row in rows:
        # Match within Berkeley only: a street name shared with Oakland would
        # otherwise silently place the pin in the wrong city.
        if (row.get("city") or "").upper() != "BERKELEY":
            continue
        key = norm_address(row.get("location_of_property"))
        if key in centroids:
            lat, lng = web_mercator_to_latlng(*centroids[key])
            coords[row["apn"]] = (round(lat, 7), round(lng, 7))
    print(f"  berkeley parcel centroids: {len(coords)}")

    pending = [r for r in rows if r["apn"] not in coords]
    print(f"  census geocoder: {len(pending)} to resolve")
    for start in range(0, len(pending), CENSUS_CHUNK):
        chunk = pending[start:start + CENSUS_CHUNK]
        for attempt in range(3):
            try:
                body = census_batch(chunk)
                break
            except Exception as exc:  # noqa: BLE001 - transient, retried below
                print(f"    retry {attempt}: {exc}")
                time.sleep(5)
        else:
            print(f"    chunk at {start} failed, leaving uncoded")
            continue
        matched = 0
        for record in csv.reader(io.StringIO(body)):
            if len(record) >= 6 and record[2] == "Match":
                try:
                    lng, lat = (float(v) for v in record[5].split(","))
                except ValueError:
                    continue
                coords[record[0]] = (round(lat, 7), round(lng, 7))
                matched += 1
        print(f"    {start}-{start + len(chunk)}: {matched} matched")

    out_path.write_text(json.dumps(coords))
    print(f"  geocoded {len(coords)}/{len(rows)} -> {out_path}")
    return coords


# ---------------------------------------------------------------------------
# Stage 2: bills
# ---------------------------------------------------------------------------

def upsert(base_url, headers, table, records, chunk_size=UPSERT_CHUNK):
    for start in range(0, len(records), chunk_size):
        chunk = records[start:start + chunk_size]
        try:
            post_json(f"{base_url}/rest/v1/{table}?on_conflict=apn", chunk, headers)
        except urllib.error.HTTPError as exc:
            sys.exit(f"  upsert failed at {start}: {exc.code} {exc.read().decode()[:400]}")
        print(f"    {start}-{start + len(chunk)}")


def load_bills(base_url, headers, rows, coords):
    records = []
    for row in rows:
        apn = s(row.get("apn"))
        if not apn:
            continue
        point = coords.get(apn)
        records.append({
            "apn": apn,
            "location_of_property": s(row.get("location_of_property")),
            "city": s(row.get("city")),
            "zip_code": s(row.get("situs_zip")),
            "has_vpt": as_int(row.get("has_vpt")) or 0,
            "vpt_marker": s(row.get("vpt_marker")),
            "delinquent": as_int(row.get("delinquent")) or 0,
            "power_status": s(row.get("power_status")),
            "condition_score": as_float(row.get("condition_score")),
            "condition_notes": s(row.get("condition_notes")),
            "owner_name": s(row.get("owner_name")),
            "owner_phone": s(row.get("owner_phone")),
            "owner_mobile_phone": s(row.get("owner_mobile_phone")),
            "owner_email": s(row.get("owner_email")),
            "owner_contact_status": s(row.get("owner_contact_status")),
            "tenant_verified": as_bool(row.get("tenant_verified")),
            "prop_occupancy_type": s(row.get("prop_occupancy_type")),
            "prop_ownership_type": s(row.get("prop_ownership_type")),
            "prop_last_sale_date": s(row.get("prop_last_sale_date")),
            "primary_resident_name": s(row.get("primary_resident_name")),
            "primary_resident_age": s(row.get("primary_resident_age")),
            "deceased_count": as_int(row.get("deceased_count")),
            "important_notes": s(row.get("important_notes")),
            "tax_year": s(row.get("tax_year")),
            "last_payment": s(row.get("last_payment")),
            "bill_url": s(row.get("bill_url")),
            "property_search_url": s(row.get("property_search_url")),
            "mailing_search_url": s(row.get("mailing_search_url")),
            "owner_details_url": s(row.get("owner_details_url")),
            "research_status": s(row.get("research_status")),
            "research_updated_at": s(row.get("research_updated_at")),
            "added_at": s(row.get("added_at")),
            "lat": point[0] if point else None,
            "lng": point[1] if point else None,
        })

    # PostgREST rejects a bulk insert whose objects differ in key set, and
    # added_at is NOT NULL, so a row missing it has to fall back to the column
    # default rather than send an explicit null.
    if any(r["added_at"] is None for r in records):
        print("  added_at absent on some rows; using column default for all")
        for record in records:
            record.pop("added_at")

    coded = sum(1 for r in records if r["lat"] is not None)
    print(f"  upserting {len(records)} rows ({coded} with coordinates)")
    upsert(base_url, headers, "bills", records)
    return records


# ---------------------------------------------------------------------------
# Stage 3: images
# ---------------------------------------------------------------------------

def upload_images(base_url, headers, anon_key, rows):
    pending = []
    for row in rows:
        apn = s(row.get("apn"))
        if not apn:
            continue
        path = IMAGE_DIR / f"{apn}.jpg"
        if path.exists():
            pending.append((apn, path))
    print(f"  {len(pending)} of {len(rows)} rows have a local image")

    # Mirrors condition_scanner._upload_to_storage's object naming.
    def object_name(apn):
        return apn.replace("/", "_").replace("\\", "_") + ".jpg"

    def send(item):
        apn, path = item
        quoted = urllib.parse.quote(object_name(apn))
        request = urllib.request.Request(
            f"{base_url}/storage/v1/object/{BUCKET}/{quoted}",
            data=path.read_bytes(), method="POST",
            headers={
                "apikey": anon_key,
                "Authorization": headers["Authorization"],
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
            },
        )
        try:
            urllib.request.urlopen(request, timeout=180)
        except Exception:  # noqa: BLE001 - reported in the failure tally
            return apn, None
        return apn, f"{base_url}/storage/v1/object/public/{BUCKET}/{quoted}"

    uploaded, failed = {}, []
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
        for done, (apn, url) in enumerate(pool.map(send, pending), 1):
            if url:
                uploaded[apn] = url
            else:
                failed.append(apn)
            if done % 100 == 0:
                print(f"    {done}/{len(pending)}")
    print(f"  uploaded {len(uploaded)}, failed {len(failed)}")

    if uploaded:
        print("  linking bills.streetview_image_path")
        upsert(base_url, headers, "bills",
               [{"apn": a, "streetview_image_path": u} for a, u in uploaded.items()],
               chunk_size=150)
    if failed:
        print(f"  first failures: {failed[:5]}")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="bills CSV export to restore from")
    parser.add_argument("--coords", type=Path, default=Path("coords.json"),
                        help="where geocoding results are cached")
    parser.add_argument("--skip-geocode", action="store_true",
                        help="reuse an existing --coords file")
    parser.add_argument("--skip-bills", action="store_true")
    parser.add_argument("--skip-images", action="store_true")
    args = parser.parse_args()

    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    anon_key = os.environ.get("SUPABASE_ANON_KEY") or ""
    if not base_url or not anon_key:
        sys.exit("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    with open(args.csv, encoding="utf-8-sig") as handle:
        rows = [r for r in csv.DictReader(handle) if s(r.get("apn"))]
    print(f"{len(rows)} rows in {args.csv}")

    headers = build_headers(base_url, anon_key)

    if args.skip_geocode:
        coords = {k: tuple(v) for k, v in json.loads(args.coords.read_text()).items()}
        print(f"reusing {len(coords)} cached coordinates")
    else:
        print("geocoding")
        coords = geocode(rows, args.coords)

    if not args.skip_bills:
        print("loading bills")
        load_bills(base_url, headers, rows, coords)

    if not args.skip_images:
        print("uploading street view images")
        upload_images(base_url, headers, anon_key, rows)

    print("done")


if __name__ == "__main__":
    main()

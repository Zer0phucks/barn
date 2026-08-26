#!/usr/bin/env python3
"""Backfill bills.lat/lng from parcels.row_json for rows that lack coordinates.

find_meas_w_addresses.py now derives coordinates inline during the scrape, so
freshly scanned rows never need this. It stays for data that arrives another
way — a bulk CSV merge, a restored dump, or a parcel export that landed after
its bill row.

Safe to re-run: only touches rows where lat is still null. The bills_set_geom
trigger fills in the geography column on each update, which is what
scout_next()'s KNN ordering and the map_markers view depend on.

    python backfill_coordinates.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import db  # noqa: E402
from geo_utils import derive_latlng  # noqa: E402

BATCH_SIZE = 500


def iter_rows_missing_coords(client, limit: int | None):
    """Yield (apn, row_json) for bills with no lat, joined to their parcel."""
    offset = 0
    seen = 0
    while True:
        page = (
            client.table("bills")
            .select("apn")
            .is_("lat", "null")
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        rows = page.data or []
        if not rows:
            return

        apns = [r["apn"] for r in rows if r.get("apn")]
        parcels = (
            client.table("parcels").select("apn, row_json").in_("apn", apns).execute()
        )
        parcel_map = {p["apn"]: p.get("row_json") for p in (parcels.data or []) if p.get("apn")}

        for apn in apns:
            yield apn, parcel_map.get(apn)
            seen += 1
            if limit and seen >= limit:
                return

        # Rows just updated drop out of the `lat is null` filter, so the window
        # does not advance for them; only skip past rows we could not fix.
        offset += len(rows) if len(rows) < BATCH_SIZE else 0
        if len(rows) < BATCH_SIZE:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N rows.")
    args = parser.parse_args()

    client = db.get_client()
    updated = skipped = 0

    for apn, row_json in iter_rows_missing_coords(client, args.limit):
        latlng = derive_latlng(row_json)
        if latlng is None:
            skipped += 1
            continue
        lat, lng = latlng
        if not args.dry_run:
            client.table("bills").update({"lat": lat, "lng": lng}).eq("apn", apn).execute()
        updated += 1
        if updated % 100 == 0:
            print(f"  {updated} updated, {skipped} without usable centroid")

    verb = "would update" if args.dry_run else "updated"
    print(f"Done: {verb} {updated}, skipped {skipped} (no parcel centroid).")


if __name__ == "__main__":
    main()

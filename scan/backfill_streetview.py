#!/usr/bin/env python3
"""
Backfill missing streetview images for all properties in the bills table.

Phase 1: Update DB for images that already exist on disk but aren't recorded.
Phase 2: Fetch satellite images via Playwright for properties with parcel coordinates.
Phase 3: Geocode addresses for properties without parcel data, then fetch their images.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import db
from geo_utils import derive_latlng

STREETVIEW_DIR = BASE_DIR / "streetview_images"
STREETVIEW_DIR.mkdir(exist_ok=True)

CONCURRENCY = 6
MAP_WAIT_MS = 4500
BATCH_SIZE = 500

shutdown_requested = False


def get_coords_from_parcel(row_json) -> tuple[float, float] | None:
    return derive_latlng(row_json)


def get_missing_apns() -> list[str]:
    client = db.get_client()
    apns: list[str] = []
    offset = 0
    while True:
        r = (client.table("bills")
             .select("apn")
             .or_("streetview_image_path.is.null,streetview_image_path.eq.")
             .range(offset, offset + BATCH_SIZE - 1)
             .execute())
        chunk = r.data or []
        apns.extend(row["apn"] for row in chunk)
        if len(chunk) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return apns


def phase1_reconcile_disk(missing_apns: list[str]) -> list[str]:
    """Update DB for images already on disk. Returns APNs still needing fetch."""
    updated = 0
    still_missing = []
    for apn in missing_apns:
        safe = apn.replace("/", "_").replace("\\", "_")
        path = STREETVIEW_DIR / f"{safe}.jpg"
        if path.exists() and path.stat().st_size > 1000:
            try:
                db.get_client().table("bills").update(
                    {"streetview_image_path": str(path)}
                ).eq("apn", apn).execute()
                updated += 1
            except Exception as e:
                print(f"  DB update failed for {apn}: {e}")
                still_missing.append(apn)
        else:
            still_missing.append(apn)
    if updated:
        print(f"  Phase 1: Updated {updated} DB records for existing images on disk")
    return still_missing


def get_coords_batch(apns: list[str]) -> list[tuple[str, float, float]]:
    """Fetch parcel coordinates for a batch of APNs from the parcels table."""
    client = db.get_client()
    results: list[tuple[str, float, float]] = []
    for i in range(0, len(apns), 100):
        chunk = apns[i : i + 100]
        r = client.table("parcels").select("apn,row_json").in_("apn", chunk).execute()
        for row in r.data or []:
            apn = row.get("apn")
            coords = get_coords_from_parcel(row.get("row_json"))
            if apn and coords:
                results.append((apn, coords[0], coords[1]))
    return results


def get_missing_with_addresses(apns: list[str]) -> list[tuple[str, str]]:
    """Fetch address info for APNs from the bills table. Returns (apn, full_address)."""
    client = db.get_client()
    results: list[tuple[str, str]] = []
    for i in range(0, len(apns), BATCH_SIZE):
        chunk = apns[i : i + BATCH_SIZE]
        r = (client.table("bills")
             .select("apn, location_of_property, city")
             .in_("apn", chunk)
             .execute())
        for row in r.data or []:
            addr = (row.get("location_of_property") or "").strip()
            city = (row.get("city") or "").strip().lstrip("_ ")
            if addr and city:
                results.append((row["apn"], f"{addr}, {city}, CA"))
    return results


def make_map_html_query(query: str) -> str:
    """Build embedded maps HTML using an address query instead of coordinates."""
    from urllib.parse import quote_plus
    return f"""<!DOCTYPE html><html><head>
<style>body{{margin:0;padding:0;overflow:hidden;background:#eee}}iframe{{border:none;width:640px;height:480px}}</style>
</head><body>
<iframe src="https://maps.google.com/maps?q={quote_plus(query)}&t=k&z=19&output=embed"></iframe>
</body></html>"""


def make_map_html(lat: float, lng: float) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>body{{margin:0;padding:0;overflow:hidden;background:#eee}}iframe{{border:none;width:640px;height:480px}}</style>
</head><body>
<iframe src="https://maps.google.com/maps?q={lat},{lng}&t=k&z=19&output=embed"></iframe>
</body></html>"""


async def _screenshot_map(page, apn: str, html: str) -> bool:
    """Load map HTML in a page, screenshot the iframe, save and update DB."""
    safe = apn.replace("/", "_").replace("\\", "_")
    path = STREETVIEW_DIR / f"{safe}.jpg"
    if path.exists() and path.stat().st_size > 1000:
        return True
    try:
        await page.set_content(html)
        await page.wait_for_timeout(MAP_WAIT_MS)
        element = page.locator("iframe")
        await element.screenshot(path=str(path), type="jpeg", quality=90)
        if path.exists() and path.stat().st_size > 500:
            db.get_client().table("bills").update(
                {"streetview_image_path": str(path)}
            ).eq("apn", apn).execute()
            return True
        return False
    except Exception as e:
        print(f"  Error for {apn}: {e}")
        return False


async def worker(browser, queue: asyncio.Queue, stats: dict):
    page = await browser.new_page(viewport={"width": 640, "height": 480})
    try:
        while not shutdown_requested:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if len(item) == 3:
                apn, lat, lng = item
                html = make_map_html(lat, lng)
            else:
                apn, address = item
                html = make_map_html_query(address)
            ok = await _screenshot_map(page, apn, html)
            stats["done"] += 1
            if ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1
            if stats["done"] % 25 == 0:
                elapsed = time.time() - stats["start"]
                rate = stats["done"] / elapsed if elapsed > 0 else 0
                remaining = (stats["total"] - stats["done"]) / rate if rate > 0 else 0
                print(
                    f"  Progress: {stats['done']}/{stats['total']} "
                    f"({stats['success']} ok, {stats['failed']} fail) "
                    f"- {rate:.1f}/s, ~{remaining/60:.0f}m remaining"
                )
            queue.task_done()
    finally:
        await page.close()


async def fetch_batch(items: list[tuple], label: str):
    """Fetch satellite images for a list of (apn, lat, lng) or (apn, address) tuples."""
    if not items:
        print(f"  {label}: Nothing to fetch!")
        return

    from playwright.async_api import async_playwright

    queue: asyncio.Queue = asyncio.Queue()
    for item in items:
        queue.put_nowait(item)

    stats = {
        "done": 0, "success": 0, "failed": 0,
        "total": len(items), "start": time.time(),
    }

    print(f"  {label}: Fetching {len(items)} images with {CONCURRENCY} workers...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        workers = [asyncio.create_task(worker(browser, queue, stats)) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)
        await browser.close()

    elapsed = time.time() - stats["start"]
    print(
        f"  {label} done: {stats['success']} fetched, {stats['failed']} failed "
        f"in {elapsed/60:.1f}m ({stats['done']/elapsed:.1f}/s)"
    )


def handle_signal(sig, frame):
    global shutdown_requested
    print("\nShutdown requested, finishing current batch...")
    shutdown_requested = True


async def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("=== Streetview Image Backfill ===")
    print(f"Image directory: {STREETVIEW_DIR}")

    print("\nGathering properties missing streetview images...")
    missing_apns = get_missing_apns()
    print(f"  {len(missing_apns)} properties missing streetview in DB")

    if not missing_apns:
        print("Nothing to do!")
        return

    print("\nPhase 1: Reconciling disk images with DB...")
    still_missing = phase1_reconcile_disk(missing_apns)
    print(f"  {len(still_missing)} still need fetching")

    if not still_missing or shutdown_requested:
        print("Done!")
        return

    print("\nResolving parcel coordinates...")
    apns_with_coords = get_coords_batch(still_missing)
    parcel_apns = {t[0] for t in apns_with_coords}
    no_parcel_apns = [a for a in still_missing if a not in parcel_apns]
    print(f"  {len(apns_with_coords)} have parcel coords, {len(no_parcel_apns)} need address lookup")

    if apns_with_coords and not shutdown_requested:
        await fetch_batch(apns_with_coords, "Phase 2 (parcel coords)")

    if no_parcel_apns and not shutdown_requested:
        print(f"\nPhase 3: Resolving addresses for {len(no_parcel_apns)} properties...")
        addr_items = get_missing_with_addresses(no_parcel_apns)
        print(f"  {len(addr_items)} have usable addresses")
        if addr_items and not shutdown_requested:
            await fetch_batch(addr_items, "Phase 3 (address lookup)")

    print("\n=== Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

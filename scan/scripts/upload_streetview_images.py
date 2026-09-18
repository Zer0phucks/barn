#!/usr/bin/env python3
"""Upload local streetview_images/<apn>.jpg files to Supabase Storage for bills rows.

The Android scout app and the gallery read bills.streetview_image_path as a URL,
so images that only exist on the scanner's disk are invisible to them. This
uploads the image for every bill that has a local file and records its public
URL, using the same object naming as condition_scanner._upload_to_storage.

Rows that already hold an http(s) URL are skipped unless --force is given.

    python scripts/upload_streetview_images.py [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
import db  # noqa: E402

STREETVIEW_DIR = BASE_DIR / "streetview_images"
STORAGE_BUCKET = "streetview-images"
WORKERS = 3


def all_bills() -> list[dict]:
    client = db.get_client()
    rows, offset = [], 0
    while True:
        page = (
            client.table("bills")
            .select("apn,streetview_image_path")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        rows += page
        if len(page) < 1000:
            return rows
        offset += 1000


def upload(apn: str, local_path: Path, attempts: int = 3) -> str:
    # The shared Supabase client drops connections under concurrent uploads
    # ("Server disconnected"); a short retry clears nearly all of them.
    for attempt in range(1, attempts + 1):
        try:
            return _upload_once(apn, local_path)
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(attempt)
    raise AssertionError("unreachable")


def _upload_once(apn: str, local_path: Path) -> str:
    object_path = f"{apn.replace('/', '_').replace(chr(92), '_')}.jpg"
    storage = db.get_client().storage.from_(STORAGE_BUCKET)
    storage.upload(
        object_path,
        local_path.read_bytes(),
        file_options={"content-type": "image/jpeg", "upsert": "true"},
    )
    url = storage.get_public_url(object_path).rstrip("?")
    db.get_client().table("bills").update({"streetview_image_path": url}).eq("apn", apn).execute()
    return url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="re-upload rows that already have a URL")
    args = parser.parse_args()

    todo, no_file, has_url = [], 0, 0
    for row in all_bills():
        existing = (row.get("streetview_image_path") or "").strip()
        if existing.startswith(("http://", "https://")) and not args.force:
            has_url += 1
            continue
        local = STREETVIEW_DIR / f"{row['apn'].replace('/', '_').replace(chr(92), '_')}.jpg"
        if local.is_file():
            todo.append((row["apn"], local))
        else:
            no_file += 1

    print(f"to upload: {len(todo)}, already have URL: {has_url}, no local image: {no_file}")
    if args.dry_run or not todo:
        return

    done = failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(upload, apn, path): apn for apn, path in todo}
        for future in as_completed(futures):
            try:
                future.result()
                done += 1
            except Exception as exc:  # keep going; report at the end
                failed += 1
                print(f"  failed {futures[future]}: {exc}")
            if (done + failed) % 100 == 0:
                print(f"  {done + failed}/{len(todo)}")
    print(f"uploaded {done}, failed {failed}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Export CyberBackgroundChecks links from bills table.

Outputs:
- CSV with columns: apn, link_type, url
- TXT containing one unique URL per line
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import db


def is_cbc_url(url: str) -> bool:
    return "cyberbackgroundchecks.com" in (url or "").lower()


def fetch_all_bills_links(batch_size: int = 1000) -> list[dict[str, str]]:
    client = db.get_client()
    rows: list[dict[str, str]] = []
    start = 0
    while True:
        end = start + batch_size - 1
        res = (
            client.table("bills")
            .select("apn,property_search_url,mailing_search_url")
            .range(start, end)
            .execute()
        )
        batch = res.data or []
        if not batch:
            break
        for item in batch:
            apn = (item.get("apn") or "").strip()
            prop = (item.get("property_search_url") or "").strip()
            mail = (item.get("mailing_search_url") or "").strip()
            if prop and is_cbc_url(prop):
                rows.append({"apn": apn, "link_type": "property", "url": prop})
            if mail and is_cbc_url(mail):
                rows.append({"apn": apn, "link_type": "mailing", "url": mail})
        start += batch_size
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CBC links to CSV/TXT")
    parser.add_argument("--out-dir", default="export_batches", help="Output directory")
    parser.add_argument("--prefix", default="cbc_links", help="Output file prefix")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    rows = fetch_all_bills_links()
    if not rows:
        print("No CBC links found.")
        return

    csv_path = out_dir / f"{args.prefix}_{ts}.csv"
    txt_path = out_dir / f"{args.prefix}_{ts}.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["apn", "link_type", "url"])
        writer.writeheader()
        writer.writerows(rows)

    seen: set[str] = set()
    unique_urls: list[str] = []
    for r in rows:
        u = r["url"]
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    with txt_path.open("w", encoding="utf-8") as f:
        for u in unique_urls:
            f.write(u + "\n")

    print(f"Exported {len(rows)} rows to {csv_path}")
    print(f"Exported {len(unique_urls)} unique URLs to {txt_path}")


if __name__ == "__main__":
    main()


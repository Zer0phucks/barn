#!/usr/bin/env python3
"""
Take full-page screenshots for a list of links (TXT or CSV).

Safe behavior:
- Does NOT automate CAPTCHA interaction.
- If a challenge page is detected, pauses and asks you to solve manually.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable

from playwright.sync_api import sync_playwright


CHALLENGE_MARKERS = (
    "just a moment",
    "security verification",
    "enable javascript and cookies to continue",
    "challenge-platform",
    "verify you are human",
)


def is_challenge(content: str) -> bool:
    text = (content or "").lower()
    return any(marker in text for marker in CHALLENGE_MARKERS)


def slugify(value: str, max_len: int = 70) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return s[:max_len] if s else "link"


def read_links(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Links file not found: {path}")

    out: list[str] = []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if "url" in (reader.fieldnames or []):
                for row in reader:
                    u = (row.get("url") or "").strip()
                    if u:
                        out.append(u)
            else:
                f.seek(0)
                raw = csv.reader(f)
                for row in raw:
                    if not row:
                        continue
                    u = (row[0] or "").strip()
                    if u and u.lower().startswith("http"):
                        out.append(u)
    else:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u and u.lower().startswith("http"):
                    out.append(u)

    # Keep order, dedupe
    seen: set[str] = set()
    deduped: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def chunk(iterable: list[str], limit: int | None) -> Iterable[str]:
    if limit is None or limit <= 0:
        yield from iterable
    else:
        for i, item in enumerate(iterable):
            if i >= limit:
                break
            yield item


def main() -> None:
    parser = argparse.ArgumentParser(description="Take full-page screenshots from link list.")
    parser.add_argument("--links", required=True, help="Path to TXT/CSV link file")
    parser.add_argument("--out-dir", default="export_batches/cbc_screenshots", help="Output directory")
    parser.add_argument("--wait-seconds", type=float, default=2.0, help="Wait after navigation")
    parser.add_argument("--post-action-wait-seconds", type=float, default=2.0, help="Wait after manual challenge solve")
    parser.add_argument(
        "--challenge-wait-seconds",
        type=float,
        default=30.0,
        help="Fallback wait in non-interactive mode when challenge is detected",
    )
    parser.add_argument("--timeout-seconds", type=float, default=60.0, help="Navigation timeout")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of links")
    parser.add_argument(
        "--profile-dir",
        default=".cbc_profile_screenshots",
        help="Persistent Playwright profile dir (keeps session cookies)",
    )
    args = parser.parse_args()

    links_path = Path(args.links)
    out_dir = Path(args.out_dir)
    profile_dir = Path(args.profile_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    links = read_links(links_path)
    if not links:
        print("No links found.")
        return

    timeout_ms = int(args.timeout_seconds * 1000)
    wait_ms = int(max(0.0, args.wait_seconds) * 1000)
    post_wait_ms = int(max(0.0, args.post_action_wait_seconds) * 1000)
    challenge_wait_ms = int(max(0.0, args.challenge_wait_seconds) * 1000)
    total = min(len(links), args.limit) if args.limit and args.limit > 0 else len(links)

    print(f"Loaded {len(links)} links. Processing {total}.")
    print(f"Screenshots directory: {out_dir}")
    print(f"Playwright profile: {profile_dir}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 1000},
            locale="en-US",
        )
        page = context.pages[0] if context.pages else context.new_page()

        for i, url in enumerate(chunk(links, args.limit), start=1):
            print(f"[{i}/{total}] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(wait_ms)
            except Exception as e:
                print(f"  navigation error: {e}")

            html = page.content() or ""
            if is_challenge(html):
                print("  challenge detected. Solve it manually in browser, then press Enter to continue.")
                if sys.stdin.isatty():
                    input("  press Enter when ready...")
                else:
                    print(f"  non-interactive session; waiting {args.challenge_wait_seconds:.1f}s before continuing.")
                    page.wait_for_timeout(challenge_wait_ms)
                page.wait_for_timeout(post_wait_ms)

            filename = f"{i:05d}_{slugify(url)}.png"
            out_path = out_dir / filename
            try:
                page.screenshot(path=str(out_path), full_page=True)
                print(f"  saved: {out_path}")
            except Exception as e:
                print(f"  screenshot error: {e}")

        context.close()

    print("Done.")


if __name__ == "__main__":
    main()

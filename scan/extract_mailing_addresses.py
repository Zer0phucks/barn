#!/usr/bin/env python3
"""Extract mailing addresses from parcels CSV and write one per line to a text file."""
import csv

from pathlib import Path

INPUT_CSV = Path(__file__).resolve().parent / "Parcels_5567367248157875843.csv"
OUTPUT_TXT = Path(__file__).resolve().parent / "mailing_addresses.txt"

with open(INPUT_CSV, newline="", encoding="utf-8", errors="replace") as f_in:
    reader = csv.DictReader(f_in)
    if "MailingAddress" not in reader.fieldnames:
        raise SystemExit("CSV has no 'MailingAddress' column")
    addresses = [row["MailingAddress"].strip() for row in reader if row.get("MailingAddress", "").strip()]

with open(OUTPUT_TXT, "w", encoding="utf-8") as f_out:
    f_out.write("\n".join(addresses))

print(f"Wrote {len(addresses)} addresses to {OUTPUT_TXT}")

#!/usr/bin/env python3
"""
Parse bill PDFs in /home/noob/vpt/bandos and extract property location.
Outputs CSV with Google Maps links.
"""
from pathlib import Path
from urllib.parse import quote_plus
import csv
import re

from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
BANDOS_DIR = BASE_DIR / "bandos"
OUTPUT_CSV = BASE_DIR / "bandos_locations.csv"


def extract_location(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Location of Property:"):
            return line.replace("Location of Property:", "", 1).strip()
    return None


def main() -> None:
    pdfs = sorted(BANDOS_DIR.glob("*.pdf"))
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pdf_file", "location_of_property", "google_maps_url"])
        for pdf_path in pdfs:
            try:
                reader = PdfReader(str(pdf_path))
            except Exception:
                writer.writerow([pdf_path.name, "", ""])
                continue

            # Location appears on first page; read first page text
            text = ""
            if reader.pages:
                try:
                    text = reader.pages[0].extract_text() or ""
                except Exception:
                    text = ""

            location = extract_location(text)
            if not location:
                writer.writerow([pdf_path.name, "", ""])
                continue

            maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(location)}"
            writer.writerow([pdf_path.name, location, maps_url])


if __name__ == "__main__":
    main()

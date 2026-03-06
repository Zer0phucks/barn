#!/usr/bin/env python3
"""
Build Supabase database combining:
1) All positive scan results (bill PDFs in bandos)
2) All parcel CSV columns
3) Parsed bill PDF text and key fields
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from pypdf import PdfReader

import db

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Parcels_5567367248157875843.csv"
BANDOS_DIR = BASE_DIR / "bandos"


def extract_bill_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    def grab(prefix: str) -> str | None:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(prefix):
                return line.replace(prefix, "", 1).strip()
        return None

    parcel = grab("Parcel Number:")
    if parcel:
        fields["parcel_number"] = parcel
    tracer = grab("Tracer Number:")
    if tracer:
        fields["tracer_number"] = tracer
    location = grab("Location of Property:")
    if location:
        fields["location_of_property"] = location
    tax_year = grab("Tax Year:")
    if tax_year:
        fields["tax_year"] = tax_year
    last_payment = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^PAID\s+([A-Z]{3}\s+\d{1,2},\s+\d{4})", line)
        if m:
            last_payment = m.group(1)
    if last_payment:
        fields["last_payment"] = last_payment
    delinquent = False
    for line in text.splitlines():
        upper = line.upper()
        if "DELINQUENT" in upper and "DELINQUENCY" not in upper:
            delinquent = True
            break
    fields["delinquent"] = "1" if delinquent else "0"
    return fields


def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def build_db() -> None:
    # Load parcels CSV into memory
    apn_to_rowjson: dict[str, str] = {}
    with CSV_PATH.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apn = (row.get("APN") or "").strip()
            if not apn:
                continue
            apn_to_rowjson[apn] = json.dumps(row, ensure_ascii=True)

    # Upsert all parcels to Supabase in batches
    for apn, row_json in apn_to_rowjson.items():
        db.upsert_parcel(apn, row_json)

    # Process bill PDFs (positive results)
    pdfs = sorted(BANDOS_DIR.glob("*.pdf"))
    for pdf_path in pdfs:
        pdf_file = pdf_path.name
        raw_text = read_pdf_text(pdf_path)
        fields = extract_bill_fields(raw_text)
        parcel_number = fields.get("parcel_number")
        apn = None
        m = re.match(r"bill_(.+)_\d{4}\.pdf", pdf_file)
        if m:
            apn = m.group(1)
        elif parcel_number:
            apn = parcel_number
        if not apn:
            continue
        row_json = apn_to_rowjson.get(apn)
        if row_json:
            db.upsert_parcel(apn, row_json)
        db.upsert_bill(
            apn=apn,
            pdf_file=pdf_file,
            parcel_number=parcel_number,
            tracer_number=fields.get("tracer_number"),
            location_of_property=fields.get("location_of_property"),
            tax_year=fields.get("tax_year"),
            last_payment=fields.get("last_payment"),
            delinquent=int(fields.get("delinquent") or 0),
            raw_text=raw_text,
        )
        db.upsert_result(apn, pdf_file)


if __name__ == "__main__":
    build_db()

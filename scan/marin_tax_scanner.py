#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

BASE_URL = "https://apps.marincounty.gov"
SEARCH_URL = f"{BASE_URL}/taxbillonline"
MARIN_CITIES = {
    "BELVEDERE",
    "BELVEDERE TIBURON",
    "CORTE MADERA",
    "FAIRFAX",
    "GREENBRAE",
    "KENTFIELD",
    "LARKSPUR",
    "MARIN CITY",
    "MILL VALLEY",
    "NOVATO",
    "ROSS",
    "SAN ANSELMO",
    "SAN RAFAEL",
    "SAUSALITO",
    "TIBURON",
}
DELINQUENT_MARKERS = (
    "delinquent",
    "default",
    "past due",
    "redemption",
    "penalty",
    "unpaid",
)


@dataclass(frozen=True)
class MarinBillStatus:
    tax_year: str
    bill_number: str
    bill_type: str
    install_1: str
    install_2: str


@dataclass(frozen=True)
class MarinTaxResult:
    apn: str
    property_id: str
    found: bool
    is_delinquent: bool
    bill_url: str | None
    tax_year: str | None
    situs_address: str | None
    bills: list[MarinBillStatus]
    error: str | None = None


def normalize_marin_property_id(apn: str) -> str:
    parts = [part for part in re.split(r"\D+", apn.strip()) if part]
    if len(parts) >= 3 and len(parts[2]) <= 2:
        return f"{int(parts[0]):03d}{int(parts[1]):03d}{int(parts[2]):02d}"
    digits = "".join(parts)
    if len(digits) == 8:
        return digits
    if len(digits) == 7:
        return f"0{digits}"
    return digits


def format_property_id(property_id: str) -> str:
    digits = re.sub(r"\D+", "", property_id)
    if len(digits) != 8:
        return property_id
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_status_delinquent(status: str, tax_year: str) -> bool:
    value = status.strip().lower()
    if not value or value == "paid":
        return False
    if any(marker in value for marker in DELINQUENT_MARKERS):
        return True
    year_match = re.match(r"(\d{4})/", tax_year.strip())
    if year_match and int(year_match.group(1)) < 2025:
        return True
    return False


def parse_search_results(apn: str, html_text: str) -> MarinTaxResult:
    property_id = normalize_marin_property_id(apn)
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)
    if "Tax Bills for Parcel # / Property ID" not in text:
        return MarinTaxResult(
            apn=apn,
            property_id=property_id,
            found=False,
            is_delinquent=False,
            bill_url=None,
            tax_year=None,
            situs_address=None,
            bills=[],
            error="No tax bill search results found",
        )

    situs_address = None
    m = re.search(r"Situs Address:\s*([^\n]+)", text)
    if m:
        situs_address = _clean_text(m.group(1))

    bills: list[MarinBillStatus] = []
    for table in soup.find_all("table"):
        headers = [_clean_text(cell.get_text(" ", strip=True)).lower() for cell in table.find_all("th")]
        if not {"tax year", "bill number", "install 1", "install 2"}.issubset(set(headers)):
            continue
        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            if len(cells) < 5:
                continue
            bills.append(
                MarinBillStatus(
                    tax_year=cells[0],
                    bill_number=cells[1],
                    bill_type=cells[2],
                    install_1=cells[3],
                    install_2=cells[4],
                )
            )

    if not bills:
        return MarinTaxResult(
            apn=apn,
            property_id=property_id,
            found=False,
            is_delinquent=False,
            bill_url=None,
            tax_year=None,
            situs_address=situs_address,
            bills=[],
            error="No bill rows found",
        )

    latest = bills[0]
    is_delinquent = any(
        _is_status_delinquent(bill.install_1, bill.tax_year)
        or _is_status_delinquent(bill.install_2, bill.tax_year)
        for bill in bills
    )
    return MarinTaxResult(
        apn=apn,
        property_id=property_id,
        found=True,
        is_delinquent=is_delinquent,
        bill_url=f"{BASE_URL}/TaxBillOnline/Bill?BillNumber={latest.bill_number}",
        tax_year=latest.tax_year,
        situs_address=situs_address,
        bills=bills,
    )


def create_session():
    from curl_cffi import requests

    session = requests.Session(impersonate="chrome124")
    response = session.get(SEARCH_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    accept_url = None
    for link in soup.find_all("a", href=True):
        if link.get_text(" ", strip=True).lower() == "accept":
            accept_url = link["href"]
            break
    if accept_url:
        accepted = session.get(accept_url, timeout=30)
        accepted.raise_for_status()
    return session


def check_marin_property_taxes(session: Any, apn: str) -> MarinTaxResult:
    property_id = normalize_marin_property_id(apn)
    response = session.get(SEARCH_URL, params={"PropertyId": property_id}, timeout=30)
    response.raise_for_status()
    return parse_search_results(apn, response.text)


def _normalized_city(row: dict[str, Any]) -> str:
    return str(row.get("city") or "").strip().lstrip("_ ").upper()


def load_marin_bill_rows() -> list[dict[str, Any]]:
    import db

    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        result = (
            db.get_client()
            .table("bills")
            .select("apn,city,location_of_property,delinquent,bill_url,tax_year")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        chunk = result.data or []
        rows.extend(row for row in chunk if _normalized_city(row) in MARIN_CITIES or "TIBUR" in _normalized_city(row))
        if len(chunk) < page_size:
            break
        offset += page_size
    return rows


def update_marin_delinquency(rows: list[dict[str, Any]], dry_run: bool = True, limit: int | None = None) -> dict[str, Any]:
    import db

    session = create_session()
    summary: dict[str, Any] = {
        "checked": 0,
        "found": 0,
        "delinquent": 0,
        "not_delinquent": 0,
        "updated": 0,
        "errors": [],
        "delinquent_apns": [],
    }
    selected_rows = rows[:limit] if limit else rows
    for index, row in enumerate(selected_rows, start=1):
        apn = str(row.get("apn") or "").strip()
        if not apn:
            continue
        summary["checked"] += 1
        try:
            result = check_marin_property_taxes(session, apn)
            if not result.found:
                summary["errors"].append({"apn": apn, "error": result.error})
                print(f"[{index}/{len(selected_rows)}] {apn} not found: {result.error}", flush=True)
                continue
            summary["found"] += 1
            summary["delinquent" if result.is_delinquent else "not_delinquent"] += 1
            if result.is_delinquent:
                summary["delinquent_apns"].append(apn)
            fields = {
                "delinquent": 1 if result.is_delinquent else 0,
                "bill_url": result.bill_url,
                "tax_year": result.tax_year,
                "raw_text": json.dumps(
                    {
                        "source": "marin_taxbillonline",
                        "property_id": format_property_id(result.property_id),
                        "situs_address": result.situs_address,
                        "bills": [bill.__dict__ for bill in result.bills],
                    },
                    sort_keys=True,
                ),
            }
            if not dry_run:
                db.update_bill_fields(apn, fields)
                summary["updated"] += 1
            print(
                f"[{index}/{len(selected_rows)}] {apn} {row.get('city') or ''} "
                f"delinquent={result.is_delinquent} bills={len(result.bills)}",
                flush=True,
            )
            time.sleep(0.15)
        except Exception as exc:
            summary["errors"].append({"apn": apn, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(selected_rows)}] {apn} error: {exc}", flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Marin County tax delinquency for BARN properties.")
    parser.add_argument("--apply", action="store_true", help="Write delinquency results to Supabase.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of Marin-like rows to check.")
    args = parser.parse_args()
    rows = load_marin_bill_rows()
    print(f"Loaded {len(rows)} Marin-like properties")
    summary = update_marin_delinquency(rows, dry_run=not args.apply, limit=args.limit)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

BASE_URL = "https://taxcolp.cccttc.us"
LOOKUP_URL = f"{BASE_URL}/lookup/"
APN_API_URL = f"{BASE_URL}/api/lookup/apn"
CONTRA_COSTA_CITIES = {
    "ALAMO",
    "ANTIOCH",
    "BAY POINT",
    "BETHEL ISLAND",
    "BRENTWOOD",
    "BYRON",
    "CLAYTON",
    "CLYDE",
    "CONCORD",
    "CROCKETT",
    "DANVILLE",
    "DIABLO",
    "DISCOVERY BAY",
    "EL CERRITO",
    "EL SOBRANTE",
    "HERCULES",
    "KENSINGTON",
    "KNIGHTSEN",
    "LAFAYETTE",
    "MARTINEZ",
    "MORAGA",
    "OAKLEY",
    "ORINDA",
    "PACHECO",
    "PINOLE",
    "PITTSBURG",
    "PLEASANT HILL",
    "PORT COSTA",
    "RICHMOND",
    "RODEO",
    "SAN PABLO",
    "SAN RAMON",
    "WALNUT CREEK",
}


@dataclass(frozen=True)
class ContraCostaTaxResult:
    apn: str
    normalized_apn: str
    found: bool
    is_delinquent: bool
    bill_url: str | None
    tax_year: str | None
    address: str | None
    last_payment: str | None
    response: dict[str, Any] | None = None
    error: str | None = None


def normalize_contra_costa_apn(apn: str) -> str:
    parts = [part for part in re.split(r"\D+", apn.strip()) if part]
    if len(parts) >= 4:
        return f"{int(parts[0]):03d}{int(parts[1]):03d}{int(parts[2]):03d}{int(parts[3]):01d}"
    digits = "".join(parts)
    if len(digits) == 10:
        return digits
    if 0 < len(digits) < 10:
        return digits.zfill(10)
    return digits


def format_contra_costa_apn(apn: str) -> str:
    digits = re.sub(r"\D+", "", apn)
    if len(digits) != 10:
        return apn
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}-{digits[9:]}"


def _normalized_city(row: dict[str, Any]) -> str:
    return str(row.get("city") or "").strip().lstrip("_ .,").upper()


def _is_response_delinquent(response: dict[str, Any]) -> bool:
    details = response.get("details") or {}
    if any(
        bool(details.get(flag))
        for flag in ("delinquent", "owesPriorYear", "budContainsDelinquentTaxes")
    ):
        return True
    for installment in response.get("installments") or []:
        is_prior_year = bool(installment.get("priorYear"))
        if is_prior_year and not bool(details.get("containsPriorYear")):
            # The API includes old historical late/transfer rows. Only treat
            # prior-year rows as active delinquency when the detail flags say
            # prior-year taxes are part of the current account state.
            continue
        if bool(installment.get("isDelinquent")):
            return True
        status = str(installment.get("status") or "").strip().upper()
        if status in {"DELINQUENT", "DEFAULT", "TRANSFER", "REDEMPTION"}:
            return True
        penalty = str(installment.get("priorYearDelinquentPenalty") or "").replace(",", "").strip()
        if status != "PAID" and penalty:
            try:
                if float(penalty) > 0:
                    return True
            except ValueError:
                pass
    return False


def _latest_paid_date(response: dict[str, Any]) -> str | None:
    latest: datetime | None = None
    latest_text: str | None = None
    for installment in response.get("installments") or []:
        paid_date = installment.get("paidDate")
        if not paid_date:
            continue
        try:
            parsed = datetime.strptime(str(paid_date), "%m/%d/%Y")
        except ValueError:
            continue
        if latest is None or parsed > latest:
            latest = parsed
            latest_text = str(paid_date)
    return latest_text


def parse_api_response(apn: str, response: dict[str, Any]) -> ContraCostaTaxResult:
    normalized = normalize_contra_costa_apn(apn)
    details = response.get("details") or {}
    api_apn = details.get("apn") or format_contra_costa_apn(normalized)
    return ContraCostaTaxResult(
        apn=apn,
        normalized_apn=normalized,
        found=True,
        is_delinquent=_is_response_delinquent(response),
        bill_url=f"{LOOKUP_URL}?apn={normalized}&verify=true",
        tax_year=(response.get("assessment") or {}).get("assessmentYear"),
        address=details.get("address"),
        last_payment=_latest_paid_date(response),
        response={
            "source": "contra_costa_tax_lookup",
            "apn": api_apn,
            "details": details,
            "assessment": response.get("assessment"),
            "installments": response.get("installments") or [],
            "resultsMessages": response.get("resultsMessages"),
        },
    )


def check_contra_costa_property_taxes(session: requests.Session, apn: str) -> ContraCostaTaxResult:
    normalized = normalize_contra_costa_apn(apn)
    response = session.get(
        APN_API_URL,
        params={"apn": normalized},
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    if response.status_code == 404:
        return ContraCostaTaxResult(
            apn=apn,
            normalized_apn=normalized,
            found=False,
            is_delinquent=False,
            bill_url=None,
            tax_year=None,
            address=None,
            last_payment=None,
            error=response.json().get("displayMessage", "APN not found"),
        )
    if response.status_code == 400:
        return ContraCostaTaxResult(
            apn=apn,
            normalized_apn=normalized,
            found=False,
            is_delinquent=False,
            bill_url=None,
            tax_year=None,
            address=None,
            last_payment=None,
            error=response.json().get("displayMessage", "Invalid APN"),
        )
    response.raise_for_status()
    return parse_api_response(apn, response.json())


def load_contra_costa_bill_rows() -> list[dict[str, Any]]:
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
        rows.extend(row for row in chunk if _normalized_city(row) in CONTRA_COSTA_CITIES)
        if len(chunk) < page_size:
            break
        offset += page_size
    return rows


def update_contra_costa_delinquency(
    rows: list[dict[str, Any]], dry_run: bool = True, limit: int | None = None
) -> dict[str, Any]:
    import db

    session = requests.Session()
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
            result = check_contra_costa_property_taxes(session, apn)
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
                "last_payment": result.last_payment,
                "raw_text": json.dumps(result.response, sort_keys=True),
            }
            if not dry_run:
                db.update_bill_fields(apn, fields)
                summary["updated"] += 1
            print(
                f"[{index}/{len(selected_rows)}] {apn} {row.get('city') or ''} "
                f"delinquent={result.is_delinquent}",
                flush=True,
            )
            time.sleep(0.05)
        except Exception as exc:
            summary["errors"].append({"apn": apn, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(selected_rows)}] {apn} error: {exc}", flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Contra Costa County tax delinquency for BARN properties.")
    parser.add_argument("--apply", action="store_true", help="Write delinquency results to Supabase.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of Contra Costa-like rows to check.")
    args = parser.parse_args()
    rows = load_contra_costa_bill_rows()
    print(f"Loaded {len(rows)} Contra Costa-like properties")
    summary = update_contra_costa_delinquency(rows, dry_run=not args.apply, limit=args.limit)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

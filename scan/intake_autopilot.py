#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import argparse
import csv
import json
import logging
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fcntl

import db
import find_meas_w_addresses as vpt_scanner

BASE_DIR = Path(__file__).resolve().parent
PARCELS_CSV_PATH = BASE_DIR / "parcels.csv"
LEGACY_PARCELS_CSV_PATH = BASE_DIR / "Parcels_5567367248157875843.csv"
BACKLOG_LOCK_PATH = BASE_DIR / ".parcels.csv.lock"

logger = logging.getLogger(__name__)

intake_state: dict[str, Any] = {
    "is_running": False,
    "current_apn": None,
    "processed": 0,
    "promoted": 0,
    "remaining": 0,
    "mode": None,
    "last_summary": None,
}


@dataclass(slots=True)
class IntakeResult:
    apn: str
    address: str
    has_vpt: bool
    is_delinquent: bool
    bill_url: str | None
    vpt_marker: str | None
    power_status: str
    promoted: bool
    row: dict[str, str]


def canonical_parcels_path() -> Path:
    if PARCELS_CSV_PATH.exists():
        return PARCELS_CSV_PATH
    return LEGACY_PARCELS_CSV_PATH


def should_promote_property(power_status: str | None, has_vpt: bool) -> bool:
    return (power_status or "").strip().lower() == "off" or bool(has_vpt)


def reconcile_backlog_rows(rows: list[dict[str, str]], existing_apns: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if (row.get("APN") or "").strip() not in existing_apns]


def load_backlog_rows(csv_path: Path | None = None) -> tuple[list[dict[str, str]], list[str]]:
    path = csv_path or canonical_parcels_path()
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_backlog_csv(csv_path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=csv_path.parent,
        delete=False,
    ) as tmp_handle:
        writer = csv.DictWriter(tmp_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp_path = Path(tmp_handle.name)
    os.replace(tmp_path, csv_path)


@contextmanager
def backlog_lock(lock_path: Path | None = None):
    path = lock_path or BACKLOG_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def get_existing_bill_apns() -> set[str]:
    response = db.get_client().table("bills").select("apn").execute()
    return {str(row["apn"]) for row in (response.data or []) if row.get("apn")}


def upsert_promoted_parcel(result: IntakeResult) -> None:
    row_json = json.dumps(result.row, ensure_ascii=True)
    bill_html = ""
    if result.bill_url:
        bill_html = vpt_scanner.fetch_text(result.bill_url)
    vpt_scanner.upsert_db(
        result.apn,
        result.bill_url or "",
        bill_html,
        row_json,
        power_status=result.power_status,
    )


async def evaluate_parcel(row: dict[str, str]) -> IntakeResult:
    from pge_power_check import check_pge_power_status

    apn = (row.get("APN") or "").strip()
    address = (
        row.get("SitusAddress")
        or row.get("ADDRESS")
        or row.get("MailingAddress")
        or row.get("SitusStreet")
        or ""
    ).strip()

    tax_task = asyncio.to_thread(vpt_scanner.check_property_taxes, apn)
    if address:
        pge_task = check_pge_power_status(address, headless=True, verbose=False)
    else:
        async def _unknown() -> bool | None:
            return None
        pge_task = _unknown()

    tax_result, pge_result = await asyncio.gather(tax_task, pge_task)
    power_status = "unknown"
    if pge_result is True:
        power_status = "on"
    elif pge_result is False:
        power_status = "off"

    has_vpt = bool(tax_result.get("has_vpt"))
    promoted = should_promote_property(power_status=power_status, has_vpt=has_vpt)

    return IntakeResult(
        apn=apn,
        address=address,
        has_vpt=has_vpt,
        is_delinquent=bool(tax_result.get("is_delinquent")),
        bill_url=tax_result.get("bill_url"),
        vpt_marker=tax_result.get("vpt_marker"),
        power_status=power_status,
        promoted=promoted,
        row=row,
    )


async def _scan_backlog_rows(rows: list[dict[str, str]], max_concurrency: int) -> list[IntakeResult]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _bounded(row: dict[str, str]) -> IntakeResult:
        async with semaphore:
            intake_state["current_apn"] = (row.get("APN") or "").strip()
            result = await evaluate_parcel(row)
            intake_state["processed"] += 1
            if result.promoted:
                intake_state["promoted"] += 1
            return result

    return await asyncio.gather(*[_bounded(row) for row in rows])


def run_daily_intake(
    reconcile: bool = True,
    max_concurrency: int = 4,
    trigger_enrichment: bool = True,
) -> dict[str, Any]:
    import enrichment_runner

    path = canonical_parcels_path()
    intake_state.update(
        {
            "is_running": True,
            "current_apn": None,
            "processed": 0,
            "promoted": 0,
            "remaining": 0,
            "mode": "daily_intake",
        }
    )

    with backlog_lock():
        rows, fieldnames = load_backlog_rows(path)
        if reconcile:
            rows = reconcile_backlog_rows(rows, get_existing_bill_apns())
            write_backlog_csv(path, rows, fieldnames)

        results = asyncio.run(_scan_backlog_rows(rows, max_concurrency=max_concurrency))
        promoted_apns: list[str] = []
        surviving_rows: list[dict[str, str]] = []

        for result in results:
            if result.promoted and result.apn:
                upsert_promoted_parcel(result)
                promoted_apns.append(result.apn)
                logger.info(
                    "intake_promoted %s",
                    json.dumps(
                        {
                            "apn": result.apn,
                            "power_status": result.power_status,
                            "has_vpt": result.has_vpt,
                            "is_delinquent": result.is_delinquent,
                            "bill_url": result.bill_url,
                        },
                        sort_keys=True,
                    ),
                )
            else:
                surviving_rows.append(result.row)

        write_backlog_csv(path, surviving_rows, fieldnames)
        intake_state["remaining"] = len(surviving_rows)

    if trigger_enrichment:
        enrichment_runner.start_enrichment(promoted_apns, sweep_pending=True)

    summary = {
        "processed": intake_state["processed"],
        "promoted": intake_state["promoted"],
        "remaining": intake_state["remaining"],
        "promoted_apns": promoted_apns,
        "csv_path": str(path),
    }
    intake_state["is_running"] = False
    intake_state["current_apn"] = None
    intake_state["last_summary"] = summary
    return summary


def start_daily_intake(
    reconcile: bool = True,
    max_concurrency: int = 4,
    trigger_enrichment: bool = True,
) -> bool:
    if intake_state["is_running"]:
        return False

    def _runner() -> None:
        try:
            run_daily_intake(
                reconcile=reconcile,
                max_concurrency=max_concurrency,
                trigger_enrichment=trigger_enrichment,
            )
        finally:
            intake_state["is_running"] = False
            intake_state["current_apn"] = None

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return True


def get_intake_state() -> dict[str, Any]:
    return dict(intake_state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the daily parcel intake backlog scanner.")
    parser.add_argument("--reconcile-only", action="store_true", help="Only remove APNs already present in bills from parcels.csv")
    parser.add_argument("--no-enrichment", action="store_true", help="Skip triggering enrichment after promotions")
    parser.add_argument("--max-concurrency", type=int, default=4, help="Maximum number of parcel scans to evaluate concurrently")
    args = parser.parse_args()

    path = canonical_parcels_path()
    if args.reconcile_only:
        with backlog_lock():
            rows, fieldnames = load_backlog_rows(path)
            reconciled = reconcile_backlog_rows(rows, get_existing_bill_apns())
            write_backlog_csv(path, reconciled, fieldnames)
        return

    run_daily_intake(
        reconcile=True,
        max_concurrency=max(1, args.max_concurrency),
        trigger_enrichment=not args.no_enrichment,
    )


if __name__ == "__main__":
    main()

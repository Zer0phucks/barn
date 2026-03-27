#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import threading
from typing import Any

import db

enrichment_state: dict[str, Any] = {
    "is_running": False,
    "current_apn": None,
    "queue": [],
    "completed": 0,
    "failed": 0,
}


def bill_needs_enrichment(bill: dict[str, Any]) -> bool:
    research_status = (bill.get("research_status") or "").strip().lower()
    has_completed_research = research_status == "completed"
    has_condition = bill.get("condition_score") is not None
    return (not has_completed_research) or (not has_condition)


def build_enrichment_queue(new_apns: list[str], pending_apns: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for apn in [*new_apns, *pending_apns]:
        clean = (apn or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def get_bills_needing_enrichment() -> list[str]:
    response = db.get_client().table("bills").select("apn,research_status,condition_score").execute()
    return [
        str(row["apn"])
        for row in (response.data or [])
        if row.get("apn") and bill_needs_enrichment(row)
    ]


def _refresh_outreach(apn: str) -> None:
    try:
        bill = db.get_bill(apn)
        if not bill:
            return
        score = db.calculate_outreach_score(bill)
        completeness = db.calculate_contact_completeness(bill)
        outreach = db.get_outreach(apn)
        stage = db.determine_outreach_stage(bill, outreach)
        db.get_client().table("bills").update(
            {
                "outreach_score": score,
                "contact_completeness": completeness,
                "outreach_stage": stage,
            }
        ).eq("apn", apn).execute()
        db.upsert_outreach(apn, outreach_score=score, stage=stage)
    except Exception:
        pass


async def enrich_property(apn: str) -> tuple[bool, list[str]]:
    import condition_scanner
    import gemini_research_scanner

    notes: list[str] = []
    bill = db.get_bill(apn)
    if not bill:
        return False, [f"Missing bill for {apn}"]

    research_status = (bill.get("research_status") or "").strip().lower()
    if research_status != "completed":
        gemini_research_scanner.update_research_status(apn, "in_progress")
        try:
            success, result = await gemini_research_scanner.research_property(apn)
        except gemini_research_scanner.FatalResearchError as exc:
            gemini_research_scanner.update_research_status(apn, "failed")
            return False, [str(exc)]
        if not success:
            gemini_research_scanner.update_research_status(apn, "failed")
            return False, [str(result)]

        safe_apn = apn.replace("/", "_").replace("\\", "_")
        report_filename = f"report_{safe_apn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = gemini_research_scanner.REPORTS_DIR / report_filename
        with report_path.open("w", encoding="utf-8") as handle:
            handle.write(result)
        gemini_research_scanner.update_research_status(apn, "completed", str(report_path))
        notes.append(f"research:{report_path}")

    bill = db.get_bill(apn) or bill
    if bill.get("condition_score") is None:
        success, score, condition_notes, image_path = await condition_scanner.analyze_property_condition(apn)
        if not success:
            return False, [*notes, str(condition_notes)]

        condition_scanner.update_condition(apn, score, condition_notes, image_path)
        notes.append(f"condition:{score:.1f}")

    _refresh_outreach(apn)
    return True, notes


async def _process_queue() -> None:
    while enrichment_state["queue"]:
        apn = enrichment_state["queue"].pop(0)
        enrichment_state["current_apn"] = apn
        success, _notes = await enrich_property(apn)
        if success:
            enrichment_state["completed"] += 1
        else:
            enrichment_state["failed"] += 1

    enrichment_state["is_running"] = False
    enrichment_state["current_apn"] = None


def start_enrichment(apns: list[str], sweep_pending: bool = False) -> bool:
    pending_apns = get_bills_needing_enrichment() if sweep_pending else []
    queue = build_enrichment_queue(apns, pending_apns)
    if not queue:
        return True

    if enrichment_state["is_running"]:
        enrichment_state["queue"] = build_enrichment_queue(enrichment_state["queue"], queue)
        return True

    enrichment_state["is_running"] = True
    enrichment_state["queue"] = queue
    enrichment_state["completed"] = 0
    enrichment_state["failed"] = 0

    def _run() -> None:
        asyncio.run(_process_queue())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return True


def get_enrichment_state() -> dict[str, Any]:
    pending_count = len(get_bills_needing_enrichment())
    return {
        "is_running": enrichment_state["is_running"],
        "current_apn": enrichment_state["current_apn"],
        "queue_length": len(enrichment_state["queue"]),
        "completed": enrichment_state["completed"],
        "failed": enrichment_state["failed"],
        "pending_count": pending_count,
    }

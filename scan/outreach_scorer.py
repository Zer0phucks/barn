"""Outreach scoring engine -- calculates outreach readiness scores for all properties."""
from __future__ import annotations

import logging
import threading
from typing import Any

import db

logger = logging.getLogger(__name__)

scorer_state: dict[str, Any] = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "failed": 0,
}


def get_scorer_state() -> dict[str, Any]:
    return {
        "is_running": scorer_state["is_running"],
        "total": scorer_state["total"],
        "completed": scorer_state["completed"],
        "failed": scorer_state["failed"],
    }


def _run_scoring(apns: list[str] | None = None) -> None:
    """Score properties. If apns is None, score all."""
    global scorer_state
    try:
        if apns:
            resp = db.get_client().table("bills").select("*").in_("apn", apns).execute()
        else:
            resp = db.get_client().table("bills").select("*").execute()

        bills = resp.data or []
        scorer_state["total"] = len(bills)
        scorer_state["completed"] = 0
        scorer_state["failed"] = 0

        for bill in bills:
            try:
                apn = bill["apn"]
                score = db.calculate_outreach_score(bill)
                completeness = db.calculate_contact_completeness(bill)
                outreach = db.get_outreach(apn)
                stage = db.determine_outreach_stage(bill, outreach)

                db.get_client().table("bills").update({
                    "outreach_score": score,
                    "contact_completeness": completeness,
                    "outreach_stage": stage,
                }).eq("apn", apn).execute()

                db.upsert_outreach(apn, outreach_score=score, stage=stage)
                scorer_state["completed"] += 1

            except Exception:
                logger.exception("Failed to score APN %s", bill.get("apn"))
                scorer_state["failed"] += 1

    except Exception:
        logger.exception("Scoring run failed")
    finally:
        scorer_state["is_running"] = False


def start_scoring(apns: list[str] | None = None) -> bool:
    """Start the scoring engine in a background thread."""
    global scorer_state
    if scorer_state["is_running"]:
        return False
    scorer_state["is_running"] = True
    thread = threading.Thread(target=_run_scoring, args=(apns,), daemon=True)
    thread.start()
    return True

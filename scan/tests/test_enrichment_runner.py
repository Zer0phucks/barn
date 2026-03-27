from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

from enrichment_runner import build_enrichment_queue, bill_needs_enrichment


class BillNeedsEnrichmentTests(unittest.TestCase):
    def test_requires_enrichment_when_research_incomplete(self) -> None:
        bill = {"research_status": "unchecked", "condition_score": 5.0}
        self.assertTrue(bill_needs_enrichment(bill))

    def test_requires_enrichment_when_condition_missing(self) -> None:
        bill = {"research_status": "completed", "condition_score": None}
        self.assertTrue(bill_needs_enrichment(bill))

    def test_skips_bills_when_both_research_and_condition_are_complete(self) -> None:
        bill = {"research_status": "completed", "condition_score": 4.0}
        self.assertFalse(bill_needs_enrichment(bill))


class BuildEnrichmentQueueTests(unittest.TestCase):
    def test_prioritizes_new_apns_and_deduplicates(self) -> None:
        queue = build_enrichment_queue(["A", "B"], ["B", "C", "A", "D"])
        self.assertEqual(["A", "B", "C", "D"], queue)

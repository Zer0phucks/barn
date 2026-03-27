from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

from intake_autopilot import (
    reconcile_backlog_rows,
    should_promote_property,
    write_backlog_csv,
)


class ShouldPromotePropertyTests(unittest.TestCase):
    def test_promotes_when_power_is_off_and_vpt_is_false(self) -> None:
        self.assertTrue(should_promote_property(power_status="off", has_vpt=False))

    def test_promotes_when_vpt_is_true_and_power_is_on(self) -> None:
        self.assertTrue(should_promote_property(power_status="on", has_vpt=True))

    def test_does_not_promote_when_power_on_and_no_vpt(self) -> None:
        self.assertFalse(should_promote_property(power_status="on", has_vpt=False))

    def test_does_not_promote_when_power_unknown_and_no_vpt(self) -> None:
        self.assertFalse(should_promote_property(power_status="unknown", has_vpt=False))


class ReconcileBacklogRowsTests(unittest.TestCase):
    def test_removes_existing_apns_from_backlog(self) -> None:
        rows = [
            {"APN": "1", "SitusAddress": "A"},
            {"APN": "2", "SitusAddress": "B"},
            {"APN": "3", "SitusAddress": "C"},
        ]

        reconciled = reconcile_backlog_rows(rows, existing_apns={"2"})

        self.assertEqual(["1", "3"], [row["APN"] for row in reconciled])


class WriteBacklogCsvTests(unittest.TestCase):
    def test_writes_surviving_rows_with_original_header_order(self) -> None:
        rows = [
            {"APN": "1", "SitusAddress": "A", "SitusCity": "OAKLAND"},
            {"APN": "3", "SitusAddress": "C", "SitusCity": "BERKELEY"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "parcels.csv"
            fieldnames = ["APN", "SitusAddress", "SitusCity"]

            write_backlog_csv(csv_path, rows, fieldnames)

            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(fieldnames, reader.fieldnames)
                self.assertEqual(rows, list(reader))

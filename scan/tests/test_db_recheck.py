from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import db


class _PagedQuery:
    def __init__(self, client: "_PagedClient", table: str) -> None:
        self._client = client
        self._table = table
        self._range = (0, 999)

    def select(self, *args, **kwargs):
        return self

    def or_(self, expr):
        self._client.filters.append((self._table, "or", expr))
        return self

    def ilike(self, column, value):
        self._client.filters.append((self._table, "ilike", column, value))
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        start, end = self._range
        rows = self._client.rows.get(self._table, [])
        return type("R", (), {"data": rows[start : end + 1]})()


class _PagedClient:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.filters: list[tuple] = []

    def table(self, name):
        return _PagedQuery(self, name)


class RecheckHelperTests(unittest.TestCase):
    def test_get_bills_for_recheck_pages_past_1000_rows(self) -> None:
        client = _PagedClient({"bills": [{"apn": f"{i:04d}", "has_vpt": 1} for i in range(2300)]})
        with patch("db.get_client", return_value=client):
            rows = db.get_bills_for_recheck(city="OAKLAND")

        self.assertEqual(len(rows), 2300)
        self.assertEqual(rows["2299"]["has_vpt"], 1)
        self.assertIn(("bills", "or", "has_vpt.eq.1,delinquent.eq.1"), client.filters)
        self.assertIn(("bills", "ilike", "city", "OAKLAND"), client.filters)

    def test_get_bills_for_recheck_without_city_has_no_city_filter(self) -> None:
        client = _PagedClient({"bills": [{"apn": "001", "has_vpt": 1}]})
        with patch("db.get_client", return_value=client):
            db.get_bills_for_recheck()

        self.assertFalse([f for f in client.filters if f[1] == "ilike"])

    def test_get_curated_apns_unions_all_tables(self) -> None:
        client = _PagedClient(
            {
                "list_properties": [{"apn": "001"}, {"apn": "002"}],
                "scout_results": [{"apn": "002"}, {"apn": "003"}],
                "outreach": [{"apn": "004"}],
                "outreach_messages": [{"apn": "005"}, {"apn": None}],
            }
        )
        with patch("db.get_client", return_value=client):
            self.assertEqual(db.get_curated_apns(), {"001", "002", "003", "004", "005"})

    def test_get_results_apns_pages(self) -> None:
        client = _PagedClient({"bills": [{"apn": str(i)} for i in range(1500)]})
        with patch("db.get_client", return_value=client):
            self.assertEqual(len(db.get_results_apns()), 1500)


if __name__ == "__main__":
    unittest.main()

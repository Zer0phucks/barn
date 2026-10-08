from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import db


class _FakeQuery:
    """Records PostgREST builder calls and returns canned rows."""

    def __init__(self, log: dict, data: list[dict]) -> None:
        self._log = log
        self._data = data

    def _record(self, name, *args, **kwargs):
        self._log.setdefault(name, []).append((args, kwargs))
        return self

    def __getattr__(self, name):
        return lambda *args, **kwargs: self._record(name, *args, **kwargs)

    def execute(self):
        return type("R", (), {"data": self._data, "count": len(self._data)})()


class _FakeClient:
    def __init__(self, data: list[dict] | None = None) -> None:
        self.log: dict = {}
        self._data = data or []

    def table(self, name):
        return _FakeQuery(self.log, self._data)


class ZipFilterTests(unittest.TestCase):
    def _run(self, **kwargs):
        client = _FakeClient()
        with patch("db.get_client", return_value=client):
            db.get_bills_with_parcels_filtered(page=1, page_size=25, **kwargs)
        return client

    def test_zip_filter_matches_zip_code_or_situs_zip(self) -> None:
        client = self._run(zip_filter="94606")
        args, _ = client.log["or_"][0]
        self.assertEqual("zip_code.in.(94606),situs_zip.in.(94606)", args[0])

    def test_zip_filter_accepts_multiple_zips(self) -> None:
        client = self._run(zip_filter="94606,94704")
        args, _ = client.log["or_"][0]
        self.assertEqual("zip_code.in.(94606,94704),situs_zip.in.(94606,94704)", args[0])

    def test_zip_filter_ignores_non_zip_values(self) -> None:
        client = self._run(zip_filter="not-a-zip")
        self.assertNotIn("or_", client.log)

    def test_distinct_zips_union_both_columns(self) -> None:
        rows = [
            {"zip_code": "94606", "situs_zip": None},
            {"zip_code": None, "situs_zip": "94704"},
            {"zip_code": "94606", "situs_zip": "94606"},
        ]
        client = _FakeClient(data=rows)
        with patch("db.get_client", return_value=client):
            zips = db.get_distinct_zips()
        self.assertEqual(["94606", "94704"], zips)


if __name__ == "__main__":
    unittest.main()

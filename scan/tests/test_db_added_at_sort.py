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
    """Records the PostgREST builder calls get_bills_with_parcels_filtered makes."""

    def __init__(self, log: dict) -> None:
        self._log = log

    def _record(self, name, *args, **kwargs):
        self._log.setdefault(name, []).append((args, kwargs))
        return self

    def __getattr__(self, name):
        return lambda *args, **kwargs: self._record(name, *args, **kwargs)

    def execute(self):
        return type("R", (), {"data": [], "count": 0})()


class _FakeClient:
    def __init__(self) -> None:
        self.log: dict = {}
        self.table_name = None

    def table(self, name):
        self.table_name = name
        return _FakeQuery(self.log)


class AddedAtSortTests(unittest.TestCase):
    """`added_at` is a real bills column, so sorting by it must reach the database
    rather than being silently dropped or sorted client-side."""

    def _run(self, **kwargs):
        client = _FakeClient()
        with patch("db.get_client", return_value=client):
            db.get_bills_with_parcels_filtered(page=1, page_size=25, **kwargs)
        return client

    def test_added_at_sort_is_forwarded_to_the_view(self) -> None:
        client = self._run(sort="added_at", order="desc")
        self.assertEqual("map_markers", client.table_name)
        args, kwargs = client.log["order"][0]
        self.assertEqual("added_at", args[0])
        self.assertTrue(kwargs["desc"])

    def test_ascending_order_is_respected(self) -> None:
        client = self._run(sort="added_at", order="asc")
        _, kwargs = client.log["order"][0]
        self.assertFalse(kwargs["desc"])

    def test_bills_sort_keys_are_translated_to_view_columns(self) -> None:
        # The view renames location_of_property -> location; callers still use
        # the bills name, so ordering by it must not 400.
        client = self._run(sort="location_of_property", order="asc")
        args, _ = client.log["order"][0]
        self.assertEqual("location", args[0])


if __name__ == "__main__":
    unittest.main()

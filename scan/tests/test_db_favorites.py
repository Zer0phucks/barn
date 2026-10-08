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
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def delete(self):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return type("R", (), {"data": self._data})()


class _FakeClient:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def table(self, name):
        return _FakeQuery(self._data)


class _BulkDeleteQuery:
    def __init__(self) -> None:
        self.filters: list[tuple] = []

    def delete(self):
        return self

    def eq(self, *args):
        self.filters.append(("eq", args))
        return self

    def in_(self, *args):
        self.filters.append(("in", args))
        return self

    def execute(self):
        return type("R", (), {"data": [{"apn": "001"}]})()


class FavoritesTests(unittest.TestCase):
    def test_add_favorites_retries_with_fresh_list_id(self) -> None:
        with patch("db.get_favorites_list_id", side_effect=[2, 5]) as resolve, patch(
            "db.add_properties_to_list", side_effect=[RuntimeError("stale list"), 1]
        ) as add:
            result = db._add_to_favorites(["001"])

        self.assertEqual(1, result)
        self.assertEqual(2, resolve.call_count)
        self.assertEqual(2, add.call_count)
        self.assertEqual(5, add.call_args.args[0])

    def test_bulk_remove_favorites_filters_list_and_chunks(self) -> None:
        query = _BulkDeleteQuery()

        class _Client:
            def table(self, name):
                self.table_name = name
                return query

        client = _Client()
        with patch("db.get_favorites_list_id", return_value=2), patch(
            "db.get_client", return_value=client
        ):
            removed = db.bulk_remove_favorites(["001", " ", "002", None])

        self.assertEqual("list_properties", client.table_name)
        self.assertIn(("eq", ("list_id", 2)), query.filters)
        self.assertIn(("in", ("apn", ["001", "002"])), query.filters)
        self.assertEqual(1, removed)

    def test_bulk_remove_favorites_without_list_returns_zero(self) -> None:
        with patch("db.get_favorites_list_id", return_value=None), patch(
            "db.bulk_remove_properties_from_list",
            side_effect=AssertionError("must not delete without a list"),
        ):
            self.assertEqual(0, db.bulk_remove_favorites(["001"]))

    def test_delete_list_clears_favorites_cache(self) -> None:
        db._favorites_list_id = 2
        try:
            with patch("db.get_client", return_value=_FakeClient([{"id": 2}])):
                deleted = db.delete_list(2)
            self.assertTrue(deleted)
            self.assertIsNone(db._favorites_list_id)
        finally:
            db._favorites_list_id = None


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from webgui import db_impl


class _FakeQuery:
    def __init__(self, table_name: str, tables: dict[str, list[dict]]) -> None:
        self.table_name = table_name
        self.tables = tables
        self.eq_filters: dict[str, object] = {}
        self.in_filters: dict[str, list[object]] = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self.eq_filters[field] = value
        return self

    def in_(self, field: str, values):
        self.in_filters[field] = list(values)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.table_name == "list_properties":
            list_id = self.eq_filters.get("list_id")
            data = [row for row in self.tables["list_properties"] if row["list_id"] == list_id]
            data.sort(key=lambda row: row["sort_order"])
            return SimpleNamespace(data=data)

        if self.table_name == "bills":
            apns = set(self.in_filters.get("apn", []))
            data = [row for row in self.tables["bills"] if row["apn"] in apns]
            return SimpleNamespace(data=data)

        if self.table_name == "parcels":
            apns = self.in_filters.get("apn")
            if apns is None:
                raise AssertionError("expected parcels lookup to use a bulk apn query")
            data = [row for row in self.tables["parcels"] if row["apn"] in set(apns)]
            return SimpleNamespace(data=data)

        raise AssertionError(f"unexpected table lookup: {self.table_name}")


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self.tables = tables

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(table_name, self.tables)


class GetListPropertiesTests(unittest.TestCase):
    def test_bulk_loads_parcels_for_all_list_properties(self) -> None:
        fake_client = _FakeClient(
            {
                "list_properties": [
                    {"list_id": 7, "apn": "002-002", "sort_order": 2},
                    {"list_id": 7, "apn": "001-001", "sort_order": 1},
                ],
                "bills": [
                    {
                        "apn": "001-001",
                        "location_of_property": "123 Test St",
                        "city": "OAKLAND",
                        "has_vpt": 1,
                        "condition_score": 6.0,
                    },
                    {
                        "apn": "002-002",
                        "location_of_property": "456 Test Ave",
                        "city": "ALAMEDA",
                        "has_vpt": 0,
                        "condition_score": 3.0,
                    },
                ],
                "parcels": [
                    {"apn": "001-001", "row_json": {"x": 1, "y": 1}},
                    {"apn": "002-002", "row_json": {"x": 2, "y": 2}},
                ],
            }
        )

        with patch.object(db_impl, "get_client", return_value=fake_client):
            properties = db_impl.get_list_properties(7)

        self.assertEqual(["001-001", "002-002"], [row["apn"] for row in properties])
        self.assertEqual({"x": 1, "y": 1}, properties[0]["row_json"])
        self.assertEqual({"x": 2, "y": 2}, properties[1]["row_json"])


if __name__ == "__main__":
    unittest.main()

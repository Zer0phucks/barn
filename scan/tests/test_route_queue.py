from __future__ import annotations

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import db


class _FakeQuery:
    def __init__(self, table_name: str, tables: dict[str, list[dict]], operations: list[tuple]) -> None:
        self.table_name = table_name
        self.tables = tables
        self.operations = operations
        self.eq_filters: dict[str, object] = {}
        self.in_filters: dict[str, list[object]] = {}
        self.order_field: str | None = None
        self.order_desc = False
        self.limit_count: int | None = None
        self.insert_payload = None
        self.upsert_payload = None
        self.update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self.eq_filters[field] = value
        return self

    def in_(self, field: str, values):
        self.in_filters[field] = list(values)
        return self

    def order(self, field: str, desc: bool = False, **_kwargs):
        self.order_field = field
        self.order_desc = desc
        return self

    def limit(self, count: int):
        self.limit_count = count
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.upsert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def delete(self):
        self.operations.append(("delete", self.table_name, dict(self.eq_filters)))
        return self

    def execute(self):
        if self.upsert_payload is not None:
            payloads = self.upsert_payload if isinstance(self.upsert_payload, list) else [self.upsert_payload]
            for payload in payloads:
                rows = self.tables.setdefault(self.table_name, [])
                existing = next(
                    (
                        row
                        for row in rows
                        if row.get("list_id") == payload.get("list_id") and row.get("apn") == payload.get("apn")
                    ),
                    None,
                )
                if existing:
                    existing.update(payload)
                else:
                    rows.append(dict(payload))
                self.operations.append(("upsert", self.table_name, dict(payload)))
            return SimpleNamespace(data=payloads)

        if self.update_payload is not None:
            updated = []
            for row in self.tables.get(self.table_name, []):
                if self._matches(row):
                    row.update(self.update_payload)
                    updated.append(dict(row))
                    self.operations.append(("update", self.table_name, dict(self.eq_filters), dict(self.update_payload)))
            return SimpleNamespace(data=updated)

        rows = [dict(row) for row in self.tables.get(self.table_name, []) if self._matches(row)]
        if self.order_field:
            rows.sort(key=lambda row: row.get(self.order_field) if row.get(self.order_field) is not None else -1, reverse=self.order_desc)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return SimpleNamespace(data=rows, count=len(rows))

    def _matches(self, row: dict) -> bool:
        for field, value in self.eq_filters.items():
            if row.get(field) != value:
                return False
        for field, values in self.in_filters.items():
            if row.get(field) not in set(values):
                return False
        return True


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self.tables = tables
        self.operations: list[tuple] = []

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(table_name, self.tables, self.operations)


class RouteQueueTests(unittest.TestCase):
    def test_reorder_list_properties_rewrites_sort_order_to_requested_apn_order(self) -> None:
        fake_client = _FakeClient(
            {
                "list_properties": [
                    {"list_id": 7, "apn": "001", "sort_order": 0},
                    {"list_id": 7, "apn": "002", "sort_order": 1},
                    {"list_id": 7, "apn": "003", "sort_order": 2},
                ]
            }
        )

        with patch.object(db, "get_client", return_value=fake_client):
            reordered = db.reorder_list_properties(7, ["003", "001", "002"])

        self.assertEqual(3, reordered)
        rows = sorted(fake_client.tables["list_properties"], key=lambda row: row["sort_order"])
        self.assertEqual(["003", "001", "002"], [row["apn"] for row in rows])

    def test_add_properties_to_list_appends_after_existing_max_sort_order(self) -> None:
        fake_client = _FakeClient(
            {
                "list_properties": [
                    {"list_id": 7, "apn": "001", "sort_order": 4},
                    {"list_id": 7, "apn": "002", "sort_order": 5},
                ]
            }
        )

        with patch.object(db, "get_client", return_value=fake_client):
            added = db.add_properties_to_list(7, ["002", "003", "004"])

        self.assertEqual(2, added)
        rows = sorted(fake_client.tables["list_properties"], key=lambda row: row["sort_order"])
        self.assertEqual(
            [("001", 4), ("002", 5), ("003", 6), ("004", 7)],
            [(row["apn"], row["sort_order"]) for row in rows],
        )

    def test_get_list_route_preview_returns_ordered_mappable_stops(self) -> None:
        fake_client = _FakeClient(
            {
                "list_properties": [
                    {"list_id": 7, "apn": "002", "sort_order": 1},
                    {"list_id": 7, "apn": "001", "sort_order": 0},
                ],
                "bills": [
                    {
                        "apn": "001",
                        "location_of_property": "101 First St",
                        "city": "OAKLAND",
                        "has_vpt": 1,
                        "condition_score": 4.5,
                        "streetview_image_path": "streetview/1.jpg",
                        "power_status": "off",
                    },
                    {
                        "apn": "002",
                        "location_of_property": "202 Second St",
                        "city": "OAKLAND",
                        "has_vpt": 0,
                        "condition_score": 6.0,
                        "streetview_image_path": "streetview/2.jpg",
                        "power_status": "on",
                    },
                ],
                "parcels": [
                    {"apn": "001", "row_json": {"CENTROID_X": "-13603237.85", "CENTROID_Y": "4547675.35"}},
                    {"apn": "002", "row_json": {"CENTROID_X": "-13603200.00", "CENTROID_Y": "4547600.00"}},
                ],
            }
        )

        with patch.object(db, "get_client", return_value=fake_client):
            preview = db.get_list_route_preview(7)

        self.assertEqual(2, preview["total"])
        self.assertEqual(["001", "002"], [stop["apn"] for stop in preview["stops"]])
        self.assertEqual([0, 1], [stop["queue_position"] for stop in preview["stops"]])
        self.assertTrue(all(isinstance(stop["lat"], float) for stop in preview["stops"]))
        self.assertTrue(all(isinstance(stop["lng"], float) for stop in preview["stops"]))


if __name__ == "__main__":
    unittest.main()

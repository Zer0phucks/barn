from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import db


class _FakeRpcResponse:
    data = [{"rows": [], "total": 0}]


class _FakeRpcCall:
    def execute(self):
        return _FakeRpcResponse()


class _FakeClient:
    def __init__(self) -> None:
        self.payload = None

    def rpc(self, name, payload):
        self.payload = {"name": name, "payload": payload}
        return _FakeRpcCall()


class AddedAtSortTests(unittest.TestCase):
    def test_added_at_is_allowed_and_forwarded_to_rpc(self) -> None:
        fake_client = _FakeClient()

        with patch("db.get_client", return_value=fake_client), patch(
            "db._enrich_rows_with_contact_fields", side_effect=lambda rows: rows
        ):
            db.get_bills_with_parcels_filtered(sort="added_at", order="desc", page=1, page_size=25)

        self.assertEqual("get_bills_filtered", fake_client.payload["name"])
        self.assertEqual("added_at", fake_client.payload["payload"]["p_sort"])
        self.assertEqual("desc", fake_client.payload["payload"]["p_order"])

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import db


def _load_webgui_db_impl() -> ModuleType:
    module_name = "test_webgui_db_impl"
    module_path = SCAN_DIR / "webgui" / "db_impl.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeRpcResponse:
    data = []


class _FakeRpcCall:
    def execute(self):
        return _FakeRpcResponse()


class _FakeClient:
    def __init__(self) -> None:
        self.payload = None

    def rpc(self, name, payload):
        self.payload = {"name": name, "payload": payload}
        return _FakeRpcCall()


class RootDbRpcPayloadTests(unittest.TestCase):
    def test_get_bills_for_map_does_not_send_removed_owner_name_arg(self) -> None:
        fake_client = _FakeClient()

        with patch("db.get_client", return_value=fake_client), patch(
            "db._enrich_rows_with_contact_fields", side_effect=lambda rows: rows
        ):
            db.get_bills_for_map(q="oakland", city_filter="oakland", vpt_filter="1")

        self.assertEqual("get_bills_for_map", fake_client.payload["name"])
        self.assertNotIn("p_owner_name", fake_client.payload["payload"])

    def test_get_bills_filtered_sends_owner_name_arg_to_disambiguate_overloads(self) -> None:
        fake_client = _FakeClient()

        with patch("db.get_client", return_value=fake_client), patch(
            "db._parse_get_bills_filtered_response", return_value=([], 0)
        ), patch("db._enrich_rows_with_contact_fields", side_effect=lambda rows: rows):
            db.get_bills_with_parcels_filtered(q="oakland", city_filter="oakland")

        self.assertEqual("get_bills_filtered", fake_client.payload["name"])
        self.assertEqual("", fake_client.payload["payload"]["p_owner_name"])


class WebGuiDbImplRpcPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_db_impl = _load_webgui_db_impl()

    def test_get_bills_for_map_does_not_send_removed_owner_name_arg(self) -> None:
        fake_client = _FakeClient()

        with patch.object(self.webgui_db_impl, "get_client", return_value=fake_client), patch.object(
            self.webgui_db_impl, "_enrich_rows_with_contact_fields", side_effect=lambda rows: rows
        ):
            self.webgui_db_impl.get_bills_for_map(q="oakland", city_filter="oakland", vpt_filter="1")

        self.assertEqual("get_bills_for_map", fake_client.payload["name"])
        self.assertNotIn("p_owner_name", fake_client.payload["payload"])

    def test_get_bills_filtered_sends_owner_name_arg_to_disambiguate_overloads(self) -> None:
        fake_client = _FakeClient()

        with patch.object(self.webgui_db_impl, "get_client", return_value=fake_client), patch.object(
            self.webgui_db_impl, "_parse_get_bills_filtered_response", return_value=([], 0)
        ):
            self.webgui_db_impl.get_bills_with_parcels_filtered(q="oakland", city_filter="oakland")

        self.assertEqual("get_bills_filtered", fake_client.payload["name"])
        self.assertEqual("", fake_client.payload["payload"]["p_owner_name"])

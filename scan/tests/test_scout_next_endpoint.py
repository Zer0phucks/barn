from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))


def _load_webgui_app() -> ModuleType:
    module_name = "test_webgui_app"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rpc_returning(rows):
    """Stub db.get_client() so .rpc(name, params).execute().data == rows.

    Also records the call so tests can assert on the parameters actually sent
    to the scout_next() RPC.
    """
    execute = MagicMock()
    execute.execute.return_value = MagicMock(data=rows)
    client = MagicMock()
    client.rpc.return_value = execute
    return client


class ScoutNextEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_returns_nearest_property_from_rpc(self) -> None:
        row = {
            "apn": "001-001",
            "address": "123 Test St",
            "city": "OAKLAND",
            "has_vpt": 1,
            "condition_score": 5.0,
            "streetview_image_path": None,
            "latitude": 37.8,
            "longitude": -122.2,
            "distance_km": 1.23456,
            "remaining": 0,
        }
        client = _rpc_returning([row])

        with self.webgui_app.app.test_request_context("/api/scout/next?lat=37.8&lng=-122.2"):
            with patch.object(self.webgui_app.db, "get_client", return_value=client):
                response = self.webgui_app.api_scout_next.__wrapped__()

        payload = response.get_json()
        self.assertEqual("001-001", payload["property"]["apn"])
        self.assertEqual("123 Test St", payload["property"]["address"])
        self.assertTrue(payload["property"]["has_vpt"])
        self.assertEqual(1.23, payload["property"]["distance_km"])
        self.assertEqual(0, payload["remaining"])
        self.assertEqual("scout_next", client.rpc.call_args[0][0])

    def test_passes_filters_through_to_rpc(self) -> None:
        client = _rpc_returning([])

        query = (
            "/api/scout/next?lat=37.8&lng=-122.2&city=OAKLAND&q=main"
            "&vpt=1&list_id=7&condition_min=2&condition_max=8"
        )
        with self.webgui_app.app.test_request_context(query):
            with patch.object(self.webgui_app.db, "get_client", return_value=client):
                response = self.webgui_app.api_scout_next.__wrapped__()

        params = client.rpc.call_args[0][1]
        self.assertEqual(37.8, params["p_lat"])
        self.assertEqual("OAKLAND", params["p_city"])
        self.assertEqual("main", params["p_q"])
        self.assertTrue(params["p_vpt_only"])
        self.assertEqual(7, params["p_list_id"])
        self.assertEqual(2.0, params["p_condition_min"])
        self.assertEqual(8.0, params["p_condition_max"])
        # Empty result is a valid answer, not an error.
        self.assertIsNone(response.get_json()["property"])

    def test_blank_and_malformed_filters_become_null(self) -> None:
        client = _rpc_returning([])

        with self.webgui_app.app.test_request_context(
            "/api/scout/next?lat=37.8&lng=-122.2&city=&list_id=abc&condition_min="
        ):
            with patch.object(self.webgui_app.db, "get_client", return_value=client):
                self.webgui_app.api_scout_next.__wrapped__()

        params = client.rpc.call_args[0][1]
        # SQL uses `p_x is null` to mean "no filter", so blanks must not arrive
        # as empty strings or the query silently matches nothing.
        self.assertIsNone(params["p_city"])
        self.assertIsNone(params["p_list_id"])
        self.assertIsNone(params["p_condition_min"])

    def test_missing_location_is_rejected(self) -> None:
        for query in ("/api/scout/next", "/api/scout/next?lat=0&lng=0", "/api/scout/next?lat=x&lng=y"):
            with self.subTest(query=query):
                with self.webgui_app.app.test_request_context(query):
                    response, status = self.webgui_app.api_scout_next.__wrapped__()
                self.assertEqual(400, status)
                self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()

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


def _load_webgui_app() -> ModuleType:
    module_name = "test_webgui_app"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScoutNextEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_returns_property_when_filtered_property_list_has_match(self) -> None:
        row = {
            "apn": "001-001",
            "location_of_property": "123 Test St",
            "city": "OAKLAND",
            "has_vpt": 1,
            "condition_score": 5.0,
            "streetview_image_path": None,
            "row_json": {"x": 1, "y": 1},
        }

        with self.webgui_app.app.test_request_context("/api/scout/next?lat=37.8&lng=-122.2"):
            with patch.object(self.webgui_app, "ensure_scout_tables"), patch.object(
                self.webgui_app.db, "get_scout_results", return_value=[]
            ), patch.object(
                self.webgui_app.db, "get_bills_for_map", return_value=[]
            ), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=([row], 1),
                create=True,
            ), patch.object(
                self.webgui_app, "web_mercator_to_latlng", return_value=(37.8, -122.2)
            ):
                response = self.webgui_app.api_scout_next.__wrapped__()

        payload = response.get_json()

        self.assertEqual("001-001", payload["property"]["apn"])
        self.assertEqual(0, payload["remaining"])


if __name__ == "__main__":
    unittest.main()

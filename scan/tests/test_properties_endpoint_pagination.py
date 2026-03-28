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
    module_name = "test_webgui_app_properties_pagination"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PropertiesEndpointPaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_properties_endpoint_fetches_full_filtered_set_before_paginating(self) -> None:
        full_rows = [
            {
                "apn": f"{index:03d}",
                "location_of_property": f"{index} Test St",
                "city": "OAKLAND",
                "has_vpt": 0,
                "condition_score": None,
                "streetview_image_path": None,
                "row_json": {"x": index + 1, "y": index + 1},
            }
            for index in range(450)
        ]

        def fake_get_bills_with_parcels_filtered(**kwargs):
            if kwargs.get("page_size") == 0:
                return full_rows, len(full_rows)
            return full_rows[:200], len(full_rows)

        with self.webgui_app.app.test_request_context("/api/properties?page=3&per_page=200"):
            with patch.object(self.webgui_app, "ensure_scout_tables"), patch.object(
                self.webgui_app.db, "get_scout_results", return_value=[]
            ), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                side_effect=fake_get_bills_with_parcels_filtered,
                create=True,
            ), patch.object(
                self.webgui_app, "web_mercator_to_latlng", side_effect=lambda x, y: (y, x)
            ):
                response = self.webgui_app.api_properties_list.__wrapped__()

        payload = response.get_json()

        self.assertEqual(450, payload["total"])
        self.assertEqual(3, payload["total_pages"])
        self.assertEqual(50, len(payload["properties"]))
        self.assertEqual("400", payload["properties"][0]["apn"])


if __name__ == "__main__":
    unittest.main()

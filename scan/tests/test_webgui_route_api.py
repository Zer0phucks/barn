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
    module_name = "test_webgui_app_route_api"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RouteApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_reorder_route_api_cleans_apns_and_delegates_to_db(self) -> None:
        with self.webgui_app.app.test_request_context(
            "/api/lists/7/reorder",
            method="POST",
            json={"apns": [" 003 ", "", "001", None, "002"]},
        ):
            with patch.object(self.webgui_app, "ensure_lists_tables"), patch.object(
                self.webgui_app.db, "get_list", return_value={"id": 7, "name": "Route"}
            ), patch.object(
                self.webgui_app.db, "reorder_list_properties", return_value=3
            ) as reorder:
                response = self.webgui_app.api_lists_reorder.__wrapped__(7)

        self.assertEqual({"success": True, "count": 3}, response.get_json())
        reorder.assert_called_once_with(7, ["003", "001", "002"])

    def test_route_preview_api_returns_db_preview_payload(self) -> None:
        preview = {
            "total": 2,
            "stops": [
                {"apn": "001", "queue_position": 0, "lat": 37.8, "lng": -122.2},
                {"apn": "002", "queue_position": 1, "lat": 37.9, "lng": -122.3},
            ],
        }
        with self.webgui_app.app.test_request_context("/api/lists/7/route-preview"):
            with patch.object(self.webgui_app, "ensure_lists_tables"), patch.object(
                self.webgui_app.db, "get_list", return_value={"id": 7, "name": "Route"}
            ), patch.object(
                self.webgui_app.db, "get_list_route_preview", return_value=preview
            ):
                response = self.webgui_app.api_lists_route_preview.__wrapped__(7)

        self.assertEqual(preview, response.get_json())

    def test_search_list_id_scopes_results_to_selected_route(self) -> None:
        rows = [
            self._search_row("001", "1 Test St"),
            self._search_row("002", "2 Test St"),
            self._search_row("003", "3 Test St"),
        ]
        rendered: dict = {}

        def fake_render_template(template_name: str, **context):
            rendered["template_name"] = template_name
            rendered.update(context)
            return "rendered"

        with self.webgui_app.app.test_request_context("/search?list_id=7"):
            with patch.object(self.webgui_app.db, "get_list", return_value={"id": 7, "name": "Route"}), patch.object(
                self.webgui_app.db,
                "get_list_properties",
                return_value=[{"apn": "003"}, {"apn": "001"}],
            ), patch.object(
                self.webgui_app.db, "get_favorites_apns", return_value=[]
            ), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=(rows, len(rows)),
            ), patch.object(
                self.webgui_app.db, "get_distinct_zips", return_value=[]
            ), patch.object(
                self.webgui_app.db, "get_lists", return_value=[{"id": 7, "name": "Route"}]
            ), patch.object(
                self.webgui_app, "render_template", side_effect=fake_render_template
            ):
                response = self.webgui_app.search_page.__wrapped__()

        self.assertEqual("rendered", response)
        self.assertEqual(["001", "003"], [row["apn"] for row in rendered["rows"]])
        self.assertEqual(2, rendered["total"])

    def test_gallery_list_id_scopes_results_to_selected_route(self) -> None:
        rows = [
            self._gallery_row("001", "1 Test St"),
            self._gallery_row("002", "2 Test St"),
            self._gallery_row("003", "3 Test St"),
        ]
        rendered: dict = {}

        def fake_render_template(template_name: str, **context):
            rendered["template_name"] = template_name
            rendered.update(context)
            return "rendered"

        with self.webgui_app.app.test_request_context("/gallery?list_id=7"):
            with patch.object(self.webgui_app.db, "get_list", return_value={"id": 7, "name": "Route"}), patch.object(
                self.webgui_app.db,
                "get_list_properties",
                return_value=[{"apn": "003"}, {"apn": "001"}],
            ), patch.object(
                self.webgui_app.db, "get_favorites_apns", return_value=[]
            ), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=(rows, len(rows)),
            ), patch.object(
                self.webgui_app.db, "get_distinct_zips", return_value=[]
            ), patch.object(
                self.webgui_app.db, "get_distinct_cities", return_value=[], create=True
            ), patch.object(
                self.webgui_app.db, "get_lists", return_value=[{"id": 7, "name": "Route"}]
            ), patch.object(
                self.webgui_app, "render_template", side_effect=fake_render_template
            ):
                response = self.webgui_app.gallery_page.__wrapped__()

        self.assertEqual("rendered", response)
        self.assertEqual(["001", "003"], [row["apn"] for row in rendered["rows"]])
        self.assertEqual(2, rendered["total"])

    @staticmethod
    def _search_row(apn: str, address: str) -> dict:
        return {
            "apn": apn,
            "added_at": None,
            "pdf_file": "",
            "bill_url": "",
            "parcel_number": "",
            "tracer_number": "",
            "location_of_property": address,
            "tax_year": "",
            "last_payment": "",
            "delinquent": 0,
            "power_status": "",
            "has_vpt": 0,
            "vpt_marker": "",
            "city": "OAKLAND",
            "condition_score": None,
            "condition_notes": "",
            "streetview_image_path": "",
            "property_search_url": "",
            "mailing_search_url": "",
            "situs_zip": "",
            "owner_name": "",
            "important_notes": "",
            "outreach_score": None,
            "outreach_stage": "",
            "row_json": {},
        }

    @classmethod
    def _gallery_row(cls, apn: str, address: str) -> dict:
        row = cls._search_row(apn, address)
        row.update(
            {
                "prop_last_sale_date": "",
                "deceased_count": None,
                "prop_occupancy_type": "",
            }
        )
        return row


if __name__ == "__main__":
    unittest.main()

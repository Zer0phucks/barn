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
    module_name = "test_webgui_app_gallery_city_filter"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GalleryCityFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_gallery_accepts_multiple_city_checkbox_values(self) -> None:
        rows = [
            {
                "apn": "001",
                "location_of_property": "1 Test St",
                "city": "OAKLAND",
                "situs_zip": "94601",
                "power_status": "",
                "has_vpt": 0,
                "delinquent": 0,
                "condition_score": None,
                "condition_notes": "",
                "row_json": {},
            },
            {
                "apn": "002",
                "location_of_property": "2 Test St",
                "city": "BERKELEY",
                "situs_zip": "94702",
                "power_status": "",
                "has_vpt": 0,
                "delinquent": 0,
                "condition_score": None,
                "condition_notes": "",
                "row_json": {},
            },
            {
                "apn": "003",
                "location_of_property": "3 Test St",
                "city": "ALAMEDA",
                "situs_zip": "94501",
                "power_status": "",
                "has_vpt": 0,
                "delinquent": 0,
                "condition_score": None,
                "condition_notes": "",
                "row_json": {},
            },
        ]
        rendered: dict = {}

        def fake_render_template(template_name: str, **context):
            rendered["template_name"] = template_name
            rendered.update(context)
            return "rendered"

        with self.webgui_app.app.test_request_context("/gallery?city=Oakland&city=Berkeley"):
            with patch.object(self.webgui_app.db, "get_favorites_apns", return_value=[]), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=(rows, len(rows)),
            ) as get_filtered, patch.object(
                self.webgui_app.db, "get_distinct_zips", return_value=["94501", "94601", "94702"]
            ), patch.object(
                self.webgui_app.db, "get_distinct_cities", return_value=["ALAMEDA", "BERKELEY", "OAKLAND"], create=True
            ), patch.object(
                self.webgui_app, "render_template", side_effect=fake_render_template
            ):
                response = self.webgui_app.gallery_page.__wrapped__()

        self.assertEqual("rendered", response)
        self.assertEqual("gallery.html", rendered["template_name"])
        self.assertEqual("OAKLAND,BERKELEY", rendered["city_filter"])
        self.assertEqual(["ALAMEDA", "BERKELEY", "OAKLAND"], rendered["available_cities"])
        self.assertEqual(["001", "002"], [row["apn"] for row in rendered["rows"]])
        self.assertEqual(2, rendered["total"])
        get_filtered.assert_called_once()
        self.assertEqual("", get_filtered.call_args.kwargs["city_filter"])

    def test_gallery_filters_by_county_before_pagination(self) -> None:
        rows = [
            {
                "apn": "001",
                "location_of_property": "1 Test St",
                "city": "OAKLAND",
                "situs_zip": "94601",
                "power_status": "",
                "has_vpt": 0,
                "delinquent": 0,
                "condition_score": None,
                "condition_notes": "",
                "row_json": {},
            },
            {
                "apn": "002",
                "location_of_property": "2 Test St",
                "city": "SAN RAFAEL",
                "situs_zip": "94901",
                "power_status": "",
                "has_vpt": 0,
                "delinquent": 0,
                "condition_score": None,
                "condition_notes": "",
                "row_json": {},
            },
        ]
        rendered: dict = {}

        def fake_render_template(template_name: str, **context):
            rendered["template_name"] = template_name
            rendered.update(context)
            return "rendered"

        with self.webgui_app.app.test_request_context("/gallery?county=Marin"):
            with patch.object(self.webgui_app.db, "get_favorites_apns", return_value=[]), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=(rows, len(rows)),
            ) as get_filtered, patch.object(
                self.webgui_app.db, "get_distinct_zips", return_value=["94601", "94901"]
            ), patch.object(
                self.webgui_app.db, "get_distinct_cities", return_value=["OAKLAND", "SAN RAFAEL"], create=True
            ), patch.object(
                self.webgui_app, "render_template", side_effect=fake_render_template
            ):
                response = self.webgui_app.gallery_page.__wrapped__()

        self.assertEqual("rendered", response)
        self.assertEqual("MARIN", rendered["county_filter"])
        self.assertEqual(["002"], [row["apn"] for row in rendered["rows"]])
        self.assertEqual(1, rendered["total"])
        get_filtered.assert_called_once()
        self.assertEqual(0, get_filtered.call_args.kwargs["page_size"])

    def test_search_filters_by_county_before_pagination(self) -> None:
        rows = [
            self._search_row("001", "OAKLAND"),
            self._search_row("002", "WALNUT CREEK"),
        ]
        rendered: dict = {}

        def fake_render_template(template_name: str, **context):
            rendered["template_name"] = template_name
            rendered.update(context)
            return "rendered"

        with self.webgui_app.app.test_request_context("/search?county=Contra+Costa"):
            with patch.object(self.webgui_app.db, "get_favorites_apns", return_value=[]), patch.object(
                self.webgui_app.db,
                "get_bills_with_parcels_filtered",
                return_value=(rows, len(rows)),
            ) as get_filtered, patch.object(
                self.webgui_app.db, "get_distinct_zips", return_value=["94601", "94595"]
            ), patch.object(
                self.webgui_app, "render_template", side_effect=fake_render_template
            ):
                response = self.webgui_app.search_page.__wrapped__()

        self.assertEqual("rendered", response)
        self.assertEqual("CONTRA COSTA", rendered["county_filter"])
        self.assertEqual(["002"], [row["apn"] for row in rendered["rows"]])
        self.assertEqual(1, rendered["total"])
        get_filtered.assert_called_once()
        self.assertEqual(0, get_filtered.call_args.kwargs["page_size"])

    @staticmethod
    def _search_row(apn: str, city: str) -> dict:
        return {
            "apn": apn,
            "added_at": None,
            "pdf_file": "",
            "bill_url": "",
            "parcel_number": "",
            "tracer_number": "",
            "location_of_property": f"{apn} Test St",
            "tax_year": "",
            "last_payment": "",
            "delinquent": 0,
            "power_status": "",
            "has_vpt": 0,
            "vpt_marker": "",
            "city": city,
            "condition_score": None,
            "condition_notes": "",
            "streetview_image_path": "",
            "property_search_url": "",
            "mailing_search_url": "",
            "research_status": "",
            "situs_zip": "",
            "owner_name": "",
            "important_notes": "",
            "row_json": {},
        }


if __name__ == "__main__":
    unittest.main()

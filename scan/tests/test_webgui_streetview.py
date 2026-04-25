from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))


def _load_webgui_app() -> ModuleType:
    module_name = "test_webgui_app_streetview"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StreetViewEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()

    def test_missing_local_image_fetches_google_streetview_by_address(self) -> None:
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "image/jpeg"}
        fake_response.content = b"\xff\xd8streetview-image\xff\xd9"

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.webgui_app.app.test_request_context("/api/streetview/123-456-7"):
                with patch.object(self.webgui_app, "STREETVIEW_DIR", Path(tmpdir)), patch.object(
                    self.webgui_app.db,
                    "get_bill_with_parcel",
                    return_value={
                        "apn": "123-456-7",
                        "location_of_property": "123 Main St",
                        "city": "Oakland",
                        "row_json": {},
                    },
                ), patch.dict(self.webgui_app.os.environ, {"MAPS_API_KEY": "test-maps-key"}), patch(
                    "requests.get", return_value=fake_response
                ) as get:
                    response = self.webgui_app.app.make_response(
                        self.webgui_app.api_streetview_image.__wrapped__("123-456-7")
                    )

        self.assertEqual(200, response.status_code)
        self.assertEqual("image/jpeg", response.mimetype)
        self.assertEqual(b"\xff\xd8streetview-image\xff\xd9", response.get_data())
        args, kwargs = get.call_args
        self.assertEqual("https://maps.googleapis.com/maps/api/streetview", args[0])
        self.assertEqual("123 Main St, Oakland, CA", kwargs["params"]["location"])
        self.assertEqual("test-maps-key", kwargs["params"]["key"])
        self.assertEqual("true", kwargs["params"]["return_error_code"])

    def test_missing_local_image_redirects_to_signed_storage_image(self) -> None:
        fake_bucket = Mock()
        fake_bucket.exists.return_value = True
        fake_bucket.create_signed_url.return_value = {
            "signedURL": "https://storage.example/streetview/123-456-7.jpg?token=abc"
        }
        fake_storage = Mock()
        fake_storage.from_.return_value = fake_bucket
        fake_client = Mock()
        fake_client.storage = fake_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.webgui_app.app.test_request_context("/api/streetview/123-456-7"):
                with patch.object(self.webgui_app, "STREETVIEW_DIR", Path(tmpdir)), patch.object(
                    self.webgui_app.db, "get_client", return_value=fake_client
                ), patch.object(
                    self.webgui_app.db, "get_bill_with_parcel", return_value=None
                ), patch.dict(self.webgui_app.os.environ, {"STREETVIEW_STORAGE_BUCKET": "streetview-images"}):
                    response = self.webgui_app.app.make_response(
                        self.webgui_app.api_streetview_image.__wrapped__("123-456-7")
                    )

        self.assertEqual(302, response.status_code)
        self.assertEqual("https://storage.example/streetview/123-456-7.jpg?token=abc", response.headers["Location"])
        fake_storage.from_.assert_called_once_with("streetview-images")
        fake_bucket.exists.assert_called_once_with("123-456-7.jpg")
        fake_bucket.create_signed_url.assert_called_once_with("123-456-7.jpg", 86400)


if __name__ == "__main__":
    unittest.main()

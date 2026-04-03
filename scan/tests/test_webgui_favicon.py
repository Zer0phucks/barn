from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))


def _load_webgui_app() -> ModuleType:
    module_name = "test_webgui_app_favicon"
    module_path = SCAN_DIR / "webgui" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WebGuiFaviconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.webgui_app = _load_webgui_app()
        cls.client = cls.webgui_app.app.test_client()

    def test_favicon_request_does_not_404(self) -> None:
        response = self.client.get("/favicon.ico")

        self.assertEqual(204, response.status_code)


if __name__ == "__main__":
    unittest.main()

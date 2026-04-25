"""Vercel/Flask entrypoint. Ensures project root is on path and our db module loads before webgui."""
import sys
from pathlib import Path

def _bootstrap():
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _db_py = ROOT / "db.py"
    if _db_py.exists():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("db", _db_py)
        _db = importlib.util.module_from_spec(_spec)
        sys.modules["db"] = _db
        _spec.loader.exec_module(_db)
    from webgui.app import app as _app
    return _app

app = _bootstrap()

"""Vercel/Flask entrypoint. Ensures project root is on path and our db module loads before webgui."""
import os
import sys
import traceback
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

try:
    app = _bootstrap()
except Exception as e:
    from flask import Flask, jsonify
    _err_app = Flask(__name__)
    _msg = str(e)
    _tb = traceback.format_exc()
    @_err_app.route("/")
    @_err_app.route("/<path:path>")
    def _err(path=None):
        body = {"error": _msg}
        if os.environ.get("VERCEL_ENV") != "production":
            body["traceback"] = _tb
        return jsonify(body), 500
    app = _err_app

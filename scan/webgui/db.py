"""
Database layer for BARN-scan (Supabase). Copy of root db.py for Vercel when root is webgui.
When parent/db.py exists, we load it; otherwise this file is the canonical db (same content as root).
"""
from pathlib import Path
import sys
import importlib.util

_here = Path(__file__).resolve().parent
_root = _here.parent
_root_db = _root / "db.py"

if _root_db.exists():
    _spec = importlib.util.spec_from_file_location("db", _root_db)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["db"] = _mod
    _spec.loader.exec_module(_mod)
    for _k, _v in vars(_mod).items():
        if not _k.startswith("_"):
            globals()[_k] = _v
else:
    # Vercel may use webgui as root: use in-webgui copy of db
    import webgui.db_impl as _impl
    for _k in dir(_impl):
        if not _k.startswith("_"):
            globals()[_k] = getattr(_impl, _k)

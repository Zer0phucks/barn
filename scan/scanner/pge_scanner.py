#!/usr/bin/env python3
"""
Scanner wrapper for pge_scanner.py

Allows imports via `scanner.pge_scanner` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pge_scanner as _impl  # type: ignore

get_pge_state = _impl.get_pge_state
start_pge_scan = _impl.start_pge_scan
stop_pge_scan = _impl.stop_pge_scan


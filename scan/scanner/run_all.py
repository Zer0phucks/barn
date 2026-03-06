#!/usr/bin/env python3
"""
Scanner wrapper for run_all.py

Allows imports via `scanner.run_all` while keeping the main script at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import run_all as _impl  # type: ignore

scan_state = _impl.scan_state
get_scan_state = _impl.get_scan_state
start_scan = _impl.start_scan
stop_scan = _impl.stop_scan
main = _impl.main


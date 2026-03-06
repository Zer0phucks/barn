#!/usr/bin/env python3
"""
Scanner wrapper for condition_scanner.py

Allows imports via `scanner.condition_scanner` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import condition_scanner as _impl  # type: ignore

GOOGLE_API_KEY = _impl.GOOGLE_API_KEY
condition_state = _impl.condition_state
ensure_condition_columns = _impl.ensure_condition_columns
get_condition_state = _impl.get_condition_state
start_condition_scan = _impl.start_condition_scan
get_condition_score = _impl.get_condition_score


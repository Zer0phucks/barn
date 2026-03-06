#!/usr/bin/env python3
"""
Scanner wrapper for contact_scanner.py

Allows imports via `scanner.contact_scanner` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import contact_scanner as _impl  # type: ignore

GOOGLE_API_KEY = _impl.GOOGLE_API_KEY
contact_state = _impl.contact_state
get_contact_state = _impl.get_contact_state
start_contact_scan = _impl.start_contact_scan

#!/usr/bin/env python3
"""
Scanner wrapper for gemini_research_scanner.py

Allows imports via `scanner.gemini_research_scanner` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gemini_research_scanner as _impl  # type: ignore

GOOGLE_API_KEY = _impl.GOOGLE_API_KEY
research_state = _impl.research_state
ensure_research_columns = _impl.ensure_research_columns
get_research_state = _impl.get_research_state
start_research = _impl.start_research
get_research_report = _impl.get_research_report


#!/usr/bin/env python3
"""
Scanner wrapper for outreach_scorer.py

Allows imports via `scanner.outreach_scorer` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import outreach_scorer as _impl  # type: ignore

scorer_state = _impl.scorer_state
get_scorer_state = _impl.get_scorer_state
start_scoring = _impl.start_scoring

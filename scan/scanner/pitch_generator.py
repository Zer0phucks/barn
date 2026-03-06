#!/usr/bin/env python3
"""
Scanner wrapper for pitch_generator.py

Allows imports via `scanner.pitch_generator` while delegating to the
main module at project root.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pitch_generator as _impl  # type: ignore

pitch_state = _impl.pitch_state
get_pitch_state = _impl.get_pitch_state
generate_pitch = _impl.generate_pitch
start_pitch_generation = _impl.start_pitch_generation
